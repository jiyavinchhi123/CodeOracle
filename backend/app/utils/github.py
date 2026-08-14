import io
import zipfile
from pathlib import Path

import httpx

from app.config import Settings
from app.utils.security import SKIP_DIRS, SOURCE_EXTENSIONS, is_safe_path, parse_github_url


class GitHubError(Exception):
    pass


async def download_github_repo(url: str, dest: Path, settings: Settings) -> tuple[str, list[str]]:
    """Download public GitHub repo archive and extract source files."""
    owner, repo = parse_github_url(url)
    dest.mkdir(parents=True, exist_ok=True)

    api_url = f"{settings.github_api_base}/repos/{owner}/{repo}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "CodeOracle/1.0"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    async with httpx.AsyncClient(timeout=90.0, follow_redirects=True) as client:
        resp = await client.get(api_url, headers=headers)
        if resp.status_code == 404:
            raise GitHubError(f"Repository not found: {owner}/{repo}")
        if resp.status_code == 403:
            raise GitHubError(
                "GitHub API rate limit exceeded. Set GITHUB_TOKEN in .env or try again later."
            )
        if resp.status_code != 200:
            raise GitHubError(f"GitHub API error: {resp.status_code} {resp.text[:200]}")

        data = resp.json()
        if data.get("private"):
            raise GitHubError("Private repositories are not supported")

        default_branch = data.get("default_branch", "main")
        archive_url = f"{settings.github_api_base}/repos/{owner}/{repo}/zipball/{default_branch}"
        archive_resp = await client.get(archive_url, headers=headers)
        if archive_resp.status_code == 403:
            raise GitHubError(
                "GitHub download rate limit exceeded. Set GITHUB_TOKEN in .env or try again later."
            )
        if archive_resp.status_code != 200:
            raise GitHubError(
                f"Failed to download repository archive: {archive_resp.status_code}"
            )
        zip_bytes = archive_resp.content

    extracted = _extract_github_zip(zip_bytes, dest, settings)
    if not extracted:
        raise GitHubError(
            "No Python (.py) or Java (.java) source files found in repository. "
            "CodeOracle currently supports Python and Java codebases only."
        )

    label = f"{owner}/{repo}"
    return label, extracted


def _extract_github_zip(zip_bytes: bytes, dest: Path, settings: Settings) -> list[str]:
    extracted: list[str] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        root_prefix = ""
        for name in zf.namelist():
            if "/" in name:
                root_prefix = name.split("/")[0] + "/"
                break

        for info in zf.infolist():
            if info.is_dir():
                continue
            rel = info.filename
            if root_prefix and rel.startswith(root_prefix):
                rel = rel[len(root_prefix):]

            rel = rel.replace("\\", "/")
            parts = Path(rel).parts
            if any(p in SKIP_DIRS for p in parts):
                continue

            ext = Path(rel).suffix.lower()
            if ext not in SOURCE_EXTENSIONS:
                continue

            target = dest / rel
            if not is_safe_path(dest, target):
                continue

            if info.file_size > 10 * 1024 * 1024:
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(info.filename))
            extracted.append(rel)

    return extracted
