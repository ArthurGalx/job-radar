"""Programas de trainee do Seja Trainee (sejatrainee.com.br).

Fonte de natureza diferente de todas as outras: não é board de vaga, é um
site editorial que ACOMPANHA a temporada de trainee e publica um artigo por
programa aberto ("Grupo Safra abre trainee com salário de R$ 11.000",
"Garena, dona do Free Fire, abre Trainee"). Para quem disputa trainee, isso
é melhor que board — programa grande é anunciado ali antes de virar card em
portal, e vários nem chegam aos portais.

É WordPress, então tem API REST pública (/wp-json/wp/v2/posts) com título,
data, link e resumo em JSON — sem navegador e sem HTML pra raspar.

DUAS PECULIARIDADES, ambas tratadas aqui e não no motor:

1. Não existe cidade. Programa de trainee é nacional e a alocação sai
   durante a seleção. As vagas são marcadas com Job.programa_nacional, e o
   filtro de cidade as aceita por causa disso (ver
   RegrasFiltro.aceitar_programa_nacional) — sem essa marca, a allowlist de
   São Paulo descartaria 100% do que esta fonte traz.

2. Nem todo artigo é anúncio de programa. O site também publica pauta
   editorial ("o que é trainee", "como se preparar"). Os padrões em
   _TITULOS_EDITORIAIS descartam esse tipo antes de virar vaga — o resto
   passa, inclusive matéria de opinião sobre programa aberto, que continua
   apontando pra inscrição.
"""

import html
import re

import requests

from job import Job
from logger import get_logger
from scrapers.base import BaseScraper

logger = get_logger()

_URL = "https://sejatrainee.com.br/wp-json/wp/v2/posts"
_TIMEOUT = 25
_CABECALHOS = {"User-Agent": "Mozilla/5.0 (compatible; JobRadar/1.0)"}

# Quantos artigos recentes ler por ciclo. A temporada de trainee concentra
# vários anúncios por dia; 30 cobre com folga o intervalo de 3h entre
# ciclos, e o dedup por link cuida da repetição.
_POR_PAGINA = 30

_PADRAO_TAG = re.compile(r"<[^>]+>")

# Pauta educativa, não anúncio de programa. Casado no título normalizado.
_TITULOS_EDITORIAIS = (
    "o que e trainee",
    "como se preparar",
    "como passar",
    "dicas para",
    "curriculo",
    "entrevista de emprego",
    "diferenca entre",
)

_LOCAL_NACIONAL = "Brasil (programa nacional)"


def _texto(trecho: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_PADRAO_TAG.sub(" ", trecho))).strip()


class SejaTraineeScraper(BaseScraper):

    def __init__(self, termos_busca: list[str]):
        # A API devolve os artigos mais recentes, sem parâmetro de busca —
        # como no scraper de ATS, o termo não tem onde ser aplicado e o
        # filtro de cargo do projeto é quem decide o que entra.
        self.termos_busca = termos_busca

    def buscar_vagas(self) -> list[Job]:
        try:
            resposta = requests.get(
                f"{_URL}?per_page={_POR_PAGINA}", timeout=_TIMEOUT, headers=_CABECALHOS
            )
            resposta.raise_for_status()
            artigos = resposta.json()
        except requests.RequestException as e:
            logger.warning(f"[SejaTrainee] {type(e).__name__}")
            return []
        except ValueError:
            logger.warning("[SejaTrainee] resposta fora do formato JSON esperado.")
            return []

        vagas = [v for v in (self._montar_vaga(a) for a in artigos) if v is not None]
        logger.info(f"[SejaTrainee] {len(vagas)} programa(s) de trainee encontrado(s)")
        return vagas

    def _montar_vaga(self, artigo: dict) -> Job | None:
        from job import _normalizar

        titulo = _texto((artigo.get("title") or {}).get("rendered", ""))
        link = artigo.get("link", "")
        if not titulo or not link:
            return None

        titulo_norm = _normalizar(titulo)
        if any(p in titulo_norm for p in _TITULOS_EDITORIAIS):
            return None

        job = Job(
            titulo=titulo,
            # A empresa está dentro do título ("Grupo Safra abre trainee
            # com salário de R$ 11.000") e extrair com regra fixa erraria
            # mais do que acertaria — o formato varia a cada matéria.
            empresa="Ver no anúncio",
            local=_LOCAL_NACIONAL,
            link=link,
            site="Seja Trainee",
            modalidade="Não informado",
            publicado_em=(artigo.get("date") or "")[:10],
        )
        job.programa_nacional = True
        job.descricao = _texto((artigo.get("excerpt") or {}).get("rendered", ""))
        return job
