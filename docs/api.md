# API 参考

服务端的 REST + WebSocket 接口。

> 通用约定
> - Base URL：`http://<host>:<port>`（默认 `http://127.0.0.1:8080`）
> - 鉴权：所有 `/v1/*` 端点需要 `X-API-Key` Header
> - 错误：4xx 表示请求方问题（401 鉴权失败、429 配额耗尽），5xx 表示服务端问题

---

## 1. Chat

### `POST /v1/chat`

非流式对话。一次请求返回完整结果（适合单轮）。

**请求**

```json
{
  "session_id": "sess_abc123",
  "title": "Demo",
  "workspace": "/path/to/project",
  "model": "gpt-4o-mini",
  "provider_id": "openai-default",
  "messages": [
    { "role": "system", "content": "..." },
    { "role": "user", "content": "..." }
  ],
  "refs": ["#foo:bar"]
}
```

**响应**

```json
{
  "session_id": "sess_abc123",
  "answer": "完整答复",
  "iterations": 3,
  "tokens": 1234,
  "tool_calls": [
    { "id": "call_1", "name": "bash", "arguments": {"command": "ls"} }
  ]
}
```

### `WS /v1/chat/ws`

流式对话。事件类型如下：

| 事件 | 说明 |
| --- | --- |
| `session` | 返回分配的 session_id |
| `text` | 增量 assistant 文本 |
| `tool_call` | 智能体即将调用某个工具 |
| `tool_result` | 工具执行结果 |
| `plan` | 模型输出的 `<plan>`（已解析） |
| `finish` | 本轮模型自然结束 |
| `done` | 整次 run 完成 |
| `error` | 出错 |

**客户端发送**

```json
{ "session_id": "sess_abc123", "workspace": "...", "message": "你好", "model": "gpt-4o-mini" }
```

---

## 2. Agent

### `POST /v1/agent/run`

无会话化执行（一次性任务）。适合 CI / 脚本场景。

```json
{
  "workspace": "/path/to/project",
  "task": "为 foo.py 添加单元测试",
  "model": "gpt-4o-mini",
  "provider_id": "openai-default",
  "refs": []
}
```

返回同 `/v1/chat` 响应结构（无 `session_id`）。

---

## 3. Completion

### `POST /v1/completion`

行内补全（CUE）端点。客户端在编辑器中调用。

```json
{
  "prefix": "def fibonacci(n):\n    ",
  "suffix": "",
  "language": "python",
  "max_tokens": 200
}
```

返回：

```json
{ "text": "if n < 2:\n        return n\n    ...", "model": "gpt-4o-mini" }
```

---

## 4. Models

### `GET /v1/models`

列出当前启用的模型与 provider。

```json
{ "providers": [{ "id": "openai-default", "kind": "openai", "default_model": "gpt-4o-mini" }] }
```

---

## 5. Health

### `GET /health` / `GET /healthz`

返回 `{ "status": "ok", "version": "0.1.0" }`，用于健康检查 / 探针。