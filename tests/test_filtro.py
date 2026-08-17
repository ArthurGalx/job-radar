"""Testes automatizados da camada de filtro (job.py) — roda no workflow do
GitHub Actions a cada push (ver .github/workflows/tests.yml).

MEDIDO: seis rodadas seguidas de "corrigir → surgir regressão" durante o
desenvolvimento desta sessão — UF ambígua batendo Estados Unidos em vez de
Brasil, "Porto Alegre" virando Portugal por substring, "Remote - Brazil/
LATAM" perdendo um dos dois mercados declarados, vocabulário de modalidade
("Remoto", "Não informado") virando candidato a país... Cada validação foi
feita manualmente (bash ad-hoc, fora do projeto) e não ficou — o mesmo tipo
de bug podia voltar a qualquer commit futuro sem ninguém notar até aparecer
em produção.

extrair_escopo_remoto() e Job.combina_com() são função pura: não abrem
browser, não tocam rede, não tocam banco — só transformam
(texto, texto) -> resultado. É o tipo de código mais barato de testar que
existe, e é exatamente a camada que mais bugs reais teve neste projeto.

Cada caso abaixo documenta um bug JÁ CORRIGIDO nesta base (não é cenário
hipotético) — o valor esperado foi conferido rodando o código real antes de
virar asserção, não deduzido lendo o comentário.
"""

import pytest

from job import Job, _detectar_senioridade, extrair_escopo_remoto
from perfis import PERFIL_BR, PERFIL_INTL


# ---------------------------------------------------------------------------
# extrair_escopo_remoto(local, modalidade) -> set[str]
# ---------------------------------------------------------------------------

CASOS_ESCOPO = [
    # --- UF ambígua BR x EUA: 6 siglas colidem (AL/MA/MT/MS/PA/SC) — ver
    # _SIGLAS_UF_AMBIGUAS em job.py. Sem desambiguar pela capital, essas 6
    # viravam "Estados Unidos" e a vaga brasileira era barrada.
    ("uf-ambigua-al-maceio", "Remoto (Maceió, AL)", "", {"Brasil"}),
    ("uf-ambigua-ma-sao-luis", "Remoto (São Luís, MA)", "", {"Brasil"}),
    ("uf-ambigua-mt-cuiaba", "Remoto (Cuiabá, MT)", "", {"Brasil"}),
    ("uf-ambigua-ms-campo-grande", "Remoto (Campo Grande, MS)", "", {"Brasil"}),
    ("uf-ambigua-pa-belem", "Remoto (Belém, PA)", "", {"Brasil"}),
    ("uf-ambigua-sc-florianopolis", "Remoto (Florianópolis, SC)", "", {"Brasil"}),
    # Mesma sigla ambígua, mas SEM capital brasileira reconhecida — tem que
    # continuar resolvendo Estados Unidos (a desambiguação não pode virar
    # "toda sigla de 2 letras é Brasil por padrão").
    ("uf-ambigua-sem-capital-br-continua-eua", "Remote (Anytown, AL)", "", {"Estados Unidos"}),
    # UF que não colide com sigla americana resolve direto, sem precisar
    # olhar a cidade.
    ("uf-nao-ambigua-resolve-direto", "Remoto (Recife, PE)", "", {"Brasil"}),

    # --- "Porto Alegre"/"Santiago do Cacém" virando Portugal/Chile por
    # substring (a chave batia dentro do nome da cidade brasileira/
    # portuguesa maior). Casamento de cidade isolada agora é por IGUALDADE
    # do candidato inteiro, não substring.
    ("porto-alegre-com-uf-nao-vira-portugal", "Remoto (Porto Alegre, RS)", "", {"Brasil"}),
    ("porto-alegre-sem-uf-nao-vira-portugal", "Remoto (Porto Alegre)", "Remoto", {"Brasil"}),
    ("santiago-do-cacem-nao-vira-chile", "Remoto (Santiago do Cacém)", "Remoto", {"santiago do cacem"}),
    # Anti-regressão: "Porto"/"Santiago" SOZINHOS continuam resolvendo pro
    # país de verdade — o fix é sobre substring dentro de nome composto,
    # não sobre desativar o reconhecimento da cidade.
    ("porto-sozinho-continua-portugal", "Remoto (Porto)", "Remoto", {"Portugal"}),
    ("santiago-sozinho-continua-chile", "Remoto (Santiago)", "Remoto", {"Chile"}),

    # --- Multimercado: "Remote - Brazil/LATAM" resolvia só pro primeiro
    # match (Brasil, que o perfil internacional REJEITA de propósito) e
    # perdia o LATAM (que ele aceita) — vaga válida sendo descartada.
    ("multimercado-brazil-barra-latam", "Remote - Brazil/LATAM", "", {"Brasil", "LATAM"}),
    ("multimercado-latam-mais-brazil", "Remote - LATAM + Brazil", "", {"Brasil", "LATAM"}),

    # --- Modalidade virando escopo geográfico falso: sem separador textual
    # ("Remote — ...") mas com `modalidade` confirmando remoto, `local`
    # inteiro virava candidato — incluindo o próprio vocabulário de
    # modalidade ("Remoto") e o placeholder de campo vazio ("Não
    # informado"), que não são nome de país nenhum.
    ("modalidade-remoto-sem-complemento-sem-escopo", "Remoto", "Remoto", set()),
    ("placeholder-nao-informado-sem-escopo", "Não informado", "Remoto", set()),
    ("placeholder-nao-informado-com-remoto-sem-escopo", "Não informado (Remoto)", "Remoto", set()),
    ("home-office-sem-escopo", "Home Office", "Remoto", set()),

    # --- Formato de cidade/região da Ibéria e LATAM comum no LinkedIn:
    # "Greater X", "X, X provincia" (província repete o nome da capital),
    # CEP espanhol na frente, "X Metropolitan Area" — nenhum batia por
    # igualdade exata antes da limpeza de ruído.
    ("greater-buenos-aires", "Greater Buenos Aires", "Remoto", {"Argentina"}),
    ("madrid-provincia-duplicado", "Madrid, Madrid provincia", "Remoto", {"Espanha"}),
    ("cep-espanhol-na-frente", "08015, Barcelona, Barcelona provincia", "Remoto", {"Espanha"}),
    ("medellin-metropolitan-area", "Medellín Metropolitan Area", "Remoto", {"Colômbia"}),

    # --- Sigla de estado mexicano (formato "Cidade, SIGLA" igual ao
    # americano/brasileiro, mas nenhuma sigla mexicana estava cadastrada).
    ("sigla-mexico-nl-monterrey", "Monterrey, N.L.", "Remoto", {"México"}),
    ("sigla-mexico-cdmx", "Cuauhtémoc, CDMX", "Remoto", {"México"}),

    # --- Abrangência dentro do Brasil ("Barueri + 35 cidades") não é nome
    # de país estrangeiro — precisa cair em "sem restrição", não em
    # "escopo desconhecido" (que seria rejeitado pelo motivo errado).
    ("regiao-br-barueri-mais-cidades", "Remoto (Barueri + 35 cidades)", "", set()),

    # --- ANTI-REGRESSÃO CRÍTICA: vaga americana sem sigla de estado, só
    # texto livre ("Greater Seattle Area") tem que continuar caindo em
    # "escopo desconhecido" (não-vazio, rejeitável) — é o vazamento que
    # motivou boa parte do trabalho de escopo nesta sessão. NUNCA deveria
    # virar conjunto vazio (que combina_com() trata como "sem restrição,
    # aceita").
    ("greater-seattle-area-continua-barrada", "Greater Seattle Area", "Remoto", {"seattle"}),

    # --- Sem restrição explícita.
    ("anywhere-sem-restricao", "Remote (Anywhere)", "", set()),
    ("worldwide-sem-restricao", "Remote - Worldwide", "", set()),

    # --- País fora do dicionário fica "escopo desconhecido" (rejeitável),
    # não "sem restrição" — filtro de mercado é allowlist, não blocklist.
    ("pais-nao-mapeado-fica-desconhecido", "Remote - Vietnam", "", {"vietnam"}),

    # --- Formatos básicos por extenso, incluindo país depois da cidade.
    ("us-only-classico", "Remote — US only", "", {"Estados Unidos"}),
    ("brazil-based", "Remote, Brazil based", "", {"Brasil"}),
    ("pais-depois-da-cidade", "Remote - Florida, United States", "", {"Estados Unidos"}),
]


@pytest.mark.parametrize(
    "nome,local,modalidade,esperado",
    CASOS_ESCOPO,
    ids=[c[0] for c in CASOS_ESCOPO],
)
def test_extrair_escopo_remoto(nome, local, modalidade, esperado):
    assert extrair_escopo_remoto(local, modalidade) == esperado


# ---------------------------------------------------------------------------
# Job.combina_com(regras) -> bool — pipeline completo (cargo + cidade/
# modalidade + mercado + idioma), não só a extração de escopo isolada.
# ---------------------------------------------------------------------------

CASOS_COMBINA_COM = [
    # Anti-regressão crítica (mesmo caso do teste de escopo, agora
    # end-to-end): vaga americana sem sigla de estado tem que ser barrada
    # no perfil internacional (que só aceita LATAM/Ibéria).
    ("seattle-barrada-perfil-intl", "Senior Product Manager", "Greater Seattle Area", "Remoto", PERFIL_INTL, False),
    # Remota sem mercado declarado: só passa se o TÍTULO afirmar idioma/
    # região (spanish/portuguese/latam/...) — regra adicionada depois que
    # cargo remoto sem relação nenhuma com o mercado passava só por não ter
    # nada que o rejeitasse.
    # Era "passa" quando o perfil mirava mercado hispanofalante. Virou
    # rejeição: o usuário fala português e inglês, e vaga que pede espanhol
    # no título entra na blocklist (ver TERMOS_EXCLUIDOS_INTL).
    ("spanish-speaking-agora-barrada", "Spanish Speaking Product Owner", "Remote", "Remoto", PERFIL_INTL, False),
    ("portuguese-speaking-sem-mercado-passa", "Portuguese Speaking Product Owner", "Remote", "Remoto", PERFIL_INTL, True),
    ("product-owner-latam-passa", "Product Owner LATAM", "Remote", "Remoto", PERFIL_INTL, True),
    # Era barrada quando o perfil EXIGIA marcador de idioma no título
    # (espanhol/português/LATAM) pra vaga remota sem mercado declarado.
    # Passou a valer o oposto: anúncio internacional é escrito em inglês
    # por padrão e quase nunca repete "english" no título, então exigir o
    # marcador rejeitava justamente a vaga remota global dos EUA e do Reino
    # Unido que o usuário pediu pra priorizar. O controle de idioma virou a
    # blocklist (ver TERMOS_EXCLUIDOS_INTL / IDIOMAS_NAO_FALADOS).
    ("remota-global-sem-mercado-agora-passa", "Senior Product Owner", "Remote", "Remoto", PERFIL_INTL, True),
    # EUA e Reino Unido foram ACEITOS a pedido explícito do usuário — ele
    # quer ver essas vagas, mesmo sabendo que boa parte exige autorização de
    # trabalho local. Este caso era o oposto ("us-only-continua-barrada")
    # até então.
    ("us-only-agora-passa", "Product Owner", "Remote — US only", "Remoto", PERFIL_INTL, True),
    ("uk-passa", "Product Owner", "Remote - United Kingdom", "Remoto", PERFIL_INTL, True),
    # O mercado continua sendo allowlist: país que não está na lista segue
    # barrado, e a blocklist de idioma continua valendo por cima do
    # mercado aceito.
    ("india-continua-barrada", "Product Owner", "Remote - India", "Remoto", PERFIL_INTL, False),
    ("us-only-com-espanhol-barrada", "Product Owner (Spanish Speaker)", "Remote — US only", "Remoto", PERFIL_INTL, False),
    # Mercado CONFIRMADO no texto dispensa o sinal de idioma no título — o
    # país hispanofalante já é o próprio sinal.
    # Portugal e não Espanha: mercado hispanofalante saiu de
    # MERCADOS_REMOTO_ACEITOS_INTL junto com a virada pra inglês/português.
    ("mercado-confirmado-dispensa-idioma-no-titulo", "Senior Product Owner", "Remote - Portugal", "Remoto", PERFIL_INTL, True),
    ("mercado-hispanofalante-agora-barrado", "Senior Product Owner", "Remote - Espanha", "Remoto", PERFIL_INTL, False),

    # Perfil Brasil: cargo e cidade são checados em campos separados
    # (título vs. local) — cidade fora da lista aceita barra mesmo com
    # cargo batendo.
    ("cidade-fora-da-lista-barrada", "Product Owner", "Nova York", "Presencial", PERFIL_BR, False),
    ("cargo-fora-do-escopo-barrado", "Vendedor Externo", "São Paulo, SP", "Presencial", PERFIL_BR, False),
    ("cargo-forte-cidade-aceita-passa", "Product Owner Pleno", "São Paulo, SP", "Presencial", PERFIL_BR, True),
    # Escopo antigo (Dados/BI) não deve mais passar sozinho: o radar virou
    # produto/trainee e "Analista de Dados" deixou de ser cargo forte — o
    # vocabulário de dados sobrou só como QUALIFICADORES_DOMINIO.
    ("cargo-do-escopo-antigo-barrado", "Analista de Dados Pleno", "São Paulo, SP", "Presencial", PERFIL_BR, False),
    # keywords_ambiguo (ex: "Trainee", "Business Analyst") só conta com
    # qualificador de domínio junto no título — sozinho é ruído de outra
    # área (banco, varejo, RH, finanças).
    ("trainee-sem-qualificador-barrado", "Programa Trainee 2026", "São Paulo, SP", "Presencial", PERFIL_BR, False),
    ("trainee-com-qualificador-passa", "Trainee de Tecnologia", "São Paulo, SP", "Presencial", PERFIL_BR, True),
    ("cargo-ambiguo-sem-qualificador-barrado", "Business Analyst", "São Paulo, SP", "Presencial", PERFIL_BR, False),
    ("cargo-ambiguo-com-qualificador-passa", "Business Analyst de Tecnologia", "São Paulo, SP", "Presencial", PERFIL_BR, True),
    # MEDIDO no primeiro ciclo real (285 vagas, 61% eram isto): "Product
    # Manager"/"Gerente de Produto" em indústria e varejo é gerente de
    # categoria, não produto digital. Virou cargo ambíguo — exige marcador
    # de tecnologia no título. "Product Owner" continua forte porque
    # praticamente não existe fora de tech.
    ("pm-de-industria-barrado", "Product Manager - Negócio Café", "São Paulo, SP", "Presencial", PERFIL_BR, False),
    ("gerente-de-produto-varejo-barrado", "Gerente de Produto - Calçados", "São Paulo, SP", "Presencial", PERFIL_BR, False),
    ("pm-com-marcador-tech-passa", "Digital Product Manager", "São Paulo, SP", "Presencial", PERFIL_BR, True),
    ("gerente-de-produto-com-marcador-tech-passa", "Gerente de Produto Digital", "São Paulo, SP", "Presencial", PERFIL_BR, True),
    ("product-owner-continua-forte", "Product Owner", "São Paulo, SP", "Presencial", PERFIL_BR, True),
    # Business Architect: cargo que o usuário já ocupou, aprovado sozinho
    # (não é usado fora de tecnologia/consultoria).
    ("business-architect-passa-sozinho", "Business Architect", "São Paulo, SP", "Presencial", PERFIL_BR, True),
    ("business-architect-com-nivel-passa", "Business Architect Jr", "São Paulo, SP", "Presencial", PERFIL_BR, True),
    ("arquiteto-de-negocios-passa", "Arquiteto de Negócios", "São Paulo, SP", "Presencial", PERFIL_BR, True),
    # "produto" NÃO é qualificador de domínio (se fosse, "Gerente de
    # Produto" se autoqualificaria e o eixo ambíguo nunca rejeitaria nada).
    ("produto-nao-qualifica-cargo-ambiguo", "Business Analyst de Produto", "São Paulo, SP", "Presencial", PERFIL_BR, False),
    # Geografia: perfil BR deixou de aceitar mercado remoto de outro país
    # (94% do primeiro ciclo era isso) — vaga remota de fora é assunto do
    # perfil Internacional.
    ("remoto-chile-barrado-no-perfil-br", "Product Owner", "Remote - Chile", "Remoto", PERFIL_BR, False),
    ("remoto-brasil-passa-no-perfil-br", "Product Owner", "Remote - Brazil", "Remoto", PERFIL_BR, True),
    ("remoto-latam-passa-no-perfil-br", "Product Owner", "Remote - LATAM", "Remoto", PERFIL_BR, True),
    # Blocklist do perfil internacional: o usuário fala português e inglês,
    # não espanhol. Vaga que exige espanhol no título é rejeitada mesmo
    # passando em cargo e mercado — sem isso ela entrava pelo eixo de
    # mercado (LATAM aceito), já que o gate de idioma só olha vaga SEM
    # mercado declarado.
    ("exige-espanhol-barrada", "Product Owner (Spanish Speaker)", "Remote - LATAM", "Remoto", PERFIL_INTL, False),
    # A blocklist cobre TODA língua fora de português e inglês, não só
    # espanhol — francês, alemão, holandês e nórdicas aparecem bastante em
    # vaga remota europeia.
    ("exige-frances-barrada", "Product Owner - French Speaking", "Remote - LATAM", "Remoto", PERFIL_INTL, False),
    ("exige-alemao-barrada", "Product Owner (German C1)", "Remote - LATAM", "Remoto", PERFIL_INTL, False),
    ("exige-holandes-barrada", "Product Owner - Dutch Native", "Remote - LATAM", "Remoto", PERFIL_INTL, False),
    # A blocklist vale no perfil BRASIL também: vaga bilíngue de mercado
    # local existe aqui ("Product Owner - Francês Fluente").
    ("exige-frances-barrada-no-br", "Product Owner - Francês Fluente", "São Paulo, SP", "Presencial", PERFIL_BR, False),
    ("exige-japones-barrada-no-br", "Product Owner (Japonês)", "São Paulo, SP", "Presencial", PERFIL_BR, False),
    # Menção a PAÍS não é exigência de idioma: o match é por borda de
    # palavra, então "german" não bate "Germany".
    ("pais-no-titulo-nao-e-idioma", "Product Owner - Germany Team", "São Paulo, SP", "Presencial", PERFIL_BR, True),
    ("exige-espanhol-em-espanhol-barrada", "Product Owner - Español", "Remote - LATAM", "Remoto", PERFIL_INTL, False),
    ("portugues-continua-passando", "Product Owner - Portuguese Speaker", "Remote - LATAM", "Remoto", PERFIL_INTL, True),
    # MEDIDO ao vivo na Gupy: o card corta o nome da cidade em ~10
    # caracteres ("Santo Andr... - SP"). CIDADES tem as duas grafias por
    # causa disso — nenhuma das duas cobre a outra (borda de palavra).
    ("cidade-truncada-pela-gupy-passa", "Product Owner", "Santo Andr... - SP", "Presencial", PERFIL_BR, True),
    ("cidade-por-extenso-passa", "Product Owner", "São Bernardo do Campo - SP", "Presencial", PERFIL_BR, True),
    ("outro-estado-truncado-barrado", "Product Owner", "Rio de Jan... - RJ", "Presencial", PERFIL_BR, False),
    # Ferramenta/método no título só aprova com palavra de cargo junto —
    # espelho da regra de cargo ambíguo (ver FERRAMENTAS_TITULO).
    ("ferramenta-sem-cargo-barrada", "Desenvolvedor Java (time Scrum)", "São Paulo, SP", "Presencial", PERFIL_BR, False),
    ("ferramenta-com-cargo-passa", "Analista Scrum", "São Paulo, SP", "Presencial", PERFIL_BR, True),
]


@pytest.mark.parametrize(
    "nome,titulo,local,modalidade,perfil,esperado",
    CASOS_COMBINA_COM,
    ids=[c[0] for c in CASOS_COMBINA_COM],
)
def test_combina_com(nome, titulo, local, modalidade, perfil, esperado):
    job = Job(
        titulo=titulo, empresa="Teste", local=local, link=f"https://teste.invalido/{nome}",
        site="Teste", modalidade=modalidade,
    )
    assert job.combina_com(perfil.regras) == esperado


# ---------------------------------------------------------------------------
# _detectar_senioridade -- "manager"/"gerente" dentro do NOME do cargo não é
# liderança. MEDIDO no primeiro ciclo do escopo de produto: "APM (Associate
# Product Manager)" classificava "Liderança" e levava -2 no score, quando o
# anúncio não disse nada sobre nível.
# ---------------------------------------------------------------------------

CASOS_SENIORIDADE = [
    ("apm-sem-nivel-nao-e-lideranca", "APM (Associate Product Manager)", "Não especificado"),
    ("growth-pm-sem-nivel-nao-e-lideranca", "Growth Product Manager", "Não especificado"),
    ("product-owner-sem-nivel", "Product Owner", "Não especificado"),
    # Nível explícito continua ganhando do nome do cargo.
    ("pm-junior", "Product Manager Junior", "Júnior"),
    ("gerente-de-produto-jr", "Gerente de Produto Jr", "Júnior"),
    ("apm-pleno", "Associate Product Manager Pleno", "Pleno"),
    ("pm-senior", "Product Manager Sênior", "Sênior"),
    # Liderança de verdade não pode ser afetada pela limpeza do nome do
    # cargo: aqui "gerente"/"head"/"coordenador" é chefia mesmo.
    ("gerente-de-vendas-e-lideranca", "Gerente de Vendas", "Liderança"),
    ("head-de-produto-e-lideranca", "Head de Produto", "Liderança"),
    ("coordenador-de-produto-e-lideranca", "Coordenador de Produto", "Liderança"),
    # Trainee e Estágio viraram níveis separados (só trainee é alvo).
    ("trainee-e-nivel-proprio", "Trainee de Tecnologia", "Trainee"),
    ("estagio-e-nivel-proprio", "Estágio em Produto Digital", "Estágio"),
]


@pytest.mark.parametrize(
    "nome,titulo,esperado",
    CASOS_SENIORIDADE,
    ids=[c[0] for c in CASOS_SENIORIDADE],
)
def test_detectar_senioridade(nome, titulo, esperado):
    assert _detectar_senioridade(titulo) == esperado


# ---------------------------------------------------------------------------
# Job.publicacao_antiga -- meses/anos = True, dias/semanas/vazio/absoluto
# sem ano = False. Ver MEDIDO na property (job.py): vaga real da Sólides
# ("há 7 meses") no jobs.db motivou o campo.
# ---------------------------------------------------------------------------

CASOS_PUBLICACAO_ANTIGA = [
    # Caso real, capturado no jobs.db em produção (Solides, "ANALISTA DE
    # DADOS / MIGRAÇÃO - PLENO") -- o caso que motivou o campo.
    ("caso-real-solides-7-meses", "há 7 meses", True),
    ("mes-singular", "há 1 mês", True),
    ("anos-plural", "há 2 anos", True),
    ("ano-singular", "há 1 ano", True),
    # Dias/semanas continuam "fresca" -- só mês/ano é sinal inequívoco.
    ("dias-nao-e-antiga", "há 3 dias", False),
    ("semanas-nao-e-antiga", "há 2 semanas", False),
    ("hoje-nao-e-antiga", "hoje", False),
    ("ontem-nao-e-antiga", "ontem", False),
    # Sem dado nenhum (fonte não expõe) -- não dá pra afirmar "antiga" por
    # ausência de informação.
    ("vazio-nao-e-antiga", "", False),
    # Formato absoluto SEM ano -- não dá pra calcular idade sem saber o
    # ano, então fica False de propósito (não arrisca adivinhar).
    ("absoluto-sem-ano-nao-e-antiga", "Publicada em 11/08", False),
]


@pytest.mark.parametrize(
    "nome,publicado_em,esperado",
    CASOS_PUBLICACAO_ANTIGA,
    ids=[c[0] for c in CASOS_PUBLICACAO_ANTIGA],
)
def test_publicacao_antiga(nome, publicado_em, esperado):
    job = Job(
        titulo="Product Owner", empresa="Teste", local="São Paulo, SP",
        link=f"https://teste.invalido/{nome}", site="Teste", modalidade="Presencial",
        publicado_em=publicado_em,
    )
    assert job.publicacao_antiga == esperado


# ---------------------------------------------------------------------------
# Afinidade e barreira (job.py) — os dois eixos que leem a DESCRIÇÃO.
#
# MEDIDO nas 10 vagas reais que o usuário mandou analisar: ágil, backlog e
# comunicação com stakeholders aparecem em 8-10 delas, então não separam
# nada; o que separa é integração/API, automação, IA, dados próprios,
# discovery e métrica de experiência. Antes destes eixos, quase toda vaga
# aprovada empatava em 6 e o 10 era inalcançável.
# ---------------------------------------------------------------------------

def _vaga_com_descricao(descricao: str) -> Job:
    job = Job(
        titulo="Product Owner Pleno", empresa="Teste", local="São Paulo - SP",
        link="https://teste.invalido/afinidade", site="Gupy", modalidade="Híbrido",
    )
    job.descricao = descricao
    job.distancia_km = 5.0
    return job


def test_afinidade_conta_grupos_distintos():
    pontos, grupos = _vaga_com_descricao(
        "Buscamos alguém com experiência em APIs e integrações, "
        "automação de processos e análise em Power BI."
    ).afinidade()
    assert pontos == 3
    assert set(grupos) == {"integracao", "automacao", "dados"}


def test_afinidade_tem_teto():
    """Vaga que cita tudo não pode estourar a escala."""
    pontos, grupos = _vaga_com_descricao(
        "IA generativa, automação, APIs, SQL, discovery e NPS."
    ).afinidade()
    assert len(grupos) > 3
    assert pontos == 3


def test_agil_e_backlog_nao_contam_como_afinidade():
    """Aparecem em 9 de 10 vagas — pontuar isso é o que achatava tudo em 6."""
    pontos, grupos = _vaga_com_descricao(
        "Scrum, Kanban, gestão de backlog, histórias de usuário e critérios de aceite."
    ).afinidade()
    assert pontos == 0 and grupos == []


def test_sem_descricao_afinidade_zero():
    """Fonte que não expõe descrição (LinkedIn) não é penalizada — só não
    ganha o bônus, o que é limitação do eixo, não julgamento da vaga."""
    job = Job(titulo="Product Owner", empresa="T", local="São Paulo - SP",
              link="https://teste.invalido/sem", site="LinkedIn", modalidade="Híbrido")
    assert job.afinidade() == (0, [])


def test_barreira_anos_altos():
    pontos, motivos = _vaga_com_descricao("Exigimos 5 anos de experiência como PO.").barreira()
    assert pontos == -2 and motivos == ["pede 5+ anos"]


def test_barreira_ignora_anos_dentro_do_alcance():
    """2 a 4 anos é a faixa que ele consegue disputar — não desconta."""
    pontos, motivos = _vaga_com_descricao("De 2 a 3 anos de experiência.").barreira()
    assert pontos == 0 and motivos == []


def test_barreira_certificacao():
    pontos, motivos = _vaga_com_descricao("Diferencial: certificação PSPO I.").barreira()
    assert pontos == -1 and motivos == ["pede certificação"]


def test_safe_nao_conta_como_certificacao():
    """MEDIDO na vaga real da Gauge: "Metodologias Ágeis (Scrum, Kanban,
    SAFe, Lean)" é menção a framework, não exigência de certificado."""
    pontos, _ = _vaga_com_descricao("Metodologias Ágeis (Scrum, Kanban, SAFe, Lean).").barreira()
    assert pontos == 0


def test_score_chega_a_dez():
    """O teto virou alcançável: cargo forte 3 + pleno 2 + local 2 + afinidade 3."""
    vaga = _vaga_com_descricao("Integrações via API, automação de processos e dashboards em Looker.")
    assert vaga.pontuar_relevancia(PERFIL_BR.regras) == 10


def test_score_nunca_negativo():
    vaga = _vaga_com_descricao("Exigimos 8 anos de experiência e certificação PSPO.")
    vaga.titulo = "Product Owner Sênior"
    vaga.distancia_km = 40.0
    assert vaga.pontuar_relevancia(PERFIL_BR.regras) == 0
