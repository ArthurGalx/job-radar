
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
    texto = (
        f"🎯 <b>Nova vaga encontrada!</b>\n\n"
        f"<b>{job.titulo}</b>\n"
        f"🏢 {job.empresa}\n"
        f"📍 {job.local}\n"
        f"🌐 {job.site}\n\n"
        f"🔗 {job.link}"
    )
    return enviar_mensagem(texto)