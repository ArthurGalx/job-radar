
import argparse
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone

from config import (
    DIGEST_HORA_UTC,
    FONTES_COM_DESCRICAO,
    INTERVALO_MINUTOS,
    LIMIAR_CARTA,
    LIMIAR_DIGEST_IMEDIATO,
)
from database.database import (
    BancoVazioSuspeito,
    definir_metadado,
    iniciar_db,
    ja_vista,
    marcar_digest_enviado,
    obter_metadado,
    obter_vagas_pendentes_digest,
    salvar_vaga,
)
from notifier.telegram import (
    enviar_digest,
    enviar_mensagem,
    notificar_vaga,
    notificar_vaga_exploratoria,
    processar_feedback_pendente,
)
from exporters.sheets import exportar_vaga
from job import _normalizar
from scrapers.descricao_gupy import buscar_descricao, buscar_endereco
from utils.geo import distancia_km
from perfis import FREQUENCIA_ALTA, PERFIS, Perfil
from utils.filtro import filtrar_vagas
from logger import get_logger

logger = get_logger()


def _medir_distancia(vaga) -> float | None:
    """Distância da vaga até onde o usuário mora, pra descontar no score o
    deslocamento (ver utils/geo.py e _PESO_DISTANCIA_* em job.py).

    O card de busca só diz a cidade, e "São Paulo - SP" pode ser tanto 2 km
    quanto 25 km de casa. Nas fontes que expõem o endereço completo na
    página da vaga (hoje só a Gupy), vale uma requisição a mais pra medir de
    verdade — mas só quando há deslocamento (vaga remota não desconta nada)
    e só depois da vaga ter passado no filtro, que é o que mantém isso em
    poucas requisições por ciclo.
    """
    if _normalizar(vaga.modalidade) not in ("presencial", "hibrido"):
        return None

    texto_local = vaga.local
    if vaga.site in FONTES_COM_DESCRICAO:
        endereco = buscar_endereco(vaga.link)
        if endereco:
            texto_local = endereco

    return distancia_km(texto_local, vaga.modalidade)


def _descricao_se_elegivel(vaga) -> str:
    """Texto do anúncio, só pra vaga que vale carta escrita à mão.

    Duas condições (ver LIMIAR_CARTA e FONTES_COM_DESCRICAO em config.py):
    score alto o bastante e fonte cuja página individual dá pra ler sem
    navegador. As duas juntas mantêm isso em ~1-3 requisições por ciclo, em
    cima das centenas que a busca já faz — buscar descrição de toda vaga
    aprovada multiplicaria o custo do ciclo sem uso pra 95% delas.
    """
    if vaga.site not in FONTES_COM_DESCRICAO or vaga.relevancia < LIMIAR_CARTA:
        return ""
    logger.info(f"Buscando descrição completa (score {vaga.relevancia}): {vaga.titulo}")
    return buscar_descricao(vaga.link)


# O projeto inteiro trabalha em UTC (o runner do GitHub Actions roda em
# UTC), e isso está certo pra tudo que é interno — dedup, offset de rodízio,
# heartbeat. A cadência "uma vez por dia" é a exceção: ela é uma promessa
# feita ao USUÁRIO, que vive em Brasília, então o "dia" tem que ser o dele.
#
# MEDIDO na prática: com a janela de execução das 08h às 23h de Brasília
# (11:00-02:00 UTC), o primeiro ciclo de cada dia UTC é o das 02:00 UTC —
# ou seja, o das 23h da noite anterior em Brasília. Em dia UTC, o perfil
# internacional cairia sempre no ciclo da noite; em dia local, cai no
# primeiro da manhã, que é o que "uma vez por dia" quer dizer pra quem lê
# a notificação.
_FUSO_BRASILIA = timezone(timedelta(hours=-3))


def _data_local() -> date:
    return datetime.now(_FUSO_BRASILIA).date()


def _perfil_ja_rodou_hoje(perfil: Perfil) -> bool:
    """Só pra perfil marcado com uma_vez_por_dia (ver perfis.py).

    A data fica em metadados (mesma tabela do heartbeat e do rodízio de
    termos), então sobrevive entre execuções do GitHub Actions — cada run é
    uma máquina nova.
    """
    return obter_metadado(f"perfil_ultimo_dia_{perfil.chave}") == _data_local().isoformat()


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


def _enviar_digest_diario(perfil: Perfil):
    """No máximo 1 digest por dia (por perfil) — ver item 08. Junta tudo
    que ficou digest_pendente=1 desde o último envio (pode ser de vários
    ciclos de 3h) e manda ranqueado, melhor primeiro.

    Disparo: no ciclo cujo horário UTC bate com DIGEST_HORA_UTC (0 =
    meia-noite UTC = 21h em Brasília) — o cron já passa por essa hora
    exata todo dia, não precisa de agendamento à parte. Mesma lógica de
    "só uma vez por dia" do heartbeat (data salva em metadados), mas com
    um reforço: se por qualquer motivo o ciclo exato de DIGEST_HORA_UTC
    falhar/pular um dia inteiro, manda no primeiro ciclo depois de 24h
    sem envio — não deixa a fila crescer indefinidamente esperando um
    horário exato que pode não voltar a bater certo (ex: workflow atrasado
    pelo GitHub Actions naquele dia).
    """
    chave = f"digest_ultimo_dia_{perfil.chave}"
    hoje = date.today()
    agora = datetime.now(timezone.utc)

    ultimo_envio_str = obter_metadado(chave)
    se_ja_enviou_hoje = ultimo_envio_str == hoje.isoformat()
    if se_ja_enviou_hoje:
        return

    # ">=" e não "==": o GitHub Actions atrasa a execução agendada com
    # frequência (medido: 25 min), e com poucos ciclos por dia — depois que
    # o cron parou de rodar de madrugada — um atraso que atravesse a virada
    # da hora faria o digest do dia inteiro ser pulado. Com ">=", o
    # primeiro ciclo a partir da hora-alvo envia; os ciclos seguintes do
    # mesmo dia não repetem, porque a data já ficou salva em metadados.
    horario_certo = agora.hour >= DIGEST_HORA_UTC
    atrasado = ultimo_envio_str is not None and (
        hoje - date.fromisoformat(ultimo_envio_str)
    ).days >= 2
    if not (horario_certo or atrasado):
        return

    vagas_pendentes = obter_vagas_pendentes_digest(perfil.chave)
    if not vagas_pendentes:
        # Marca mesmo sem vaga nenhuma — senão o "atrasado" acima dispara
        # todo ciclo seguinte até aparecer alguma vaga pendente de novo.
        definir_metadado(chave, hoje.isoformat())
        return

    if enviar_digest(vagas_pendentes, perfil.nome):
        marcar_digest_enviado(perfil.chave)
        definir_metadado(chave, hoje.isoformat())
        logger.info(f"[{perfil.nome}] Digest diário enviado: {len(vagas_pendentes)} vaga(s).")
    else:
        # Não marca metadado nem limpa a fila — tenta de novo no próximo
        # ciclo (ver enviar_digest/marcar_digest_enviado: preferir duplicar
        # a perder vaga).
        logger.warning(
            f"[{perfil.nome}] Falha ao enviar digest diário ({len(vagas_pendentes)} vaga(s) "
            "pendentes) - tenta de novo no próximo ciclo."
        )


def ciclo_de_busca(perfil: Perfil):
    total_novas = 0
    total_brutas = 0
    total_filtradas = 0
    scrapers_com_problema = []
    descartes_escopo_ciclo: Counter = Counter()

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
            vagas_filtradas, descartes = filtrar_vagas(vagas, perfil.regras, medir_distancia=_medir_distancia)
            descartes_escopo_ciclo.update(descartes)

            # Eixo secundário (Ibéria, quando ligado): mesma regra de cargo,
            # cidade diferente — sem duplicar o que já bateu na regra
            # primária.
            vagas_secundarias = []
            if perfil.eixo_secundario_ativo and perfil.regras_eixo_secundario is not None:
                ids_filtradas = {v.id for v in vagas_filtradas}
                candidatas, descartes_secundario = filtrar_vagas(vagas, perfil.regras_eixo_secundario, medir_distancia=_medir_distancia)
                descartes_escopo_ciclo.update(descartes_secundario)
                vagas_secundarias = [v for v in candidatas if v.id not in ids_filtradas]

            total_filtradas += len(vagas_filtradas) + len(vagas_secundarias)

            novas_da_fonte = 0
            for vaga in vagas_filtradas:
                if ja_vista(vaga):
                    continue

                # Item 08: só notifica na hora quando a relevância passa do
                # limiar (ver LIMIAR_DIGEST_IMEDIATO em config.py) — abaixo
                # disso, vai pra fila do digest diário sem mensagem
                # individual (ver _enviar_digest_diario). Fila é salvar com
                # digest_pendente=True: não tem "notificação que pode
                # falhar" nesse caminho (a mensagem só sai no digest, depois),
                # então salvar direto não arrisca perder a vaga do jeito que
                # salvar ANTES de notificar arriscava no caminho imediato.
                #
                # MEDIDO: vaga com Job.publicacao_antiga (publicado_em "há X
                # meses/anos" — ver job.py) nunca vai pra notificação
                # imediata, mesmo com relevância alta — score mede "bate com
                # o que você procura", não "é recente". Site com pouco
                # volume pra um termo deixa vaga de meses atrás na página
                # visível (confirmado ao vivo: Sólides ordena por data, mas
                # sem volume novo suficiente a antiga não sai da 1ª página).
                # Não é descartada (mesma vaga ainda pode estar aberta) — só
                # sai do caminho "🚨 urgente" e vai pro digest em lote.
                imediata = vaga.relevancia >= LIMIAR_DIGEST_IMEDIATO and not vaga.publicacao_antiga
                if imediata:
                    # Notifica ANTES de salvar. Se salvasse primeiro e o
                    # Telegram falhasse, a vaga ficava marcada como "vista"
                    # pra sempre — o próximo ciclo pulava ela em ja_vista()
                    # e a vaga se perdia sem nunca ter sido notificada de
                    # verdade.
                    if not notificar_vaga(vaga):
                        logger.warning(
                            f"[{perfil.nome}] Falha ao notificar '{vaga.titulo}' - não marcada "
                            "como vista, tenta de novo no próximo ciclo."
                        )
                        continue
                    salvar_vaga(vaga, perfil_chave=perfil.chave)
                    logger.info(f"[{perfil.nome}] Nova vaga: {vaga.titulo} - {vaga.empresa}")
                else:
                    salvar_vaga(vaga, perfil_chave=perfil.chave, digest_pendente=True)
                    motivo_digest = "vaga antiga" if vaga.publicacao_antiga else f"relevância {vaga.relevancia}/10"
                    logger.info(
                        f"[{perfil.nome}] Nova vaga (digest, {motivo_digest}): "
                        f"{vaga.titulo} - {vaga.empresa}"
                    )

                # DEPOIS de salvar, nunca antes: a planilha é canal extra
                # (ver exporters/sheets.py) e não pode virar pré-requisito
                # de nada. Falha aqui só loga — a vaga já está notificada e
                # marcada como vista, e repetir o ciclo por causa da
                # planilha é o que faria a vaga ser notificada duas vezes.
                exportar_vaga(
                    vaga,
                    perfil_nome=perfil.nome,
                    canal="imediata" if imediata else "digest",
                    motivo=vaga.motivo_aprovacao(perfil.regras),
                    descricao=_descricao_se_elegivel(vaga),
                )

                total_novas += 1
                novas_da_fonte += 1

            for vaga in vagas_secundarias:
                if ja_vista(vaga):
                    continue

                # Mesma regra de vaga antiga do loop acima.
                imediata = vaga.relevancia >= LIMIAR_DIGEST_IMEDIATO and not vaga.publicacao_antiga
                if imediata:
                    if not notificar_vaga_exploratoria(vaga):
                        logger.warning(
                            f"[{perfil.nome}] Falha ao notificar '{vaga.titulo}' (exploratória) - "
                            "não marcada como vista, tenta de novo no próximo ciclo."
                        )
                        continue
                    salvar_vaga(vaga, perfil_chave=perfil.chave)
                    logger.info(
                        f"[{perfil.nome}] Nova vaga exploratória ({perfil.eixo_secundario_rotulo}): "
                        f"{vaga.titulo} - {vaga.empresa}"
                    )
                else:
                    salvar_vaga(vaga, perfil_chave=perfil.chave, digest_pendente=True, exploratoria=True)
                    motivo_digest = "vaga antiga" if vaga.publicacao_antiga else f"relevância {vaga.relevancia}/10"
                    logger.info(
                        f"[{perfil.nome}] Nova vaga exploratória (digest, {motivo_digest}): "
                        f"{vaga.titulo} - {vaga.empresa}"
                    )

                # Regras do eixo secundário, não as primárias: é por elas
                # que a vaga exploratória passou (ver regras_eixo_secundario
                # em perfis.py), então é o motivo delas que explica a linha.
                exportar_vaga(
                    vaga,
                    perfil_nome=perfil.nome,
                    canal="imediata" if imediata else "digest",
                    motivo=vaga.motivo_aprovacao(perfil.regras_eixo_secundario),
                    exploratoria=True,
                    descricao=_descricao_se_elegivel(vaga),
                )

                total_novas += 1
                novas_da_fonte += 1

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

    # MEDIDO: descarte por escopo era invisível no log — o funil mostra
    # bruta → filtrada → nova, mas nunca QUAL escopo derrubou vaga nem
    # QUANTAS. Um escopo mal reconhecido (texto cru tipo "lagos nigeria",
    # não mapeado em _MERCADOS_REMOTO) barra do jeito certo, mas some sem
    # rastro — foi assim que um bug real (escopo virando allowlist) passou
    # despercebido até virar relato explícito. Loga só quando há descarte
    # (a maioria dos ciclos não tem nenhum), ordenado do que mais derrubou
    # vaga pro que menos derrubou.
    if descartes_escopo_ciclo:
        detalhe = "; ".join(
            f"{escopo} ({n})" for escopo, n in descartes_escopo_ciclo.most_common()
        )
        logger.info(f"[{perfil.nome}] Descarte por escopo: {detalhe}")

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
    _enviar_digest_diario(perfil)


def _rodar_um_ciclo_de_cada(perfis: list[Perfil], ignorar_cadencia: bool = False):
    # Uma vez por execução, não por perfil: o offset do getUpdates (ver
    # processar_feedback_pendente) é global — feedback de vaga não tem
    # perfil, e rodar duas vezes na mesma execução só gastaria uma chamada
    # de API à toa (a segunda sempre veria "nada novo desde a última vez").
    processar_feedback_pendente()

    for perfil in perfis:
        if perfil.uma_vez_por_dia and not ignorar_cadencia and _perfil_ja_rodou_hoje(perfil):
            logger.info(
                f"[{perfil.nome}] Já rodou hoje (perfil de cadência diária) — pulando neste ciclo."
            )
            continue

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

        # Marca DEPOIS de rodar: se o ciclo morrer no meio (fonte travada,
        # timeout do runner), o perfil não fica marcado como "já rodou hoje"
        # e tenta de novo no ciclo seguinte, em vez de sumir pelo resto do
        # dia. É o oposto da escolha feita em _construir_scrapers, onde
        # marcar antes é o certo — lá o risco é uma fonte lenta ser
        # retentada a cada ciclo; aqui, é o perfil inteiro não rodar.
        if perfil.uma_vez_por_dia:
            definir_metadado(f"perfil_ultimo_dia_{perfil.chave}", _data_local().isoformat())


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
        "--ignorar-cadencia-diaria",
        action="store_true",
        help="Roda também os perfis marcados com uma_vez_por_dia mesmo que já tenham "
             "rodado hoje (ver perfis.py). Usado no disparo MANUAL do workflow: quem "
             "aperta o botão está pedindo aquele perfil agora, e a cadência existe pra "
             "controlar o automático, não pra impedir o pedido explícito.",
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
        _rodar_um_ciclo_de_cada(perfis_selecionados, args.ignorar_cadencia_diaria)
        return

    while True:
        _rodar_um_ciclo_de_cada(perfis_selecionados, args.ignorar_cadencia_diaria)
        logger.info(f"Aguardando {INTERVALO_MINUTOS} minutos até a próxima checagem...")
        time.sleep(INTERVALO_MINUTOS * 60)


if __name__ == "__main__":
    main()
