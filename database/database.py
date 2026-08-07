
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


def ja_vista(job_id: str) -> bool:
    with _conectar() as conn:
        cursor = conn.execute(
            "SELECT 1 FROM vagas_vistas WHERE id = ?", (job_id,)
        )
        return cursor.fetchone() is not None


def salvar_vaga(job):
    with _conectar() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO vagas_vistas (id, titulo, empresa, local, link, site)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job.id, job.titulo, job.empresa, job.local, job.link, job.site),
        )