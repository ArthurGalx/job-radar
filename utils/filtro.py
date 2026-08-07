
from job import Job


def filtrar_vagas(vagas: list[Job], keywords: list[str], cidades: list[str]) -> list[Job]:
    return [v for v in vagas if v.combina_com(keywords, cidades)]