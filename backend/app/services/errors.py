class IngestionError(Exception):
    """Raised when ingestion fails after a job record was created."""

    def __init__(self, job_id: str, message: str) -> None:
        self.job_id = job_id
        self.message = message
        super().__init__(message)
