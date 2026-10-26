from __future__ import annotations

import json
import logging

from datetime import datetime, timezone
from typing import Any


_STANDARD_LOG_RECORD_FIELDS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """
    Dependency-free JSON log formatter.

    Converts standard Python logging records into
    structured JSON suitable for development and
    production log aggregation.
    """

    def format(
        self,
        record: logging.LogRecord,
    ) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=timezone.utc,
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include any custom structured fields
        # supplied using logging(..., extra={...}).
        for key, value in record.__dict__.items():
            if (
                key in _STANDARD_LOG_RECORD_FIELDS
                or key.startswith("_")
            ):
                continue

            try:
                json.dumps(value)
                payload[key] = value

            except (
                TypeError,
                ValueError,
            ):
                payload[key] = str(value)

        # Include exception details when present.
        if record.exc_info:
            payload["exception"] = self.formatException(
                record.exc_info
            )

        if record.stack_info:
            payload["stack_info"] = record.stack_info

        return json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        )


def configure_logging(
    level: int = logging.INFO,
) -> None:
    """
    Configure application-wide structured JSON logging.

    This replaces existing root handlers so logs do not
    appear twice when FastAPI/Uvicorn reloads.
    """

    root_logger = logging.getLogger()

    root_logger.setLevel(
        level
    )

    # Remove any previously configured handlers.
    for handler in list(
        root_logger.handlers
    ):
        root_logger.removeHandler(
            handler
        )

    stream_handler = logging.StreamHandler()

    stream_handler.setLevel(
        level
    )

    stream_handler.setFormatter(
        JsonFormatter()
    )

    root_logger.addHandler(
        stream_handler
    )

    # Reduce noisy HTTP polling logs from Supabase/httpx.
    logging.getLogger(
        "httpx"
    ).setLevel(
        logging.WARNING
    )

    logging.getLogger(
        "httpcore"
    ).setLevel(
        logging.WARNING
    )