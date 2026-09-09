/**
 * Shared Protocol —— 客户端 / 服务端共享类型定义
 *
 * 拷贝此文件到客户端与服务端各自的代码中使用；
 * 也可以用 ts-proto / openapi-generator 等工具生成。
 */

export type Role = 'system' | 'user' | 'assistant' | 'tool';

export interface ToolCallWire {
  id: string;
  name: string;
  arguments: Record<string, any>;
}

export interface ChatMessageWire {
  role: Role;
  content: string;
  name?: string | null;
  tool_calls?: ToolCallWire[] | null;
  tool_call_id?: string | null;
}

export interface ChatRequestWire {
  session_id?: string | null;
  title?: string | null;
  workspace?: string | null;
  model?: string | null;
  provider_id?: string | null;
  messages: ChatMessageWire[];
  refs?: string[];
}

export interface ChatResponseWire {
  session_id: string;
  answer: string;
  iterations: number;
  tokens: number;
  tool_calls: ToolCallWire[];
}

export interface AgentRunRequestWire {
  workspace?: string | null;
  task: string;
  model?: string | null;
  provider_id?: string | null;
  refs?: string[];
}

export interface AgentRunResponseWire {
  answer: string;
  iterations: number;
  tokens: number;
  tool_calls: ToolCallWire[];
}

// =================== WebSocket 事件 =====================

export type WsEventType =
  | 'session'
  | 'text'
  | 'tool_call'
  | 'tool_result'
  | 'plan'
  | 'finish'
  | 'done'
  | 'error';

export interface WsEventWire {
  type: WsEventType;
  session_id?: string;
  iteration?: number;
  content?: string;
  tool?: string;
  args?: Record<string, any>;
  result?: string;
  plan?: string;
}

export interface WsSendWire {
  session_id?: string | null;
  workspace?: string;
  message: string;
  provider_id?: string;
  model?: string;
  refs?: string[];
}