
import argparse
import time

from config import (
    KEYWORDS,
    KEYWORDS_CARGO_FORTE,
    KEYWORDS_CARGO_AMBIGUO,
    QUALIFICADORES_DADOS,
    CIDADES,
    INTERVALO_MINUTOS,
    TERMOS_BUSCA,
)
from database.database import iniciar_db, ja_vista, salvar_vaga
from notifier.telegram import notificar_vaga, enviar_mensagem
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

# Revelo não entrou: o portal de vagas exige login pra navegar, não dá pra
# fazer scraping público de forma confiável.
SCRAPERS = [
    GupyScraper(termos_busca=TERMOS_BUSCA),
    TramposScraper(termos_busca=TERMOS_BUSCA),
    Jobs99Scraper(termos_busca=TERMOS_BUSCA),
    CathoScraper(termos_busca=TERMOS_BUSCA),
    SolidesScraper(termos_busca=TERMOS_BUSCA),
    GeekHunterScraper(termos_busca=TERMOS_BUSCA),
    IndeedScraper(termos_busca=TERMOS_BUSCA),
    LinkedInScraper(termos_busca=TERMOS_BUSCA),
]


def ciclo_de_busca():
    total_novas = 0
    total_brutas = 0
    scrapers_com_problema = []

    for scraper in SCRAPERS:
        nome = scraper.__class__.__name__
        try:
            vagas = scraper.buscar_vagas()
        except Exception as e:
            logger.error(f"Erro no scraper {nome}: {e}")
            scrapers_com_problema.append(nome)
            continue

        # Cada scraper trata timeout por termo internamente (só loga e segue
        # pro próximo termo), então um site totalmente bloqueado não lança
        # exceção pra cá — só devolve lista vazia. Por isso também contamos
        # "0 vaga bruta nessa fonte" como problema, não só exceção.
        if not vagas:
            logger.warning(f"{nome} não retornou nenhuma vaga bruta neste ciclo.")
            scrapers_com_problema.append(nome)
            continue

        total_brutas += len(vagas)
        vagas_filtradas = filtrar_vagas(
            vagas, KEYWORDS_CARGO_FORTE, KEYWORDS_CARGO_AMBIGUO, QUALIFICADORES_DADOS, CIDADES
        )

        for vaga in vagas_filtradas:
            if ja_vista(vaga.id):
                continue

            salvar_vaga(vaga)
            notificar_vaga(vaga)
            total_novas += 1
            logger.info(f"Nova vaga: {vaga.titulo} - {vaga.empresa}")

    logger.info(f"Ciclo concluído. {total_novas} vaga(s) nova(s).")

    # Alerta de saúde: se a maioria das fontes falhou/voltou vazia, avisa no
    # Telegram. Sem isso, um bloqueio geral ou mudança de layout passaria
    # despercebido — o workflow do GitHub Actions continuaria "verde" mesmo
    # com tudo quebrado.
    if len(scrapers_com_problema) >= len(SCRAPERS) / 2:
        enviar_mensagem(
            "⚠️ <b>JobRadar com problema</b>\n\n"
            f"{len(scrapers_com_problema)}/{len(SCRAPERS)} fontes falharam ou voltaram "
            f"vazias neste ciclo: {', '.join(scrapers_com_problema)}.\n\n"
            "Vale checar o log do GitHub Actions."
        )


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

    if not args.once:
        print(f"\nIntervalo de checagem: {INTERVALO_MINUTOS} min\n")

    iniciar_db()

    if args.once:
        # No GitHub Actions, quem controla a frequência é o cron do workflow,
        # não essa variável — por isso não faz sentido imprimir um intervalo
        # aqui, ele nem é usado nesse modo.
        ciclo_de_busca()
        return

    while True:
        ciclo_de_busca()
        logger.info(f"Aguardando {INTERVALO_MINUTOS} minutos até a próxima checagem...")
        time.sleep(INTERVALO_MINUTOS * 60)


if __name__ == "__main__":
    main()