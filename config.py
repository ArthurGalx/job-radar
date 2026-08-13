
import os
from dotenv import load_dotenv

load_dotenv()

# Cargo forte: título que só existe mesmo em vaga de dados/BI, sem
# possibilidade real de ser outra área.
KEYWORDS_CARGO_FORTE = [
    "Analista de Dados",
    "Analista BI",
    "Analista de BI",
    "Business Intelligence",
    "Data Analytics",
    "Analytics Engineer",
    "Analista de Analytics",
    "Data Analyst",
    "Desenvolvedor BI",
    "Consultor BI",
    "Analista de Inteligência de Negócios",
    "BI Developer",
    "BI Analyst",
    "Analista de Reporting",
    "Analista de Inteligência de Mercado",
]

# Cargo ambíguo: título que também é usado em vaga sem nada a ver com
# dados/BI (ex: "Business Analyst" e "Analista de Negócios" existem em
# TI, finanças, RH, operações... qualquer área). Só conta como match se o
# título TAMBÉM tiver um QUALIFICADORES_DADOS junto — é o que permite ir
# adicionando cargo adjacente (Product Analyst, CRM Analyst, Marketing
# Analyst etc.) sem cada um virar fonte de ruído sozinho.
KEYWORDS_CARGO_AMBIGUO = [
    "Business Analyst",
    "Analista de Negócios",
    "Business Analytics",
]

# Termo que precisa aparecer junto no título quando o cargo é ambíguo, pra
# confirmar que é vaga de dados/BI e não de outra área qualquer.
QUALIFICADORES_DADOS = [
    "dados",
    "data",
    "bi",
    "sql",
    "power bi",
    "analytics",
    "kpi",
    "dashboard",
    "métricas",
    "reporting",
    "insights",
]

KEYWORDS = KEYWORDS_CARGO_FORTE + KEYWORDS_CARGO_AMBIGUO

# Termos de busca enviados a cada site. Ficam separados das KEYWORDS de
# propósito: TERMOS_BUSCA é a rede ampla (o que é pesquisado em cada site,
# incluindo termos de ferramenta/stack pra achar vaga com título atípico),
# enquanto KEYWORDS é o filtro final e só olha o título da vaga já
# encontrada. Um termo de ferramenta (ex: "dax") só resulta em notificação
# se o TÍTULO da vaga também bater com uma keyword de cargo — isso evita
# falso positivo de vaga que só cita a ferramenta como diferencial.
#
# TERMOS_CARGO é derivado direto de KEYWORDS (em vez de mantido à mão em
# lista separada) — antes as duas listas divergiam: metade das KEYWORDS
# (ex: "Desenvolvedor BI", "BI Analyst", "Analista de Negócios") nunca era
# buscada de verdade, só existia como filtro, então só pegava essas vagas
# por sorte via outro termo. Com a derivação automática isso não pode mais
# acontecer — toda keyword nova em KEYWORDS já vira busca também.
TERMOS_CARGO_EXTRA = [
    # termos mais amplos que a keyword exata, mantidos por dar rede mais
    # larga na busca (a keyword em si é mais restrita, de propósito, pra
    # não gerar falso positivo no filtro de título).
    "power bi",
    "inteligência de mercado",
]

TERMOS_CARGO = sorted(set(k.lower() for k in KEYWORDS) | set(TERMOS_CARGO_EXTRA))

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

INTERVALO_MINUTOS = int(os.getenv("INTERVALO_MINUTOS", 120))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "jobs.db")