"""Vagas do InfoJobs Brasil.

Portal generalista grande, renderizado no SERVIDOR — diferente da Gupy e
da Sólides, cuja LISTA exige navegador. Aqui um GET devolve o HTML já com
os cards, então esta fonte custa uma requisição por termo de busca, sem
Playwright.

O card do InfoJobs é o mais rico do projeto: além de título, empresa e
local, ele traz LATITUDE E LONGITUDE da vaga, a modalidade, a faixa de
experiência exigida e um resumo do anúncio. Isso alimenta três eixos do
score de uma vez só, sem abrir a página da vaga:

- as coordenadas dão distância EXATA (ver utils/geo.py), em vez da
  estimativa por CEP ou por centro de cidade que as outras fontes obrigam;
- "Entre 5 e 10 anos" entra no eixo de barreira (ver job.barreira);
- o resumo alimenta o eixo de afinidade.

O resumo é TRUNCADO pelo site (o texto completo só existe na página da
vaga). É o suficiente pros eixos, e evita uma segunda requisição por vaga
— mas é o motivo de a afinidade de uma vaga do InfoJobs tender a ser
menor que a de uma vaga do ATS, onde o texto vem inteiro.
"""

import html
import re
from urllib.parse import quote_plus

import requests

from job import Job
from logger import get_logger
from scrapers.base import BaseScraper

logger = get_logger()

_BASE = "https://www.infojobs.com.br"
_TIMEOUT = 25
_CABECALHOS = {"User-Agent": "Mozilla/5.0 (compatible; JobRadar/1.0)"}

# Cada card começa aqui — é o separador mais estável do HTML (o id vem do
# número da vaga, e o atributo existe em todos).
_PADRAO_CARD = re.compile(r'<div id="vacancy(\d+)"', re.IGNORECASE)

_PADRAO_LINK = re.compile(r'data-href="([^"]+)"')
_PADRAO_TITULO = re.compile(r'js_vacancyTitle[^>]*>(.*?)</h2>', re.DOTALL)
_PADRAO_EMPRESA = re.compile(r'<div class="text-body">(.*?)</div>', re.DOTALL)

# MEDIDO no HTML real: o selo de empresa verificada guarda um bloco de
# HTML INTEIRO dentro de um atributo (data-bs-title="<div class='text-
# left'>Este selo indica...</a>.</div>"). Isso quebra qualquer regex de
# tag: o `</a>` e o `</div>` de dentro do atributo são encontrados antes
# dos de verdade, e o parser ou pega o texto errado ("AmorSaúde Este
# selo") ou não casa nada (aconteceram os dois). Como o HTML de dentro do
# atributo usa aspas SIMPLES, dá pra remover o atributo inteiro com
# segurança casando pelas aspas duplas que o delimitam.
_PADRAO_ATRIBUTO_COM_HTML = re.compile(r'\s(?:data-bs-title|data-original-title|title)="[^"]*"')
_PADRAO_LOCAL = re.compile(r'<div class="mb-8">\s*(.*?)\s*(?:<span|</div>)', re.DOTALL)
_PADRAO_COORDENADAS = re.compile(
    r'data-vagalatitude="(-?[\d.]+)"\s+data-vagalongitude="(-?[\d.]+)"'
)
_PADRAO_DATA = re.compile(r'class="js_date" data-value="([^" ]+)')
# Os ícones identificam cada informação da faixa de metadados do card —
# o texto vem logo depois do </svg> correspondente.
_PADRAO_MODALIDADE = re.compile(r'house-and-building.*?</svg>\s*([^<]+)', re.DOTALL)
_PADRAO_EXPERIENCIA = re.compile(r'#suitcase.*?</svg>\s*([^<]+)', re.DOTALL)
_PADRAO_RESUMO = re.compile(r'Sobre a vaga:\s*(.*?)</div>', re.DOTALL)
_PADRAO_TAG = re.compile(r"<[^>]+>")

_MODALIDADES = {"presencial": "Presencial", "hibrido": "Híbrido", "home office": "Remoto"}


def _sem_tooltip(card: str) -> str:
    return _PADRAO_ATRIBUTO_COM_HTML.sub("", card)


def _texto(trecho: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_PADRAO_TAG.sub(" ", trecho))).strip()


def _primeiro(padrao: re.Pattern, texto: str, grupo: int = 1) -> str:
    m = padrao.search(texto)
    return _texto(m.group(grupo)) if m else ""


class InfoJobsScraper(BaseScraper):

    def __init__(self, termos_busca: list[str]):
        self.termos_busca = termos_busca

    def buscar_vagas(self) -> list[Job]:
        vagas: list[Job] = []
        for termo in self.termos_busca:
            try:
                encontradas = self._buscar_termo(termo)
                vagas.extend(encontradas)
            except requests.RequestException as e:
                # Mesma disciplina do resto do projeto: nunca logar str(e)
                # (a mensagem do requests carrega a URL inteira) — só o tipo.
                logger.warning(f"[InfoJobs] '{termo}': {type(e).__name__}")

        logger.info(f"[InfoJobs] {len(vagas)} vaga(s) encontrada(s) no total")
        return vagas

    def _buscar_termo(self, termo: str) -> list[Job]:
        url = f"{_BASE}/empregos.aspx?palabra={quote_plus(termo)}"
        resposta = requests.get(url, timeout=_TIMEOUT, headers=_CABECALHOS)
        resposta.raise_for_status()

        vagas = [self._montar_vaga(card) for card in self._cards(resposta.text)]
        vagas = [v for v in vagas if v is not None]
        logger.info(f"[InfoJobs] Buscando: {termo} — {len(vagas)} vaga(s)")
        return vagas

    @staticmethod
    def _cards(pagina: str) -> list[str]:
        """Fatia o HTML em um pedaço por vaga. Casar campo por campo na
        página inteira misturaria dados de vagas diferentes — o título de
        uma com a empresa da seguinte."""
        marcas = [m.start() for m in _PADRAO_CARD.finditer(pagina)]
        return [pagina[ini:fim] for ini, fim in zip(marcas, marcas[1:] + [len(pagina)])]

    def _montar_vaga(self, card: str) -> Job | None:
        card = _sem_tooltip(card)
        titulo = _primeiro(_PADRAO_TITULO, card)
        caminho = _primeiro(_PADRAO_LINK, card)
        if not titulo or not caminho:
            return None

        modalidade_texto = _primeiro(_PADRAO_MODALIDADE, card).lower()
        modalidade = _MODALIDADES.get(
            modalidade_texto.replace("í", "i"), modalidade_texto.capitalize() or "Não informado"
        )

        job = Job(
            titulo=titulo,
            empresa=_primeiro(_PADRAO_EMPRESA, card) or "Não informado",
            local=_primeiro(_PADRAO_LOCAL, card),
            link=caminho if caminho.startswith("http") else f"{_BASE}{caminho}",
            site="InfoJobs",
            modalidade=modalidade,
            publicado_em=_primeiro(_PADRAO_DATA, card),
        )

        # Resumo + faixa de experiência juntos: o primeiro alimenta o eixo
        # de afinidade, o segundo o de barreira ("Entre 5 e 10 anos" bate
        # o padrão de anos altos em job.py).
        experiencia = _primeiro(_PADRAO_EXPERIENCIA, card)
        resumo = _primeiro(_PADRAO_RESUMO, card)
        job.descricao = "\n".join(filter(None, [
            f"EXPERIÊNCIA: {experiencia}" if experiencia else "",
            resumo,
        ]))

        m = _PADRAO_COORDENADAS.search(card)
        if m:
            job.coordenadas = (float(m.group(1)), float(m.group(2)))

        return job
