
import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone

from config import (
    KEYWORDS,
    KEYWORDS_CARGO_FORTE,
    KEYWORDS_CARGO_AMBIGUO,
    QUALIFICADORES_DADOS,
    FERRAMENTAS_TITULO,
    QUALIFICADORES_CARGO,
    CIDADES,
    INTERVALO_MINUTOS,
    TERMOS_BUSCA,
    TERMOS_POR_CICLO,
)
from database.database import (
    BancoVazioSuspeito,
    definir_metadado,
    iniciar_db,
    ja_vista,
    obter_metadado,
    salvar_vaga,
)
from notifier.telegram import notificar_vaga, enviar_mensagem
from scrapers.catho import CathoScraper
from scrapers.geekhunter import GeekHunterScraper
from scrapers.gupy import GupyScraper
from scrapers.indeed import IndeedScraper
from scrapers.jobs99 import Jobs99Scraper
from scrapers.linkedin import LinkedInScraper
from scrapers.solides import SolidesScraper
from utils.filtro import filtrar_vagas
from logger import get_logger

logger = get_logger()

# Revelo não entrou: o portal de vagas exige login pra navegar, não dá pra
# fazer scraping público de forma confiável.
#
# Trampos SAIU depois de investigar por que rendia 0 notificação em 6 dias
# (~71 vagas brutas/ciclo com 99Jobs). Testei o parâmetro de busca (term=)
# direto na API do site com "analista de dados" e "business intelligence" —
# os dois devolveram a MESMA lista de vagas (Diretor de Arte, SDR,
# Atendimento Publicitário...), nenhuma de dados. A busca do site não
# filtra nada, é sempre o feed genérico recente; a categoria própria
# "Análise e Gestão de Dados" do site tem só 4 vagas no total, contra 226
# de "Emprego" geral (majoritariamente marketing/criação/comercial). O
# vazio vinha da FONTE (site não é de tecnologia/dados) — código do
# scraper continua em scrapers/trampos.py se algum dia mudar.
#
# 99Jobs FICOU: mesma investigação, resultado diferente. A busca por
# "analista de dados" no site retorna vaga de verdade relevante ("Analista
# de Dados Sênior" etc.) — só que presencial/híbrida em São Paulo, fora da
# lista CIDADES e sem sinal de remoto. O vazio aí vem do FILTRO de
# localização (a mesma limitação que afeta o sistema todo), não da fonte —
# remover jogaria fora uma fonte que funciona.
#
# Cadência por fonte: medido em jobradar.log + jobs.db (vagas notificadas /
# vagas brutas retornadas, somado por fonte). Gupy e LinkedIn confirmam o
# que foi medido à parte (Gupy ~2,6%); Catho, GeekHunter e 99Jobs ficam
# abaixo de 1%. Fontes de baixo rendimento continuam rodando (podem
# melhorar, e ainda cobrem cidade que outra fonte não cobre), só não em
# todo ciclo — acordo com FREQUENCIA_BAIXA abaixo.
FREQUENCIA_ALTA = "alta"
FREQUENCIA_BAIXA = "baixa"

_DEFINICAO_SCRAPERS = [
    (GupyScraper, FREQUENCIA_ALTA),       # ~2,6% de rendimento
    (LinkedInScraper, FREQUENCIA_ALTA),    # ~8,5% de rendimento — a melhor fonte de longe
    (SolidesScraper, FREQUENCIA_ALTA),     # ~1,1%
    (IndeedScraper, FREQUENCIA_ALTA),      # ~1,1%
    (CathoScraper, FREQUENCIA_BAIXA),      # <1%, e ainda tem timeout frequente em headless
    (GeekHunterScraper, FREQUENCIA_BAIXA), # <1%
    (Jobs99Scraper, FREQUENCIA_BAIXA),     # <1%, mas fonte confirmada funcionando
]


def _fontes_baixa_frequencia_ja_rodaram_hoje() -> bool:
    return obter_metadado("baixa_frequencia_ultimo_dia") == date.today().isoformat()


# Não é mais uma lista fixa construída uma vez: os scrapers recebem só o
# BLOCO de termos do ciclo atual (ver _proximo_bloco_termos), e a lista de
# QUAIS fontes entram também varia por ciclo (ver FREQUENCIA_BAIXA acima) —
# então precisam ser (re)criados a cada ciclo, não guardados numa constante
# de módulo.
def _construir_scrapers(termos_busca):
    rodar_baixa_frequencia = not _fontes_baixa_frequencia_ja_rodaram_hoje()

    scrapers = [
        classe(termos_busca=termos_busca)
        for classe, frequencia in _DEFINICAO_SCRAPERS
        if frequencia == FREQUENCIA_ALTA or rodar_baixa_frequencia
    ]

    if rodar_baixa_frequencia:
        # Marca ANTES de rodar (não depois): mesmo que uma fonte de baixa
        # frequência falhe nesse ciclo, ela "rodou" no sentido de já ter
        # sido tentada hoje — não deve ser tentada de novo no ciclo
        # seguinte só porque deu erro. Falha individual já é tratada e
        # logada normalmente em ciclo_de_busca(), como qualquer scraper.
        definir_metadado("baixa_frequencia_ultimo_dia", date.today().isoformat())

    return scrapers

# Medido: 378 sessões de navegador por ciclo rodando em sequência, ~61min —
# latência alta entre a vaga sair no site e a notificação chegar, porque uma
# fonte lenta segura todas as outras atrás dela na fila. Cada scraper já é
# auto-contido (cria e fecha seu(s) próprio(s) browser(s) Playwright dentro
# de buscar_vagas()), então dá pra rodar vários ao mesmo tempo em threads —
# é o padrão suportado pela sync API do Playwright entre threads, contanto
# que cada thread não compartilhe Browser/Page com outra (aqui nenhuma
# compartilha, cada scraper é isolado).
#
# Não uso as 8 fontes de uma vez: o runner do GitHub Actions tem CPU/RAM
# limitados, e 8 Chromium headless disputando os mesmos núcleos ao mesmo
# tempo não dá 8x de ganho — só mais contenção. 4 é um meio-termo: reduz a
# fila de 8 sequenciais pra só 2 "rodadas" de fato, sem lotar o runner.
# Escrita no banco e envio pro Telegram continuam só na thread principal
# (processadas conforme cada future termina, não dentro das threads) —
# então não tem escrita concorrente no SQLite nem race condition no dedup.
MAX_SCRAPERS_CONCORRENTES = 4


def _proximo_bloco_termos() -> list[str]:
    """Rodízio: cada ciclo pega um BLOCO fixo (TERMOS_POR_CICLO) de
    TERMOS_BUSCA, começando de onde o ciclo anterior parou, e avança —
    volta pro início quando chega no fim da lista. A posição fica salva no
    jobs.db (tabela metadados), então sobrevive entre execuções do GitHub
    Actions (cada run é uma máquina nova).

    Isso é o que desacopla custo por ciclo do tamanho de TERMOS_BUSCA: 42
    termos com bloco de 10 leva 5 ciclos pra cobrir tudo (~15h com o cron de
    3h); se a lista crescer pra 84, passa a levar 9 ciclos (~27h) — mais
    lento pra cobrir tudo, mas cada ciclo individual continua custando o
    mesmo. Sem isso, dobrar TERMOS_BUSCA dobrava o tempo de TODO ciclo.
    """
    total = len(TERMOS_BUSCA)
    if total == 0:
        return []

    tamanho_bloco = min(TERMOS_POR_CICLO, total)

    offset_salvo = obter_metadado("termos_offset")
    # % total protege contra a lista ter encolhido desde o último ciclo
    # (termo removido do config.py) — sem isso, um offset salvo maior que o
    # tamanho atual da lista quebraria o acesso por índice abaixo.
    offset = int(offset_salvo) % total if offset_salvo else 0

    bloco = [TERMOS_BUSCA[(offset + i) % total] for i in range(tamanho_bloco)]

    definir_metadado("termos_offset", str((offset + tamanho_bloco) % total))

    return bloco


def _enviar_heartbeat_diario(total_novas: int, scrapers_com_problema: list[str], total_fontes: int):
    """No máximo 1 mensagem por dia confirmando que o ciclo rodou.

    O alerta de saúde acima só dispara quando ≥50% das fontes falha — mas se
    o workflow parar de rodar por completo (cron desabilitado pelo GitHub
    Actions por inatividade do repositório, erro de config, etc.), não
    existe ALERTA NENHUM disso: silêncio no Telegram fica idêntico a "rodou
    e não achou vaga nova". O heartbeat fecha essa lacuna — se ele parar de
    chegar um dia, o problema é o workflow não estar rodando, não a busca
    não ter achado nada.

    A data do último envio fica salva no próprio jobs.db (tabela
    metadados), então sobrevive entre execuções do GitHub Actions (cada
    run é uma máquina nova) e não manda duplicado se o workflow rodar mais
    de uma vez no mesmo dia (cron normal ou workflow_dispatch manual).
    """
    hoje = date.today().isoformat()
    if obter_metadado("heartbeat_ultimo_dia") == hoje:
        return

    hora_brasilia = datetime.now(timezone.utc).strftime("%H:%M UTC")
    if scrapers_com_problema:
        status = f"{len(scrapers_com_problema)}/{total_fontes} fonte(s) com problema"
    else:
        status = "todas as fontes ok"

    enviar_mensagem(
        f"💓 <b>JobRadar ativo</b>\n\n"
        f"Confirmação diária: o ciclo rodou agora ({hora_brasilia}, {status}). "
        f"{total_novas} vaga(s) nova(s) neste ciclo.\n\n"
        "Se essa mensagem parar de chegar, o workflow parou de rodar — "
        "não que faltou vaga."
    )
    definir_metadado("heartbeat_ultimo_dia", hoje)


def ciclo_de_busca():
    total_novas = 0
    total_brutas = 0
    scrapers_com_problema = []

    termos_do_ciclo = _proximo_bloco_termos()
    logger.info(
        f"Bloco de termos deste ciclo: {len(termos_do_ciclo)}/{len(TERMOS_BUSCA)} — "
        f"{', '.join(termos_do_ciclo)}"
    )
    scrapers = _construir_scrapers(termos_do_ciclo)

    # A parte lenta (abrir navegador, navegar, esperar seletor) roda em
    # paralelo aqui. Tudo que segue (filtrar, checar dedup, notificar,
    # salvar) continua rodando só na thread principal, um scraper de cada
    # vez, conforme a future dele termina — nunca duas threads escrevendo
    # no SQLite ou chamando o Telegram ao mesmo tempo.
    with ThreadPoolExecutor(max_workers=MAX_SCRAPERS_CONCORRENTES) as executor:
        futures = {executor.submit(scraper.buscar_vagas): scraper for scraper in scrapers}

        for future in as_completed(futures):
            scraper = futures[future]
            nome = scraper.__class__.__name__

            try:
                vagas = future.result()
            except Exception as e:
                logger.error(f"Erro no scraper {nome}: {e}")
                scrapers_com_problema.append(nome)
                continue

            # Cada scraper trata timeout por termo internamente (só loga e
            # segue pro próximo termo), então um site totalmente bloqueado
            # não lança exceção pra cá — só devolve lista vazia. Por isso
            # também contamos "0 vaga bruta nessa fonte" como problema, não
            # só exceção.
            if not vagas:
                logger.warning(f"{nome} não retornou nenhuma vaga bruta neste ciclo.")
                scrapers_com_problema.append(nome)
                continue

            total_brutas += len(vagas)
            vagas_filtradas = filtrar_vagas(
                vagas,
                KEYWORDS_CARGO_FORTE,
                KEYWORDS_CARGO_AMBIGUO,
                QUALIFICADORES_DADOS,
                FERRAMENTAS_TITULO,
                QUALIFICADORES_CARGO,
                CIDADES,
            )

            for vaga in vagas_filtradas:
                if ja_vista(vaga):
                    continue

                # Notifica ANTES de salvar. Se salvasse primeiro e o Telegram
                # falhasse, a vaga ficava marcada como "vista" pra sempre — o
                # próximo ciclo pulava ela em ja_vista() e a vaga se perdia sem
                # nunca ter sido notificada de verdade.
                if not notificar_vaga(vaga):
                    logger.warning(
                        f"Falha ao notificar '{vaga.titulo}' - não marcada como vista, "
                        "tenta de novo no próximo ciclo."
                    )
                    continue

                salvar_vaga(vaga)
                total_novas += 1
                logger.info(f"Nova vaga: {vaga.titulo} - {vaga.empresa}")

    logger.info(f"Ciclo concluído. {total_novas} vaga(s) nova(s).")

    # Alerta de saúde: se a maioria das fontes falhou/voltou vazia, avisa no
    # Telegram. Sem isso, um bloqueio geral ou mudança de layout passaria
    # despercebido — o workflow do GitHub Actions continuaria "verde" mesmo
    # com tudo quebrado.
    if len(scrapers_com_problema) >= len(scrapers) / 2:
        enviar_mensagem(
            "⚠️ <b>JobRadar com problema</b>\n\n"
            f"{len(scrapers_com_problema)}/{len(scrapers)} fontes falharam ou voltaram "
            f"vazias neste ciclo: {', '.join(scrapers_com_problema)}.\n\n"
            "Vale checar o log do GitHub Actions."
        )

    _enviar_heartbeat_diario(total_novas, scrapers_com_problema, len(scrapers))


def main():
    parser = argparse.ArgumentParser(description="JobRadar - monitor de vagas")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Roda um único ciclo de busca e encerra (usado no GitHub Actions, "
             "que já dispara o script periodicamente via cron).",
    )
    args = parser.parse_args()

    print("=" * 50)
    print("JOBRADAR")
    print("=" * 50)

    print("\nPalavras monitoradas:")
    for palavra in KEYWORDS:
        print(f"• {palavra}")

    if not args.once:
        print(f"\nIntervalo de checagem: {INTERVALO_MINUTOS} min\n")

    try:
        iniciar_db()
    except BancoVazioSuspeito as e:
        # Aborta ANTES de rodar qualquer busca — ver database.py. Se
        # deixasse passar, toda vaga encontrada bateria "não vista" e
        # notificaria centenas de vagas antigas de uma vez.
        logger.error(str(e))
        enviar_mensagem(f"🛑 <b>JobRadar abortado</b>\n\n{e}")
        sys.exit(1)

    if args.once:
        # No GitHub Actions, quem controla a frequência é o cron do workflow,
        # não essa variável — por isso não faz sentido imprimir um intervalo
        # aqui, ele nem é usado nesse modo.
        ciclo_de_busca()
        return

    while True:
        ciclo_de_busca()
        logger.info(f"Aguardando {INTERVALO_MINUTOS} minutos até a próxima checagem...")
        time.sleep(INTERVALO_MINUTOS * 60)


if __name__ == "__main__":
    main()