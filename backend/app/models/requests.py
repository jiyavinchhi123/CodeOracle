from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.analysis import AnalysisResult, AnalysisStatus


class AnalyzeGitHubRequest(BaseModel):
    url: str = Field(..., min_length=1, description="Public GitHub repository URL")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("URL cannot be empty")
        return v


class JobStatusResponse(BaseModel):
    job_id: str
    status: AnalysisStatus
    progress: Optional[str] = None
    error: Optional[str] = None
    result: Optional[AnalysisResult] = None
