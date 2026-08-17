
# Config do programa internacional (busca vaga remota fora do Brasil em
# INGLÊS ou PORTUGUÊS — os idiomas que o usuário fala; o perfil nasceu
# mirando também espanhol e foi reduzido quando ficou claro que ele não
# fala a língua). Separado do config.py de propósito —
# ver decisão registrada na conversa: misturar ia forçar o filtro de cidade
# do Nordeste e as keywords em português do JobRadar original a servir dois
# propósitos diferentes ao mesmo tempo, deixando os dois mais frágeis.
#
# Credenciais do Telegram e caminho do banco são os MESMOS do projeto
# principal (reaproveita o bot já configurado, e o dedup por link no mesmo
# jobs.db não tem risco de colisão — o id é hash do link, e vaga
# internacional nunca vai ter o mesmo link de uma vaga brasileira).
from config import (  # noqa: F401
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    DB_PATH,
    CIDADES_EUROPA_IBERICA,
    IDIOMAS_NAO_FALADOS,
)

# Cargo em inglês e português — os dois idiomas em que o anúncio pode vir e
# que o usuário lê.
#
# Escopo virou PRODUTO junto com o perfil BR (ver cabeçalho do config.py):
# eram cargos de Dados/BI (Data Analyst, BI Analyst, Analista de Datos...).
# Trainee NÃO entra aqui de propósito — programa de trainee é ritual de
# empresa grande do mercado local, não existe como vaga remota contratando
# estrangeiro; buscar isso lá fora só gastaria sessão de busca.
#
# O eixo de Data Annotation / AI Evaluator (Data Annotator, AI Trainer,
# Search Quality Rater...) SAIU: é trabalho de rotular dado pra treinar IA,
# nicho remoto que paga em dólar mas que não constrói carreira de produto —
# fora do escopo pedido. Fácil de recolocar (é só voltar os 6 títulos e os
# termos de busca correspondentes) se a prioridade mudar pra renda remota.
KEYWORDS_INTL = [
    "Product Owner",
    "Associate Product Manager",
    "Product Analyst",
    "Product Operations",
    # Nomenclatura em português (a espanhola saiu junto com o resto do eixo
    # hispanofalante — ver TERMOS_EXCLUIDOS_INTL).
    "Dono do Produto",
]

# MEDIDO contra as 1.168 vagas do jobs.db real: "Business Analyst" como
# cargo FORTE (era assim quando o perfil buscava dados/BI) sozinho respondia
# por ~60 das ~79 aprovações do perfil internacional — e o que entrava era
# BA de ERP/Salesforce/SWIFT/Finance & Risk em Lisboa, Madrid, Querétaro:
# cargo homônimo de outra especialidade, nada de produto. Passou pro eixo
# AMBÍGUO (mesma regra do perfil BR): só conta com qualificador de domínio
# junto no título.
#
# Esse perfil não tinha eixo ambíguo nenhum até aqui (keywords_ambiguo=[] em
# perfis.py) — a simplicidade fazia sentido enquanto todo cargo da lista era
# inequívoco; "Business Analyst" nunca foi.
KEYWORDS_AMBIGUO_INTL = [
    # Mesma correção do perfil BR (ver o MEDIDO em KEYWORDS_CARGO_AMBIGUO
    # no config.py): "Product Manager" em indústria/varejo/farma é gerente
    # de categoria, não produto digital — e boa parte do ruído medido veio
    # justamente de Espanha, Portugal e Chile, que é onde ESTE perfil
    # busca. Manter forte aqui só mudaria o canal por onde o mesmo lixo
    # chega.
    "Product Manager",
    "Gerente de Produto",
    "Analista de Produto",
    "Analista de Produtos",
    "Business Analyst",
    "Analista de Negócios",
    "Project Manager",
    "Program Manager",
]

# Mesmo papel do QUALIFICADORES_DOMINIO do config.py, em versão multilíngue:
# confirma que o cargo ambíguo é de produto/tech.
QUALIFICADORES_DOMINIO_INTL = [
    # "product"/"producto"/"produto" fora pelo mesmo motivo do config.py:
    # a palavra está dentro do próprio cargo ambíguo agora, então ela se
    # autoqualificaria e o par nunca rejeitaria nada.
    "digital",
    "saas",
    "platform",
    "plataforma",
    "startup",
    "e-commerce",
    "ecommerce",
    "fintech",
    "marketplace",
    "agile",
    "scrum",
]

# Termos de busca: cargo + sinal de idioma (português/espanhol/bilíngue) ou
# +sinal de mercado (LATAM, Spanish Market). Não faz sentido buscar só
# "data analyst" sozinho aqui — isso é o mundo inteiro sem filtro nenhum de
# idioma, a maioria fora do nosso alcance.
TERMOS_BUSCA_INTL = [
    "product owner portuguese speaker",
    "product manager portuguese speaker",
    "bilingual product owner portuguese",
    "english speaking product owner",
    "remote product owner latam",
    "remote product manager latam",
    "remote product manager latin america",
    "product owner brazil remote",
    "product manager brazil remote",
    "associate product manager remote",
    "junior product manager remote",
    "product owner remoto",
    # MEDIDO ao vivo: vaga real ("Business Analyst (Colombia) - Remote",
    # Connect Tech+Talent) aparece em location=Colombia&f_WT=2 pro termo
    # bare "business analyst" — testei "spanish speaker", "business
    # intelligence spanish speaker", "remote data analyst latin america" e
    # "latam" contra a mesma vaga, location e filtro remoto: nenhum achou
    # (o anúncio não repete nenhuma dessas frases). O comentário original
    # lá em cima ("não faz sentido buscar só o cargo sozinho, é o mundo
    # inteiro sem idioma") não vale AQUI: todo termo desta lista já roda
    # escopado por país (LOCATIONS_INTL) + remoto (f_WT=2) — nunca é busca
    # global. E o filtro de idioma pós-busca (RegrasFiltro.idiomas_exigidos)
    # só entra em jogo quando a vaga NÃO declara mercado nenhum no texto —
    # quando o local já é um país aceito (ex: Colômbia), o PAÍS é o sinal,
    # dispensa achar "spanish"/"portuguese" no título (mesma regra que já
    # vale pro resto do filtro, ver job.py). Termo de cargo puro, escopado
    # por país aceito, é seguro e fecha o vazamento: KEYWORDS_INTL aprova o
    # cargo, mas ele nunca era BUSCADO sozinho — só entrava por acidente,
    # dentro de uma frase combinada. ("data analyst"/"business intelligence"
    # saíram junto com a virada de escopo; "business analyst" fica, é o
    # cargo adjacente que sobrou.)
    "business analyst",
    "product owner",
    "product manager",
    # Termos "soltos" (idioma/mercado sem cargo emparelhado na própria
    # busca) — diferente dos de cima, que sempre combinam cargo+idioma numa
    # frase só. MEDIDO: zero ocorrência de "Spanish"/"Español"/"LATAM" como
    # termo próprio no projeto — toda vaga que anuncia a vaga com o idioma
    # em destaque ("Spanish Speaker — Product Role", "LATAM Remote Team") e
    # não bate exatamente numa das frases combinadas acima ficava invisível
    # pra busca. Não é o mesmo risco do comentário lá em cima (buscar só o
    # cargo sozinho, sem NENHUM filtro de idioma) — aqui é o oposto, idioma
    # sem cargo na busca, e o cargo continua sendo exigido depois por
    # KEYWORDS_INTL antes de qualquer notificação.
    #
    # Os termos em espanhol ("spanish speaker", "spanish market"...) saíram:
    # o usuário fala português e inglês, e buscar por espanhol era pedir
    # exatamente a vaga que ele não pode aceitar. "latam" fica — a região
    # inclui o Brasil e boa parte das vagas remotas de lá é em inglês.
    "portuguese speaker",
    "portuguese speaking",
    "latam",
]

# MEDIDO: filtro de cargo (KEYWORDS_INTL) nunca checou idioma — a exigência
# de espanhol/português vivia só nos TERMOS de busca acima, que casam
# contra o anúncio inteiro (LinkedIn/Indeed indexam a descrição toda, não
# só o título) e nunca são reconferidos depois. Resultado: "Senior Data
# Analyst"/"Data Analyst" remoto e sem mercado declarado passava sem
# nenhuma palavra em comum com espanhol/português/LATAM no que a gente
# guarda (título/empresa/local). Usado em Job.combina_com() só quando a
# vaga é remota SEM mercado aceito declarado (ver RegrasFiltro.idiomas_
# exigidos e comentário lá) — quando o escopo já é um país hispanofalante/
# lusófono aceito, o país é o sinal, essa lista nem entra em jogo.
#
# Mesmo vocabulário dos termos soltos acima (spanish/portuguese/latam),
# mais a grafia em espanhol/português — busca casa com anúncio em inglês
# na maioria das vezes, mas o TÍTULO que sobra pode vir em qualquer um dos
# três idiomas.
# O usuário fala português (nativo) e inglês (avançado) — espanhol não.
# Espanhol SAIU desta lista e os termos de busca em espanhol saíram junto
# (ver TERMOS_BUSCA_INTL): vaga que pede espanhol como requisito não serve,
# e ela era a maioria do que este perfil buscava, porque o pipeline nasceu
# mirando mercado hispanofalante.
#
# "english" entra com uma ressalva importante: quase todo anúncio
# internacional é escrito em inglês, então exigir a PALAVRA "english" no
# título não é filtro de idioma de verdade — é sinal de que o anúncio
# destaca o idioma (ex: "English-speaking Product Owner"). Continua valendo
# só pro caso de vaga remota SEM mercado declarado, que é quando não há
# outro sinal nenhum (ver RegrasFiltro.idiomas_exigidos).
IDIOMAS_EXIGIDOS_INTL = [
    "english",
    "portuguese",
    "português",
    "portugues",
    "brazil",
    "brasil",
    "latam",
    "latin america",
    "america latina",
    "lusofono",
    "lusófono",
]

# Vaga cujo TÍTULO exige espanhol é rejeitada mesmo passando em tudo o
# resto. Sem isso, "Product Owner (Spanish Speaker) - Remote LATAM"
# continuaria entrando pelo eixo de mercado (LATAM aceito), já que o gate
# de idioma só olha vaga sem mercado declarado.
# Blocklist do perfil internacional = a lista compartilhada de idiomas que
# o usuário não fala (ver IDIOMAS_NAO_FALADOS em config.py). Era uma lista
# própria só com espanhol; virou referência à lista comum quando ficou
# claro que o problema não era espanhol especificamente, e sim qualquer
# língua fora de português e inglês — francês, alemão, holandês e nórdicas
# aparecem bastante em vaga remota europeia.
TERMOS_EXCLUIDOS_INTL = IDIOMAS_NAO_FALADOS

# Rodízio de termos, mesmo mecanismo do TERMOS_POR_CICLO em config.py (ver
# _proximo_bloco_termos em main.py) — só que com chave de metadados própria
# (sufixo "_internacional"), pra não colidir com o rodízio do perfil BR.
# Esse perfil nunca tinha rodízio antes de virar perfil de verdade (rodava a
# lista de termos INTEIRA todo ciclo, sem custo controlado, e nem chegava a
# rodar de fato — não estava no workflow do GitHub Actions). 27 termos x até
# 6 países/domínios por fonte já é bastante busca; bloco de 10 mantém o
# custo por ciclo parecido com o do perfil BR.
TERMOS_POR_CICLO_INTL = 10

# Mercados pesquisados por rodada de busca no LinkedIn (parâmetro location
# do endpoint). Lista enxuta de propósito — cada país aqui multiplica o
# número de buscas (termos x países), então começa pequeno e dá pra
# expandir depois que confirmar que vale o tempo de execução.
#
# "United States" e "United Kingdom" foram REMOVIDOS de propósito: mesmo com
# os termos de busca pedindo "spanish/portuguese speaker", o location filtra
# geografia, não idioma — a maioria das vagas retornadas pra EUA/Reino Unido
# é vaga comum do mercado local, que pede inglês fluente (causa raiz do
# problema relatado). O escopo agora é só América Latina + países ibéricos
# que falam espanhol/português, que é o que esse pipeline sempre quis cobrir.
#
# "Latin America"/"LATAM"/"EMEA"/"Iberia" NÃO entraram aqui — testei ao
# vivo no endpoint do LinkedIn e nenhum desses nomes de região resolve como
# location de verdade (retorna resultado genérico, sem filtrar nada, ou
# vazio). O endpoint só reconhece país/cidade específico. Por isso os
# países de LATAM entraram nominalmente, e "latam"/"latin america" como
# texto dentro do termo de busca (acima) em vez de location. "Iberia" não
# precisa de entrada própria — já é coberto por Spain + Portugal abaixo.
# Reduzida a Portugal quando o perfil passou a valer só pra vaga em inglês
# ou português: buscar em Spain/Mexico/Colombia/Argentina/Chile é procurar
# vaga do mercado local hispanofalante, que é justamente a que não serve.
# Vaga remota em inglês de qualquer país continua chegando pelo
# WeWorkRemotely (agregador global de vaga remota, ver perfis.py) e pelos
# termos com "latam"/"brazil remote", que não dependem de location.
LOCATIONS_INTL = [
    # Ordem = prioridade declarada pelo usuário: prefere EUA e Inglaterra a
    # Portugal. O LinkedIn busca location por location, então a ordem
    # também decide quem entra primeiro quando o ciclo é interrompido.
    #
    # EUA e Reino Unido tinham sido REMOVIDOS pela autora original porque
    # "a maioria das vagas pede inglês fluente" — o que era problema pra
    # ela e não é pra este usuário (inglês avançado). O que continua
    # valendo é o filtro de MERCADO: vaga "Remote - US only" segue sendo
    # rejeitada, porque morar no Brasil não muda com o idioma. O que entra
    # de lá é vaga globalmente remota ou que aceita LATAM/Brasil
    # explicitamente.
    "United States",
    "United Kingdom",
    "Portugal",
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

# Ver MERCADOS_REMOTO_ACEITOS em config.py e Job.escopo_remoto/
# extrair_escopo_remoto em job.py. Duas listas com propósito DIFERENTE,
# mesma lógica de TERMOS_BUSCA/TERMOS_POR_CICLO vs KEYWORDS: LOCATIONS_INTL
# é ONDE BUSCAR (custo real — cada país multiplica busca × termo, então fica
# enxuto nos mercados que mais contratam); esta lista aqui é O QUE ACEITAR
# (custo zero — só comparação de string), então cobre TODO país
# hispanofalante/lusófono, não só os 6 de LOCATIONS_INTL. Precisa ser
# abrangente porque desde que _mercado_correspondente() virou allowlist
# estrita (ver job.py) — escopo declarado que não bate aqui é REJEITADO,
# mesmo vindo de um país que o projeto quer aceitar, então faltar um país
# aqui vira falso negativo (barra vaga boa), não falso positivo.
#
# NÃO inclui "Brasil" porque esse pipeline é justamente o de vaga remota
# FORA do Brasil (main.py/PERFIL_BR já cobre o Brasil). Vaga "Remote — US
# only"/"Remote — India"/"Remote — Vietnam" segue sendo rejeitada, agora
# inclusive quando o país não está no dicionário de job.py (ver
# MEDIDO em _mercado_correspondente).
MERCADOS_REMOTO_ACEITOS_INTL = [
    # Só mercado onde a vaga é em português ou em inglês. Os países
    # hispanofalantes saíram junto com a virada do perfil pra "inglês ou
    # português" — vaga "Remote - Mexico"/"Remote - Chile" é anúncio do
    # mercado local, em espanhol, que o usuário não fala.
    "Portugal",
    # Lusófonos: mesma língua, e o anúncio vem em português.
    "Angola",
    "Moçambique",
    "Cabo Verde",
    # "LATAM" fica porque é guarda-chuva que inclui o Brasil, e vaga remota
    # anunciada pra região inteira costuma ser de empresa que opera em
    # inglês — diferente de vaga de um país hispanofalante específico.
    "LATAM",
    # EUA e Reino Unido ENTRAM a pedido explícito do usuário, que quer ver
    # essas vagas. Eles estavam fora de propósito: "Remote — US only" é
    # vaga que exige autorização de trabalho local, e morar no Brasil não
    # muda com o idioma. Continuam sendo a aposta mais incerta da lista —
    # boa parte vai ser inalcançável sem visto —, mas quem decide o que
    # vale tentar é ele, não o filtro. Tirar de novo é apagar duas linhas.
    "Estados Unidos",
    "Reino Unido",
]

# Eixo separado pra isso, controlado por ATIVAR_EIXO_IBERICO — dá pra
# desligar sem mexer no resto do pipeline internacional (nem em
# CIDADES_INTL). Quando ativo, vaga presencial/híbrida em Portugal/Espanha
# passa também, mas marcada como "exploratória" na notificação (ver
# main_intl.py), pra distinguir de vaga remota de verdade.
# CIDADES_EUROPA_IBERICA (a lista de cidades) mudou pra config.py — o
# pipeline BR (main.py) passou a ter o mesmo eixo (ver ATIVAR_EIXO_IBERICO_BR
# lá), e as duas listas eram idênticas, então centralizei numa só pra não
# correr risco de uma mudar e a outra ficar pra trás. Esse toggle aqui
# continua LOCAL e independente do ATIVAR_EIXO_IBERICO_BR — são eixos de
# pipelines diferentes, cada um liga/desliga por conta própria.
#
# DESLIGADO: do mercado internacional, só interessa vaga remota — vaga
# presencial/híbrida em Lisboa/Madrid não é o que o usuário quer, mesmo
# achada de propósito via LOCATIONS_INTL. Continua fácil de religar depois
# (só o toggle), sem apagar nada da lista/lógica.
ATIVAR_EIXO_IBERICO = False

# Indeed usa subdomínio por país, não parâmetro de location como o
# LinkedIn. Confirmei ao vivo que es.indeed.com, pt.indeed.com e
# mx.indeed.com funcionam e trazem vaga local de verdade (ex: "Analista de
# Dados" em Lisboa, "Data Analyst" em Barcelona). co/ar/cl seguem o mesmo
# padrão de domínio mas não testei individualmente — se algum não resolver
# como esperado, o scraper só loga 0 vagas pra aquele país, não quebra o
# resto.
#
# "Estados Unidos" (www.indeed.com) e "Reino Unido" (uk.indeed.com) foram
# REMOVIDOS pelo mesmo motivo do LOCATIONS_INTL: domínio de país não filtra
# idioma, e a maioria das vagas desses dois mercados pede inglês fluente —
# era a fonte real das notificações de vaga em inglês.
#
# Mesmo aviso do Indeed BR original: tem proteção anti-bot que pode
# bloquear acesso automatizado (principalmente de IP de nuvem/datacenter),
# mesmo funcionando em teste manual.
DOMINIOS_INDEED_INTL = {
    # Mesma prioridade do LOCATIONS_INTL acima. Domínio de país
    # hispanofalante saiu: devolve vaga do mercado local, em espanhol.
    "Estados Unidos": "www.indeed.com",
    "Reino Unido": "uk.indeed.com",
    "Portugal": "pt.indeed.com",
}
