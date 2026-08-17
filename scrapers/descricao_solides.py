"""Descrição de uma vaga da Sólides (vagas.solides.com.br).

Mesmo mecanismo da Gupy (Next.js com __NEXT_DATA__ no HTML, ver
scrapers/descricao_comum.py), com duas diferenças:

- o texto vem TODO num campo só (`description`), sem separação entre
  requisitos e responsabilidades — então não há o que ordenar, diferente
  do montar_texto da Gupy;
- não há campo de endereço com CEP, só o texto de local que o card de
  busca já traz. Por isso este módulo não tem buscar_endereco: a medição
  de distância dessas vagas continua no nível de cidade.
"""

from scrapers.descricao_comum import MAX_CARACTERES, buscar_next_data, limpar_html

_CAMINHO = ("props", "pageProps", "vacancy")


def buscar_descricao(link: str) -> str:
    """Texto do anúncio, ou "" em qualquer falha."""
    texto = limpar_html(buscar_next_data(link, _CAMINHO).get("description", ""))
    return texto[:MAX_CARACTERES]
