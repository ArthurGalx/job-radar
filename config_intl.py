
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
    "Business Analyst",
    # Nomenclatura em espanhol
    "Analista de Datos",
    "Analista de Inteligencia de Negocios",
    "Especialista en Datos",
    "Analista de Business Intelligence",
    "Analista de Reportes",
    # Eixo separado: Data Annotation / AI Evaluator — não é análise de
    # dados, é rotular/avaliar dado pra treinar IA, mas é um nicho remoto
    # que contrata muito por idioma (PT-BR/ES) e paga em dólar, então entra
    # como categoria própria de cargo, não mistura com as de análise.
    "Data Annotator",
    "Data Annotation",
    "AI Evaluator",
    "AI Trainer",
    "Data Labeler",
    "Search Quality Rater",
]

# Termos de busca: cargo + sinal de idioma (português/espanhol/bilíngue) ou
# +sinal de mercado (LATAM, Spanish Market). Não faz sentido buscar só
# "data analyst" sozinho aqui — isso é o mundo inteiro sem filtro nenhum de
# idioma, a maioria fora do nosso alcance.
TERMOS_BUSCA_INTL = [
    "data analyst spanish speaker",
    "data analyst spanish speaking",
    "data analyst portuguese speaker",
    "data analyst portuguese speaking",
    "bilingual data analyst spanish",
    "bilingual data analyst portuguese",
    "business intelligence spanish speaker",
    "business intelligence spanish speaking",
    "business intelligence portuguese speaker",
    "business intelligence portuguese speaking",
    "remote data analyst latam",
    "remote data analyst latin america",
    "data analyst spanish market",
    "business intelligence spanish markets",
    "analista de datos remoto",
    # Eixo Data Annotation / AI Evaluator
    "data annotation spanish speaker",
    "data annotation portuguese speaker",
    "ai evaluator spanish",
    "ai evaluator portuguese",
    "ai trainer portuguese speaker",
    "ai trainer spanish speaker",
    "remote data annotator latam",
]

# Mercados pesquisados por rodada de busca no LinkedIn (parâmetro location
# do endpoint). Lista enxuta de propósito — cada país aqui multiplica o
# número de buscas (termos x países), então começa pequeno e dá pra
# expandir depois que confirmar que vale o tempo de execução.
#
# "Latin America"/"LATAM"/"EMEA"/"Iberia" NÃO entraram aqui — testei ao
# vivo no endpoint do LinkedIn e nenhum desses nomes de região resolve como
# location de verdade (retorna resultado genérico, sem filtrar nada, ou
# vazio). O endpoint só reconhece país/cidade específico. Por isso os
# países de LATAM entraram nominalmente, e "latam"/"latin america" como
# texto dentro do termo de busca (acima) em vez de location. "Iberia" não
# precisa de entrada própria — já é coberto por Spain + Portugal abaixo.
LOCATIONS_INTL = [
    "United States",
    "Spain",
    "Portugal",
    "United Kingdom",
    "Mexico",
    "Colombia",
    "Argentina",
    "Chile",
]

# Sem cidade nenhuma — só remoto, de qualquer país. "Remote" cobre o termo
# em inglês (a maioria dos cards vai estar em inglês), "Remoto" cobre os
# poucos que vierem em português/espanhol.
#
# PROBLEMA que isso sozinho causava: CIDADES_INTL é uma whitelist — só
# aceita "Remote"/"Remoto" no local. Isso rejeita vaga presencial/híbrida
# em Lisboa ou Madrid mesmo quando ela é achada de propósito (via
# LOCATIONS_INTL = Portugal/Spain), porque o local não escreve "Remote"
# literalmente. Não é uma regra "excluir Portugal" — é a lógica de
# whitelist só admitir o que está na lista, o que dá no mesmo na prática.
#
CIDADES_INTL = ["Remote", "Remoto"]

# CIDADES_EUROPA_IBERICA é o eixo separado pra isso, controlado por
# ATIVAR_EIXO_IBERICO — dá pra desligar sem mexer no resto do pipeline
# internacional (nem em CIDADES_INTL). Ligado por padrão: quando ativo,
# vaga presencial/híbrida em Portugal/Espanha passa também, mas marcada
# como "exploratória" na notificação (ver main_intl.py), pra distinguir de
# vaga remota de verdade.
ATIVAR_EIXO_IBERICO = True

CIDADES_EUROPA_IBERICA = [
    "Portugal",
    "Lisboa",
    "Porto",
    "Braga",
    "Espanha",
    "España",
    "Spain",
    "Madrid",
    "Barcelona",
    "Valencia",
]

# Indeed usa subdomínio por país, não parâmetro de location como o
# LinkedIn. Confirmei ao vivo que es.indeed.com, pt.indeed.com e
# mx.indeed.com funcionam e trazem vaga local de verdade (ex: "Analista de
# Dados" em Lisboa, "Data Analyst" em Barcelona). uk/co/ar/cl seguem o
# mesmo padrão de domínio mas não testei individualmente — se algum não
# resolver como esperado, o scraper só loga 0 vagas pra aquele país, não
# quebra o resto.
#
# Mesmo aviso do Indeed BR original: tem proteção anti-bot que pode
# bloquear acesso automatizado (principalmente de IP de nuvem/datacenter),
# mesmo funcionando em teste manual.
DOMINIOS_INDEED_INTL = {
    "Estados Unidos": "www.indeed.com",
    "Espanha": "es.indeed.com",
    "Portugal": "pt.indeed.com",
    "Reino Unido": "uk.indeed.com",
    "México": "mx.indeed.com",
    "Colômbia": "co.indeed.com",
    "Argentina": "ar.indeed.com",
    "Chile": "cl.indeed.com",
}
