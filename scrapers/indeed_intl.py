
import time

from playwright.sync_api import sync_playwright

from job import Job
from logger import get_logger
from scrapers.base import BaseScraper

logger = get_logger()

# Começa sem paginar (igual linkedin_intl.py) — pipeline novo, ainda não
# validado em produção.
MAX_PAGINAS = 1


class IndeedIntlScraper(BaseScraper):
    """Busca vaga internacional no Indeed, variando o subdomínio por país
    (dominios: {"Espanha": "es.indeed.com", ...}) em vez de ficar fixo em
    br.indeed.com como o scrapers/indeed.py original.

    Mesmo aviso do Indeed BR: proteção anti-bot (Cloudflare) pode bloquear
    acesso automatizado mesmo funcionando em teste manual — se um país
    específico voltar 0 vagas de forma consistente em todos os termos, é
    provável bloqueio daquele domínio, não erro de seletor.
    """

    def __init__(self, termos_busca: list[str], dominios: dict[str, str]):
        self.termos_busca = termos_busca
        self.dominios = dominios

    def buscar_vagas(self) -> list[Job]:
        vagas: list[Job] = []
        for termo in self.termos_busca:
            for pais, dominio in self.dominios.items():
                vagas.extend(self._buscar_termo(termo, pais, dominio))

        logger.info(f"[Indeed Intl] {len(vagas)} vaga(s) encontrada(s) no total")
        return vagas

    def _buscar_termo(self, termo: str, pais: str, dominio: str) -> list[Job]:
        logger.info(f"[Indeed Intl] Buscando: '{termo}' em {pais} ({dominio})")
        vagas: list[Job] = []
        termo_url = termo.replace(" ", "+")

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
                for pagina in range(MAX_PAGINAS):
                    start = pagina * 10
                    url = f"https://{dominio}/jobs?q={termo_url}&l=&start={start}"
                    page.goto(url, timeout=60000)
                    try:
                        page.wait_for_selector(".job_seen_beacon", state="attached", timeout=25000)
                    except Exception:
                        if pagina == 0:
                            logger.warning(
                                f"[Indeed Intl] Nenhum card em {pais} ({dominio}) — "
                                "possível bloqueio anti-bot ou 0 vaga real."
                            )
                        break
                    time.sleep(2)

                    cards = page.query_selector_all(".job_seen_beacon")
                    if not cards:
                        break

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
                            link = f"https://{dominio}/viewjob?jk={jk}"

                            vagas.append(Job(
                                titulo=titulo,
                                empresa=empresa,
                                local=local,
                                link=link,
                                site=f"Indeed Internacional ({pais})",
                            ))
                        except Exception as e:
                            logger.warning(f"[Indeed Intl] Erro ao processar card: {e}")
                            continue

            except Exception as e:
                logger.error(f"[Indeed Intl] Erro ao buscar '{termo}' em {pais}: {e}")
            finally:
                browser.close()

        return vagas
