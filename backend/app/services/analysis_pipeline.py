import asyncio
from datetime import datetime, timezone

from app.ai.breaking_changes import BreakingChangeService
from app.ai.explainer import ExplainerService
from app.ai.modernizer import ModernizerService
from app.ai.provider import get_llm_provider
from app.ai.test_generator import TestGeneratorService
from app.analyzers.project_analyzer import ProjectAnalyzer
from app.config import Settings
from app.models.analysis import AnalysisResult, AnalysisStatus
from app.services.storage import JobStorage
from app.services.test_runner import TestRunnerService


class AnalysisPipeline:
    def __init__(self, settings: Settings, storage: JobStorage) -> None:
        self.settings = settings
        self.storage = storage
        self.analyzer = ProjectAnalyzer()
        self.test_runner = TestRunnerService()

    async def run(self, job_id: str, project_name: str) -> AnalysisResult:
        try:
            return await asyncio.wait_for(
                self._run(job_id, project_name),
                timeout=self.settings.analysis_timeout_seconds,
            )
        except asyncio.TimeoutError:
            msg = f"Analysis timed out after {self.settings.analysis_timeout_seconds}s"
            result = AnalysisResult(
                job_id=job_id,
                status=AnalysisStatus.FAILED,
                error=msg,
                completed_at=datetime.now(timezone.utc),
                ai_mode="heuristic",
            )
            self.storage.save_result(result)
            self.storage.update_job_status(job_id, AnalysisStatus.FAILED, error=msg)
            return result

    async def _run(self, job_id: str, project_name: str) -> AnalysisResult:
        workspace = self.storage.get_workspace(job_id)
        self.storage.update_job_status(job_id, AnalysisStatus.ANALYZING, "Scanning source files…")

        provider, ai_mode = get_llm_provider(self.settings)

        try:
            summary, tree, contents, parsed_files, graph = await asyncio.to_thread(
                self.analyzer.analyze_workspace, workspace, project_name
            )
            self.storage.update_job_status(
                job_id,
                AnalysisStatus.AI_PROCESSING,
                f"Analyzing {len(parsed_files)} files — generating explanations and tests…",
            )

            explainer = ExplainerService(provider, ai_mode, self.settings)
            test_gen = TestGeneratorService(provider, ai_mode, self.settings)
            modernizer = ModernizerService(provider, ai_mode, self.settings)
            breaking_svc = BreakingChangeService(provider, ai_mode)

            modules, generated_tests, modernization = await asyncio.gather(
                explainer.explain_modules(parsed_files),
                test_gen.generate_tests(parsed_files),
                modernizer.modernize(parsed_files),
            )

            self.storage.update_job_status(job_id, AnalysisStatus.AI_PROCESSING, "Checking breaking changes…")
            breaking = await breaking_svc.analyze(parsed_files, modernization.files)

            if modernization.files:
                self.storage.save_refactored(job_id, modernization.files)
            test_dir = self.storage.save_tests(job_id, generated_tests)

            self.storage.update_job_status(job_id, AnalysisStatus.AI_PROCESSING, "Running generated tests…")
            test_results = await asyncio.to_thread(
                self.test_runner.run_tests, generated_tests, test_dir, ai_mode
            )

            result = AnalysisResult(
                job_id=job_id,
                status=AnalysisStatus.COMPLETED,
                summary=summary,
                file_tree=tree,
                file_contents=contents,
                modules=modules,
                dependency_graph=graph,
                generated_tests=generated_tests,
                test_results=test_results,
                modernization=modernization,
                breaking_changes=breaking,
                completed_at=datetime.now(timezone.utc),
                ai_mode=ai_mode,
            )
            self.storage.save_result(result)
            self.storage.update_job_status(job_id, AnalysisStatus.COMPLETED, clear_progress=True)
            return result

        except Exception as exc:
            result = AnalysisResult(
                job_id=job_id,
                status=AnalysisStatus.FAILED,
                error=str(exc),
                completed_at=datetime.now(timezone.utc),
                ai_mode=ai_mode,
            )
            self.storage.save_result(result)
            self.storage.update_job_status(job_id, AnalysisStatus.FAILED, error=str(exc), clear_progress=True)
            return result
