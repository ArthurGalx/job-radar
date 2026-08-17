"""Testes do export pra planilha (exporters/sheets.py).

montar_linha() é função pura (não faz rede, não lê config) — mesma
filosofia do test_filtro.py: testar a camada que tem regra de verdade sem
depender de serviço externo nenhum.

O que importa proteger aqui:
- toda coluna declarada em COLUNAS tem valor na linha (uma coluna a mais no
  Python sem o campo correspondente escreveria a planilha DESALINHADA, com
  o valor caindo na coluna errada — o Apps Script escreve por posição);
- export desligado (sem secret) não levanta exceção nem trava o ciclo, que
  é a regra de ouro do módulo.
"""

import pytest

from exporters import sheets
from exporters.sheets import COLUNAS, exportar_vaga, montar_linha
from job import Job


def _job():
    job = Job(
        titulo="Product Owner Júnior",
        empresa="Empresa Teste",
        local="São Paulo - SP",
        link="https://teste.invalido/vaga/1",
        site="Gupy",
        modalidade="Híbrido",
        publicado_em="há 2 dias",
    )
    job.relevancia = 7
    return job


def test_nao_escreve_coluna_de_acompanhamento():
    """O funil é registrado nas colunas que o usuário criou na planilha
    ("Fiz inscrição?", "Respondeu?"...). O robô não pode escrever nada
    nelas, nem recriar a `situacao` que duplicava esse papel."""
    linha = montar_linha(_job(), "Brasil", "imediata", "Cargo forte")
    assert "situacao" not in linha
    assert "situacao" not in COLUNAS


def test_montar_linha_preenche_todas_as_colunas():
    linha = montar_linha(_job(), "Brasil", "imediata", "Cargo forte")
    assert set(linha) == set(COLUNAS), "linha e COLUNAS divergiram"


def test_montar_linha_usa_dados_da_vaga():
    linha = montar_linha(_job(), "Brasil", "imediata", "Cargo forte")
    assert linha["titulo"] == "Product Owner Júnior"
    assert linha["fonte"] == "Gupy"
    assert linha["relevancia"] == 7
    assert linha["senioridade"] == "Júnior"
    assert linha["canal"] == "imediata"


def test_montar_linha_marca_exploratoria():
    linha = montar_linha(_job(), "Internacional", "digest", "Cargo forte", exploratoria=True)
    assert linha["canal"] == "digest (exploratória)"


def test_exportar_sem_configuracao_nao_faz_rede(monkeypatch):
    """Sem secret, exportar_vaga devolve False e NÃO chama requests — é o
    que garante que rodar local (sem planilha configurada) não vira erro de
    conexão em todo ciclo."""
    monkeypatch.setattr(sheets, "SHEETS_WEBHOOK_URL", "")
    monkeypatch.setattr(sheets, "SHEETS_TOKEN", "")

    def _explode(*args, **kwargs):
        raise AssertionError("não deveria chamar a rede com export desligado")

    monkeypatch.setattr(sheets.requests, "post", _explode)
    assert exportar_vaga(_job(), perfil_nome="Brasil", canal="imediata", motivo="Cargo forte") is False


def test_exportar_engole_falha_de_rede(monkeypatch):
    """Planilha fora do ar não pode derrubar o ciclo — a vaga já foi
    notificada e salva quando o export roda (ver main.py)."""
    monkeypatch.setattr(sheets, "SHEETS_WEBHOOK_URL", "https://exemplo.invalido/exec")
    monkeypatch.setattr(sheets, "SHEETS_TOKEN", "segredo")

    def _falha(*args, **kwargs):
        raise sheets.requests.ConnectionError("sem rede")

    monkeypatch.setattr(sheets.requests, "post", _falha)
    assert exportar_vaga(_job(), perfil_nome="Brasil", canal="imediata", motivo="Cargo forte") is False


def test_exportar_envia_payload_esperado(monkeypatch):
    monkeypatch.setattr(sheets, "SHEETS_WEBHOOK_URL", "https://exemplo.invalido/exec")
    monkeypatch.setattr(sheets, "SHEETS_TOKEN", "segredo")
    capturado = {}

    class _Resposta:
        def raise_for_status(self):
            return None

    def _post(url, json=None, timeout=None):
        capturado["url"] = url
        capturado["json"] = json
        return _Resposta()

    monkeypatch.setattr(sheets.requests, "post", _post)
    assert exportar_vaga(_job(), perfil_nome="Brasil", canal="imediata", motivo="Cargo forte") is True
    assert capturado["json"]["token"] == "segredo"
    assert capturado["json"]["colunas"] == COLUNAS
    assert capturado["json"]["linha"]["link"] == "https://teste.invalido/vaga/1"
