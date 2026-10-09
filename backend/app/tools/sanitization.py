import re
from typing import Any

SENSITIVE_KEY = re.compile(
    r"(^|_)(authorization|cookie|password|passwd|secret|token|api_key|private_key)($|_)",
    re.IGNORECASE,
)
SECRET_PATTERNS = (
    re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]{8,}"),
    re.compile(r"\b(?:sk|ghp|github_pat)_[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)(postgres(?:ql)?://[^:\s/]+:)[^@\s]+(@)"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


def sanitize_text(value: str, *, max_chars: int = 4000) -> str:
    cleaned = value
    cleaned = SECRET_PATTERNS[0].sub("Bearer [REDACTED]", cleaned)
    cleaned = SECRET_PATTERNS[1].sub("[REDACTED]", cleaned)
    cleaned = SECRET_PATTERNS[2].sub(r"\1[REDACTED]\2", cleaned)
    cleaned = SECRET_PATTERNS[3].sub("[REDACTED PRIVATE KEY]", cleaned)
    if len(cleaned) > max_chars:
        return f"{cleaned[:max_chars]}…[truncated]"
    return cleaned


def sanitize(value: Any, *, max_chars: int = 4000) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]"
            if SENSITIVE_KEY.search(str(key))
            else sanitize(item, max_chars=max_chars)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize(item, max_chars=max_chars) for item in value]
    if isinstance(value, str):
        return sanitize_text(value, max_chars=max_chars)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return sanitize_text(str(value), max_chars=max_chars)
