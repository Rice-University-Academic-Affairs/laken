from __future__ import annotations

import logging

logger = logging.getLogger("laken")

_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("laken: %(message)s"))
_handler.setLevel(logging.INFO)
logger.addHandler(_handler)
logger.setLevel(logging.DEBUG)


DEBUG = logging.DEBUG
INFO = logging.INFO


def set_log_level(level: int = INFO) -> None:
    logger.setLevel(level)
    _handler.setLevel(level)
