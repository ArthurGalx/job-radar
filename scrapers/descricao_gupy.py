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


def buscar_descricao(link: str) -> str:
    """Devolve o texto do anúncio, ou "" em qualquer falha.

    Best-effort igual ao export pra planilha: isso roda DEPOIS da vaga já
    ter sido notificada e salva, e não pode derrubar o ciclo. Sem
    descrição, a linha da planilha só fica sem esse campo.
    """
    try:
        resposta = requests.get(link, timeout=_TIMEOUT, headers=_CABECALHOS)
        resposta.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"Não consegui buscar a descrição da vaga: {type(e).__name__}")
        return ""

    m = _PADRAO_NEXT_DATA.search(resposta.text)
    if not m:
        logger.warning("Página da vaga sem __NEXT_DATA__ — layout da Gupy pode ter mudado.")
        return ""

    try:
        dados = json.loads(m.group(1))
        vaga = dados["props"]["pageProps"]["job"]
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning("__NEXT_DATA__ da Gupy sem o campo job no formato esperado.")
        return ""

    return montar_texto(vaga)
