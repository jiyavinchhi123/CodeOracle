from app.config import get_settings
from app.services.storage import JobStorage

_settings = get_settings()
_storage = JobStorage(_settings)


def get_storage() -> JobStorage:
    return _storage
