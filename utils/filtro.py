
from job import Job


def filtrar_vagas(
    vagas: list[Job],
    keywords_forte: list[str],
    keywords_ambiguo: list[str],
    qualificadores_dados: list[str],
    ferramentas_titulo: list[str],
    qualificadores_cargo: list[str],
    cidades: list[str],
) -> list[Job]:
    return [
        v for v in vagas
        if v.combina_com(
            keywords_forte,
            keywords_ambiguo,
            qualificadores_dados,
            ferramentas_titulo,
            qualificadores_cargo,
            cidades,
        )
    ]