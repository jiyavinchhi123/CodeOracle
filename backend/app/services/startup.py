import asyncio
from pathlib import Path

from app.config import Settings
from app.models.analysis import AnalysisStatus
from app.services.analysis_pipeline import AnalysisPipeline
from app.services.storage import JobStorage
from app.utils.security import SOURCE_EXTENSIONS


def _project_name_from_job(job) -> str:
    label = job.source_label or job.id
    if job.source_type == "zip":
        return Path(label).stem or "uploaded-project"
    if job.source_type == "github" and "/" in label:
        return label.rstrip("/").split("/")[-1]
    return label or job.id


def _workspace_has_sources(workspace: Path) -> bool:
    if not workspace.exists():
        return False
    for path in workspace.rglob("*"):
        if path.is_file() and path.suffix.lower() in SOURCE_EXTENSIONS:
            return True
    return False


async def recover_jobs_on_startup(storage: JobStorage, settings: Settings) -> None:
    """Recover legacy job folders and resume or fail interrupted analyses."""
    pipeline = AnalysisPipeline(settings, storage)

    for job_id in storage.list_job_ids():
        job = storage.get_job(job_id)
        if not job:
            continue

        workspace = storage.get_workspace(job_id)
        result = storage.get_result(job_id)

        if result:
            continue

        if job.status in (
            AnalysisStatus.COMPLETED,
            AnalysisStatus.FAILED,
        ):
            continue

        if not _workspace_has_sources(workspace):
            if job.status != AnalysisStatus.PENDING:
                storage.update_job_status(
                    job_id,
                    AnalysisStatus.FAILED,
                    error="Analysis interrupted: no source files found in job workspace.",
                )
            continue

        project_name = _project_name_from_job(job)
        if job.status == AnalysisStatus.PENDING:
            storage.update_job_status(job_id, AnalysisStatus.INGESTING)

        storage.update_job_status(job_id, AnalysisStatus.ANALYZING)
        asyncio.create_task(pipeline.run(job_id, project_name))
