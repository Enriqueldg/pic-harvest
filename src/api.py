import asyncio
import hashlib
import io
import os
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum

import requests
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import Response, StreamingResponse
from PIL import Image
from pydantic import BaseModel

from pic_harvest import PicHarvest
from utils import fetch

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
        self.pic_contents: dict[str, bytes] = {}  # filename -> bytes
        self.error: str | None = None


class HarvestRequest(BaseModel):
    url: str
    formats: list[str] | None = None
    min_width: int = 300
    min_height: int = 300


def _url_to_filename(url: str) -> str:
    stem = os.path.basename(url.split("?")[0])
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{url_hash}_{stem}"


def _fetch_pic_to_memory(url: str, min_width: int, min_height: int) -> tuple[str, bytes] | None:
    """Download a single image into memory, returning (filename, content) or None if filtered out."""
    try:
        r = fetch(url, timeout=10)
    except requests.RequestException:
        return None
    content = r.content
    try:
        img = Image.open(io.BytesIO(content))
        width, height = img.size
        if width < min_width or height < min_height:
            return None
    except Exception:
        return None
    return _url_to_filename(url), content


def _run_harvest(job_id: str, req: HarvestRequest) -> None:
    job = _jobs[job_id]
    job.status = Status.running
    try:
        h = PicHarvest(req.url, req.formats, req.min_width, req.min_height)
        h.crawl()
        h.get_all_pages_pics_urls()
        job.pic_urls = h.pics_urls

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {
                pool.submit(_fetch_pic_to_memory, url, req.min_width, req.min_height): url
                for url in h.pics_urls
            }
            for future in as_completed(futures):
                result = future.result()
                if result:
                    filename, content = result
                    job.pic_contents[filename] = content

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
    return {"status": job.status, "pics": list(job.pic_contents.keys()), "error": job.error}


@app.get("/jobs/{job_id}/pics")
def get_pic_urls(job_id: str):
    job = _get_job_or_404(job_id)
    if job.status != Status.done:
        raise HTTPException(status_code=400, detail=f"Job is {job.status.value}, not done")
    return {"pics": job.pic_urls}


@app.get("/jobs/{job_id}/pics/{filename}")
def download_pic(job_id: str, filename: str):
    job = _get_job_or_404(job_id)
    content = job.pic_contents.get(filename)
    if not content:
        raise HTTPException(status_code=404, detail="File not found")
    return Response(content=content, media_type="image/*", headers={
        "Content-Disposition": f'attachment; filename="{filename}"'
    })


@app.get("/jobs/{job_id}/download")
def download_zip(job_id: str):
    job = _get_job_or_404(job_id)
    if job.status != Status.done:
        raise HTTPException(status_code=400, detail=f"Job is {job.status.value}, not done")

    def _iter_zip():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for filename, content in job.pic_contents.items():
                zf.writestr(filename, content)
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