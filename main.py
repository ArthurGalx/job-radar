
import argparse
import time

from config import KEYWORDS, CIDADES, INTERVALO_MINUTOS
from database.database import iniciar_db, ja_vista, salvar_vaga
from notifier.telegram import notificar_vaga
from scrapers.catho import CathoScraper
from scrapers.geekhunter import GeekHunterScraper
from scrapers.gupy import GupyScraper
from scrapers.indeed import IndeedScraper
from scrapers.jobs99 import Jobs99Scraper
from scrapers.linkedin import LinkedInScraper
from scrapers.solides import SolidesScraper
from scrapers.trampos import TramposScraper
from utils.filtro import filtrar_vagas
from logger import get_logger

logger = get_logger()

# Termos de busca enviados para cada site (a filtragem fina por KEYWORDS/CIDADES
# acontece depois, em filtrar_vagas). Mantidos enxutos pra não deixar o ciclo
# muito longo, já que cada termo é uma nova página carregada por site.
_TERMOS_BUSCA = [
    "analista de dados",
    "power bi",
    "business intelligence",
]

# Revelo não entrou: o portal de vagas exige login pra navegar, não dá pra
# fazer scraping público de forma confiável.
SCRAPERS = [
    GupyScraper(termos_busca=_TERMOS_BUSCA),
    TramposScraper(termos_busca=_TERMOS_BUSCA),
    Jobs99Scraper(termos_busca=_TERMOS_BUSCA),
    CathoScraper(termos_busca=_TERMOS_BUSCA),
    SolidesScraper(termos_busca=_TERMOS_BUSCA),
    GeekHunterScraper(termos_busca=_TERMOS_BUSCA),
    IndeedScraper(termos_busca=_TERMOS_BUSCA),
    LinkedInScraper(termos_busca=_TERMOS_BUSCA),
]


def ciclo_de_busca():
    total_novas = 0

    for scraper in SCRAPERS:
        try:
            vagas = scraper.buscar_vagas()
        except Exception as e:
            logger.error(f"Erro no scraper {scraper.__class__.__name__}: {e}")
            continue

        vagas_filtradas = filtrar_vagas(vagas, KEYWORDS, CIDADES)

        for vaga in vagas_filtradas:
            if ja_vista(vaga.id):
                continue

            salvar_vaga(vaga)
            notificar_vaga(vaga)
            total_novas += 1
            logger.info(f"Nova vaga: {vaga.titulo} - {vaga.empresa}")

    logger.info(f"Ciclo concluído. {total_novas} vaga(s) nova(s).")


def main():
    parser = argparse.ArgumentParser(description="JobRadar - monitor de vagas")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Roda um único ciclo de busca e encerra (usado no GitHub Actions, "
             "que já dispara o script periodicamente via cron).",
    )
    args = parser.parse_args()

    print("=" * 50)
    print("JOBRADAR")
    print("=" * 50)

    print("\nPalavras monitoradas:")
    for palavra in KEYWORDS:
        print(f"• {palavra}")

    print(f"\nIntervalo de checagem: {INTERVALO_MINUTOS} min\n")

    iniciar_db()

    if args.once:
        ciclo_de_busca()
        return

    while True:
        ciclo_de_busca()
        logger.info(f"Aguardando {INTERVALO_MINUTOS} minutos até a próxima checagem...")
        time.sleep(INTERVALO_MINUTOS * 60)


if __name__ == "__main__":
    main()