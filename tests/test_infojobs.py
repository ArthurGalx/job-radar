"""Testes do parser do InfoJobs (scrapers/infojobs.py).

O HTML abaixo é uma redução do card REAL, preservando as duas armadilhas
que quebraram o parser na primeira versão:

1. o selo de "empresa verificada" guarda um bloco de HTML INTEIRO dentro
   de um atributo (data-bs-title="<div class='text-left'>...</a>.</div>"),
   e os `</a>`/`</div>` de dentro do atributo são encontrados antes dos de
   verdade — o parser pegava "AmorSaúde Este selo" como nome da empresa,
   ou não casava nada;
2. os metadados (modalidade, experiência) não têm classe própria: são
   identificados pelo ÍCONE que vem antes deles.
"""

from scrapers.infojobs import InfoJobsScraper

CARD = '''
<div id="vacancy11910817" data-id="11910817" data-href="/vaga-de-product-owner-pleno__11910817.aspx">
  <div hidden class="js_date" data-value="2026/08/13 09:30:00"></div>
  <a href="/vaga-de-product-owner-pleno__11910817.aspx">
    <h2 class="h3 js_vacancyTitle"> Product Owner Pleno </h2>
  </a>
  <div class="text-body">
    <a class="text-body" href="https://www.infojobs.com.br/empresa-teste__-939744.aspx">
      EMPRESA <span class="text-nowrap"> TESTE
        <span onclick="event.stopPropagation();" data-bs-toggle="tooltip"
              data-bs-title="<div class='text-left'>Este selo indica que a empresa foi verificada.
              <a href='https://blog.infojobs.com.br/x/'>Saiba o que isso significa</a>.</div>">
          <svg class="icon icon-verified"><use xlink:href="#verified" /></svg>
        </span>
      </span>
    </a>
  </div>
  <div class="mb-8"> São Paulo - SP<span hidden class="js_divUserVagaDistance">,
    <span class="js_UserVagaDistance" data-vagalatitude="-23.5777299" data-vagalongitude="-46.5768518">0</span> Km de você.</span>
  </div>
  <div class="d-inline-flex">
    <div><svg class="icon icon-money"><use xlink:href="#money" /></svg> A combinar </div>
    <div><svg class="icon icon-suitcase"><use xlink:href="#suitcase" /></svg> Entre 5 e 10 anos </div>
    <div><svg class="icon icon-house-and-building"><use xlink:href="#house-and-building" /></svg> H&#xED;brido </div>
  </div>
  <div class="text-medium"> Sobre a vaga: Buscamos PO com discovery e APIs.</div>
</div>
'''


def _vaga():
    scraper = InfoJobsScraper(termos_busca=[])
    return scraper._montar_vaga(CARD)


def test_extrai_titulo_e_link():
    vaga = _vaga()
    assert vaga.titulo == "Product Owner Pleno"
    assert vaga.link == "https://www.infojobs.com.br/vaga-de-product-owner-pleno__11910817.aspx"
    assert vaga.site == "InfoJobs"


def test_empresa_nao_engole_o_texto_do_selo():
    """A armadilha nº 1: sem limpar o atributo, saía "EMPRESA TESTE Este
    selo indica que a empresa foi verificada"."""
    assert _vaga().empresa == "EMPRESA TESTE"


def test_local_sem_o_texto_de_distancia():
    assert _vaga().local == "São Paulo - SP"


def test_coordenadas_da_vaga():
    """É o dado mais valioso do card: distância exata, sem estimar por CEP
    ou centro de cidade."""
    lat, lon = _vaga().coordenadas
    assert round(lat, 3) == -23.578 and round(lon, 3) == -46.577


def test_modalidade_pelo_icone():
    assert _vaga().modalidade == "Híbrido"


def test_descricao_junta_experiencia_e_resumo():
    """A faixa de experiência alimenta o eixo de barreira e o resumo o de
    afinidade — por isso os dois vão pro mesmo campo."""
    descricao = _vaga().descricao
    assert "Entre 5 e 10 anos" in descricao
    assert "discovery e APIs" in descricao


def test_data_de_publicacao():
    assert _vaga().publicado_em == "2026/08/13"


def test_card_sem_titulo_e_descartado():
    assert InfoJobsScraper(termos_busca=[])._montar_vaga('<div id="vacancy1"></div>') is None


def test_cards_sao_fatiados_por_vaga():
    """Sem fatiar, o título de uma vaga casaria com a empresa da seguinte."""
    pagina = CARD + CARD.replace("11910817", "22222222")
    assert len(InfoJobsScraper._cards(pagina)) == 2
