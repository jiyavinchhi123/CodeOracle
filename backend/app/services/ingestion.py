import asyncio
from pathlib import Path

from app.config import Settings
from app.models.analysis import AnalysisStatus
from app.services.analysis_pipeline import AnalysisPipeline
from app.services.storage import JobStorage
from app.utils.github import GitHubError, download_github_repo
from app.utils.security import parse_github_url
from app.utils.zip_utils import ZipValidationError, validate_and_extract_zip


class IngestionService:
    def __init__(self, settings: Settings, storage: JobStorage) -> None:
        self.settings = settings
        self.storage = storage
        self.pipeline = AnalysisPipeline(settings, storage)

    async def ingest_zip(self, zip_bytes: bytes, filename: str) -> str:
        job = self.storage.create_job("zip", filename)
        self.storage.update_job_status(job.id, AnalysisStatus.INGESTING, "Extracting uploaded archive…")
        asyncio.create_task(self._ingest_zip_job(job.id, zip_bytes, filename))
        return job.id

    async def _ingest_zip_job(self, job_id: str, zip_bytes: bytes, filename: str) -> None:
        workspace = self.storage.get_workspace(job_id)
        try:
            validate_and_extract_zip(zip_bytes, workspace, self.settings)
        except ZipValidationError as exc:
            self.storage.update_job_status(job_id, AnalysisStatus.FAILED, error=str(exc), clear_progress=True)
            return

        project_name = Path(filename).stem or "uploaded-project"
        await self._run_pipeline(job_id, project_name)

    async def ingest_github(self, url: str) -> str:
        parse_github_url(url)
        job = self.storage.create_job("github", url)
        self.storage.update_job_status(
            job.id, AnalysisStatus.INGESTING, "Downloading repository from GitHub…"
        )
        asyncio.create_task(self._ingest_github_job(job.id, url))
        return job.id

    async def _ingest_github_job(self, job_id: str, url: str) -> None:
        workspace = self.storage.get_workspace(job_id)
        try:
            project_name, _ = await download_github_repo(url, workspace, self.settings)
        except GitHubError as exc:
            self.storage.update_job_status(job_id, AnalysisStatus.FAILED, error=str(exc), clear_progress=True)
            return

        await self._run_pipeline(job_id, project_name)

    async def _run_pipeline(self, job_id: str, project_name: str) -> None:
        try:
            await self.pipeline.run(job_id, project_name)
        except Exception as exc:
            self.storage.update_job_status(job_id, AnalysisStatus.FAILED, error=str(exc), clear_progress=True)
