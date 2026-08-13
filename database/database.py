
import sqlite3
import os
from contextlib import contextmanager

from config import DB_PATH


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
    existente (linha antiga fica com chave_secundaria NULL, só não participa
    da dedup secundária retroativamente — dedup por id continua valendo
    pra ela)."""
    colunas = [linha[1] for linha in conn.execute("PRAGMA table_info(vagas_vistas)")]
    if "chave_secundaria" not in colunas:
        conn.execute("ALTER TABLE vagas_vistas ADD COLUMN chave_secundaria TEXT")


def iniciar_db():
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
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_vagas_chave_secundaria "
            "ON vagas_vistas (chave_secundaria)"
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


def salvar_vaga(job):
    with _conectar() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO vagas_vistas
                (id, titulo, empresa, local, link, site, chave_secundaria)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (job.id, job.titulo, job.empresa, job.local, job.link, job.site, job.chave_secundaria),
        )