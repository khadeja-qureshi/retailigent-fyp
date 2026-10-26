"""
Structured (JSON) logging for the API and its background jobs.

LOG_FORMAT=json  -> one JSON object per line (default; for log aggregators)
LOG_FORMAT=text  -> human readable (local development)

Anything passed as `extra={...}` to a logger call is emitted as a JSON field,
so job logs are queryable: {"event": "job_run", "job": "...", "status": "ok"}.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

# Attributes every LogRecord has; everything else came from `extra=`.
_STANDARD_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(log_format: str = "json", level: str = "INFO") -> None:
    """Idempotent: safe to call more than once (e.g. under --reload)."""

    root = logging.getLogger()
    root.setLevel(level.upper())

    for handler in list(root.handlers):
        if getattr(handler, "_retailigent", False):
            root.removeHandler(handler)

    handler = logging.StreamHandler()
    handler._retailigent = True  # type: ignore[attr-defined]

    if log_format.lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s: %(message)s"
            )
        )

    root.addHandler(handler)
