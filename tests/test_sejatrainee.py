"""Testes do scraper de programas de trainee (scrapers/sejatrainee.py).

A fonte é editorial: publica um artigo por programa aberto, mas também
pauta educativa. E não tem cidade — programa de trainee é nacional, e a
alocação sai durante a seleção.
"""

from job import Job
from perfis import PERFIL_BR
from scrapers.sejatrainee import SejaTraineeScraper


def _artigo(titulo, link="https://sejatrainee.com.br/programa-x/", data="2026-08-18T10:00:00"):
    return {
        "title": {"rendered": titulo},
        "link": link,
        "date": data,
        "excerpt": {"rendered": "<p>Inscrições abertas para o programa.</p>"},
    }


def _montar(titulo):
    return SejaTraineeScraper(termos_busca=[])._montar_vaga(_artigo(titulo))


def test_artigo_de_programa_vira_vaga():
    vaga = _montar("Grupo Safra abre trainee com salário de R$ 11.000")
    assert vaga is not None
    assert vaga.site == "Seja Trainee"
    assert vaga.publicado_em == "2026-08-18"
    assert vaga.programa_nacional is True
    assert "Inscrições abertas" in vaga.descricao


def test_pauta_educativa_e_descartada():
    """O site também publica conteúdo de orientação, que não é anúncio."""
    assert _montar("O que é trainee e como funciona o programa") is None
    assert _montar("Dicas para se dar bem na entrevista de emprego") is None


def test_artigo_sem_link_e_descartado():
    scraper = SejaTraineeScraper(termos_busca=[])
    assert scraper._montar_vaga({"title": {"rendered": "Trainee X"}, "link": ""}) is None


def test_programa_nacional_passa_no_filtro_sem_cidade():
    """Sem a marca de programa nacional, a allowlist de São Paulo
    descartaria 100% desta fonte."""
    vaga = _montar("Trainee Itaú 2027 abre inscrições")
    assert vaga.local == "Brasil (programa nacional)"
    assert vaga.combina_com(PERFIL_BR.regras) is True


def test_vaga_comum_sem_cidade_continua_barrada():
    """A exceção vale só pra quem a FONTE marcou como programa nacional —
    não é um buraco no filtro de cidade."""
    vaga = Job(titulo="Product Owner", empresa="X", local="Brasil",
               link="https://teste.invalido/1", site="LinkedIn", modalidade="Presencial")
    assert vaga.combina_com(PERFIL_BR.regras) is False


def test_trainee_nacional_pontua_alto():
    """Cargo forte (3) + nível alvo (2) + local (2) — é o que o usuário
    quer ver no topo durante a temporada."""
    vaga = _montar("Programa de Trainee 2027 da Ambev")
    assert vaga.pontuar_relevancia(PERFIL_BR.regras) >= 7
