"""Celery tasks for dataset imports."""

from celery import shared_task


@shared_task(name="datasets.process_import_job")
def process_import_job(job_id: str) -> dict[str, int]:
    """Process a JSONL dataset import job."""

    from agentproof_backend.apps.datasets.services import process_import_job as process_job

    result = process_job(job_id=job_id)
    return {
        "total_rows": result.total_rows,
        "imported_rows": result.imported_rows,
        "error_rows": result.error_rows,
    }


@shared_task(name="datasets.cleanup_import_files")
def cleanup_import_files() -> int:
    """Delete expired dataset import files."""

    from agentproof_backend.apps.datasets.services import cleanup_import_files as cleanup_files

    return cleanup_files()
