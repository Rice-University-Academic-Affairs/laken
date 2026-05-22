from __future__ import annotations

import logging

logger = logging.getLogger("laken")

DEBUG = logging.DEBUG
INFO = logging.INFO


def _ensure_stream_handler() -> None:
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("laken: %(message)s"))
    logger.addHandler(handler)


def set_log_level(level: int = INFO) -> None:
    _ensure_stream_handler()
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)
