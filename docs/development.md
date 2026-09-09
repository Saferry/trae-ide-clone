# 开发者指南

## 1. 开发环境

- Python 3.11+
- Node.js 20+（用于客户端构建）
- 推荐 IDE：PyCharm / VS Code

## 2. 服务端开发

```bash
cd server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .[dev]
```

跑测试：

```bash
TRAE_CONFIG=tests/fixtures/trae.test.yaml pytest -q
```

启动开发模式：

```bash
TRAE_CONFIG=./trae.yaml uvicorn trae_server.main:app --reload --port 8080
```

### 2.1 模块布局

```
src/trae_server/
├── api/         FastAPI 路由（REST + WebSocket）
├── agents/      智能体循环（runner / main_agent / subagent）
├── tools/       工具注册中心（每个工具一个文件）
├── models/      模型适配（OpenAI / Anthropic / Router）
├── index/       代码库索引（ChromaDB / SQLite fallback）
├── mcp/         MCP 客户端
├── rules/       .trae/rules.md 加载
├── auth/        API Key + JWT + 配额
├── storage/     SQLite 持久化
├── sandbox/     沙箱策略与执行
├── config.py    配置中心
├── logging.py   结构化日志
└── main.py      FastAPI 入口
```

### 2.2 添加自定义工具

```python
# src/trae_server/tools/my_tool.py
from .base import RiskLevel, Tool, ToolContext, ToolResult

class MyTool(Tool):
    name = "my_tool"
    description = "做一件很酷的事"
    risk_level = RiskLevel.LOW
    parameters = {"type": "object", "properties": {...}}

    async def execute(self, args, ctx):
        return ToolResult(content="done")

# 在 tools/base.py 的 _register_builtin() 中注册：
# reg.register(MyTool())
```

### 2.3 添加自定义模型 Provider

在 `config/trae.yaml` 的 `models.providers` 增加：

```yaml
models:
  providers:
    - id: my-vllm
      kind: openai  # 任何 OpenAI 兼容协议的服务
      base_url: "http://my-vllm:8000/v1"
      api_key: "any"
      default_model: "qwen2.5-coder-32b"
      enabled: true
```

### 2.4 添加子智能体

在工作区下创建 `.trae/agents/my-agent.md`：

```markdown
---
name: my-agent
description: 一句话描述
tools: [read_file, write_file]
context_window: 8000
model: openai-default/gpt-4o-mini
---
你是 ...（自由书写 system prompt）
```

主智能体即可通过 `delegate(subagent="my-agent", task="...")` 调用。

## 3. 客户端开发

```bash
cd client
npm install
```

按 F5 启动 Extension Development Host（VS Code 会打开新窗口加载扩展）。

构建 vsix：

```bash
npm run package
```

## 4. 测试

### 4.1 后端单元测试

`server/tests/`，使用 pytest：

```bash
pytest -q
pytest --cov=trae_server --cov-report=term-missing
```

### 4.2 API 冒烟测试

```bash
# 服务端启动后
curl http://127.0.0.1:8080/health
curl -H "X-API-Key: your-key" http://127.0.0.1:8080/v1/models

curl -X POST http://127.0.0.1:8080/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{"messages":[{"role":"user","content":"你好"}]}'
```

## 5. 代码规范

- Python：ruff + mypy（pyproject.toml 已配置）
- TypeScript：ESLint（默认配置）+ Prettier（推荐）

提交前 `pre-commit` 钩子可加 ruff / eslint。

## 6. 安全

- 不要在仓库中提交 `.env`、`trae.yaml`、`*.key` 等敏感文件（`.gitignore` 已覆盖）
- 调试时使用 `local-dev-key-please-change` 之外的 API Key
- 生产环境启用 HTTPS（部署文档）
- 开启 `audit_enabled` 并定期导出 `audit_logs` 表做合规审计