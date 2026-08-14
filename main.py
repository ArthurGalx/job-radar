
import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone

from config import INTERVALO_MINUTOS
from database.database import (
    BancoVazioSuspeito,
    definir_metadado,
    iniciar_db,
    ja_vista,
    obter_metadado,
    salvar_vaga,
)
from notifier.telegram import notificar_vaga, notificar_vaga_exploratoria, enviar_mensagem
from perfis import FREQUENCIA_ALTA, PERFIS, Perfil
from utils.filtro import filtrar_vagas
from logger import get_logger

logger = get_logger()


def _fontes_baixa_frequencia_ja_rodaram_hoje(perfil: Perfil) -> bool:
    chave = f"baixa_frequencia_ultimo_dia_{perfil.chave}"
    return obter_metadado(chave) == date.today().isoformat()


# Não é mais uma lista fixa construída uma vez: os scrapers recebem só o
# BLOCO de termos do ciclo atual (ver _proximo_bloco_termos), e a lista de
# QUAIS fontes entram também varia por ciclo (fonte de baixa frequência só
# entra na primeira execução do dia) — então precisam ser (re)criados a
# cada ciclo, não guardados numa constante de módulo. Cada perfil tem sua
# própria chave de metadados (sufixo perfil.chave), pra rodar dois perfis
# na mesma execução sem um pisar na cadência do outro.
def _construir_scrapers(perfil: Perfil, termos_busca: list[str]):
    rodar_baixa_frequencia = not _fontes_baixa_frequencia_ja_rodaram_hoje(perfil)

    scrapers = [
        definicao.classe(termos_busca=termos_busca, **definicao.kwargs_extras)
        for definicao in perfil.definicao_scrapers
        if definicao.frequencia == FREQUENCIA_ALTA or rodar_baixa_frequencia
    ]

    if rodar_baixa_frequencia:
        # Marca ANTES de rodar (não depois): mesmo que uma fonte de baixa
        # frequência falhe nesse ciclo, ela "rodou" no sentido de já ter
        # sido tentada hoje — não deve ser tentada de novo no ciclo
        # seguinte só porque deu erro. Falha individual já é tratada e
        # logada normalmente em ciclo_de_busca(), como qualquer scraper.
        definir_metadado(f"baixa_frequencia_ultimo_dia_{perfil.chave}", date.today().isoformat())

    return scrapers


def _proximo_bloco_termos(perfil: Perfil) -> list[str]:
    """Rodízio: cada ciclo pega um BLOCO fixo (perfil.termos_por_ciclo) de
    perfil.termos_busca, começando de onde o ciclo anterior parou, e avança
    — volta pro início quando chega no fim da lista. A posição fica salva
    no jobs.db (tabela metadados, chave com sufixo do perfil — dois perfis
    rotacionam de forma independente), então sobrevive entre execuções do
    GitHub Actions (cada run é uma máquina nova).

    Isso é o que desacopla custo por ciclo do tamanho da lista de termos:
    lista grande leva mais ciclos pra cobrir tudo, mas cada ciclo individual
    continua custando o mesmo. Sem isso, dobrar a lista de termos dobrava o
    tempo de TODO ciclo.
    """
    total = len(perfil.termos_busca)
    if total == 0:
        return []

    tamanho_bloco = min(perfil.termos_por_ciclo, total)

    chave_offset = f"termos_offset_{perfil.chave}"
    offset_salvo = obter_metadado(chave_offset)
    # % total protege contra a lista ter encolhido desde o último ciclo
    # (termo removido do config.py) — sem isso, um offset salvo maior que o
    # tamanho atual da lista quebraria o acesso por índice abaixo.
    offset = int(offset_salvo) % total if offset_salvo else 0

    bloco = [perfil.termos_busca[(offset + i) % total] for i in range(tamanho_bloco)]

    definir_metadado(chave_offset, str((offset + tamanho_bloco) % total))

    return bloco


def _enviar_heartbeat_diario(
    perfil: Perfil, total_novas: int, scrapers_com_problema: list[str], total_fontes: int
):
    """No máximo 1 mensagem por dia (por perfil) confirmando que o ciclo
    rodou.

    O alerta de saúde só dispara quando ≥50% das fontes falha — mas se o
    workflow parar de rodar por completo (cron desabilitado pelo GitHub
    Actions por inatividade do repositório, erro de config, etc.), não
    existe ALERTA NENHUM disso: silêncio no Telegram fica idêntico a "rodou
    e não achou vaga nova". O heartbeat fecha essa lacuna — se ele parar de
    chegar um dia, o problema é o workflow não estar rodando, não a busca
    não ter achado nada. Por perfil: silêncio só do perfil Internacional
    (por exemplo) fica visível mesmo com o perfil Brasil rodando normal.

    A data do último envio fica salva no próprio jobs.db (tabela
    metadados), então sobrevive entre execuções do GitHub Actions (cada
    run é uma máquina nova) e não manda duplicado se o workflow rodar mais
    de uma vez no mesmo dia (cron normal ou workflow_dispatch manual).
    """
    chave = f"heartbeat_ultimo_dia_{perfil.chave}"
    hoje = date.today().isoformat()
    if obter_metadado(chave) == hoje:
        return

    hora_brasilia = datetime.now(timezone.utc).strftime("%H:%M UTC")
    if scrapers_com_problema:
        status = f"{len(scrapers_com_problema)}/{total_fontes} fonte(s) com problema"
    else:
        status = "todas as fontes ok"

    enviar_mensagem(
        f"💓 <b>JobRadar {perfil.nome} ativo</b>\n\n"
        f"Confirmação diária: o ciclo rodou agora ({hora_brasilia}, {status}). "
        f"{total_novas} vaga(s) nova(s) neste ciclo.\n\n"
        "Se essa mensagem parar de chegar, o workflow parou de rodar — "
        "não que faltou vaga."
    )
    definir_metadado(chave, hoje)


def ciclo_de_busca(perfil: Perfil):
    total_novas = 0
    total_brutas = 0
    total_filtradas = 0
    scrapers_com_problema = []

    termos_do_ciclo = _proximo_bloco_termos(perfil)
    logger.info(
        f"[{perfil.nome}] Bloco de termos deste ciclo: {len(termos_do_ciclo)}/"
        f"{len(perfil.termos_busca)} — {', '.join(termos_do_ciclo)}"
    )
    scrapers = _construir_scrapers(perfil, termos_do_ciclo)

    # A parte lenta (abrir navegador, navegar, esperar seletor) roda em
    # paralelo aqui. Tudo que segue (filtrar, checar dedup, notificar,
    # salvar) continua rodando só na thread principal, um scraper de cada
    # vez, conforme a future dele termina — nunca duas threads escrevendo
    # no SQLite ou chamando o Telegram ao mesmo tempo. Cada scraper já é
    # auto-contido (cria e fecha seu(s) próprio(s) browser(s) Playwright
    # dentro de buscar_vagas()), então dá pra rodar vários ao mesmo tempo em
    # threads sem risco — nenhum compartilha Browser/Page com outro.
    with ThreadPoolExecutor(max_workers=perfil.max_scrapers_concorrentes) as executor:
        futures = {executor.submit(scraper.buscar_vagas): scraper for scraper in scrapers}

        for future in as_completed(futures):
            scraper = futures[future]
            nome = scraper.__class__.__name__

            try:
                vagas = future.result()
            except Exception as e:
                logger.error(f"[{perfil.nome}] Erro no scraper {nome}: {e}")
                scrapers_com_problema.append(nome)
                continue

            # Cada scraper trata timeout por termo internamente (só loga e
            # segue pro próximo termo), então um site totalmente bloqueado
            # não lança exceção pra cá — só devolve lista vazia. Por isso
            # também contamos "0 vaga bruta nessa fonte" como problema, não
            # só exceção.
            if not vagas:
                logger.warning(f"[{perfil.nome}] {nome} não retornou nenhuma vaga bruta neste ciclo.")
                scrapers_com_problema.append(nome)
                continue

            total_brutas += len(vagas)
            vagas_filtradas = filtrar_vagas(vagas, perfil.regras)

            # Eixo secundário (Ibéria, quando ligado): mesma regra de cargo,
            # cidade diferente — sem duplicar o que já bateu na regra
            # primária.
            vagas_secundarias = []
            if perfil.eixo_secundario_ativo and perfil.regras_eixo_secundario is not None:
                ids_filtradas = {v.id for v in vagas_filtradas}
                candidatas = filtrar_vagas(vagas, perfil.regras_eixo_secundario)
                vagas_secundarias = [v for v in candidatas if v.id not in ids_filtradas]

            total_filtradas += len(vagas_filtradas) + len(vagas_secundarias)

            novas_da_fonte = 0
            for vaga in vagas_filtradas:
                if ja_vista(vaga):
                    continue

                # Notifica ANTES de salvar. Se salvasse primeiro e o Telegram
                # falhasse, a vaga ficava marcada como "vista" pra sempre — o
                # próximo ciclo pulava ela em ja_vista() e a vaga se perdia sem
                # nunca ter sido notificada de verdade.
                if not notificar_vaga(vaga):
                    logger.warning(
                        f"[{perfil.nome}] Falha ao notificar '{vaga.titulo}' - não marcada como "
                        "vista, tenta de novo no próximo ciclo."
                    )
                    continue

                salvar_vaga(vaga)
                total_novas += 1
                novas_da_fonte += 1
                logger.info(f"[{perfil.nome}] Nova vaga: {vaga.titulo} - {vaga.empresa}")

            for vaga in vagas_secundarias:
                if ja_vista(vaga):
                    continue

                if not notificar_vaga_exploratoria(vaga):
                    logger.warning(
                        f"[{perfil.nome}] Falha ao notificar '{vaga.titulo}' (exploratória) - não "
                        "marcada como vista, tenta de novo no próximo ciclo."
                    )
                    continue

                salvar_vaga(vaga)
                total_novas += 1
                novas_da_fonte += 1
                logger.info(
                    f"[{perfil.nome}] Nova vaga exploratória ({perfil.eixo_secundario_rotulo}): "
                    f"{vaga.titulo} - {vaga.empresa}"
                )

            # Funil por fonte: sem isso só dava pra ver bruta (por fonte) e
            # nova (só o total do ciclo) — o meio (quanto o filtro de
            # cargo/cidade descarta, fonte por fonte) ficava invisível.
            logger.info(
                f"[{perfil.nome}][{nome}] Funil: {len(vagas)} brutas → "
                f"{len(vagas_filtradas) + len(vagas_secundarias)} filtradas → {novas_da_fonte} novas"
            )

    logger.info(
        f"[{perfil.nome}] Ciclo concluído: {total_brutas} brutas → {total_filtradas} filtradas → "
        f"{total_novas} nova(s)."
    )

    # Alerta de saúde: se a maioria das fontes falhou/voltou vazia, avisa no
    # Telegram. Sem isso, um bloqueio geral ou mudança de layout passaria
    # despercebido — o workflow do GitHub Actions continuaria "verde" mesmo
    # com tudo quebrado.
    if scrapers and len(scrapers_com_problema) >= len(scrapers) / 2:
        enviar_mensagem(
            f"⚠️ <b>JobRadar {perfil.nome} com problema</b>\n\n"
            f"{len(scrapers_com_problema)}/{len(scrapers)} fontes falharam ou voltaram "
            f"vazias neste ciclo: {', '.join(scrapers_com_problema)}.\n\n"
            "Vale checar o log do GitHub Actions."
        )

    _enviar_heartbeat_diario(perfil, total_novas, scrapers_com_problema, len(scrapers))


def _rodar_um_ciclo_de_cada(perfis: list[Perfil]):
    for perfil in perfis:
        print(f"\n{'=' * 50}")
        print(f"PERFIL: {perfil.nome.upper()}")
        print("=" * 50)

        print("\nPalavras monitoradas:")
        for palavra in perfil.palavras_monitoradas:
            print(f"• {palavra}")

        if perfil.paises_pesquisados:
            print("\nPaíses pesquisados:")
            for pais in perfil.paises_pesquisados:
                print(f"• {pais}")

        ciclo_de_busca(perfil)


def main():
    parser = argparse.ArgumentParser(description="JobRadar - monitor de vagas")
    parser.add_argument(
        "--perfil",
        required=True,
        nargs="+",
        choices=sorted(PERFIS.keys()),
        help=(
            "Qual(is) mercado(s) rodar nesta execução — 'brasil', 'internacional', "
            "ou os dois (--perfil brasil internacional)."
        ),
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Roda um único ciclo de busca (de cada perfil selecionado) e encerra "
             "(usado no GitHub Actions, que já dispara o script periodicamente via cron).",
    )
    args = parser.parse_args()

    perfis_selecionados = [PERFIS[chave] for chave in args.perfil]

    if not args.once:
        print(f"\nIntervalo de checagem: {INTERVALO_MINUTOS} min\n")

    # Chamado UMA VEZ só, antes de qualquer perfil rodar — não por perfil.
    # A checagem de "banco suspeito" (ver database.py) compara se o arquivo
    # já existia ANTES desta execução; se cada perfil chamasse iniciar_db()
    # separadamente na mesma execução, o segundo perfil veria o arquivo que
    # o primeiro acabou de criar/popular momentos atrás e podia disparar
    # falso positivo (arquivo "já existia" só porque o perfil anterior já
    # rodou nesta mesma execução, não porque é run antigo de verdade).
    try:
        iniciar_db()
    except BancoVazioSuspeito as e:
        logger.error(str(e))
        nomes = ", ".join(p.nome for p in perfis_selecionados)
        enviar_mensagem(f"🛑 <b>JobRadar abortado</b>\n\nPerfis desta execução: {nomes}\n\n{e}")
        sys.exit(1)

    if args.once:
        _rodar_um_ciclo_de_cada(perfis_selecionados)
        return

    while True:
        _rodar_um_ciclo_de_cada(perfis_selecionados)
        logger.info(f"Aguardando {INTERVALO_MINUTOS} minutos até a próxima checagem...")
        time.sleep(INTERVALO_MINUTOS * 60)


if __name__ == "__main__":
    main()
