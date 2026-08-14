from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.dependencies import get_storage
from app.config import get_settings
from app.models.requests import AnalyzeGitHubRequest, JobStatusResponse
from app.services.errors import IngestionError
from app.services.ingestion import IngestionService
from app.services.storage import JobStorage
from app.utils.security import parse_github_url

router = APIRouter(prefix="/api", tags=["analysis"])


@router.get("/health")
async def health():
    settings = get_settings()
    return {
        "status": "ok",
        "service": "CodeOracle",
        "llm_configured": settings.llm_configured,
    }


@router.post("/analyze/zip", response_model=JobStatusResponse)
async def analyze_zip(
    file: UploadFile = File(...),
    storage: JobStorage = Depends(get_storage),
):
    settings = get_settings()

    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a .zip archive")

    content = await file.read()
    ingestion = IngestionService(settings, storage)

    try:
        job_id = await ingestion.ingest_zip(content, file.filename)
    except IngestionError as exc:
        job = storage.get_job(exc.job_id)
        return JobStatusResponse(
            job_id=exc.job_id,
            status=job.status if job else "failed",
            error=exc.message,
        )

    job = storage.get_job(job_id)
    return JobStatusResponse(job_id=job_id, status=job.status)


@router.post("/analyze/github", response_model=JobStatusResponse)
async def analyze_github(
    body: AnalyzeGitHubRequest,
    storage: JobStorage = Depends(get_storage),
):
    settings = get_settings()

    try:
        parse_github_url(body.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ingestion = IngestionService(settings, storage)
    try:
        job_id = await ingestion.ingest_github(body.url)
    except IngestionError as exc:
        job = storage.get_job(exc.job_id)
        return JobStatusResponse(
            job_id=exc.job_id,
            status=job.status if job else "failed",
            error=exc.message,
        )

    job = storage.get_job(job_id)
    return JobStatusResponse(job_id=job_id, status=job.status)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, storage: JobStorage = Depends(get_storage)):
    job = storage.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found. The server may have restarted before persistence was enabled — please analyze again.",
        )

    result = storage.get_result(job_id)
    return JobStatusResponse(
        job_id=job_id,
        status=job.status,
        progress=job.progress,
        error=job.error,
        result=result,
    )


@router.get("/jobs/{job_id}/files/{file_path:path}")
async def get_file_content(
    job_id: str,
    file_path: str,
    storage: JobStorage = Depends(get_storage),
):
    result = storage.get_result(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    if file_path in result.file_contents:
        return {"path": file_path, "content": result.file_contents[file_path]}

    raise HTTPException(status_code=404, detail="File not found")
