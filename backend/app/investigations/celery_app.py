from celery import Celery  # type: ignore[import-untyped]

from app.core.config import Settings

settings = Settings()
celery_app = Celery(
    "opspilot",
    broker=settings.redis_url.get_secret_value(),
    backend=settings.redis_url.get_secret_value(),
    include=["app.investigations.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_transport_options={"visibility_timeout": 3600},
)
