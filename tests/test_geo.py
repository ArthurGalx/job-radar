"""Testes da distância vaga ↔ casa (utils/geo.py) e do desconto no score.

O cálculo é local e determinístico (tabela de coordenadas + haversine), sem
geocodificação online — então dá pra testar o resultado real, não um mock.
Os endereços abaixo são os que a Gupy devolveu em vagas de verdade.

As coordenadas da tabela são aproximações de centro de região (erro de 1-3
km), então as asserções são por FAIXA — é a granularidade que o desconto
usa de fato (dentro do raio / longe / muito longe), não o número exato.
"""

import pytest

from job import Job
from perfis import PERFIL_BR
from utils.geo import RAIO_IDEAL_KM, distancia_km


CASOS_DISTANCIA = [
    # (nome, texto de local, modalidade, faixa esperada em km)
    # Endereços reais devolvidos pela Gupy, com CEP — o sinal mais preciso.
    ("mooca-do-lado-de-casa", "Rua da Mooca, 500, São Paulo, Brasil, 03104-000", "Presencial", (0, RAIO_IDEAL_KM)),
    ("centro-dentro-do-raio", "Rua Augusta, 100, São Paulo, Brasil, 01305-000", "Presencial", (0, RAIO_IDEAL_KM)),
    ("berrini-fora-do-raio", "Avenida das Nações Unidas, 14261, São Paulo, Brasil, 04795-100", "Híbrido", (RAIO_IDEAL_KM, 20)),
    ("barueri-muito-longe", "Alameda Araguaia, 2104, Barueri, São Paulo, Brasil, 06455-000", "Híbrido", (20, 40)),
    # Sem CEP: cai no nome da cidade. "São Paulo" sozinho usa o centro da
    # capital e fica dentro do raio de propósito — não dá pra saber o
    # bairro, e o projeto não penaliza por falta de informação.
    ("cidade-sem-cep-sao-paulo", "São Paulo - SP", "Híbrido", (0, RAIO_IDEAL_KM)),
    ("cidade-sem-cep-barueri", "Barueri - SP", "Presencial", (20, 40)),
    ("cidade-sem-cep-campinas", "Campinas - SP", "Presencial", (60, 120)),
]


@pytest.mark.parametrize(
    "nome,local,modalidade,faixa",
    CASOS_DISTANCIA,
    ids=[c[0] for c in CASOS_DISTANCIA],
)
def test_distancia_km(nome, local, modalidade, faixa):
    d = distancia_km(local, modalidade)
    assert d is not None
    assert faixa[0] <= d <= faixa[1], f"{d} km fora da faixa {faixa}"


def test_remota_nao_tem_distancia():
    """Sem deslocamento não há o que penalizar — mesmo que o texto de local
    cite uma cidade."""
    assert distancia_km("São Paulo - SP", "Remoto") is None


def test_endereco_irreconhecivel_devolve_none():
    assert distancia_km("Marte, Sistema Solar", "Presencial") is None


# ---------------------------------------------------------------------------
# Efeito no score (job.pontuar_relevancia)
# ---------------------------------------------------------------------------

def _vaga(distancia):
    job = Job(
        titulo="Product Owner Pleno", empresa="Teste", local="São Paulo - SP",
        link=f"https://teste.invalido/{distancia}", site="Gupy", modalidade="Presencial",
    )
    job.distancia_km = distancia
    return job


CASOS_SCORE = [
    ("dentro-do-raio-sem-desconto", 5.0, 7),
    ("no-limite-do-raio-sem-desconto", float(RAIO_IDEAL_KM), 7),
    ("longe-desconta-um", 15.0, 6),
    ("muito-longe-desconta-dois", 27.0, 5),
    # Distância desconhecida não penaliza — mesma regra de "não penalizar
    # por falta de informação" que vale pra senioridade.
    ("desconhecida-sem-desconto", None, 7),
]


@pytest.mark.parametrize(
    "nome,distancia,esperado",
    CASOS_SCORE,
    ids=[c[0] for c in CASOS_SCORE],
)
def test_desconto_de_distancia_no_score(nome, distancia, esperado):
    assert _vaga(distancia).pontuar_relevancia(PERFIL_BR.regras) == esperado


def test_distancia_nao_filtra_vaga():
    """Desconto é de ranking, nunca de aprovação: vaga longe continua
    passando no filtro, só cai no score."""
    assert _vaga(50.0).combina_com(PERFIL_BR.regras) is True
