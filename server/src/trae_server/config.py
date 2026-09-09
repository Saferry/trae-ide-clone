"""配置中心：从 YAML 文件 + 环境变量加载配置。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080
    workers: int = 1
    cors_origins: list[str] = Field(default_factory=list)


class APIKeyEntry(BaseModel):
    key: str
    name: str
    quota: dict[str, int] = Field(default_factory=dict)


class JWTConfig(BaseModel):
    enabled: bool = False
    secret: str = "change-me"
    algorithm: str = "HS256"
    expires_seconds: int = 3600


class AuthConfig(BaseModel):
    api_keys: list[APIKeyEntry] = Field(default_factory=list)
    jwt: JWTConfig = JWTConfig()


class LoggingConfig(BaseModel):
    model_config = {"protected_namespaces": ()}
    level: str = "INFO"
    json_output: bool = Field(default=True, alias="json")
    file: str = ""


class StorageConfig(BaseModel):
    database_url: str = "sqlite:///./data/trae.db"
    audit_enabled: bool = True


class ModelProviderConfig(BaseModel):
    id: str
    kind: str  # "openai" | "anthropic" | "custom"
    base_url: str = ""
    api_key: str = ""
    default_model: str = ""
    enabled: bool = True


class RoutingConfig(BaseModel):
    chat: str = ""
    agent: str = ""
    completion: str = ""
    embedding: str = ""


class ModelsConfig(BaseModel):
    providers: list[ModelProviderConfig] = Field(default_factory=list)
    routing: RoutingConfig = RoutingConfig()


class IndexerConfig(BaseModel):
    enabled: bool = True
    storage_dir: str = "./data/chroma"
    embedding_provider: str = ""
    embedding_model: str = "text-embedding-3-small"
    max_file_size_kb: int = 512
    ignore_patterns: list[str] = Field(default_factory=list)


class AgentConfig(BaseModel):
    max_iterations: int = 30
    max_subagent_depth: int = 2
    require_plan_confirmation: bool = True
    context_window: int = 128000
    dangerous_command_patterns: list[str] = Field(default_factory=list)


class MCPServerConfig(BaseModel):
    name: str
    transport: str  # "stdio" | "sse"
    command: str = ""
    args: list[str] = Field(default_factory=list)
    url: str = ""
    enabled: bool = False


class MCPConfig(BaseModel):
    enabled: bool = True
    servers: list[MCPServerConfig] = Field(default_factory=list)


class SandboxPolicyConfig(BaseModel):
    allow_network: bool = False
    allow_write: bool = True
    max_runtime_seconds: int = 60
    max_memory_mb: int = 512


class SandboxConfig(BaseModel):
    enabled: bool = True
    default_policy: str = "default"
    policies: dict[str, SandboxPolicyConfig] = Field(default_factory=dict)


class Config(BaseModel):
    server: ServerConfig = ServerConfig()
    auth: AuthConfig = AuthConfig()
    logging: LoggingConfig = LoggingConfig()
    storage: StorageConfig = StorageConfig()
    models: ModelsConfig = ModelsConfig()
    indexer: IndexerConfig = IndexerConfig()
    agent: AgentConfig = AgentConfig()
    mcp: MCPConfig = MCPConfig()
    sandbox: SandboxConfig = SandboxConfig()


def _resolve_env(value: Any) -> Any:
    """替换形如 ${OPENAI_API_KEY} 的环境变量引用。"""
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_name = value[2:-1]
        return os.environ.get(env_name, "")
    return value


def _deep_resolve_env(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _deep_resolve_env(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_resolve_env(v) for v in obj]
    return _resolve_env(obj)


def load_config(path: str | Path | None = None) -> Config:
    """从 YAML 文件加载配置；缺省时使用内置默认。"""
    if path is None:
        path = os.environ.get("TRAE_CONFIG", "./trae.yaml")

    path = Path(path)
    if not path.exists():
        return Config()

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw = _deep_resolve_env(raw)
    return Config.model_validate(raw)


def get_config() -> Config:
    """供 FastAPI Depends 使用的缓存式获取。"""
    global _cached_config
    try:
        return _cached_config
    except NameError:
        _cached_config = load_config()
        return _cached_config


def reload_config(path: str | Path | None = None) -> Config:
    """强制重新加载（用于热更新或单元测试）。"""
    global _cached_config
    _cached_config = load_config(path)
    return _cached_config