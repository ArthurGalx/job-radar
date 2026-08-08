
import time

from playwright.sync_api import sync_playwright

from job import Job
from logger import get_logger
from scrapers.base import BaseScraper

logger = get_logger()

_MODALIDADES = {"remoto", "híbrido", "hibrido", "presencial"}


def _slug(termo: str) -> str:
    return termo.strip().lower().replace(" ", "-")


class SolidesScraper(BaseScraper):
    """Busca vagas no https://vagas.solides.com.br."""

    def __init__(self, termos_busca: list[str]):
        self.termos_busca = termos_busca

    def buscar_vagas(self) -> list[Job]:
        vagas: list[Job] = []
        for termo in self.termos_busca:
            vagas.extend(self._buscar_termo(termo))

        logger.info(f"[Solides] {len(vagas)} vaga(s) encontrada(s) no total")
        return vagas

    def _buscar_termo(self, termo: str) -> list[Job]:
        logger.info(f"[Solides] Buscando: {termo}")
        vagas: list[Job] = []
        url = f"https://vagas.solides.com.br/vagas/todos/{_slug(termo)}?page=1"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
            )
            page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"
            )

            try:
                page.goto(url, timeout=60000)
                sem_resultados = False
                try:
                    page.wait_for_selector("li:has(h2 a)", state="attached", timeout=25000)
                except Exception:
                    if "0 vaga(s) encontrada" in page.inner_text("body"):
                        logger.info(f"[Solides] 0 resultados reais para '{termo}'.")
                        sem_resultados = True
                    else:
                        raise
                if not sem_resultados:
                    time.sleep(2)

                cards = [] if sem_resultados else page.query_selector_all("li:has(h2 a)")
                for card in cards:
                    try:
                        titulo_el = card.query_selector("h2 a")
                        if not titulo_el:
                            continue
                        titulo = titulo_el.inner_text().strip()

                        link = titulo_el.get_attribute("href")
                        if not link:
                            continue
                        if link.startswith("/"):
                            link = f"https://vagas.solides.com.br{link}"

                        paragrafos = card.query_selector_all("p")
                        empresa = paragrafos[0].inner_text().strip() if len(paragrafos) > 0 else "Não informado"
                        cidade = paragrafos[1].inner_text().strip() if len(paragrafos) > 1 else "Não informado"

                        modalidade = ""
                        for div in card.query_selector_all("div"):
                            texto_div = div.inner_text().strip()
                            if texto_div.lower() in _MODALIDADES:
                                modalidade = texto_div
                                break

                        local = f"{cidade} ({modalidade})" if modalidade else cidade

                        vagas.append(Job(
                            titulo=titulo,
                            empresa=empresa or "Não informado",
                            local=local,
                            link=link,
                            site="Solides",
                        ))
                    except Exception as e:
                        logger.warning(f"[Solides] Erro ao processar card: {e}")
                        continue

            except Exception as e:
                logger.error(f"[Solides] Erro ao buscar '{termo}': {e}")
            finally:
                browser.close()

        return vagas
