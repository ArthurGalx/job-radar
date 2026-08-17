
import os
from dotenv import load_dotenv

load_dotenv()

# ESCOPO DO RADAR: vaga de PRODUTO (Product Owner / PM júnior / Analista de
# Produto), TRAINEE em tecnologia e o eixo adjacente de OPERAÇÕES/AUTOMAÇÃO
# (Business Analyst, Analista de Processos/Automação) — que é o que o
# currículo mostra na prática (PO na Yuca, automação via Make/APIs, rituais
# ágeis). O radar era calibrado pra Dados/BI antes; as keywords de dados
# saíram do eixo de CARGO e sobraram só como QUALIFICADORES_DOMINIO (abaixo),
# onde continuam servindo pra confirmar que um cargo ambíguo é de tech.

# Cargo forte: título que já é inequivocamente de produto/tech, sem
# possibilidade real de ser outra área. Basta bater no título.
KEYWORDS_CARGO_FORTE = [
    "Product Owner",
    "Associate Product Manager",
    "Product Analyst",
    "Product Operations",
    "Product Ops",
    "Analista de Produto Digital",
    "Dono do Produto",
    # Cargo que o usuário já ocupou (estagiário de Business Architect na
    # Yuca) e que descreve o que ele faz de mais distintivo: desenhar e
    # automatizar processo de operação com integração e API. Entra como
    # FORTE, não ambíguo: diferente de "Product Manager", o termo não é
    # usado fora de tecnologia/consultoria — não existe "business architect
    # de calçados". As grafias em português entram separadas porque o match
    # é por borda de palavra e nenhuma cobre a outra.
    "Business Architect",
    "Arquiteto de Negócios",
    "Arquiteta de Negócios",
    # "Product Discovery" fica só em TERMOS_FERRAMENTA (busca), não aqui:
    # é método, não cargo — como keyword duplicaria o termo de busca (a
    # derivação TERMOS_CARGO já puxa toda KEYWORDS) e gastaria uma sessão
    # de busca à toa.
    "Analista de Automação",
    "Analista de Automações",
    "Analista de Processos e Automação",
    "Dueño de Producto",
]

# Cargo ambíguo: título que também é usado em vaga sem nada a ver com
# produto/tecnologia — "Trainee" existe em banco, varejo, jurídico e
# indústria; "Business Analyst" e "Analista de Negócios" existem em
# finanças, RH, operações. Só conta como match se o título TAMBÉM tiver um
# QUALIFICADORES_DOMINIO junto ("Trainee de Tecnologia", "Business Analyst
# de Produto") — é o que permite manter cargo adjacente no radar sem cada
# um virar fonte de ruído sozinho.
KEYWORDS_CARGO_AMBIGUO = [
    "Trainee",
    # "Estágio"/"Estagiário" ficam FORA: o pedido é PO/trainee, e a
    # graduação já terminou (dez/2025) — vaga de estágio seria degrau pra
    # trás, e "estágio" é um dos termos de maior volume bruto dos portais
    # (cada busca dessas custa uma sessão de navegador igual às outras).
    #
    # MEDIDO no primeiro ciclo real do escopo novo (285 vagas): "Product
    # Manager"/"Gerente de Produto" estava como cargo FORTE e 175 delas
    # (61%) eram título de PM SEM nenhum marcador de tecnologia — "Product
    # Manager – Negocio Café" (Pascual), "Product Manager Laundry" (Haier),
    # "Gerente de Produto - Calçados" (C&A), "Product Manager - Thickening"
    # (FLSmidth). Em indústria, varejo e farma essas palavras designam
    # gerente de categoria/marca, profissão diferente da de produto digital.
    # É o mesmo caso de "Business Analyst" logo abaixo, e agora usa o mesmo
    # mecanismo: só aprova com qualificador de domínio junto.
    #
    # "Product Owner" e "Associate Product Manager" continuam FORTES de
    # propósito — não existem praticamente fora de tecnologia. O custo
    # aceito aqui é perder PM de startup cujo título não cite tecnologia
    # (ex: "Product Manager - Ryz Labs"), decisão tomada com o número acima
    # na mesa.
    "Product Manager",
    "Gerente de Produto",
    "Gerente de Producto",
    "Gestor de Produto",
    "Analista de Produto",
    # Plural precisa de entrada própria: o match é por borda de palavra
    # (ver _contem_termo em job.py), então "Analista de Produto" NÃO bate
    # "Analista de Produtos".
    "Analista de Produtos",
    "Analista de Producto",
    "Assistente de Produto",
    "Business Analyst",
    "Analista de Negócios",
    "Analista de Sistemas",
    "Analista de Processos",
    "Analista de Operações",
    "Analista Funcional",
    "Analista de Inovação",
    "Analista de Projetos",
    "Project Manager",
    "Program Manager",
    "Analista de Performance",
]

# Termo que precisa aparecer junto no título quando o cargo é ambíguo, pra
# confirmar que é vaga de produto/tecnologia e não de outra área qualquer.
# É aqui que o vocabulário de dados (dados/data/BI/SQL/analytics) continua
# vivo: não aprova vaga sozinho, mas confirma que um "Trainee"/"Business
# Analyst" está no escopo de tech.
QUALIFICADORES_DOMINIO = [
    # "produto"/"product"/"producto" NÃO entram, por mais natural que
    # pareça: desde que "Gerente de Produto" virou cargo ambíguo (ver
    # acima), a palavra "produto" está DENTRO do próprio cargo — ela se
    # autoqualificaria e o par ambíguo+qualificador nunca rejeitaria nada.
    # Qualificador aqui é marcador de DOMÍNIO (é tech?), não repetição do
    # cargo. Custo conhecido: "Trainee de Produto" sozinho deixa de passar;
    # "Trainee de Produto Digital" passa pelo "digital".
    "tecnologia",
    "tecnología",
    "technology",
    "tech",
    "ti",
    "it",
    "digital",
    "software",
    "sistemas",
    "plataforma",
    "saas",
    "startup",
    "inovação",
    "automação",
    "automation",
    "ágil",
    "agile",
    "scrum",
    "growth",
    "e-commerce",
    "ecommerce",
    "marketplace",
    "fintech",
    "app",
    "mobile",
    "web",
    "cloud",
    "api",
    "crm",
    "erp",
    "ia",
    "ai",
    "dados",
    "data",
    "bi",
    "sql",
    "analytics",
]

# Ferramenta/framework que aparece como núcleo do título ("Analista de
# Processos - Scrum"). Só conta como match se o título TAMBÉM tiver uma
# palavra de cargo — é o espelho da regra de KEYWORDS_CARGO_AMBIGUO: lá o
# cargo é ambíguo e pede domínio, aqui a ferramenta é ambígua e pede cargo.
# Sem isso, "Scrum" sozinho aprovaria "Desenvolvedor (time Scrum)", que é
# vaga de dev, não de produto.
FERRAMENTAS_TITULO = [
    "Scrum",
    "Agile",
    "Ágil",
    "Jira",
    "No-Code",
    "Low-Code",
]

# Palavra de cargo que confirma que a vaga de ferramenta é de produto/
# processo. "desenvolvedor"/"developer"/"engenheiro" ficam FORA de
# propósito: é o que mantém vaga de dev fora do radar.
QUALIFICADORES_CARGO = [
    "analista",
    "analyst",
    "owner",
    "manager",
    "trainee",
    "especialista",
    "specialist",
    "consultor",
    "consultant",
    "assistente",
    "coordenador",
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
    "product owner junior",
    "product manager junior",
    "produto digital",
    "gestão de produtos",
    # "Trainee" sozinho já entra via KEYWORDS (derivação abaixo) e traz o
    # volume bruto de trainee de TODA área — estes dois vão direto no
    # recorte que interessa, pra não depender só do filtro pós-busca.
    "programa de trainee tecnologia",
    "trainee produto",
]

TERMOS_CARGO = sorted(set(k.lower() for k in KEYWORDS) | set(TERMOS_CARGO_EXTRA))

# Ferramenta/método como rede extra pra achar vaga com título atípico que
# nenhum termo de cargo pegaria. Continua valendo a regra geral: termo de
# ferramenta só vira notificação se o TÍTULO da vaga bater numa keyword de
# cargo (ou em FERRAMENTAS_TITULO + QUALIFICADORES_CARGO) — buscar "scrum"
# não faz vaga de dev entrar.
#
# A lista antiga era de stack de dados (sql/python/tableau/qlik/looker/
# bigquery). Saiu junto com o eixo de cargo de dados: sem "Analista de
# Dados" nas keywords, esses termos passariam a buscar muito e aprovar
# nada. O vocabulário de dados que sobrou vive em QUALIFICADORES_DOMINIO,
# onde ainda serve pra confirmar cargo ambíguo de tech.
TERMOS_FERRAMENTA = [
    "scrum",
    "product discovery",
    "automação de processos",
    "no-code",
]

TERMOS_BUSCA = TERMOS_CARGO + TERMOS_FERRAMENTA

# Medido: os TERMOS_BUSCA inteiros (hoje 42) rodando em TODO ciclo é o que
# gera as centenas de sessões de navegador por execução — o custo cresce
# linear com o tamanho da lista, e a lista só cresce (mais ainda com a
# expansão internacional puxando mais termos no radar). TERMOS_POR_CICLO é
# o tamanho do BLOCO usado por ciclo, não o total de termos — main.py roda
# um bloco por vez em rodízio (ver _proximo_bloco_termos) e avança pro
# próximo bloco no ciclo seguinte, salvando a posição no jobs.db. Isso
# desacopla custo por ciclo de tamanho da lista: dobrar TERMOS_BUSCA dobra
# quantos ciclos até cobrir tudo de novo, não o custo de cada ciclo.
TERMOS_POR_CICLO = 10

# Whitelist de local: São Paulo (capital + Grande SP/interior próximo, onde
# está concentrada praticamente toda vaga de produto do país) + Remoto.
#
# A lista era do Nordeste (Campina Grande, João Pessoa, Recife, Natal...) —
# trocada, não ampliada: o usuário mora em São Paulo. Manter as duas
# regiões só encheria a notificação de vaga presencial a 2.000 km.
#
# "São Paulo" bate tanto a capital quanto o texto de local que escreve o
# estado por extenso ("Campinas, São Paulo") — as cidades da região
# metropolitana abaixo existem pros anúncios que só citam a cidade
# ("Barueri - SP", "Alphaville").
CIDADES = [
    "Remoto",
    "São Paulo",
    "Barueri",
    "Alphaville",
    "Osasco",
    "Guarulhos",
    "Diadema",
    "Cotia",
    "Campinas",
    "Santo André",
    "São Bernardo",
    "São Caetano",
    # MEDIDO ao vivo na Gupy: o card corta o nome da cidade em ~10
    # caracteres ("Rio de Jan... - RJ", "Ribeirão P... - SP"). Cidade com
    # nome mais longo que isso nunca bateria escrita por extenso, então as
    # três acima precisam da forma cortada TAMBÉM — o match é por borda de
    # palavra (ver _contem_termo em job.py), e uma forma não cobre a outra:
    # "São Bernar" não bate "São Bernardo do Campo" (a borda cai no meio da
    # palavra) e "São Bernardo" não bate "São Bernar...".
    "Santo Andr",
    "São Bernar",
    "São Caeta",
]

# MEDIDO: "Data Analyst @ Lisboa" e "Analista de Datos @ Madrid" reprovavam
# na localização, não no cargo — CIDADES acima é whitelist só de cidade
# brasileira, e a expansão de LOCATIONS_LINKEDIN pra Argentina/Chile (ver
# abaixo) passou a trazer vaga presencial/híbrida em Portugal/Espanha de
# vez em quando junto. Lista SEPARADA (não misturada em CIDADES, que
# continua só-Brasil de propósito — ver decisão registrada na criação do
# config_intl.py) com toggle próprio, pra dar pra ligar/desligar esse eixo
# sem mexer no resto do filtro. Canônica aqui porque config_intl.py já
# importa de config.py (não o contrário) — o pipeline internacional reusa
# essa mesma lista em vez de manter uma cópia (risco de divergir, mesmo
# motivo da unificação de _contem_termo/_tem_termo).
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

# Toggle independente do ATIVAR_EIXO_IBERICO de config_intl.py — são dois
# eixos diferentes (esse aqui é do pipeline BR/main.py, aquele é do
# pipeline internacional/main_intl.py), cada um com seu próprio liga/
# desliga, mesmo compartilhando a mesma lista de cidades acima.
#
# DESLIGADO: do mercado internacional, só interessa vaga remota — vaga
# presencial/híbrida em Lisboa/Madrid (o que esse eixo notifica, marcada
# "exploratória") não é o que o usuário quer. CIDADES_EUROPA_IBERICA
# continua definida (não precisa apagar) pra caso o eixo volte a ser
# ligado depois — só o toggle muda.
ATIVAR_EIXO_IBERICO_BR = False

# LinkedInScraper é a única fonte do pipeline BR que também alcança vaga
# fora do Brasil (as outras são portais brasileiros) — mas até aqui rodava
# só com location=Brasil fixo no código (scrapers/linkedin.py:88), então
# essa "porta pra fora" nunca era usada.
#
# Mercado "casa": busca modalidade completa (presencial/híbrida + remoto),
# porque o usuário mora aqui e vaga local de verdade interessa.
LOCATIONS_LINKEDIN = ["Brasil"]

# Mercados adicionais: só busca REMOTA (f_WT=2) — vaga presencial/híbrida
# num país onde o usuário não mora não serve, então nem faz sentido gastar
# a passada nacional ali (era puro desperdício: Argentina/Chile já rodavam
# as duas passadas antes, mas a nacional nunca batia em CIDADES mesmo,
# que é só cidade brasileira). Espanhol ou português — mesmo critério do
# pipeline internacional. Lista reaproveita exatamente os países já usados
# e testados ao vivo no endpoint do LinkedIn em config_intl.py
# (LOCATIONS_INTL) — evita arriscar nome de país nunca testado (grafia
# errada ou região que o LinkedIn não resolve como location de verdade,
# como já visto com "LATAM"/"Latin America").
# VAZIO desde a virada pro escopo de produto. MEDIDO no primeiro ciclo real:
# das 285 vagas novas do perfil BRASIL, 269 (94%) tinham local fora do
# Brasil — Product Manager do mercado local de Chile, Espanha e Portugal,
# achado justamente por esta lista. Para vaga de dados em espanhol pagando
# em dólar isso fazia sentido; para PO júnior morando em São Paulo, o perfil
# BR virou um segundo perfil internacional pior que o original.
#
# Vaga remota de fora continua coberta — é exatamente o que o PERFIL_INTL
# faz (ver perfis.py), com termos e filtro de idioma próprios. A separação
# de responsabilidade entre os dois perfis é o que já existia no projeto;
# esta lista é que estava furando ela.
#
# Lista mantida vazia em vez de apagada: o LinkedInScraper aceita o
# parâmetro (locations_remoto_apenas) e religar é só repor os países.
LOCATIONS_LINKEDIN_REMOTO_APENAS = []

# Mercado que a vaga remota precisa aceitar pra contar, quando o texto de
# local DECLARA um escopo geográfico ("Remote — US only", "Remote — India").
# Ver Job.escopo_remoto/RegrasFiltro.mercados_remoto_aceitos em job.py — sem
# isso, uma vaga remota só pra outro país passava igual a uma remota de
# verdade pro Brasil. Vaga remota SEM escopo declarado no texto (a grande
# maioria) continua batendo normalmente, isso só filtra quando a fonte
# EXPLICITA um mercado incompatível.
#
# MEDIDO: Argentina/Chile/México/Colômbia ENTRAM nominalmente agora — a
# suposição de que "LATAM" cobria os quatro como guarda-chuva só valia
# enquanto extrair_escopo_remoto resolvia o texto pra "LATAM" literal.
# Depois que passou a reconhecer cidade (Buenos Aires/Santiago/Cidade do
# México/Bogotá — ver _CIDADES_MERCADO em job.py), o escopo passou a
# resolver pro PAÍS específico, não mais pro guarda-chuva — e o país
# específico nunca esteve nessa lista. Resultado: LOCATIONS_LINKEDIN_
# REMOTO_APENAS pagava o custo de buscar nesses 4 países e o filtro
# descartava tudo que a busca trazia de lá. "LATAM" continua na lista pra
# quando o texto disser isso literalmente (guarda-chuva de verdade, não
# substituto de nome de país). Portugal e Espanha entraram nominalmente
# pelo mesmo motivo, desde antes.
# Encolhida junto com LOCATIONS_LINKEDIN_REMOTO_APENAS acima, e pelo mesmo
# motivo: aceitar "Remote — Chile"/"Remote — Espanha" no perfil BR deixava
# entrar vaga do mercado local de outro país mesmo depois de parar de
# buscar lá (outras fontes também trazem). "LATAM" fica porque é
# guarda-chuva que inclui o Brasil — vaga "Remote - LATAM" contrata
# brasileiro. País hispanofalante nominalmente é o que sai.
MERCADOS_REMOTO_ACEITOS = ["Brasil", "LATAM"]

INTERVALO_MINUTOS = int(os.getenv("INTERVALO_MINUTOS", 180))

# Digest ranqueado (item 08): vaga com Job.pontuar_relevancia() >= este
# limiar notifica na hora (como sempre foi); abaixo disso, fica na fila do
# digest diário — ver _enviar_digest_diario em main.py.
#
# A medição antiga (~305 vagas do jobs.db de Dados/BI: 67% em score 6, só
# 7% >= 7) justificava limiar 7. Ela não vale mais depois da virada pro
# escopo de produto: o eixo de FERRAMENTA valia +2 com frequência no mundo
# BI ("Analista de BI - Power BI", "Analista de Dados SQL"), e título de
# produto quase nunca traz ferramenta ("Product Owner Pleno" e ponto). Isso
# desloca a distribuição inteira ~2 pontos pra baixo — com limiar 7,
# praticamente NADA notificaria na hora e o digest viraria o único canal.
#
# Limiar 6 recoloca no imediato o alvo real do pedido: PO/PM júnior-pleno
# (cargo forte 3 + senioridade alvo 2) tanto remoto (+1) quanto presencial
# em SP (+2), e trainee de tech presencial. Vaga sem senioridade no título
# ou acima do alvo (sênior/gerência) cai pro digest, que é o que se quer.
# Reavaliar com dado real depois de alguns dias rodando no escopo novo.
LIMIAR_DIGEST_IMEDIATO = 6

# Hora UTC a partir da qual o digest diário pode disparar (uma vez por
# perfil, por dia — ver _enviar_digest_diario). Quem dispara de fato é o
# ciclo das 20h de Brasília (23:00 UTC); o valor fica uma hora antes de
# propósito, como folga pro atraso do GitHub Actions.
#
# Era 0 (21h de Brasília) e QUEBROU junto com a mudança do cron: o
# workflow deixou de rodar de madrugada, então nenhum ciclo passava mais
# pela meia-noite UTC e o digest só sairia pelo caminho de emergência
# ("atrasado há 2 dias"). Ao mudar o cron de novo, este valor precisa
# apontar pra uma hora em que ainda exista ciclo agendado.
DIGEST_HORA_UTC = 22

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Export pra Google Sheets (ver exporters/sheets.py e o código do Apps
# Script em docs/planilha_apps_script.gs). Vazio = export desligado, e o
# resto do pipeline roda igual — é um canal EXTRA, nunca um pré-requisito:
# planilha fora do ar não pode impedir notificação nem fazer vaga ser
# perdida.
#
# A URL do web app é credencial na prática (quem tem a URL escreve na
# planilha), por isso vem de secret/.env como o token do Telegram — nunca
# hardcoded — e nunca é logada (mesmo cuidado do enviar_mensagem, ver
# MEDIDO em notifier/telegram.py sobre vazamento de token no log).
# SHEETS_TOKEN é um segundo segredo, conferido DENTRO do Apps Script: sem
# ele, qualquer um que descobrisse a URL poderia injetar linha na planilha.
SHEETS_WEBHOOK_URL = os.getenv("SHEETS_WEBHOOK_URL", "")
SHEETS_TOKEN = os.getenv("SHEETS_TOKEN", "")

# Blocklist de idioma: título que exige uma língua que o usuário não fala é
# REJEITADO, por mais que cargo, cidade e mercado aprovem. Ele fala
# português (nativo) e inglês (avançado) — qualquer outra língua no título
# significa vaga que ele não pode aceitar.
#
# Vale pros DOIS perfis (aqui e no internacional): vaga bilíngue de mercado
# local existe no Brasil também ("Analista de Produto - Francês Fluente",
# "Product Owner para cliente alemão"), não é fenômeno só de vaga de fora.
#
# Grafia em português, inglês e na própria língua, porque o anúncio pode
# vir em qualquer um dos três: um anúncio brasileiro escreve "francês", um
# internacional escreve "french", e a empresa alemã às vezes escreve
# "Deutsch" no meio de um título em inglês. O match é por borda de palavra
# (ver _contem_termo em job.py), então "german" não bate "germany" nem
# "Germany-based" — o objetivo é pegar EXIGÊNCIA DE IDIOMA, não menção a
# país.
IDIOMAS_NAO_FALADOS = [
    # Espanhol — o mais frequente no radar, porque LATAM e Ibéria são
    # justamente onde o perfil internacional busca.
    "spanish", "espanol", "español", "espanhol", "castellano", "hispanohablante",
    # Línguas da Europa Ocidental, as mais comuns em vaga remota europeia.
    "french", "français", "francais", "francês", "frances", "francophone",
    "german", "deutsch", "alemão", "alemao", "allemand",
    "italian", "italiano", "italien",
    "dutch", "nederlands", "holandês", "holandes", "flemish", "vlaams",
    # Nórdicas.
    "swedish", "svenska", "sueco",
    "norwegian", "norsk", "norueguês", "noruegues",
    "danish", "dansk", "dinamarquês", "dinamarques",
    "finnish", "suomi", "finlandês", "finlandes",
    # Leste Europeu.
    "polish", "polski", "polonês", "polones",
    "czech", "čeština", "tcheco",
    "slovak", "eslovaco",
    "hungarian", "magyar", "húngaro", "hungaro",
    "romanian", "română", "romeno",
    "bulgarian", "búlgaro", "bulgaro",
    "croatian", "croata",
    "serbian", "sérvio", "servio",
    "ukrainian", "ucraniano",
    "russian", "русский", "russo",
    "greek", "grego",
    # Ásia e Oriente Médio.
    "mandarin", "cantonese", "chinese", "chinês", "chines",
    "japanese", "japonês", "japones", "nihongo",
    "korean", "coreano",
    "thai", "tailandês", "tailandes",
    "vietnamese", "vietnamita",
    "indonesian", "bahasa", "indonésio", "indonesio",
    "hindi", "urdu", "bengali", "tamil",
    "arabic", "árabe", "arabe",
    "hebrew", "hebraico",
    "turkish", "türkçe", "turco",
    "farsi", "persian", "persa",
    # Regionais da Península Ibérica — vaga em Barcelona/Bilbao/Galiza
    # costuma exigir a língua co-oficial junto do espanhol.
    "catalan", "català", "catalão", "catalao",
    "basque", "euskara", "basco",
    "galician", "galego",
    # Africanas com presença em vaga remota europeia.
    "afrikaans", "swahili",
]

# Fontes cuja página individual entrega a descrição sem navegador (JSON
# embutido no HTML — ver scrapers/descricao_comum.py). A descrição é o que
# alimenta os eixos de afinidade e barreira do score (ver
# pontuar_relevancia em job.py); sem ela, o score volta a depender só do
# título, que em vaga de produto quase não diz nada.
#
# Buscada pra TODA vaga aprovada dessas fontes, não só pras de score alto:
# são ~15 requisições por ciclo, em cima das centenas que a busca já faz, e
# sem isso o eixo de afinidade não teria o que ler no momento em que o
# score é calculado. O valor bate com Job.site.
#
# LinkedIn ficou de fora: a página da vaga lá exige sessão e tem anti-bot
# agressivo — encareceria o ciclo e arriscaria bloqueio da fonte que mais
# rende. Vaga de lá fica sem afinidade, o que é limitação conhecida do
# eixo, não julgamento sobre a vaga.
FONTES_COM_DESCRICAO = {"Gupy", "Solides"}

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "jobs.db")