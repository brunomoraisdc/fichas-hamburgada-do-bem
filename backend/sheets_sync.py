import os
from pathlib import Path

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

from . import db

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

SHEET_NAME = os.getenv("SHEET_NAME")
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")


class SheetsSyncError(Exception):
    pass


def _get_client() -> gspread.Client:
    if not SERVICE_ACCOUNT_FILE or not Path(SERVICE_ACCOUNT_FILE).exists():
        raise SheetsSyncError(
            "GOOGLE_SERVICE_ACCOUNT_FILE não configurado ou o arquivo não existe. "
            "Veja o passo a passo em CLAUDE.md."
        )
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


def sync_to_sheet() -> int:
    """Sobrescreve a aba inteira com o estado atual do SQLite. Sem fila/retry:
    como cada chamada reescreve tudo, uma falha isolada se autocorrige na
    próxima ficha validada (ou no próximo sync manual)."""
    if not SHEET_NAME:
        raise SheetsSyncError("SHEET_NAME não configurado no .env.")

    df = db.fetch_fichas_df()
    df["pode_sair_sozinho"] = df["pode_sair_sozinho"].map({1: "Sim", 0: "Não"})
    df = df.fillna("")

    client = _get_client()
    try:
        spreadsheet = client.open(SHEET_NAME)
    except gspread.SpreadsheetNotFound as e:
        raise SheetsSyncError(
            f"Planilha '{SHEET_NAME}' não encontrada no Google Drive da conta de "
            "serviço. Crie a planilha e compartilhe com o client_email do JSON de "
            "credenciais (veja CLAUDE.md)."
        ) from e

    worksheet = spreadsheet.sheet1
    worksheet.clear()
    rows = [df.columns.tolist()] + df.values.tolist()
    worksheet.update(values=rows, range_name="A1")
    return len(df)
