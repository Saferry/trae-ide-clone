"""FastAPI 应用入口。"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import agent_router, chat_router, completion_router, models_router
from .config import get_config, load_config
from .logging import configure_logging, get_logger
from .mcp.registry import install_mcp_tools
from .storage.db import init_db
from .tools.base import get_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_config()
    configure_logging(cfg.logging.level, cfg.logging.json, cfg.logging.file)
    log = get_logger("main")
    log.info("starting trae-server", version="0.1.0")

    # 确保 data 目录存在
    Path("./data").mkdir(exist_ok=True)

    # 初始化 DB
    init_db()

    # 注册内置工具 + MCP 工具
    registry = get_registry()
    try:
        registered = await install_mcp_tools(registry)
        if registered:
            log.info("mcp tools registered", count=registered)
    except Exception as e:  # noqa: BLE001
        log.warning("mcp init failed", error=str(e))

    log.info("tools registered", total=len(registry.list_tools()))
    yield
    log.info("shutting down trae-server")


def create_app(config_path: str | None = None) -> FastAPI:
    if config_path:
        load_config(config_path)
    cfg = get_config()

    app = FastAPI(
        title="Trae IDE Clone - AI Agent Server",
        version="0.1.0",
        description="Enterprise-grade AI programming assistant backend",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.server.cors_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat_router)
    app.include_router(agent_router)
    app.include_router(models_router)
    app.include_router(completion_router)

    @app.get("/")
    async def root() -> dict:
        return {
            "name": "trae-ide-clone",
            "version": "0.1.0",
            "status": "ok",
            "docs": "/docs",
        }

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok"}

    return app


app = create_app()


def run() -> None:
    """Console entry: python -m trae_server.main"""
    import uvicorn

    cfg = get_config()
    uvicorn.run(
        "trae_server.main:app",
        host=cfg.server.host,
        port=cfg.server.port,
        workers=cfg.server.workers,
        reload=False,
    )


if __name__ == "__main__":
    run()