from __future__ import annotations

import logging
from typing import Any, Callable


LogCallback = Callable[[str, str, str, dict[str, Any] | None], None]


class AppLogHandler(logging.Handler):
    def __init__(self, callback: LogCallback) -> None:
        super().__init__()
        self.callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        try:
            category = getattr(record, "category", "system")
            metadata = getattr(record, "metadata_json", None)
            self.callback(record.levelname, category, record.getMessage(), metadata)
        except Exception:
            self.handleError(record)


def configure_logging(level: str, callback: LogCallback) -> logging.Logger:
    logger = logging.getLogger("trading_platform")
    logger.setLevel(level.upper())
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    app_handler = AppLogHandler(callback)
    app_handler.setFormatter(formatter)
    logger.addHandler(app_handler)
    return logger
