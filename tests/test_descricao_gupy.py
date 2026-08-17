"""Testes da captura de descrição da vaga (scrapers/descricao_gupy.py).

montar_texto() é a parte com regra (junta campos, limpa HTML de editor de
texto rico, corta no limite); a chamada de rede em volta é só requests.
Mesma divisão do resto do projeto — testa a função pura, não o serviço.

O HTML dos casos abaixo é o formato real devolvido pela Gupy (conferido na
vaga "Product Owner Pleno - Be.Aliant", que motivou o módulo).
"""

from scrapers import descricao_comum
from scrapers.descricao_gupy import MAX_CARACTERES, buscar_descricao, montar_texto


def test_monta_secoes_na_ordem_que_importa():
    texto = montar_texto({
        "description": "<p>Somos uma empresa de GRC.</p>",
        "responsibilities": "<p>Escrever histórias.</p>",
        "prerequisites": "<p>Experiência como PO.</p>",
    })
    # Requisitos e responsabilidades primeiro: é o que decide o conteúdo da
    # carta. Institucional por último.
    assert texto.index("REQUISITOS") < texto.index("RESPONSABILIDADES")
    assert texto.index("RESPONSABILIDADES") < texto.index("SOBRE A VAGA/EMPRESA")


def test_remove_html_e_preserva_quebra_de_lista():
    texto = montar_texto({"prerequisites": "<ul><li>Scrum</li><li>Kanban</li></ul>"})
    assert "<" not in texto
    assert "Scrum" in texto and "Kanban" in texto
    # Sem quebra por item, a lista viraria "ScrumKanban".
    assert "ScrumKanban" not in texto


def test_desescapa_entidade_html():
    texto = montar_texto({"prerequisites": "<p>Produto &amp; Tecnologia</p>"})
    assert "Produto & Tecnologia" in texto
    assert "&amp;" not in texto


def test_secao_vazia_nao_vira_rotulo_solto():
    texto = montar_texto({"prerequisites": "<p>Só isso.</p>", "responsibilities": ""})
    assert "RESPONSABILIDADES" not in texto


def test_corta_no_limite():
    texto = montar_texto({"prerequisites": "<p>" + ("a" * (MAX_CARACTERES * 2)) + "</p>"})
    assert len(texto) == MAX_CARACTERES


def test_vaga_sem_campo_nenhum_devolve_vazio():
    assert montar_texto({}) == ""


def test_falha_de_rede_devolve_vazio(monkeypatch):
    """Best-effort: a busca de descrição roda dentro do ciclo e não pode
    levantar exceção — sem descrição, a vaga só perde os eixos que dependem
    dela (afinidade e barreira, ver job.py)."""
    descricao_comum._CACHE.clear()

    def _falha(*args, **kwargs):
        raise descricao_comum.requests.ConnectionError("sem rede")

    monkeypatch.setattr(descricao_comum.requests, "get", _falha)
    assert buscar_descricao("https://exemplo.invalido/job/1") == ""


def test_pagina_sem_next_data_devolve_vazio(monkeypatch):
    """Se a Gupy mudar o layout, o módulo degrada pra vazio em vez de
    quebrar o ciclo."""
    descricao_comum._CACHE.clear()

    class _Resposta:
        text = "<html><body>página diferente</body></html>"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(descricao_comum.requests, "get", lambda *a, **k: _Resposta())
    assert buscar_descricao("https://exemplo.invalido/job/2") == ""
