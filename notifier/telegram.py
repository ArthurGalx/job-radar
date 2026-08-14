
import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from logger import get_logger

logger = get_logger()


def enviar_mensagem(texto: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram não configurado (token/chat_id ausentes no .env). Pulando envio.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    try:
        resposta = requests.post(url, data=payload, timeout=10)
        resposta.raise_for_status()
        return True
    # MEDIDO: logar a exceção direta (`{e}`) põe a URL inteira no log —
    # `url` tem o token embutido (bot{TOKEN}/sendMessage), e a mensagem
    # padrão de erro de conexão do requests/urllib3 (ProxyError,
    # ConnectionError...) inclui a URL completa que falhou. 6 ocorrências
    # reais em jobradar.log confirmaram o vazamento: arquivo é gitignored
    # (não vai pro repo) mas existe em disco e o GitHub Actions manda a
    # mesma mensagem pro stdout do job, visível em log de execução. HTTPError
    # (erro de resposta, ex: 401/403 do próprio Telegram) tem `.response`
    # com status e motivo, sem token nenhum — loga isso. Qualquer outra
    # RequestException (falha de conexão, nunca chegou a ter resposta) loga
    # só o tipo da exceção — nunca `str(e)`, nunca `url`.
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else None
        motivo = e.response.reason if e.response is not None else "sem detalhe"
        logger.error(f"Erro ao enviar mensagem no Telegram: HTTP {status} ({motivo})")
        return False
    except requests.RequestException as e:
        logger.error(
            f"Erro ao enviar mensagem no Telegram: {type(e).__name__} "
            "(falha de conexão, sem resposta do servidor)"
        )
        return False


def notificar_vaga(job) -> bool:
    # TODO (Fase 3): incluir aqui a % de compatibilidade com o currículo,
    # calculada por IA, quando essa etapa for implementada.
    #
    # Linha de publicação só aparece quando a fonte expõe isso (nem toda
    # expõe — ver Job.publicado_em / extrair_data_publicacao em job.py).
    linha_publicacao = f"<b>Publicada:</b> {job.publicado_em}\n" if job.publicado_em else ""
    linha_modalidade = f"<b>Modalidade:</b> {job.modalidade}\n" if job.modalidade else ""
    texto = (
        f"🚨 <b>Nova vaga encontrada!</b>\n\n"
        f"<b>Empresa:</b> {job.empresa}\n"
        f"<b>Cargo:</b> {job.titulo}\n"
        f"<b>Nível:</b> {job.senioridade}\n"
        f"<b>Local:</b> {job.local}\n"
        f"{linha_modalidade}"
        f"<b>Site:</b> {job.site}\n"
        f"{linha_publicacao}\n"
        f"Encontrada agora\n\n"
        f"<b>Link:</b>\n{job.link}"
    )
    return enviar_mensagem(texto)


def notificar_vaga_exploratoria(job) -> bool:
    """Vaga achada via eixo Ibérico (Portugal/Espanha) — fisicamente lá, não
    remota. Mensagem separada de notificar_vaga() de propósito: mandar isso
    pelo template normal sugeriria "achado remoto de verdade", quando na
    real é presencial/híbrida encontrada por busca geográfica dedicada (ver
    CIDADES_EUROPA_IBERICA em config.py/config_intl.py). Compartilhada pelos
    dois pipelines que têm esse eixo (main.py e main_intl.py) — texto já era
    genérico o bastante pros dois antes de virar função só de um deles,
    então movida pra cá em vez de duplicada.
    """
    linha_modalidade = f"<b>Modalidade:</b> {job.modalidade}\n" if job.modalidade else ""
    texto = (
        f"🧭 <b>Vaga exploratória (Portugal/Espanha)</b>\n\n"
        f"<b>Empresa:</b> {job.empresa}\n"
        f"<b>Cargo:</b> {job.titulo}\n"
        f"<b>Nível:</b> {job.senioridade}\n"
        f"<b>Local:</b> {job.local}\n"
        f"{linha_modalidade}"
        f"<b>Site:</b> {job.site}\n\n"
        f"Achada via busca por Portugal/Espanha — modalidade não confirmada "
        f"como remota, pode ser presencial ou híbrida. Confirma no link.\n\n"
        f"<b>Link:</b>\n{job.link}"
    )
    return enviar_mensagem(texto)