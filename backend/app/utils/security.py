import os
import re
from pathlib import Path, PurePosixPath

# Extensions we analyze
PYTHON_EXTENSIONS = {".py"}
JAVA_EXTENSIONS = {".java"}
SOURCE_EXTENSIONS = PYTHON_EXTENSIONS | JAVA_EXTENSIONS

# Skip these directories during discovery
SKIP_DIRS = {
    ".git",
    ".svn",
    ".hg",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    "target",
    ".idea",
    ".vscode",
    "site-packages",
    "_generated_tests",
    "_refactored",
}

# Max single file read size (1 MB)
MAX_FILE_BYTES = 1_048_576

# Windows-safe max filename length for artifact writes
MAX_ARTIFACT_NAME_LEN = 120


def is_safe_path(base: Path, target: Path) -> bool:
    """Ensure target resolves within base (prevent path traversal)."""
    try:
        base_resolved = base.resolve()
        target_resolved = target.resolve()
        target_resolved.relative_to(base_resolved)
        return True
    except ValueError:
        return False


def sanitize_zip_member(name: str) -> str | None:
    """Return normalized relative path or None if unsafe."""
    # Normalize to posix-style paths
    normalized = PurePosixPath(name.replace("\\", "/"))
    parts = normalized.parts
    if not parts:
        return None
    if any(p in ("", ".", "..") for p in parts):
        if ".." in parts:
            return None
    clean = str(PurePosixPath(*[p for p in parts if p not in ("", ".")]))
    if clean.startswith("/") or ".." in PurePosixPath(clean).parts:
        return None
    return clean


def detect_language(path: str) -> str | None:
    ext = Path(path).suffix.lower()
    if ext in PYTHON_EXTENSIONS:
        return "python"
    if ext in JAVA_EXTENSIONS:
        return "java"
    return None


def is_analyzable_source(rel_path: str) -> bool:
    """Return True if path should be included in static analysis."""
    parts = PurePosixPath(rel_path.replace("\\", "/")).parts
    if any(p in SKIP_DIRS for p in parts):
        return False
    if ".modern." in rel_path:
        return False
    name = parts[-1] if parts else rel_path
    if name.startswith("test_") and "_generated_tests" in rel_path:
        return False
    return detect_language(rel_path) is not None


def safe_artifact_name(label: str, suffix: str, index: int = 0) -> str:
    """Build a short, filesystem-safe artifact filename."""
    stem = Path(label.replace("\\", "/")).stem
    stem = re.sub(r"[^\w.-]", "_", stem)[:60]
    name = f"{index:02d}_{stem}{suffix}" if index else f"{stem}{suffix}"
    return name[:MAX_ARTIFACT_NAME_LEN]


def count_lines(content: str) -> int:
    if not content:
        return 0
    return content.count("\n") + (1 if content and not content.endswith("\n") else 0)


def build_file_tree(paths: list[str]) -> dict:
    """Build nested dict representing file tree."""
    tree: dict = {}
    for path in sorted(paths):
        parts = PurePosixPath(path).parts
        current = tree
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                current[part] = {"__file__": True, "path": path}
            else:
                if part not in current:
                    current[part] = {}
                elif current[part].get("__file__"):
                    # Conflict: file and directory same name — skip nesting
                    break
                current = current[part]
    return tree


def module_path_from_file(file_path: str) -> str:
    """Convert file path to module identifier."""
    p = Path(file_path)
    if p.suffix == ".py":
        parts = list(p.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(parts)
    if p.suffix == ".java":
        return str(p.with_suffix(""))
    return file_path


GITHUB_URL_PATTERN = re.compile(
    r"^https?://(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?(?:#.*)?$",
    re.IGNORECASE,
)


def parse_github_url(url: str) -> tuple[str, str]:
    """Parse owner/repo from GitHub URL. Raises ValueError if invalid."""
    url = url.strip()
    match = GITHUB_URL_PATTERN.match(url)
    if not match:
        raise ValueError(
            "Invalid GitHub URL. Expected format: https://github.com/owner/repo"
        )
    owner, repo = match.group(1), match.group(2)
    if repo.endswith(".git"):
        repo = repo[:-4]
    return owner, repo
