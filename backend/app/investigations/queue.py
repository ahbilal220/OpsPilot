import asyncio
import logging
from threading import Thread
from uuid import UUID, uuid4

from app.investigations.celery_app import celery_app

logger = logging.getLogger("opspilot.investigation.queue")


def enqueue_investigation(investigation_id: UUID) -> str:
    result = celery_app.send_task(
        "opspilot.investigations.start",
        args=[str(investigation_id)],
    )
    return str(result.id)


def _run_inline(investigation_id: UUID) -> None:
    from app.investigations.tasks import run_investigation_workflow

    try:
        asyncio.run(run_investigation_workflow(investigation_id))
    except Exception:
        logger.exception(
            "investigation.inline_failed",
            extra={"investigation_id": str(investigation_id)},
        )


def enqueue_investigation_inline(investigation_id: UUID) -> str:
    """Run the bounded demo workflow without a separate paid worker service."""
    task_id = f"inline-{uuid4()}"
    Thread(
        target=_run_inline,
        args=(investigation_id,),
        name=task_id,
        daemon=True,
    ).start()
    return task_id
