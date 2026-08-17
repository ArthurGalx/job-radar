"""Testes do scraper de ATS (scrapers/ats.py) e do desconto por setor
restrito por contrato (job.barreira).

O parsing de cada plataforma é testado contra o formato REAL devolvido
pelas APIs — conferido ao vivo na descoberta da lista de empresas, não
inventado. As três diferem no nome de quase todo campo, e é exatamente aí
que um scraper quebra em silêncio: um campo com nome errado não levanta
erro, só devolve vaga sem título ou sem local, que o filtro descarta
depois sem ninguém entender por quê.
"""

import pytest

from config import EMPRESAS_ATS
from job import Job
from perfis import PERFIL_BR
from scrapers.ats import AtsScraper, _modalidade


def _scraper():
    return AtsScraper(termos_busca=[], empresas=[])


def test_greenhouse_extrai_campos(monkeypatch):
    monkeypatch.setattr(AtsScraper, "_get", lambda self, url: {"jobs": [{
        "title": "Product Owner Pleno",
        "location": {"name": "São Paulo, SP"},
        "absolute_url": "https://boards.greenhouse.io/x/jobs/1",
        "updated_at": "2026-08-17T12:00:00-04:00",
        "content": "&lt;p&gt;Requisitos&lt;/p&gt;&lt;ul&gt;&lt;li&gt;APIs&lt;/li&gt;&lt;/ul&gt;",
    }]})
    vaga = _scraper()._greenhouse("Empresa X", "x")[0]
    assert vaga.titulo == "Product Owner Pleno"
    assert vaga.empresa == "Empresa X"
    assert vaga.local == "São Paulo, SP"
    assert vaga.publicado_em == "2026-08-17"
    # O Greenhouse devolve o HTML escapado DUAS vezes (&lt;p&gt;), então a
    # limpeza precisa desescapar antes de tirar tag — senão o texto chega
    # cheio de "&lt;p&gt;" e o eixo de afinidade lê lixo.
    assert "<" not in vaga.descricao and "APIs" in vaga.descricao


def test_lever_extrai_campos(monkeypatch):
    monkeypatch.setattr(AtsScraper, "_get", lambda self, url: [{
        "text": "Product Owner",
        "categories": {"location": "São Paulo"},
        "hostedUrl": "https://jobs.lever.co/x/1",
        "workplaceType": "remote",
        "descriptionPlain": "Discovery com usuários.",
    }])
    vaga = _scraper()._lever("Empresa Y", "y")[0]
    assert vaga.titulo == "Product Owner"
    assert vaga.modalidade == "Remoto"  # veio do campo, não do texto de local
    assert "Discovery" in vaga.descricao


def test_ashby_extrai_campos(monkeypatch):
    monkeypatch.setattr(AtsScraper, "_get", lambda self, url: {"jobs": [{
        "title": "Associate Product Manager",
        "location": "São Paulo",
        "jobUrl": "https://jobs.ashbyhq.com/x/1",
        "isRemote": True,
        "publishedAt": "2026-08-15T00:00:00Z",
        "descriptionPlain": "Automação de processos.",
    }]})
    vaga = _scraper()._ashby("Empresa Z", "z")[0]
    assert vaga.titulo == "Associate Product Manager"
    assert vaga.modalidade == "Remoto"
    assert vaga.publicado_em == "2026-08-15"


def test_empresa_com_erro_nao_derruba_as_outras(monkeypatch):
    """Slug muda quando a empresa troca de plano ou de plataforma — uma
    falha não pode custar o catálogo das outras 21."""
    def _get(self, url):
        if "quebrada" in url:
            raise ValueError("json inválido")
        return {"jobs": [{"title": "Product Owner", "location": {"name": "São Paulo"}}]}

    monkeypatch.setattr(AtsScraper, "_get", _get)
    scraper = AtsScraper(termos_busca=[], empresas=[
        ("Quebrada", "greenhouse", "quebrada"),
        ("Boa", "greenhouse", "boa"),
    ])
    vagas = scraper.buscar_vagas()
    assert len(vagas) == 1 and vagas[0].empresa == "Boa"


def test_site_e_o_mesmo_para_todas_as_empresas(monkeypatch):
    """O relatório de precisão agrupa por site; 22 valores distintos
    picotariam a métrica em amostras minúsculas."""
    monkeypatch.setattr(AtsScraper, "_get", lambda self, url: {"jobs": [
        {"title": "Product Owner", "location": {"name": "São Paulo"}}
    ]})
    scraper = AtsScraper(termos_busca=[], empresas=[
        ("A", "greenhouse", "a"), ("B", "greenhouse", "b"),
    ])
    assert {v.site for v in scraper.buscar_vagas()} == {"ATS"}


CASOS_MODALIDADE = [
    ("remoto-declarado-vence", "São Paulo", True, "Remoto"),
    ("hibrido-no-texto", "São Paulo (Hybrid)", None, "Híbrido"),
    ("remoto-no-texto", "Remote - Brazil", None, "Remoto"),
    ("sem-sinal-e-presencial", "São Paulo, SP", None, "Presencial"),
]


@pytest.mark.parametrize(
    "nome,local,declarado,esperado",
    CASOS_MODALIDADE,
    ids=[c[0] for c in CASOS_MODALIDADE],
)
def test_modalidade(nome, local, declarado, esperado):
    assert _modalidade(local, declarado) == esperado


def test_lista_de_empresas_bem_formada():
    plataformas = {"greenhouse", "lever", "ashby"}
    for nome, plataforma, slug in EMPRESAS_ATS:
        assert plataforma in plataformas, f"{nome}: plataforma '{plataforma}' não existe"
        assert nome and slug


# ---------------------------------------------------------------------------
# Setor restrito por contrato (cláusula de não concorrência de 12 meses).
# ---------------------------------------------------------------------------

def _vaga(titulo="Product Owner Pleno", empresa="Empresa", descricao=""):
    job = Job(titulo=titulo, empresa=empresa, local="São Paulo - SP",
              link=f"https://teste.invalido/{empresa}", site="ATS", modalidade="Híbrido")
    job.descricao = descricao
    job.distancia_km = 5.0
    return job


def test_empresa_conhecida_do_setor_restrito():
    pontos, motivos = _vaga(empresa="QuintoAndar").barreira(PERFIL_BR.regras)
    assert pontos == -3 and motivos == ["setor restrito por contrato"]


def test_setor_restrito_pelo_texto_do_anuncio():
    """Proptech que não é conhecida pelo nome se identifica no texto."""
    pontos, _ = _vaga(empresa="Startup Nova",
                      descricao="Plataforma de locação de imóveis para coliving.").barreira(PERFIL_BR.regras)
    assert pontos == -3


def test_vaga_fora_do_setor_nao_desconta():
    pontos, motivos = _vaga(empresa="Nubank", descricao="Produto de crédito.").barreira(PERFIL_BR.regras)
    assert pontos == 0 and motivos == []


def test_setor_restrito_derruba_o_score_sem_filtrar():
    """Desconto, não filtro: a cláusula tem prazo de 12 meses, e a vaga
    continua sendo notificada — só vai pro fim da fila."""
    vaga = _vaga(empresa="QuintoAndar", descricao="APIs, automação e dashboards.")
    assert vaga.combina_com(PERFIL_BR.regras) is True
    assert vaga.pontuar_relevancia(PERFIL_BR.regras) == 7  # 3+2+2+3-3


def test_credito_imobiliario_nao_e_setor_restrito():
    """MEDIDO nas vagas reais da XP: "crédito imobiliário" é produto que
    banco e corretora citam no texto institucional de toda vaga — marcava
    6 vagas de mercado financeiro como setor proibido. O que conta é o
    NEGÓCIO da empresa, não um produto que ela vende."""
    vaga = _vaga(empresa="XP", descricao="Oferecemos crédito imobiliário, seguros e investimentos.")
    assert vaga.barreira(PERFIL_BR.regras) == (0, [])
