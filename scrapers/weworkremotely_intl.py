
import time

from playwright.sync_api import sync_playwright

from job import Job
from logger import get_logger
from scrapers.base import BaseScraper

logger = get_logger()


class WeWorkRemotelyIntlScraper(BaseScraper):
    """Agregador de vaga 100% remota internacional (weworkremotely.com) —
    opção 2 do eixo internacional: cobertura melhor pro "remoto
    internacional" que LinkedIn/Indeed, mas foco em anúncio pago/curado, não
    aparelho de busca nacional por país. Sem filtro de idioma na própria
    busca (o site não separa por PT/ES) — a filtragem de cargo (KEYWORDS_INTL)
    já reduz bastante o ruído, e cards que não são vaga de verdade (anúncio
    promovido de outra categoria) simplesmente não batem no título.
    """

    def __init__(self, termos_busca: list[str]):
        self.termos_busca = termos_busca

    def buscar_vagas(self) -> list[Job]:
        vagas: list[Job] = []
        for termo in self.termos_busca:
            vagas.extend(self._buscar_termo(termo))

        logger.info(f"[WeWorkRemotely Intl] {len(vagas)} vaga(s) encontrada(s) no total")
        return vagas

    def _buscar_termo(self, termo: str) -> list[Job]:
        logger.info(f"[WeWorkRemotely Intl] Buscando: {termo}")
        vagas: list[Job] = []
        termo_url = termo.replace(" ", "+")
        url = f"https://weworkremotely.com/remote-jobs/search?term={termo_url}"

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
                try:
                    page.wait_for_selector("li.new-listing-container", timeout=15000)
                except Exception:
                    logger.info(f"[WeWorkRemotely Intl] 0 resultados para '{termo}'.")
                    return vagas
                time.sleep(2)

                cards = page.query_selector_all("li.new-listing-container")
                for card in cards:
                    try:
                        titulo_el = card.query_selector(".new-listing__header__title")
                        if not titulo_el:
                            continue
                        titulo = titulo_el.inner_text().strip()

                        empresa_el = card.query_selector(".new-listing__company-name")
                        empresa = empresa_el.inner_text().strip() if empresa_el else "Não informado"

                        # Todo anúncio do WeWorkRemotely já é vaga remota por
                        # definição (é a proposta do site) — o campo abaixo é
                        # a sede da empresa, não a modalidade. Por isso força
                        # "Remote" sempre, senão o filtro de cidade (que exige
                        # "remote"/"remoto" no local) rejeitaria vaga remota
                        # de verdade só porque o card mostra "San Francisco, CA"
                        # como sede.
                        sede_el = card.query_selector(".new-listing__company-headquarters")
                        sede = sede_el.inner_text().strip() if sede_el else ""
                        local = f"Remote ({sede})" if sede else "Remote"

                        link_el = card.query_selector('a[href^="/remote-jobs/"]')
                        link = link_el.get_attribute("href") if link_el else None
                        if not link:
                            continue
                        link = f"https://weworkremotely.com{link.split('?')[0]}"

                        vagas.append(Job(
                            titulo=titulo,
                            empresa=empresa,
                            local=local,
                            link=link,
                            site="We Work Remotely",
                        ))
                    except Exception as e:
                        logger.warning(f"[WeWorkRemotely Intl] Erro ao processar card: {e}")
                        continue

            except Exception as e:
                logger.error(f"[WeWorkRemotely Intl] Erro ao buscar '{termo}': {e}")
            finally:
                browser.close()

        return vagas
