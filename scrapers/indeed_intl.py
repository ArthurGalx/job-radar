
import time
from urllib.parse import quote_plus

from playwright.sync_api import sync_playwright

from job import Job, extrair_data_publicacao
from logger import get_logger
from scrapers.base import BaseScraper

logger = get_logger()

# Começa sem paginar (igual linkedin_intl.py) — pipeline novo, ainda não
# validado em produção.
MAX_PAGINAS = 1

# Filtro nativo de "Remoto"/"Teletrabajo"/"Home office" do próprio Indeed —
# mesmo espírito do f_WT=2 do LinkedIn (ver scrapers/linkedin.py). CONFIRMADO
# AO VIVO (Claude in Chrome) em es.indeed.com e mx.indeed.com: aplicar o
# filtro "Remoto"/"Home office" pela UI gera essa URL. Sem isso, a busca
# baixava toda vaga do domínio do país (~1000 resultados pro termo testado)
# e descartava a maioria por não ter sinal de remoto no texto do local — o
# perfil internacional só aceita remoto, então quase tudo que era baixado
# ia pro lixo. Mesmo código funcionou nos dois domínios testados (es./mx.),
# indício de que é uma categoria compartilhada entre os domínios do Indeed,
# não algo específico por país — mas só es./mx. foram confirmados ao vivo
# nesta sessão; se algum dos outros 4 (pt./co./ar./cl.) voltar 0 vaga de
# forma persistente em todos os termos, vale reconferir esse específico.
FILTRO_REMOTO = "&sc=0kf%3Aattr%28DSQF7%29%3B"


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
        termo_url = quote_plus(termo)

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
                    url = f"https://{dominio}/jobs?q={termo_url}&l=&start={start}{FILTRO_REMOTO}"
                    page.goto(url, timeout=60000)
                    try:
                        page.wait_for_selector(".job_seen_beacon", state="attached", timeout=25000)
                    except Exception:
                        if pagina == 0:
                            logger.warning(
                                f"[Indeed Intl] Nenhum card em {pais} ({dominio}) — "
                                "possível bloqueio anti-bot, 0 vaga real, ou FILTRO_REMOTO "
                                "não reconhecido nesse domínio (só es./mx. confirmados ao "
                                "vivo — ver comentário em FILTRO_REMOTO)."
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

                            # FILTRO_REMOTO já garante que é vaga remota (o
                            # próprio Indeed classificou assim) — marca
                            # direto, sem depender do texto de local, que
                            # muitas vezes só mostra a cidade sem dizer
                            # "remoto"/"teletrabajo" (mesmo motivo do
                            # f_WT=2 no LinkedIn).
                            modalidade = "Remoto"

                            link_el = card.query_selector("a[data-jk]")
                            jk = link_el.get_attribute("data-jk") if link_el else None
                            if not jk:
                                continue
                            link = f"https://{dominio}/viewjob?jk={jk}"

                            publicado_em = extrair_data_publicacao(card.inner_text())

                            vagas.append(Job(
                                titulo=titulo,
                                empresa=empresa,
                                local=local,
                                link=link,
                                publicado_em=publicado_em,
                                site=f"Indeed Internacional ({pais})",
                                modalidade=modalidade,
                            ))
                        except Exception as e:
                            logger.warning(f"[Indeed Intl] Erro ao processar card: {e}")
                            continue

            except Exception as e:
                logger.error(f"[Indeed Intl] Erro ao buscar '{termo}' em {pais}: {e}")
            finally:
                browser.close()

        return vagas
