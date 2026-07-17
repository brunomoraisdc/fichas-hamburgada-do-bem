import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "hamburgada.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS fichas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_ficha TEXT,
    nome_crianca TEXT,
    idade_crianca INTEGER,
    sala TEXT,
    nome_responsavel TEXT,
    rg_responsavel TEXT,
    telefone_principal TEXT,
    telefone_secundario TEXT,
    pode_sair_sozinho INTEGER,
    dados_completos TEXT NOT NULL,
    criado_em TEXT NOT NULL,
    UNIQUE(numero_ficha, nome_crianca)
);
"""


class DuplicateFichaError(Exception):
    def __init__(self, numero_ficha: str | None, nome_crianca: str | None):
        self.numero_ficha = numero_ficha
        self.nome_crianca = nome_crianca
        super().__init__(
            f"Ficha já cadastrada (numero_ficha={numero_ficha!r}, nome_crianca={nome_crianca!r})"
        )


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _get_connection() as conn:
        conn.execute(_SCHEMA)


def insert_ficha(dados: dict) -> int:
    crianca = dados.get("crianca") or {}
    responsavel = dados.get("responsavel") or {}
    autorizacoes = dados.get("autorizacoes") or {}

    pode_sair_sozinho = autorizacoes.get("pode_sair_sozinho")

    with _get_connection() as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO fichas (
                    numero_ficha, nome_crianca, idade_crianca, sala,
                    nome_responsavel, rg_responsavel, telefone_principal, telefone_secundario,
                    pode_sair_sozinho, dados_completos, criado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    crianca.get("numero_ficha"),
                    crianca.get("nome"),
                    crianca.get("idade"),
                    crianca.get("sala"),
                    responsavel.get("nome"),
                    responsavel.get("rg"),
                    responsavel.get("telefone_principal"),
                    responsavel.get("telefone_secundario"),
                    None if pode_sair_sozinho is None else int(bool(pode_sair_sozinho)),
                    json.dumps(dados, ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            raise DuplicateFichaError(
                crianca.get("numero_ficha"), crianca.get("nome")
            ) from e


def fetch_fichas_df() -> pd.DataFrame:
    with _get_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT numero_ficha, nome_crianca, idade_crianca, sala,
                   nome_responsavel, rg_responsavel, telefone_principal, telefone_secundario,
                   pode_sair_sozinho, criado_em
            FROM fichas
            ORDER BY id
            """,
            conn,
        )


def export_to_excel(path: str) -> int:
    df = fetch_fichas_df()

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Fichas")
        worksheet = writer.sheets["Fichas"]
        for column in worksheet.columns:
            max_length = max((len(str(cell.value)) for cell in column), default=0)
            worksheet.column_dimensions[column[0].column_letter].width = max_length + 2

    return len(df)
