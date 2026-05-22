from __future__ import annotations

import logging

logger = logging.getLogger("laken")


def module_logger(name: str) -> logging.Logger:
    suffix = name.removeprefix("laken.")
    return logger.getChild(suffix) if suffix else logger


def configure_logging(level: int = logging.INFO) -> None:
    if logger.handlers:
        logger.setLevel(level)
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("laken: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(level)
