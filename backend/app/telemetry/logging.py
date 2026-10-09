import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "request_id": request_id.get(),
            "incident_id": None,
            "investigation_id": None,
            "trace_id": None,
            "component": record.name,
            "event": record.getMessage(),
            "level": record.levelname,
        }
        # Allowlist metadata; never serialize request bodies, headers or exception strings.
        for key in (
            "actor_id",
            "audit",
            "method",
            "route",
            "status",
            "duration_ms",
            "incident_id",
            "investigation_id",
            "tool_name",
            "execution_id",
            "risk_level",
        ):
            if hasattr(record, key):
                data[key] = getattr(record, key)
        return json.dumps(data)


def configure_logging() -> None:
    logger = logging.getLogger("opspilot")
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
