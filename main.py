
import argparse
import time

from config import KEYWORDS, CIDADES, INTERVALO_MINUTOS
from database.database import iniciar_db, ja_vista, salvar_vaga
from notifier.telegram import notificar_vaga
from scrapers.gupy import GupyScraper
from utils.filtro import filtrar_vagas
from logger import get_logger

logger = get_logger()

# Adicione novos scrapers aqui conforme forem implementados
# (Catho, Trampos, 99jobs etc.)
SCRAPERS = [
    GupyScraper(termos_busca=[
        "analista de dados",
        "power bi",
        "business intelligence",
    ]),
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