
import os
from dotenv import load_dotenv

load_dotenv()

KEYWORDS = [
    "Analista de Dados",
    "Analista BI",
    "Analista de BI",
    "Business Intelligence",
    "Power BI",
    "Analytics",
    "Data Analyst",
    "Analista de Negócios",
    "Desenvolvedor BI",
    "Consultor BI",
    "Analista de Inteligência de Negócios",
    "BI Developer",
    "BI Analyst",
    "Analista de Reporting",
]

# Termos de busca enviados a cada site. Ficam separados das KEYWORDS de
# propósito: TERMOS_BUSCA é a rede ampla (o que é pesquisado em cada site,
# incluindo termos de ferramenta/stack pra achar vaga com título atípico),
# enquanto KEYWORDS é o filtro final e só olha o título da vaga já
# encontrada. Um termo de ferramenta (ex: "dax") só resulta em notificação
# se o TÍTULO da vaga também bater com uma keyword de cargo — isso evita
# falso positivo de vaga que só cita a ferramenta como diferencial.
TERMOS_CARGO = [
    "analista de dados",
    "analista de bi",
    "business intelligence",
    "power bi",
    "data analyst",
]

TERMOS_FERRAMENTA = [
    "dax",
    "power query",
    "microsoft fabric",
]

TERMOS_BUSCA = TERMOS_CARGO + TERMOS_FERRAMENTA

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