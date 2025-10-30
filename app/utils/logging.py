from __future__ import annotations

import json
import logging
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, MutableMapping, Sequence

DEFAULT_LOG_LEVEL = os.getenv("QNA_LOG_LEVEL", "INFO")
DEFAULT_LOG_DIR = Path(os.getenv("QNA_LOG_DIR", "data/logs"))


def configure_logging(log_level: str | None = None, log_path: Path | None = None) -> None:
    """Configure application logging with structured files and readable console output."""
    level = getattr(logging, (log_level or DEFAULT_LOG_LEVEL).upper(), logging.INFO)
    handlers: list[logging.Handler] = []

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ConsoleFormatter())
    handlers.append(console_handler)

    destination = log_path or DEFAULT_LOG_DIR / "app.log"
    destination.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(destination)
    file_handler.setFormatter(JsonFormatter())
    handlers.append(file_handler)

    logging.basicConfig(level=level, handlers=handlers)


def get_logger(name: str) -> logging.Logger:
    if not logging.getLogger().handlers:
        configure_logging()
    return logging.getLogger(name)


def _format_event(event: str, extra: MutableMapping[str, Any] | None = None) -> str:
    payload: dict[str, Any] = {"event": event}
    if extra:
        payload.update(extra)
    return json.dumps(payload, default=str)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "logger": record.name,
            "severity": record.levelname,
        }
        message = record.getMessage()
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            payload = None

        if isinstance(payload, dict):
            event = payload.pop("event", None)
            if event is not None:
                data["event"] = event
            data.update(payload)
        else:
            data["message"] = message

        if record.exc_info:
            data["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(data, default=str)


class ConsoleFormatter(logging.Formatter):
    """Pretty console formatter that unwraps structured event payloads."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = time.strftime("%H:%M:%S", time.localtime(record.created))
        level = record.levelname
        name = record.name

        message = record.getMessage()
        details = ""

        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            payload = None

        if isinstance(payload, dict):
            event = payload.pop("event", None)
            message = event or message
            if payload:
                fragments = []
                for key in sorted(payload):
                    value = payload[key]
                    fragments.append(f"{key}={value}")
                details = " " + " ".join(fragments)
        output = f"{timestamp} | {level:<8} | {name} | {message}{details}"

        if record.exc_info:
            output += "\n" + self.formatException(record.exc_info)

        return output


def log_event(logger: logging.Logger, event: str, **extra: Any) -> None:
    logger.info(_format_event(event, extra))


def log_missing_columns(
    logger: logging.Logger,
    *,
    dataset_id: str,
    dataset_name: str,
    columns: Sequence[str],
) -> None:
    if not columns:
        return
    logger.warning(
        _format_event(
            "search.context.missing_columns",
            {
                "dataset_id": dataset_id,
                "dataset_name": dataset_name,
                "missing_columns": list(columns),
                "count": len(columns),
            },
        )
    )


@contextmanager
def log_timing(logger: logging.Logger, event: str, **extra: Any):
    """Context manager that logs start and completion with elapsed milliseconds."""
    start = time.perf_counter()
    logger.info(_format_event(event + ".start", extra))
    try:
        yield
    except Exception:
        elapsed = (time.perf_counter() - start) * 1000.0
        logger.exception(_format_event(event + ".error", {**extra, "elapsed_ms": elapsed}))
        raise
    else:
        elapsed = (time.perf_counter() - start) * 1000.0
        logger.info(_format_event(event + ".complete", {**extra, "elapsed_ms": elapsed}))
