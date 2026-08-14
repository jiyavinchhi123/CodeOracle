import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models.analysis import AnalysisStatus
from app.services.storage import JobStorage
from app.utils.security import parse_github_url, sanitize_zip_member, is_analyzable_source, safe_artifact_name
from app.utils.zip_utils import ZipValidationError, validate_and_extract_zip
from app.config import Settings
from app.analyzers.python_analyzer import PythonAnalyzer
from app.analyzers.java_analyzer import JavaAnalyzer


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture
def work_dir():
    base = Path(__file__).resolve().parents[1] / "tests" / "_tmp"
    base.mkdir(parents=True, exist_ok=True)
    yield base


@pytest.fixture
def settings(work_dir):
    upload_dir = work_dir / "uploads"
    upload_dir.mkdir(exist_ok=True)
    return Settings(upload_dir=str(upload_dir), max_upload_size_mb=10, max_files=100)


SAMPLE_PYTHON = '''
"""Sample module."""
import os

class Greeter:
    """Greets users."""

    def greet(self, name: str) -> str:
        return f"Hello, {name}!"

def add(a, b):
    return a + b
'''

SAMPLE_JAVA = '''
public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }
}
'''


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_parse_github_url_valid():
    owner, repo = parse_github_url("https://github.com/octocat/Hello-World")
    assert owner == "octocat"
    assert repo == "Hello-World"


def test_parse_github_url_invalid():
    with pytest.raises(ValueError):
        parse_github_url("https://gitlab.com/foo/bar")


def test_sanitize_zip_member_blocks_traversal():
    assert sanitize_zip_member("../etc/passwd") is None
    assert sanitize_zip_member("src/main.py") == "src/main.py"


def test_python_analyzer():
    analyzer = PythonAnalyzer()
    result = analyzer.analyze_file("sample.py", SAMPLE_PYTHON)
    assert result.language == "python"
    assert len(result.classes) == 1
    assert result.classes[0]["name"] == "Greeter"
    assert len(result.functions) == 1
    assert result.classes[0]["methods"] == ["greet"]
    assert any(i["module"] == "os" for i in result.imports)


def test_java_analyzer():
    analyzer = JavaAnalyzer()
    result = analyzer.analyze_file("Calculator.java", SAMPLE_JAVA)
    assert result.language == "java"
    assert len(result.classes) == 1
    assert result.classes[0]["name"] == "Calculator"


def test_validate_zip(settings, work_dir):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("main.py", SAMPLE_PYTHON)
    dest = work_dir / "extract_zip"
    dest.mkdir(exist_ok=True)
    files = validate_and_extract_zip(buf.getvalue(), dest, settings)
    assert "main.py" in files
    assert (dest / "main.py").exists()


def test_validate_zip_rejects_traversal(settings, work_dir):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../evil.py", "x = 1")
    dest = work_dir / "extract_bad"
    dest.mkdir(exist_ok=True)
    with pytest.raises(ZipValidationError):
        validate_and_extract_zip(buf.getvalue(), dest, settings)


def test_analyze_zip_endpoint(client):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("app.py", SAMPLE_PYTHON)
    buf.seek(0)
    resp = client.post(
        "/api/analyze/zip",
        files={"file": ("test.zip", buf, "application/zip")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["status"] in ("pending", "ingesting", "analyzing", "ai_processing", "completed")


def test_analyze_github_invalid(client):
    resp = client.post("/api/analyze/github", json={"url": "not-a-url"})
    assert resp.status_code == 400


def test_is_analyzable_source_skips_artifacts():
    assert is_analyzable_source("src/main.py") is True
    assert is_analyzable_source("_generated_tests/foo.py") is False
    assert is_analyzable_source("_refactored/bar.py") is False
    assert is_analyzable_source("app.modern.py") is False


def test_safe_artifact_name_short():
    name = safe_artifact_name("hackorbit-main/backend/app/tests/test_main.py", "_test.py", 1)
    assert len(name) <= 120
    assert "_test.py" in name


def test_placeholder_api_key_not_configured():
    settings = Settings(llm_api_key="your-api-key-here")
    assert settings.llm_configured is False


def test_job_persistence_survives_reload(settings):
    storage1 = JobStorage(settings)
    job = storage1.create_job("zip", "demo.zip")
    storage1.update_job_status(job.id, AnalysisStatus.INGESTING)

    storage2 = JobStorage(settings)
    loaded = storage2.get_job(job.id)
    assert loaded is not None
    assert loaded.id == job.id
    assert loaded.status == AnalysisStatus.INGESTING
    assert (settings.upload_path / job.id / "job.json").exists()
