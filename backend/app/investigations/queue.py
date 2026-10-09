from uuid import UUID

from app.investigations.celery_app import celery_app


def enqueue_investigation(investigation_id: UUID) -> str:
    result = celery_app.send_task(
        "opspilot.investigations.start",
        args=[str(investigation_id)],
    )
    return str(result.id)
