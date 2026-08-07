
import os
from dotenv import load_dotenv

load_dotenv()

KEYWORDS = [
    "Analista de Dados",
    "Analista BI",
    "Business Intelligence",
    "Power BI",
    "Analytics",
    "Data Analyst",
    "Analista de Negócios",
    "Desenvolvedor BI",
]

CIDADES = [
    "Remoto",
    "Campina Grande",
    "João Pessoa",
    "Recife",
    "Natal",
    "Maceió",
]

INTERVALO_MINUTOS = int(os.getenv("INTERVALO_MINUTOS", 30))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "jobs.db")