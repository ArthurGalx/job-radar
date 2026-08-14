
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
    except requests.RequestException as e:
        logger.error(f"Erro ao enviar mensagem no Telegram: {e}")
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