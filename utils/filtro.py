
from job import Job, RegrasFiltro


def filtrar_vagas(vagas: list[Job], regras: RegrasFiltro) -> list[Job]:
    return [v for v in vagas if v.combina_com(regras)]