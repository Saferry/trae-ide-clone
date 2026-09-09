# Architecture（详细）

> 与 [ARCHITECTURE.md](../ARCHITECTURE.md) 互补，本文深入实现细节。

## 1. 数据流（完整版）

### Chat 单轮

```
[User in Webview]
       │  vscode message
       ▼
[ChatPanel.send()]
       │
       ▼
[WsClient.send()] ─── WS ───► [FastAPI /v1/chat/ws]
                                       │
                                       ▼
                            [AgentRunner.run()]
                                       │
                          ┌────────────┼─────────────────────────┐
                          ▼            ▼                          ▼
                [Rules Loader]  [Codebase Query (#refs)]    [LLM.stream()]
                          │            │                          │
                          └────────────┴──────────────────────────┘
                                          │
                                ┌─────────┴─────────┐
                                ▼                   ▼
                     [<tool_call> 解析]    [<plan> / <final_answer>]
                                │
                                ▼
                     [ToolRegistry.execute()]
                                │
                  ┌─────────────┼─────────────────┐
                  ▼             ▼                 ▼
           [File Tools]   [Bash + Sandbox]   [Subagent delegate]
                                                         │
                                                         ▼
                                              [独立 AgentRunner + 独立上下文]
                                                         │
                                                         ▼
                                              [Tool Result → 回填]
                                                         │
                                                         ▼
                                       [WsEvent ──► Client Webview]
```

## 2. 智能体循环（runner.py）

伪代码：

```python
for iteration in range(max_iter):
    response = llm.chat(messages + history, tools=tool_schemas)
    tool_calls = response.tool_calls or parse_inline_tool_calls(response.text)
    if not tool_calls:
        if has_final_answer(response.text):
            return response.text
        break

    history.append(AssistantMessage(content, tool_calls))
    for tc in tool_calls:
        result = await tools.execute(tc.name, tc.args, tctx)
        history.append(ToolMessage(content=result.content, tool_call_id=tc.id))
```

关键设计：
- **优先使用模型原生 tool_calls**（OpenAI / Anthropic 都支持）；解析失败时回退到文本中的 `<tool_call>` 标签
- **Plan 解析独立分支**：`<plan>` 只标记，不强制门控（`require_plan_confirmation` 配置开启时由 MainAgent 在调用前确认）
- **历史回填**：tool 结果始终追加到同一会话历史，使下一轮模型可见

## 3. 子智能体

每个 `SubagentSpec` 独立 runner + 独立 history：

```python
runner = AgentRunner(model=spec.model, system_prompt=spec.body)
scoped_tools = ToolRegistry()  # 只装载 spec.tools 列表里的
ctx = AgentContext(session_id=f"sub:{spec.name}", ...)
result = await runner.run(ctx, history, scoped_tools)
```

主智能体通过 `delegate()` 工具调用，工具返回最终 answer，**不污染主上下文**。

## 4. 工具系统

工具抽象：

```python
class Tool(ABC):
    name: str
    description: str
    risk_level: RiskLevel
    parameters: dict  # JSON Schema

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        ...
```

工具注册：

```python
registry = ToolRegistry()
registry.register(ReadFileTool())
```

工具 schema 导出（给 LLM 用）：

```python
registry.openai_tools() -> [{"type": "function", "function": {...}}, ...]
```

## 5. 沙箱

- **Linux**：Bubblewrap (`bwrap`) + user/pid/net namespace
- **macOS**：`sandbox-exec -f <profile>`
- **Windows**：`cmd /c` + 严格 timeout（生产环境建议结合 Job Object）
- 兜底（无沙箱可用）：仅依赖 dangerous_commands 正则拦截 + timeout

策略文件 `config/sandbox.example.json`：

```json
{
  "default_policy": "default",
  "policies": {
    "default": {
      "filesystem": { "deny_paths": [...] },
      "network": { "enabled": false, "allowed_domains": [...] },
      "process": { "max_runtime_seconds": 60 },
      "dangerous_commands": [...]
    }
  }
}
```

## 6. 代码库索引

- **存储**：默认 ChromaDB（持久化到 `data/chroma/`）；不可用时降级 SQLite + 暴力 cosine
- **Embedder**：默认走 OpenAI 兼容 embedding 接口，可换本地 sentence-transformers
- **构建**：扫描工作区 → 按行分块 → embedding → upsert
- **查询**：服务启动时按需 lazy build；用户触发 `index_build` 全量重建
- **JIT**：当用户首次 `#` 引用某文件时按需检索该文件附近上下文

## 7. Rules

- 工作区 `.trae/rules.md` 解析为多个 `Rule(title, content)`
- 拼装到系统消息的"工作区规则"段落
- 每次 run 重新读取（开发时可热更新）

## 8. MCP

- `MCPRegistry` 维护多个 server
- 每个 server 一个 client（stdio 或 sse）
- 启动时 `connect()` + `initialize()` + `tools/list`
- MCP tools 包装为 `MCPToolAdapter`，挂到 `ToolRegistry`
- 调用时通过 `client.call_tool(name, args)` 转发

## 9. 配置与部署

- 配置：YAML + 环境变量插值（`${OPENAI_API_KEY}`）
- 部署：Docker Compose（推荐） / 本地直跑 / K8s（参考 manifest）
- 持久化：`/app/data`（SQLite + Chroma）

## 10. 未来演进

- VS Code 整体 fork + 客户端 bundle 内嵌
- Web 端（TraeWork）
- 多用户 + RBAC
- 团队级审计面板（基于 audit_logs）
- 私有模型微调
- 端到端 E2E 测试