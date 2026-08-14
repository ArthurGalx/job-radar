
import sqlite3
import os
from contextlib import contextmanager

from config import DB_PATH
from job import _normalizar


def _garantir_pasta():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


@contextmanager
def _conectar():
    _garantir_pasta()
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _garantir_coluna_chave_secundaria(conn):
    """Migração leve: bancos criados antes da dedup por empresa+título não
    têm essa coluna. ALTER TABLE ADD COLUMN é seguro rodar preservando dado
    existente.

    MEDIDO: a migração adicionava a coluna mas não preenchia o histórico —
    linha antiga ficava com chave_secundaria NULL pra sempre, já que
    salvar_vaga só grava esse valor em INSERT novo, nunca em UPDATE
    retroativo. Resultado real: 373 linhas NULL, 52 delas duplicata de
    outra linha (mesma empresa+título achada de novo por outra fonte) que
    ja_vista() não pegava — `WHERE chave_secundaria = ?` nunca bate contra
    NULL em SQL, então a vaga reaparecia como "nova" e notificava de novo.
    Backfill roda toda vez que iniciar_db() é chamado (idempotente — só
    tem linha NULL pra processar na primeira vez depois desse fix; depois
    disso salvar_vaga já preenche em toda inserção nova, então o SELECT
    abaixo volta vazio e o loop não faz nada).
    """
    colunas = [linha[1] for linha in conn.execute("PRAGMA table_info(vagas_vistas)")]
    if "chave_secundaria" not in colunas:
        conn.execute("ALTER TABLE vagas_vistas ADD COLUMN chave_secundaria TEXT")

    linhas_nulas = conn.execute(
        "SELECT id, titulo, empresa FROM vagas_vistas WHERE chave_secundaria IS NULL"
    ).fetchall()
    for id_, titulo, empresa in linhas_nulas:
        chave = f"{_normalizar(empresa or '')}|{_normalizar(titulo or '')}"
        conn.execute(
            "UPDATE vagas_vistas SET chave_secundaria = ? WHERE id = ?",
            (chave, id_),
        )


def _garantir_coluna_publicado_em(conn):
    """Mesma lógica de migração leve acima, pra Job.publicado_em (data
    anunciada pela fonte). Precisa estar salva no banco, não só na
    notificação — é o que permite medir latência de verdade depois (tempo
    entre a fonte publicar e o JobRadar notificar), não só mostrar a data
    uma vez e esquecer."""
    colunas = [linha[1] for linha in conn.execute("PRAGMA table_info(vagas_vistas)")]
    if "publicado_em" not in colunas:
        conn.execute("ALTER TABLE vagas_vistas ADD COLUMN publicado_em TEXT")


def _garantir_coluna_modalidade(conn):
    """Mesma lógica de migração leve, pra Job.modalidade (Remoto/Híbrido/
    Presencial como campo próprio, em vez de embutido no texto de local)."""
    colunas = [linha[1] for linha in conn.execute("PRAGMA table_info(vagas_vistas)")]
    if "modalidade" not in colunas:
        conn.execute("ALTER TABLE vagas_vistas ADD COLUMN modalidade TEXT")


class BancoVazioSuspeito(RuntimeError):
    """jobs.db já existia em disco (tinha conteúdo) mas a tabela veio vazia
    depois de iniciar_db() — não é primeiro uso, é banco perdido/corrompido/
    resetado. Ver iniciar_db()."""


def iniciar_db():
    # Precisa checar ANTES de conectar: sqlite3.connect() já cria um arquivo
    # vazio de 0 byte se o caminho não existir, o que destruiria o sinal que
    # queremos capturar (arquivo existia com conteúdo real vs. nunca existiu).
    arquivo_ja_existia = os.path.exists(DB_PATH) and os.path.getsize(DB_PATH) > 0

    with _conectar() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vagas_vistas (
                id TEXT PRIMARY KEY,
                titulo TEXT,
                empresa TEXT,
                local TEXT,
                link TEXT,
                site TEXT,
                encontrada_em TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        _garantir_coluna_chave_secundaria(conn)
        _garantir_coluna_publicado_em(conn)
        _garantir_coluna_modalidade(conn)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_vagas_chave_secundaria "
            "ON vagas_vistas (chave_secundaria)"
        )
        # Tabela chave/valor genérica — usada hoje só pra guardar a data do
        # último heartbeat diário (ver notifier/telegram.py e main.py), mas
        # serve pra qualquer estado simples que precise sobreviver entre
        # ciclos sem virar coluna nova em vagas_vistas.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metadados (
                chave TEXT PRIMARY KEY,
                valor TEXT
            )
        """)
        total_vagas = conn.execute("SELECT COUNT(*) FROM vagas_vistas").fetchone()[0]

    # Se o arquivo já existia com conteúdo mas a tabela veio vazia, não é
    # primeiro uso — é banco sumido/corrompido/resetado (checkout falhou,
    # commit ruim, etc.). Se o ciclo seguisse normal, TODA vaga encontrada
    # bateria "não vista" e o sistema notificaria centenas de vagas antigas
    # de uma vez, de repente. Primeiro uso de verdade (arquivo nunca
    # existiu) não cai aqui — tabela vazia nesse caso é esperada.
    if arquivo_ja_existia and total_vagas == 0:
        raise BancoVazioSuspeito(
            f"{DB_PATH} já existia em disco (tinha conteúdo) mas a tabela "
            "vagas_vistas veio vazia — sinal de banco perdido, corrompido ou "
            "resetado, não de primeiro uso. Abortando antes de rodar "
            "qualquer busca, pra não notificar em massa vagas antigas como "
            "se fossem novas."
        )


def ja_vista(job) -> bool:
    """Recebe o Job inteiro (não só o id): precisa checar duas chaves.

    id = hash da URL (pega repost exato na mesma fonte). chave_secundaria =
    empresa+título normalizados (pega a MESMA vaga publicada em fontes
    diferentes, com URL diferente em cada uma — ver Job.chave_secundaria).
    """
    with _conectar() as conn:
        cursor = conn.execute(
            "SELECT 1 FROM vagas_vistas WHERE id = ? OR chave_secundaria = ? LIMIT 1",
            (job.id, job.chave_secundaria),
        )
        return cursor.fetchone() is not None


def obter_metadado(chave: str) -> str | None:
    with _conectar() as conn:
        cursor = conn.execute("SELECT valor FROM metadados WHERE chave = ?", (chave,))
        linha = cursor.fetchone()
        return linha[0] if linha else None


def definir_metadado(chave: str, valor: str):
    with _conectar() as conn:
        conn.execute(
            "INSERT INTO metadados (chave, valor) VALUES (?, ?) "
            "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
            (chave, valor),
        )


def salvar_vaga(job):
    with _conectar() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO vagas_vistas
                (id, titulo, empresa, local, link, site, chave_secundaria, publicado_em, modalidade)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.id, job.titulo, job.empresa, job.local, job.link, job.site,
                job.chave_secundaria, job.publicado_em, job.modalidade,
            ),
        )