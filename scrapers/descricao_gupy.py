"""Descrição e endereço de uma vaga da Gupy.

A página individual embute tudo num JSON dentro do HTML, então um GET
resolve — ver scrapers/descricao_comum.py pro mecanismo e pro cache.

MEDIDO na vaga real "Product Owner Pleno - Be.Aliant": os três campos que
interessam vêm separados — description (552 chars, sobre a empresa),
responsibilities (998) e prerequisites (1189, os requisitos). O endereço
vem completo com CEP em addressLine ("Avenida das Nações Unidas, 14261,
São Paulo, ..., 04795-100"), que é o que permite situar a vaga dentro da
cidade (ver utils/geo.py).
"""

from scrapers.descricao_comum import MAX_CARACTERES, buscar_next_data, limpar_html

_CAMINHO = ("props", "pageProps", "job")


def montar_texto(dados_vaga: dict) -> str:
    """Junta os campos da vaga num texto só, com rótulo. Função pura, e a
    parte que os testes cobrem — a chamada de rede em volta não tem regra
    nenhuma que valha testar.

    Ordem: requisitos e responsabilidades primeiro (é o que decide
    afinidade e o que escrever na carta), descrição institucional por
    último.
    """
    secoes = [
        ("REQUISITOS", limpar_html(dados_vaga.get("prerequisites", ""))),
        ("RESPONSABILIDADES", limpar_html(dados_vaga.get("responsibilities", ""))),
        ("SOBRE A VAGA/EMPRESA", limpar_html(dados_vaga.get("description", ""))),
    ]
    texto = "\n\n".join(f"{rotulo}:\n{corpo}" for rotulo, corpo in secoes if corpo)
    return texto[:MAX_CARACTERES]


def buscar_descricao(link: str) -> str:
    """Texto do anúncio, ou "" em qualquer falha."""
    return montar_texto(buscar_next_data(link, _CAMINHO))


def buscar_endereco(link: str) -> str:
    """Endereço completo com CEP, ou "" se a fonte não expõe.

    É o CEP que permite situar a vaga dentro da cidade — sem ele,
    "São Paulo - SP" pode ser tanto 2 km quanto 25 km de casa.
    """
    return buscar_next_data(link, _CAMINHO).get("addressLine", "") or ""
