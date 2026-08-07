
import time

from playwright.sync_api import sync_playwright

from job import Job
from logger import get_logger
from scrapers.base import BaseScraper

logger = get_logger()


class IndeedScraper(BaseScraper):
    """Busca vagas no https://br.indeed.com.

    Aviso: o Indeed tem proteção anti-bot (Cloudflare) que pode bloquear
    acessos automatizados repetidos, mesmo que o scraping funcione em testes
    manuais. Se começar a retornar 0 vagas de forma consistente, é provável
    bloqueio, não erro de seletor.
    """

    def __init__(self, termos_busca: list[str]):
        self.termos_busca = termos_busca

    def buscar_vagas(self) -> list[Job]:
        vagas: list[Job] = []
        for termo in self.termos_busca:
            vagas.extend(self._buscar_termo(termo))

        logger.info(f"[Indeed] {len(vagas)} vaga(s) encontrada(s) no total")
        return vagas

    def _buscar_termo(self, termo: str) -> list[Job]:
        logger.info(f"[Indeed] Buscando: {termo}")
        vagas: list[Job] = []
        termo_url = termo.replace(" ", "+")
        url = f"https://br.indeed.com/jobs?q={termo_url}&l="

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
                page.wait_for_selector(".job_seen_beacon", state="attached", timeout=25000)
                time.sleep(2)

                cards = page.query_selector_all(".job_seen_beacon")
                for card in cards:
                    try:
                        titulo_el = card.query_selector("h3.jobTitle a.jcs-JobTitle span")
                        if not titulo_el:
                            titulo_el = card.query_selector("h3.jobTitle")
                        if not titulo_el:
                            continue
                        titulo = titulo_el.inner_text().strip()

                        empresa_el = card.query_selector('[data-testid="company-name"]')
                        empresa = empresa_el.inner_text().strip() if empresa_el else "Não informado"

                        local_el = card.query_selector('[data-testid="text-location"]')
                        local = local_el.inner_text().strip() if local_el else "Não informado"

                        link_el = card.query_selector("a[data-jk]")
                        jk = link_el.get_attribute("data-jk") if link_el else None
                        if not jk:
                            continue
                        link = f"https://br.indeed.com/viewjob?jk={jk}"

                        vagas.append(Job(
                            titulo=titulo,
                            empresa=empresa,
                            local=local,
                            link=link,
                            site="Indeed",
                        ))
                    except Exception as e:
                        logger.warning(f"[Indeed] Erro ao processar card: {e}")
                        continue

                if not cards:
                    logger.warning("[Indeed] Nenhum card encontrado — possível bloqueio anti-bot.")

            except Exception as e:
                logger.error(f"[Indeed] Erro ao buscar '{termo}': {e}")
            finally:
                browser.close()

        return vagas
