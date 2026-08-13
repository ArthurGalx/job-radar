
# Config do programa internacional (busca vaga remota fora do Brasil que
# aceita/pede português ou espanhol). Separado do config.py de propósito —
# ver decisão registrada na conversa: misturar ia forçar o filtro de cidade
# do Nordeste e as keywords em português do JobRadar original a servir dois
# propósitos diferentes ao mesmo tempo, deixando os dois mais frágeis.
#
# Credenciais do Telegram e caminho do banco são os MESMOS do projeto
# principal (reaproveita o bot já configurado, e o dedup por link no mesmo
# jobs.db não tem risco de colisão — o id é hash do link, e vaga
# internacional nunca vai ter o mesmo link de uma vaga brasileira).
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DB_PATH  # noqa: F401

# Cargo em múltiplos idiomas — vaga internacional pode ter o anúncio escrito
# em inglês, português ou espanhol, dependendo de quem contratou.
KEYWORDS_INTL = [
    "Data Analyst",
    "Business Intelligence",
    "BI Analyst",
    "Data Analytics",
    "Data Specialist",
    "Analista de Dados",
    "Analista de Datos",
    "Business Analyst",
]

# Termos de busca: cargo + sinal de idioma (português/espanhol/bilíngue).
# Não faz sentido buscar só "data analyst" sozinho aqui — isso é o mundo
# inteiro sem filtro nenhum de idioma, a maioria fora do nosso alcance.
TERMOS_BUSCA_INTL = [
    "data analyst spanish speaker",
    "data analyst portuguese speaker",
    "bilingual data analyst spanish",
    "bilingual data analyst portuguese",
    "business intelligence spanish speaker",
    "business intelligence portuguese speaker",
    "remote data analyst latam",
    "analista de datos remoto",
]

# Mercados pesquisados por rodada de busca no LinkedIn (parâmetro location
# do endpoint). Lista enxuta de propósito — cada país aqui multiplica o
# número de buscas (termos x países), então começa pequeno e dá pra
# expandir depois que confirmar que vale o tempo de execução.
LOCATIONS_INTL = [
    "United States",
    "Spain",
    "Portugal",
    "United Kingdom",
]

# Sem cidade nenhuma — só remoto, de qualquer país. "Remote" cobre o termo
# em inglês (a maioria dos cards vai estar em inglês), "Remoto" cobre os
# poucos que vierem em português/espanhol.
CIDADES_INTL = ["Remote", "Remoto"]
