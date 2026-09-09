# Shared Protocol —— 客户端 / 服务端共享协议

> 本目录的 TypeScript 类型是客户端与服务端约定的 JSON schema，
> 客户端可以直接 import 使用，服务端可用 pydantic 模型 + 同名 JSON key 保持兼容。

## 主要类型

| 文件 | 内容 |
| --- | --- |
| `messages.ts` | REST 请求/响应类型、WebSocket 事件类型 |

## 协议约定

- 所有 REST 请求头：`Content-Type: application/json`，鉴权 `X-API-Key`。
- WebSocket 端点：`{serverUrl}/v1/chat/ws`，鉴权同 REST。
- 事件类型枚举：`session | text | tool_call | tool_result | plan | finish | done | error`
- 工具调用约定：服务端解析模型文本中的 `<tool_call name="...">{"arg":"value"}</tool_call>`（注意闭合标签内含零宽空格）
- 计划约定：`<plan>{JSON 或 Markdown}</plan>`
- 终态约定：`<final_answer>...</final_answer>`

## 兼容性

后续如需切换到 Protobuf / FlatBuffers，可在本目录追加 `*.proto` 并提供生成脚本。