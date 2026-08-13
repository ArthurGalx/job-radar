
from job import Job


def filtrar_vagas(
    vagas: list[Job],
    keywords_forte: list[str],
    keywords_ambiguo: list[str],
    qualificadores: list[str],
    cidades: list[str],
) -> list[Job]:
    return [
        v for v in vagas
        if v.combina_com(keywords_forte, keywords_ambiguo, qualificadores, cidades)
    ]