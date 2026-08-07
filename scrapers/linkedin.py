
import time

from playwright.sync_api import sync_playwright

from job import Job
from logger import get_logger
from scrapers.base import BaseScraper

logger = get_logger()


class LinkedInScraper(BaseScraper):
    """Busca vagas usando o endpoint público ("guest") de busca de vagas do
    LinkedIn, o mesmo usado para carregar mais resultados sem estar logado.

    Aviso importante: esse endpoint não é oficial/documentado pelo LinkedIn.
    Ele costuma funcionar sem login, mas o LinkedIn pode bloquear ou
    rate-limitar acessos automatizados repetidos a qualquer momento —
    principalmente vindos de IPs de nuvem/datacenter, como os do GitHub
    Actions. Não é possível garantir estabilidade a longo prazo. Também não
    mostra a modalidade (remoto/híbrido/presencial) na listagem, só a
    cidade — vagas remotas só são pegas se a cidade vier literalmente como
    "Remoto".
    """

    def __init__(self, termos_busca: list[str]):
        self.termos_busca = termos_busca

    def buscar_vagas(self) -> list[Job]:
        vagas: list[Job] = []
        for termo in self.termos_busca:
            vagas.extend(self._buscar_termo(termo))

        logger.info(f"[LinkedIn] {len(vagas)} vaga(s) encontrada(s) no total")
        return vagas

    def _buscar_termo(self, termo: str) -> list[Job]:
        logger.info(f"[LinkedIn] Buscando: {termo}")
        vagas: list[Job] = []
        termo_url = termo.replace(" ", "+")
        url = (
            "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
            f"?keywords={termo_url}&location=Brasil&start=0"
        )

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
            )

            try:
                page.goto(url, timeout=60000)
                time.sleep(2)

                cards = page.query_selector_all("li")
                if not cards:
                    logger.warning(
                        "[LinkedIn] Nenhum resultado retornado — provável bloqueio/"
                        "rate-limit do LinkedIn nesse endpoint."
                    )

                for card in cards:
                    try:
                        titulo_el = card.query_selector("h3.base-search-card__title")
                        if not titulo_el:
                            continue
                        titulo = titulo_el.inner_text().strip()

                        empresa_el = card.query_selector("h4.base-search-card__subtitle a")
                        empresa = empresa_el.inner_text().strip() if empresa_el else "Não informado"

                        local_el = card.query_selector(".job-search-card__location")
                        local = local_el.inner_text().strip() if local_el else "Não informado"

                        link_el = card.query_selector("a.base-card__full-link")
                        link = link_el.get_attribute("href") if link_el else None
                        if not link:
                            continue
                        link = link.split("?")[0]

                        vagas.append(Job(
                            titulo=titulo,
                            empresa=empresa,
                            local=local,
                            link=link,
                            site="LinkedIn",
                        ))
                    except Exception as e:
                        logger.warning(f"[LinkedIn] Erro ao processar card: {e}")
                        continue

            except Exception as e:
                logger.error(f"[LinkedIn] Erro ao buscar '{termo}': {e}")
            finally:
                browser.close()

        return vagas
