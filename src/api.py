import asyncio
import hashlib
import io
import os
import uuid
import zipfile
from enum import Enum

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from pic_harvest import OUTPUT_DIR, PicHarvest

app = FastAPI(title="pic-harvest")

_jobs: dict[str, "Job"] = {}


class Status(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class Job:
    def __init__(self):
        self.status = Status.pending
        self.pic_urls: list[str] = []
        self.error: str | None = None

    def filenames(self) -> list[str]:
        return [self._url_to_filename(u) for u in self.pic_urls]

    def _url_to_filename(url: str) -> str:
        stem = os.path.basename(url.split("?")[0])
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        return f"{url_hash}_{stem}"


class HarvestRequest(BaseModel):
    url: str
    formats: list[str] | None = None
    min_width: int = 300
    min_height: int = 300


def _run_harvest(job_id: str, req: HarvestRequest) -> None:
    job = _jobs[job_id]
    job.status = Status.running
    try:
        h = PicHarvest(req.url, req.formats, req.min_width, req.min_height)
        h.crawl()
        h.get_all_pages_pics_urls()
        h.download_all_pics()
        job.pic_urls = h.pics_urls
        job.status = Status.done
    except Exception as exc:
        job.status = Status.failed
        job.error = str(exc)


async def _run_harvest_async(job_id: str, req: HarvestRequest) -> None:
    await asyncio.to_thread(_run_harvest, job_id, req)


@app.post("/jobs", status_code=202)
async def create_job(req: HarvestRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    _jobs[job_id] = Job()
    background_tasks.add_task(_run_harvest_async, job_id, req)
    return {"job_id": job_id}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = _get_job_or_404(job_id)
    return {"status": job.status, "pics": job.filenames(), "error": job.error}


@app.get("/jobs/{job_id}/pics")
def get_pic_urls(job_id: str):
    job = _get_job_or_404(job_id)
    if job.status != Status.done:
        raise HTTPException(status_code=400, detail=f"Job is {job.status.value}, not done")
    return {"pics": job.pic_urls}


@app.get("/pics/{filename}")
def download_pic(filename: str):
    path = (OUTPUT_DIR / filename).resolve()
    if not path.is_relative_to(OUTPUT_DIR.resolve()) or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=filename)


@app.get("/jobs/{job_id}/download")
def download_zip(job_id: str):
    job = _get_job_or_404(job_id)
    if job.status != Status.done:
        raise HTTPException(status_code=400, detail=f"Job is {job.status.value}, not done")

    def _iter_zip():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for filename in job.filenames():
                path = OUTPUT_DIR / filename
                if path.is_file():
                    zf.write(path, filename)
        buf.seek(0)
        yield from buf

    return StreamingResponse(
        _iter_zip(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="pics_{job_id[:8]}.zip"'},
    )


def _get_job_or_404(job_id: str) -> Job:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job