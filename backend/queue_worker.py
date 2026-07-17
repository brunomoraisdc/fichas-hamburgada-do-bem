import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from . import extraction

MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 2
NUM_WORKERS = 3
JOB_TTL_SECONDS = 60 * 60  # jobs concluídos somem da memória após 1h (não acumular dado sensível)


@dataclass
class Job:
    id: str
    image_bytes: bytes
    status: str = "pendente"  # pendente | processando | concluido | erro
    dados: Optional[dict] = None
    campos_incertos: list[str] = field(default_factory=list)
    erro: Optional[str] = None
    criado_em: float = field(default_factory=time.time)


class JobQueue:
    """Fila em processo único: o volume de um evento (dezenas de voluntários,
    não milhares) não justifica um broker externo. O retry aqui cobre falhas
    transitórias do Gemini (rede/instabilidade), não perda de conexão do
    voluntário — essa é resolvida no cliente, fora desta fila."""

    def __init__(self) -> None:
        self._queue: "asyncio.Queue[Job]" = asyncio.Queue()
        self._jobs: dict[str, Job] = {}
        self._workers: list[asyncio.Task] = []

    def start(self, num_workers: int = NUM_WORKERS) -> None:
        self._workers = [
            asyncio.create_task(self._worker_loop()) for _ in range(num_workers)
        ]

    async def stop(self) -> None:
        for worker in self._workers:
            worker.cancel()
        self._workers.clear()

    def submit(self, image_bytes: bytes) -> str:
        job = Job(id=str(uuid.uuid4()), image_bytes=image_bytes)
        self._jobs[job.id] = job
        self._queue.put_nowait(job)
        return job.id

    def get(self, job_id: str) -> Optional[Job]:
        self._purge_expired()
        return self._jobs.get(job_id)

    def discard(self, job_id: str) -> None:
        self._jobs.pop(job_id, None)

    def _purge_expired(self) -> None:
        cutoff = time.time() - JOB_TTL_SECONDS
        expired = [jid for jid, job in self._jobs.items() if job.criado_em < cutoff]
        for jid in expired:
            self._jobs.pop(jid, None)

    async def _worker_loop(self) -> None:
        while True:
            job = await self._queue.get()
            try:
                await self._process(job)
            finally:
                self._queue.task_done()

    async def _process(self, job: Job) -> None:
        job.status = "processando"
        last_error = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                dados = await asyncio.to_thread(extraction.extract_ficha, job.image_bytes)
                job.dados = dados
                job.campos_incertos = extraction.find_uncertain_fields(dados)
                job.status = "concluido"
                job.image_bytes = b""
                return
            except extraction.ExtractionError as e:
                last_error = str(e)
                if attempt < MAX_ATTEMPTS:
                    await asyncio.sleep(BACKOFF_BASE_SECONDS**attempt)

        job.status = "erro"
        job.erro = last_error
        job.image_bytes = b""


job_queue = JobQueue()
