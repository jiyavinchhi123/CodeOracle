import io
import zipfile
from pathlib import Path

from app.config import Settings
from app.utils.security import SKIP_DIRS, SOURCE_EXTENSIONS, is_safe_path, sanitize_zip_member


class ZipValidationError(Exception):
    pass


def validate_and_extract_zip(zip_bytes: bytes, dest: Path, settings: Settings) -> list[str]:
    """Validate ZIP archive and extract source files safely."""
    max_size = settings.max_upload_size_mb * 1024 * 1024
    if len(zip_bytes) > max_size:
        raise ZipValidationError(
            f"ZIP exceeds maximum size of {settings.max_upload_size_mb} MB"
        )

    dest.mkdir(parents=True, exist_ok=True)
    extracted: list[str] = []

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            members = zf.infolist()
            if len(members) > settings.max_files:
                raise ZipValidationError(
                    f"ZIP contains too many files (max {settings.max_files})"
                )

            for info in members:
                if info.is_dir():
                    continue

                safe_name = sanitize_zip_member(info.filename)
                if safe_name is None:
                    continue

                # Skip hidden / junk paths
                parts = Path(safe_name).parts
                if any(p.startswith(".") and p not in (".", "..") for p in parts):
                    continue
                if any(p in SKIP_DIRS for p in parts):
                    continue

                ext = Path(safe_name).suffix.lower()
                if ext not in SOURCE_EXTENSIONS:
                    continue

                target = dest / safe_name
                if not is_safe_path(dest, target):
                    raise ZipValidationError(f"Unsafe path in ZIP: {info.filename}")

                target.parent.mkdir(parents=True, exist_ok=True)

                # Check uncompressed size
                if info.file_size > 10 * 1024 * 1024:
                    continue

                data = zf.read(info.filename)
                target.write_bytes(data)
                extracted.append(safe_name.replace("\\", "/"))

    except zipfile.BadZipFile as exc:
        raise ZipValidationError("Invalid or corrupted ZIP file") from exc

    if not extracted:
        raise ZipValidationError(
            "No Python (.py) or Java (.java) source files found in ZIP"
        )

    return extracted
