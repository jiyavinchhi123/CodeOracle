import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import Settings
from app.models.analysis import AnalysisJob, AnalysisResult, AnalysisStatus, _coerce_legacy_graph_data
from app.utils.security import safe_artifact_name


class JobStorage:
    """Job registry with filesystem persistence (survives server restarts)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._jobs: dict[str, AnalysisJob] = {}
        self._results: dict[str, AnalysisResult] = {}
        self.settings.upload_path.mkdir(parents=True, exist_ok=True)
        self._load_from_disk()

    def _job_meta_path(self, job_id: str) -> Path:
        return self.settings.upload_path / job_id / "job.json"

    def _result_path(self, job_id: str) -> Path:
        return self.settings.upload_path / job_id / "result.json"

    def _persist_job(self, job: AnalysisJob) -> None:
        path = self._job_meta_path(job.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(job.model_dump_json(indent=2), encoding="utf-8")

    def _persist_result(self, result: AnalysisResult) -> None:
        path = self._result_path(result.job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    def _load_from_disk(self) -> None:
        for entry in self.settings.upload_path.iterdir():
            if not entry.is_dir():
                continue
            job_id = entry.name
            try:
                uuid.UUID(job_id)
            except ValueError:
                continue

            meta_path = entry / "job.json"
            if meta_path.exists():
                job = AnalysisJob.model_validate_json(meta_path.read_text(encoding="utf-8"))
                self._jobs[job_id] = job
            else:
                # Recover jobs from workspace folders (e.g. after reload before job.json was written)
                has_sources = any(
                    p.is_file() and p.suffix.lower() in {".py", ".java"}
                    for p in entry.rglob("*")
                )
                job = AnalysisJob(
                    id=job_id,
                    status=AnalysisStatus.ANALYZING if has_sources else AnalysisStatus.PENDING,
                    source_type="unknown",
                    source_label=job_id,
                    workspace_path=str(entry.resolve()),
                    created_at=datetime.now(timezone.utc),
                )
                self._jobs[job_id] = job
                self._persist_job(job)

            result_path = entry / "result.json"
            if result_path.exists():
                result = self._read_result(job_id)
                if result:
                    self._results[job_id] = result
                    if job_id in self._jobs:
                        self._jobs[job_id].status = result.status
                        self._jobs[job_id].error = result.error

    def list_job_ids(self) -> list[str]:
        return list(self._jobs.keys())

    def create_job(self, source_type: str, source_label: str) -> AnalysisJob:
        job_id = str(uuid.uuid4())
        workspace = self.settings.upload_path / job_id
        workspace.mkdir(parents=True, exist_ok=True)
        job = AnalysisJob(
            id=job_id,
            status=AnalysisStatus.PENDING,
            source_type=source_type,
            source_label=source_label,
            workspace_path=str(workspace.resolve()),
            created_at=datetime.now(timezone.utc),
        )
        self._jobs[job_id] = job
        self._persist_job(job)
        return job

    def get_job(self, job_id: str) -> Optional[AnalysisJob]:
        if job_id in self._jobs:
            return self._jobs[job_id]

        # Attempt lazy load if directory exists
        workspace = self.settings.upload_path / job_id
        if not workspace.is_dir():
            return None

        meta_path = workspace / "job.json"
        if meta_path.exists():
            job = AnalysisJob.model_validate_json(meta_path.read_text(encoding="utf-8"))
        else:
            has_sources = any(
                p.is_file() and p.suffix.lower() in {".py", ".java"}
                for p in workspace.rglob("*")
            )
            job = AnalysisJob(
                id=job_id,
                status=AnalysisStatus.ANALYZING if has_sources else AnalysisStatus.PENDING,
                source_type="unknown",
                source_label=job_id,
                workspace_path=str(workspace.resolve()),
                created_at=datetime.now(timezone.utc),
            )
            self._persist_job(job)

        self._jobs[job_id] = job
        result_path = workspace / "result.json"
        if result_path.exists():
            result = self._read_result(job_id)
            if result:
                self._results[job_id] = result
        return job

    def update_job_status(
        self,
        job_id: str,
        status: AnalysisStatus,
        progress: Optional[str] = None,
        error: Optional[str] = None,
        *,
        clear_progress: bool = False,
    ) -> None:
        job = self.get_job(job_id)
        if job:
            job.status = status
            if clear_progress:
                job.progress = None
            elif progress is not None:
                job.progress = progress
            if error is not None:
                job.error = error
            self._persist_job(job)

    def save_result(self, result: AnalysisResult) -> None:
        self._results[result.job_id] = result
        job = self.get_job(result.job_id)
        if job:
            job.status = result.status
            job.error = result.error
            job.progress = None
            self._persist_job(job)
        self._persist_result(result)

    def get_result(self, job_id: str) -> Optional[AnalysisResult]:
        if job_id in self._results:
            return self._results[job_id]
        result = self._read_result(job_id)
        if result:
            self._results[job_id] = result
        return result

    def _read_result(self, job_id: str) -> Optional[AnalysisResult]:
        result_path = self._result_path(job_id)
        if not result_path.exists():
            return None
        try:
            return AnalysisResult.model_validate_json(result_path.read_text(encoding="utf-8"))
        except Exception:
            try:
                raw = json.loads(result_path.read_text(encoding="utf-8"))
                graph = raw.get("dependency_graph")
                if isinstance(graph, dict):
                    raw["dependency_graph"] = _coerce_legacy_graph_data(graph)
                result = AnalysisResult.model_validate(raw)
                self._persist_result(result)
                return result
            except Exception:
                return None

    def get_workspace(self, job_id: str) -> Path:
        job = self.get_job(job_id)
        if not job:
            raise KeyError(f"Job not found: {job_id}")
        return Path(job.workspace_path)

    def cleanup_job(self, job_id: str) -> None:
        self._jobs.pop(job_id, None)
        self._results.pop(job_id, None)
        workspace = self.settings.upload_path / job_id
        if workspace.exists():
            shutil.rmtree(workspace, ignore_errors=True)

    def save_refactored(self, job_id: str, refactored_files: list) -> None:
        workspace = self.get_workspace(job_id)
        ref_dir = workspace / "_refactored"
        ref_dir.mkdir(exist_ok=True)
        for i, rf in enumerate(refactored_files):
            ext = Path(rf.original_path).suffix or ".txt"
            target = ref_dir / safe_artifact_name(rf.original_path, f".refactored{ext}", i)
            target.write_text(rf.refactored_content, encoding="utf-8")

    def save_tests(self, job_id: str, tests: list) -> Path:
        workspace = self.get_workspace(job_id)
        test_dir = workspace / "_generated_tests"
        test_dir.mkdir(exist_ok=True)
        for i, t in enumerate(tests):
            ext = ".py" if t.language == "python" else ".java"
            safe_name = safe_artifact_name(t.source_file, f"_test{ext}", i + 1)
            (test_dir / safe_name).write_text(t.content, encoding="utf-8")
        return test_dir
