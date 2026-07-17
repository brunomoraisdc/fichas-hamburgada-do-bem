import asyncio
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db, sheets_sync
from .queue_worker import job_queue
from .schemas import JobStatusResponse, ValidateRequest

load_dotenv()

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
EVENT_PASSCODE = os.getenv("EVENT_PASSCODE")


def _check_passcode(senha: str | None) -> None:
    """Protege endpoints administrativos (export, sync manual) de qualquer
    aparelho na mesma rede do hotspot do evento. Não se aplica a upload/status
    /validate — esses ficam abertos de propósito pro voluntário que tem o QR."""
    if EVENT_PASSCODE and senha != EVENT_PASSCODE:
        raise HTTPException(status_code=403, detail="Senha inválida.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    job_queue.start()
    yield
    await job_queue.stop()


app = FastAPI(title="Hamburgada do Bem - Fichas", lifespan=lifespan)


@app.post("/api/upload")
async def upload_ficha(imagem: UploadFile = File(...)) -> dict:
    conteudo = await imagem.read()
    if not conteudo:
        raise HTTPException(status_code=400, detail="Arquivo de imagem vazio.")
    job_id = job_queue.submit(conteudo)
    return {"job_id": job_id}


@app.get("/api/status/{job_id}", response_model=JobStatusResponse)
async def status_ficha(job_id: str) -> JobStatusResponse:
    job = job_queue.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job não encontrado (pode ter expirado).")
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        dados=job.dados,
        campos_incertos=job.campos_incertos,
        erro=job.erro,
    )


@app.post("/api/validate")
async def validate_ficha(payload: ValidateRequest) -> dict:
    job = job_queue.get(payload.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job não encontrado (pode ter expirado).")

    try:
        novo_id = db.insert_ficha(payload.dados.model_dump())
    except db.DuplicateFichaError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    job_queue.discard(payload.job_id)

    try:
        await asyncio.to_thread(sheets_sync.sync_to_sheet)
    except sheets_sync.SheetsSyncError as e:
        logger.warning("Falha ao sincronizar com Google Sheets: %s", e)

    return {"id": novo_id, "status": "salvo"}


@app.get("/api/export")
async def export_fichas(senha: str | None = None) -> FileResponse:
    _check_passcode(senha)

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = tmp.name

    total = db.export_to_excel(tmp_path)
    return FileResponse(
        tmp_path,
        filename="relatorio_fichas.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"X-Total-Fichas": str(total)},
    )


@app.post("/api/sync-sheets")
async def sync_sheets_endpoint(senha: str | None = None) -> dict:
    _check_passcode(senha)
    try:
        total = await asyncio.to_thread(sheets_sync.sync_to_sheet)
    except sheets_sync.SheetsSyncError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"status": "sincronizado", "total_fichas": total}


if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
