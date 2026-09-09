"""SQLAlchemy 引擎与 Session 管理。"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..config import StorageConfig, get_config


class Base(DeclarativeBase):
    """SQLAlchemy Declarative Base。"""


def _build_engine(url: str):
    if url.startswith("sqlite:///"):
        # 确保 sqlite 父目录存在
        db_path = url.replace("sqlite:///", "", 1)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


_cached_engine = None
_cached_session_factory: sessionmaker[Session] | None = None


def engine():
    global _cached_engine
    if _cached_engine is None:
        cfg = get_config().storage
        _cached_engine = _build_engine(cfg.database_url)
    return _cached_engine


def SessionLocal() -> sessionmaker[Session]:
    global _cached_session_factory
    if _cached_session_factory is None:
        _cached_session_factory = sessionmaker(bind=engine(), autoflush=False, autocommit=False, expire_on_commit=False)
    return _cached_session_factory


def get_session() -> Generator[Session, None, None]:
    """FastAPI Depends 使用的 session 生成器。"""
    session = SessionLocal()()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """初始化所有表（首次启动时调用）。"""
    # 导入模型以注册 metadata
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine())


def reset_for_tests(url: str = "sqlite:///:memory:") -> None:
    """测试钩子：替换为内存数据库。"""
    global _cached_engine, _cached_session_factory
    _cached_engine = _build_engine(url)
    _cached_session_factory = sessionmaker(bind=_cached_engine, autoflush=False, autocommit=False, expire_on_commit=False)
    from . import models  # noqa: F401

    Base.metadata.drop_all(bind=_cached_engine)
    Base.metadata.create_all(bind=_cached_engine)