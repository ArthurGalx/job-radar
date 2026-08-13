
import argparse

from config_intl import (
    KEYWORDS_INTL,
    TERMOS_BUSCA_INTL,
    LOCATIONS_INTL,
    CIDADES_INTL,
)
from database.database import iniciar_db, ja_vista, salvar_vaga
from notifier.telegram import notificar_vaga, enviar_mensagem
from scrapers.linkedin_intl import LinkedInIntlScraper
from utils.filtro import filtrar_vagas
from logger import get_logger

logger = get_logger()

# Programa separado do main.py de propósito (ver decisão na conversa): o
# JobRadar original é todo pensado pra mercado brasileiro (cidades do
# Nordeste, keywords em português). Esse aqui busca vaga remota
# internacional que aceite português/espanhol — reaproveita job.py,
# database e notifier, mas com fonte, keywords e filtro de local próprios.
SCRAPERS_INTL = [
    LinkedInIntlScraper(termos_busca=TERMOS_BUSCA_INTL, locations=LOCATIONS_INTL),
]


def ciclo_de_busca_intl():
    total_novas = 0
    scrapers_com_problema = []

    for scraper in SCRAPERS_INTL:
        nome = scraper.__class__.__name__
        try:
            vagas = scraper.buscar_vagas()
        except Exception as e:
            logger.error(f"Erro no scraper {nome}: {e}")
            scrapers_com_problema.append(nome)
            continue

        if not vagas:
            logger.warning(f"{nome} não retornou nenhuma vaga bruta neste ciclo.")
            scrapers_com_problema.append(nome)
            continue

        # Sem cargo ambíguo/ferramenta ainda nesse pipeline — só cargo forte
        # (KEYWORDS_INTL), simples de propósito por ser a primeira versão.
        vagas_filtradas = filtrar_vagas(vagas, KEYWORDS_INTL, [], [], [], [], CIDADES_INTL)

        for vaga in vagas_filtradas:
            if ja_vista(vaga.id):
                continue

            salvar_vaga(vaga)
            notificar_vaga(vaga)
            total_novas += 1
            logger.info(f"Nova vaga internacional: {vaga.titulo} - {vaga.empresa}")

    logger.info(f"Ciclo internacional concluído. {total_novas} vaga(s) nova(s).")

    if len(scrapers_com_problema) >= len(SCRAPERS_INTL) / 2:
        enviar_mensagem(
            "⚠️ <b>JobRadar Internacional com problema</b>\n\n"
            f"{len(scrapers_com_problema)}/{len(SCRAPERS_INTL)} fontes falharam ou "
            f"voltaram vazias neste ciclo: {', '.join(scrapers_com_problema)}."
        )


def main():
    parser = argparse.ArgumentParser(description="JobRadar Internacional - vaga remota fora do Brasil")
    parser.add_argument("--once", action="store_true", help="Roda um único ciclo e encerra.")
    args = parser.parse_args()

    print("=" * 50)
    print("JOBRADAR INTERNACIONAL")
    print("=" * 50)

    print("\nPalavras monitoradas:")
    for palavra in KEYWORDS_INTL:
        print(f"• {palavra}")

    print("\nPaíses pesquisados:")
    for loc in LOCATIONS_INTL:
        print(f"• {loc}")

    iniciar_db()
    ciclo_de_busca_intl()


if __name__ == "__main__":
    main()
