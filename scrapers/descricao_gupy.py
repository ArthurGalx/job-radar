"""Busca a descrição completa de uma vaga da Gupy.

Serve pra UM caso específico: vaga que passou do LIMIAR_CARTA (ver
config.py) vira candidata a carta de apresentação escrita à mão, e pra
escrever isso é preciso o texto do anúncio — não só título, empresa e
local, que é tudo que o card de busca expõe e tudo que o resto do pipeline
guarda.

Por que não faz parte do GupyScraper: aquele scraper varre LISTA de
resultado com Playwright (a busca é renderizada no cliente), e roda pra
dezenas de vagas por termo. Aqui é o oposto — uma vaga por vez, só as
poucas que passaram do limiar, e a página individual não precisa de
navegador nenhum: o Next.js da Gupy embute os dados num JSON dentro do
próprio HTML (`__NEXT_DATA__`), então um GET simples resolve. Abrir um
Chromium pra isso custaria segundos e memória à toa.

MEDIDO na vaga real "Product Owner Pleno - Be.Aliant": os três campos que
interessam vêm separados no JSON — description (552 chars, sobre a
empresa), responsibilities (998) e prerequisites (1189, os requisitos). O
HTML de dentro deles é de editor de texto rico (<p>, <ul>, <li>, <br>),
por isso a limpeza de tag abaixo.
"""

import html
import json
import re

import requests

from logger import get_logger

logger = get_logger()

_PADRAO_NEXT_DATA = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.DOTALL,
)

# Quebra de linha antes de fechar bloco/item de lista, pra o texto não virar
# um parágrafo só quando as tags saírem.
_PADRAO_QUEBRA = re.compile(r"</(?:p|div|li|h[1-6])>|<br\s*/?>", re.IGNORECASE)
_PADRAO_TAG = re.compile(r"<[^>]+>")
_PADRAO_LINHAS_VAZIAS = re.compile(r"\n{3,}")

_TIMEOUT = 20
_CABECALHOS = {"User-Agent": "Mozilla/5.0 (compatible; JobRadar/1.0)"}

# link -> dados crus da vaga. Ver _buscar_dados.
_CACHE_DADOS: dict[str, dict] = {}

# Limite de caracteres do texto final. Célula de planilha aguenta muito
# mais, mas descrição inteira de vaga grande vira parede de texto na
# planilha sem ganho — o que importa pra escrever a carta são requisitos e
# responsabilidades, que vêm primeiro na ordem montada abaixo.
MAX_CARACTERES = 6000


def _limpar_html(trecho: str) -> str:
    if not trecho:
        return ""
    texto = _PADRAO_QUEBRA.sub("\n", trecho)
    texto = _PADRAO_TAG.sub("", texto)
    texto = html.unescape(texto)
    linhas = [linha.strip() for linha in texto.splitlines()]
    return _PADRAO_LINHAS_VAZIAS.sub("\n\n", "\n".join(linhas)).strip()


def montar_texto(dados_vaga: dict) -> str:
    """Junta os campos da vaga num texto só, com rótulo. Função pura, e a
    parte que os testes cobrem — a chamada de rede em volta não tem regra
    nenhuma que valha testar.

    Ordem: requisitos e responsabilidades primeiro (é o que decide o que
    escrever na carta), descrição institucional por último.
    """
    secoes = [
        ("REQUISITOS", _limpar_html(dados_vaga.get("prerequisites", ""))),
        ("RESPONSABILIDADES", _limpar_html(dados_vaga.get("responsibilities", ""))),
        ("SOBRE A VAGA/EMPRESA", _limpar_html(dados_vaga.get("description", ""))),
    ]
    texto = "\n\n".join(f"{rotulo}:\n{corpo}" for rotulo, corpo in secoes if corpo)
    return texto[:MAX_CARACTERES]


def _buscar_dados(link: str) -> dict:
    """Baixa a vaga e devolve o dicionário cru do __NEXT_DATA__, ou {}.

    Cache em memória por link porque o mesmo anúncio é consultado duas vezes
    no mesmo ciclo, por motivos diferentes: o endereço (pra medir distância,
    ANTES do score — ver utils/geo.py) e a descrição (pra carta, DEPOIS do
    score). Sem cache seriam dois GETs por vaga. O cache é do processo, e
    cada execução do workflow é um processo novo, então não há risco de
    servir anúncio velho entre ciclos.
    """
    if link in _CACHE_DADOS:
        return _CACHE_DADOS[link]

    dados_vaga: dict = {}
    try:
        resposta = requests.get(link, timeout=_TIMEOUT, headers=_CABECALHOS)
        resposta.raise_for_status()
        m = _PADRAO_NEXT_DATA.search(resposta.text)
        if not m:
            logger.warning("Página da vaga sem __NEXT_DATA__ — layout da Gupy pode ter mudado.")
        else:
            dados_vaga = json.loads(m.group(1))["props"]["pageProps"]["job"]
    except requests.RequestException as e:
        logger.warning(f"Não consegui buscar a vaga na Gupy: {type(e).__name__}")
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning("__NEXT_DATA__ da Gupy sem o campo job no formato esperado.")

    _CACHE_DADOS[link] = dados_vaga
    return dados_vaga


def buscar_endereco(link: str) -> str:
    """Endereço completo da vaga ("Avenida das Nações Unidas, 14261, São
    Paulo, São Paulo, Brasil, 04795-100"), ou "" se a fonte não expõe.

    É o CEP no fim dessa string que permite situar a vaga dentro da cidade
    — sem ele, "São Paulo - SP" pode ser tanto a 2 km quanto a 25 km de
    casa (ver utils/geo.py).
    """
    return _buscar_dados(link).get("addressLine", "") or ""


def buscar_descricao(link: str) -> str:
    """Devolve o texto do anúncio, ou "" em qualquer falha.

    Best-effort igual ao export pra planilha: isso roda DEPOIS da vaga já
    ter sido notificada e salva, e não pode derrubar o ciclo. Sem
    descrição, a linha da planilha só fica sem esse campo.
    """
    return montar_texto(_buscar_dados(link))
