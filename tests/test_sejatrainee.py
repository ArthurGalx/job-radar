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


# ---------------------------------------------------------------------------
# Prazo de inscrição — o dado que mais importa em programa de trainee: vaga
# comum fica aberta até preencher, trainee fecha em data marcada.
# ---------------------------------------------------------------------------

from datetime import date, timedelta

import pytest

from scrapers.sejatrainee import _extrair_prazo, _normalizar_prazo

CASOS_PRAZO = [
    # Formatos reais colhidos nos 20 artigos analisados.
    ("dia-de-mes-por-extenso", "17 de setembro", 9, 17),
    ("dia-barra-mes-maiusculo", "31/AGOSTO", 8, 31),
    ("dia-barra-mes-minusculo", "06/setembro", 9, 6),
    ("dia-barra-mes-numerico", "21/08", 8, 21),
]


@pytest.mark.parametrize(
    "nome,texto,mes,dia",
    CASOS_PRAZO,
    ids=[c[0] for c in CASOS_PRAZO],
)
def test_normaliza_prazo(nome, texto, mes, dia):
    """Sai em ISO, não no texto original: a planilha ordena por essa
    coluna, e "21/08" e "17 de setembro" lado a lado não ordenam."""
    iso = _normalizar_prazo(texto)
    assert iso, f"não normalizou '{texto}'"
    resultado = date.fromisoformat(iso)
    assert (resultado.month, resultado.day) == (mes, dia)


def test_ano_e_inferido_para_o_futuro():
    """O artigo nunca escreve o ano. Data que já passou há mais de 30 dias
    é do ano que vem — o caso do programa que abre em novembro pra turma
    seguinte."""
    ontem = date.today() - timedelta(days=1)
    iso = _normalizar_prazo(f"{ontem.day:02d}/{ontem.month:02d}")
    assert date.fromisoformat(iso).year == ontem.year

    muito_atras = date.today() - timedelta(days=90)
    iso = _normalizar_prazo(f"{muito_atras.day:02d}/{muito_atras.month:02d}")
    assert date.fromisoformat(iso).year == muito_atras.year + 1


def test_texto_sem_data_nao_inventa_prazo():
    assert _normalizar_prazo("em breve") == ""
    assert _normalizar_prazo("32/13") == ""
    assert _extrair_prazo("Programa com inscrições abertas para todo o Brasil.") == ""


def test_extrai_prazo_da_frase_completa():
    texto = "As inscrições para o programa vão até o dia 17 de setembro e são gratuitas."
    assert _extrair_prazo(texto).endswith("-09-17")


def test_prazo_encerrado_nao_filtra_nem_desconta():
    """A data vem de texto corrido e pode ser extraída errada — avisar é
    seguro, esconder não."""
    vaga = _montar("Trainee Ambev 2027 abre inscrições")
    vaga.prazo_inscricao = "2020-01-01"
    assert vaga.prazo_encerrado is True
    assert vaga.combina_com(PERFIL_BR.regras) is True
    assert vaga.pontuar_relevancia(PERFIL_BR.regras) >= 7
