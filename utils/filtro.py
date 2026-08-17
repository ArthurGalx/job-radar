
from collections import Counter

from job import Job, RegrasFiltro


def filtrar_vagas(
    vagas: list[Job],
    regras: RegrasFiltro,
    medir_distancia=None,
) -> tuple[list[Job], Counter]:
    """Além da lista aprovada, devolve um Counter com os escopos que
    causaram reprovação por mercado (ver Job.escopo_rejeitado_por_mercado)
    e quantas vagas cada um levou — ver MEDIDO lá pro motivo (descarte por
    escopo era invisível no log, só dava pra ver bruta → filtrada → nova,
    nunca o porquê).

    `medir_distancia`: callable(Job) -> float | None, aplicado só nas vagas
    APROVADAS e antes do score (ver Job.distancia_km). Entra por parâmetro
    em vez de import direto porque pode fazer rede — assim o filtro segue
    testável offline, e quem monta o ciclo decide se quer medir. None
    (default) = não mede, e nenhuma vaga leva desconto de deslocamento.
    """
    aprovadas = []
    descartes_escopo: Counter = Counter()
    for v in vagas:
        if v.combina_com(regras):
            if medir_distancia is not None:
                v.distancia_km = medir_distancia(v)
            v.relevancia = v.pontuar_relevancia(regras)
            v.motivo = v.motivo_aprovacao(regras)
            aprovadas.append(v)
        else:
            escopo = v.escopo_rejeitado_por_mercado(regras)
            if escopo:
                descartes_escopo[", ".join(sorted(escopo))] += 1
    return aprovadas, descartes_escopo