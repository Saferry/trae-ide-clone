"""结构化日志（基于 structlog）。"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def configure_logging(level: str = "INFO", json_output: bool = True, log_file: str = "") -> None:
    """初始化全局日志配置。"""
    timestamper = structlog.processors.TimeStamper(fmt="iso")

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
    ]

    if json_output:
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper(), logging.INFO)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout if not log_file else open(log_file, "a", encoding="utf-8")),
        cache_logger_on_first_use=True,
    )

    # 同时配置 stdlib logging，让 uvicorn / sqlalchemy 等走我们的格式
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout if not log_file else open(log_file, "a", encoding="utf-8"),
        level=getattr(logging, level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper(), logging.INFO)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout if not log_file else open(log_file, "a", encoding="utf-8")),
        cache_logger_on_first_use=True,
    )

    # 同时配置 stdlib logging，让 uvicorn / sqlalchemy 等走我们的格式
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout if not log_file else open(log_file, "a", encoding="utf-8"),
        level=getattr(logging, level.upper(), logging.INFO),
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)