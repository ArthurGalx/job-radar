
import re
import time

from playwright.sync_api import sync_playwright

from job import Job
from logger import get_logger
from scrapers.base import BaseScraper

logger = get_logger()

_MODALIDADES = {"presencial", "híbrido", "hibrido", "remoto"}


def _empresa_da_url(path: str) -> str:
    """A listagem não mostra o nome da empresa, só o slug na URL
    (/pt/{empresa}/jobs/{vaga}). Deriva um nome legível a partir dele."""
    partes = path.strip("/").split("/")
    if len(partes) >= 2:
        slug = partes[1]
        return slug.replace("-", " ").title()
    return "Não informado"


class GeekHunterScraper(BaseScraper):
    """Busca vagas no https://www.geekhunter.com/pt/vagas."""

    def __init__(self, termos_busca: list[str]):
        self.termos_busca = termos_busca

    def buscar_vagas(self) -> list[Job]:
        vagas: list[Job] = []
        for termo in self.termos_busca:
            vagas.extend(self._buscar_termo(termo))

        logger.info(f"[GeekHunter] {len(vagas)} vaga(s) encontrada(s) no total")
        return vagas

    def _buscar_termo(self, termo: str) -> list[Job]:
        logger.info(f"[GeekHunter] Buscando: {termo}")
        vagas: list[Job] = []
        termo_url = termo.replace(" ", "+")
        url = f"https://www.geekhunter.com/pt/vagas?searchTerm={termo_url}&page=1"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                page.goto(url, timeout=60000)
                page.wait_for_selector('a[href*="/jobs/"]', timeout=15000)
                time.sleep(2)

                cards = page.query_selector_all('a[href*="/jobs/"]')
                for card in cards:
                    try:
                        linhas = [l.strip() for l in card.inner_text().split("\n") if l.strip()]
                        if not linhas:
                            continue
                        titulo = linhas[0]

                        modalidade = ""
                        cidade = ""
                        for linha in linhas[1:]:
                            if linha.lower() in _MODALIDADES:
                                modalidade = linha.capitalize()
                            elif re.match(r"^🇧🇷", linha):
                                cidade = linha.replace("🇧🇷", "").strip()

                        if cidade:
                            local = f"{cidade} ({modalidade})" if modalidade else cidade
                        else:
                            local = modalidade or "Não informado"

                        link = card.get_attribute("href")
                        if not link:
                            continue
                        if link.startswith("/"):
                            empresa = _empresa_da_url(link)
                            link = f"https://www.geekhunter.com{link}"
                        else:
                            empresa = "Não informado"

                        vagas.append(Job(
                            titulo=titulo,
                            empresa=empresa,
                            local=local,
                            link=link,
                            site="GeekHunter",
                        ))
                    except Exception as e:
                        logger.warning(f"[GeekHunter] Erro ao processar card: {e}")
                        continue

            except Exception as e:
                logger.error(f"[GeekHunter] Erro ao buscar '{termo}': {e}")
            finally:
                browser.close()

        return vagas
