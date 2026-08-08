
import time

from playwright.sync_api import sync_playwright

from job import Job
from logger import get_logger
from scrapers.base import BaseScraper

logger = get_logger()


class GupyScraper(BaseScraper):
    """Busca vagas no portal público da Gupy (https://portal.gupy.io)."""

    def __init__(self, termos_busca: list[str]):
        self.termos_busca = termos_busca

    def buscar_vagas(self) -> list[Job]:
        vagas: list[Job] = []
        for termo in self.termos_busca:
            vagas.extend(self._buscar_termo(termo))

        logger.info(f"[Gupy] {len(vagas)} vaga(s) encontrada(s) no total")
        return vagas

    def _buscar_termo(self, termo: str) -> list[Job]:
        logger.info(f"[Gupy] Buscando: {termo}")
        vagas: list[Job] = []
        url = f"https://portal.gupy.io/job-search/term={termo.replace(' ', '%20')}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                page.goto(url, timeout=60000)
                sem_resultados = False
                try:
                    page.wait_for_selector("a:has(h3)", timeout=15000)
                except Exception:
                    if "Nenhum resultado foi encontrado" in page.inner_text("body"):
                        logger.info(f"[Gupy] 0 resultados reais para '{termo}'.")
                        sem_resultados = True
                    else:
                        raise
                time.sleep(2 if not sem_resultados else 0)  # dá tempo do React terminar de renderizar

                cards = [] if sem_resultados else page.query_selector_all("a:has(h3)")
                for card in cards:
                    try:
                        titulo_el = card.query_selector("h3")
                        if not titulo_el:
                            continue
                        titulo = titulo_el.inner_text().strip()

                        empresa_el = card.query_selector("p")
                        empresa = empresa_el.inner_text().strip() if empresa_el else "Não informado"

                        local_el = card.query_selector('[data-testid="job-location"]')
                        cidade = local_el.inner_text().strip() if local_el else "Não informado"

                        # O modelo de trabalho (Remoto/Híbrido/Presencial) fica num span
                        # separado, sem data-testid, ao lado de um ícone identificado
                        # pelo atributo alt="Ícone de Modelo de Trabalho".
                        modelo_icon = card.query_selector('svg[alt="Ícone de Modelo de Trabalho"]')
                        modelo = ""
                        if modelo_icon:
                            modelo = modelo_icon.evaluate(
                                "el => el.closest('div')?.parentElement?.querySelector('span')?.textContent?.trim() || ''"
                            )

                        local = f"{cidade} ({modelo})" if modelo else cidade

                        link = card.get_attribute("href")
                        if not link:
                            continue

                        vagas.append(Job(
                            titulo=titulo,
                            empresa=empresa,
                            local=local,
                            link=link,
                            site="Gupy",
                        ))
                    except Exception as e:
                        logger.warning(f"[Gupy] Erro ao processar card: {e}")
                        continue

            except Exception as e:
                logger.error(f"[Gupy] Erro ao buscar '{termo}': {e}")
            finally:
                browser.close()

        return vagas
