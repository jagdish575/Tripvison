"""Structured (JSON) logging with secret redaction."""

from __future__ import annotations

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_KEY_PATTERN = re.compile(r"(api_key|x-api-key|authorization)([=:]\s*)([^&\s\"',]+)", re.IGNORECASE)


class RedactingFilter(logging.Filter):
    """Masks API keys in every log record, both by pattern and by known secret values."""

    def __init__(self, secrets: list[str] | None = None) -> None:
        super().__init__()
        self.secrets = [s for s in (secrets or []) if s]

    def redact(self, text: str) -> str:
        text = _KEY_PATTERN.sub(lambda m: f"{m.group(1)}{m.group(2)}***", text)
        for secret in self.secrets:
            text = text.replace(secret, "***")
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - malformed log call
            return True
        record.msg = self.redact(message)
        record.args = ()
        extra = getattr(record, "context", None)
        if isinstance(extra, dict):
            record.context = {k: self.redact(str(v)) if isinstance(v, str) else v for k, v in extra.items()}
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = request_id_var.get()
        if rid:
            payload["request_id"] = rid
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            payload.update(context)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO", secrets: list[str] | None = None) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactingFilter(secrets))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    for noisy in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
