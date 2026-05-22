from __future__ import annotations

import logging

logger = logging.getLogger("laken")

DEBUG = logging.DEBUG
INFO = logging.INFO


def ensure_logging() -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("laken: %(message)s"))
    handler.setLevel(INFO)
    logger.addHandler(handler)
    if logger.level == logging.NOTSET:
        logger.setLevel(INFO)


def set_log_level(level: int = INFO) -> None:
    ensure_logging()
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)
