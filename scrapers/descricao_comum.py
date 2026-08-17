"""Peças compartilhadas por quem busca a descrição completa de uma vaga.

Gupy e Sólides são sites diferentes mas resolvem o mesmo problema do mesmo
jeito: são aplicações Next.js que embutem os dados da página num JSON
(`__NEXT_DATA__`) dentro do próprio HTML. Isso é o que permite buscar
descrição com um GET simples, sem abrir navegador — o scraper de LISTA
precisa de Playwright (a busca é renderizada no cliente), a página
individual não.

O que muda entre as duas é só ONDE o texto está dentro do JSON, e isso vive
no módulo de cada fonte.
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
# mais, mas descrição inteira de vaga grande vira parede de texto sem ganho
# — o que importa são requisitos e responsabilidades, que vêm primeiro.
MAX_CARACTERES = 6000

# link -> dados crus da vaga. O mesmo anúncio é consultado mais de uma vez
# no mesmo ciclo, por motivos diferentes: descrição (pra pontuar afinidade,
# ANTES do score), endereço (pra medir distância, também antes) e o texto
# que vai pra planilha (depois). Sem cache seriam três GETs por vaga. O
# cache é do processo, e cada execução do workflow é um processo novo —
# não há risco de servir anúncio velho entre ciclos.
_CACHE: dict[str, dict] = {}


def limpar_html(trecho: str) -> str:
    """Texto de editor de texto rico (<p>, <ul>, <li>, <br>) vira texto
    puro, preservando as quebras de linha que separam item de lista."""
    if not trecho:
        return ""
    texto = _PADRAO_QUEBRA.sub("\n", trecho)
    texto = _PADRAO_TAG.sub("", texto)
    texto = html.unescape(texto)
    linhas = [linha.strip() for linha in texto.splitlines()]
    return _PADRAO_LINHAS_VAZIAS.sub("\n\n", "\n".join(linhas)).strip()


def buscar_next_data(link: str, caminho: tuple[str, ...]) -> dict:
    """Baixa a página e devolve o pedaço do __NEXT_DATA__ indicado por
    `caminho` (ex: ("props", "pageProps", "job")), ou {} em qualquer falha.

    Best-effort de propósito: quem chama roda dentro do ciclo de busca e
    não pode quebrar porque um anúncio saiu do ar ou o layout mudou.
    """
    if link in _CACHE:
        return _CACHE[link]

    dados: dict = {}
    try:
        resposta = requests.get(link, timeout=_TIMEOUT, headers=_CABECALHOS)
        resposta.raise_for_status()
        m = _PADRAO_NEXT_DATA.search(resposta.text)
        if not m:
            logger.warning("Página da vaga sem __NEXT_DATA__ — layout do site pode ter mudado.")
        else:
            no = json.loads(m.group(1))
            for chave in caminho:
                no = no[chave]
            dados = no
    except requests.RequestException as e:
        logger.warning(f"Não consegui buscar a página da vaga: {type(e).__name__}")
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning("__NEXT_DATA__ sem os campos esperados — layout do site pode ter mudado.")

    _CACHE[link] = dados
    return dados
