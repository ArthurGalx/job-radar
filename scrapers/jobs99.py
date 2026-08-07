
import time

from playwright.sync_api import sync_playwright

from job import Job
from logger import get_logger
from scrapers.base import BaseScraper

logger = get_logger()

_MODALIDADES = {"remota", "híbrida", "hibrida", "presencial"}


class Jobs99Scraper(BaseScraper):
    """Busca vagas no https://www.99jobs.com."""

    def __init__(self, termos_busca: list[str]):
        self.termos_busca = termos_busca

    def buscar_vagas(self) -> list[Job]:
        vagas: list[Job] = []
        for termo in self.termos_busca:
            vagas.extend(self._buscar_termo(termo))

        logger.info(f"[99Jobs] {len(vagas)} vaga(s) encontrada(s) no total")
        return vagas

    def _buscar_termo(self, termo: str) -> list[Job]:
        logger.info(f"[99Jobs] Buscando: {termo}")
        vagas: list[Job] = []
        termo_url = termo.replace(" ", "+")
        url = f"https://www.99jobs.com/opportunities/filtered_search?search%5Bterm%5D={termo_url}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                page.goto(url, timeout=60000)
                page.wait_for_selector("a.opportunity-card", state="attached", timeout=15000)
                time.sleep(2)

                cards = page.query_selector_all("a.opportunity-card")
                for card in cards:
                    try:
                        titulo_el = card.query_selector("h1")
                        if not titulo_el:
                            continue
                        titulo = titulo_el.inner_text().strip()

                        empresa_el = card.query_selector("h2")
                        empresa = empresa_el.inner_text().strip() if empresa_el else "Não informado"

                        cidade_el = card.query_selector("p")
                        cidade = " ".join(cidade_el.inner_text().split()) if cidade_el else "Não informado"

                        modalidade = ""
                        for span in card.query_selector_all("span"):
                            texto_span = span.inner_text().strip()
                            if texto_span.lower() in _MODALIDADES:
                                modalidade = texto_span
                                break

                        local = f"{cidade} ({modalidade})" if modalidade else cidade

                        link = card.get_attribute("href")
                        if not link:
                            continue
                        if link.startswith("/"):
                            link = f"https://www.99jobs.com{link}"

                        vagas.append(Job(
                            titulo=titulo,
                            empresa=empresa,
                            local=local,
                            link=link,
                            site="99Jobs",
                        ))
                    except Exception as e:
                        logger.warning(f"[99Jobs] Erro ao processar card: {e}")
                        continue

            except Exception as e:
                logger.error(f"[99Jobs] Erro ao buscar '{termo}': {e}")
            finally:
                browser.close()

        return vagas
