/**
 * REST client: 与服务端 HTTP API 交互。
 */

import { Config } from '../config/config';
import { Logger } from '../utils/logger';

export interface ChatMessageIn {
  role: string;
  content: string;
  tool_call_id?: string | null;
  name?: string | null;
}

export interface ChatRequest {
  session_id?: string | null;
  title?: string | null;
  workspace?: string | null;
  model?: string | null;
  provider_id?: string | null;
  messages: ChatMessageIn[];
  refs?: string[];
}

export interface ChatResponse {
  session_id: string;
  answer: string;
  iterations: number;
  tokens: number;
  tool_calls: Array<{ id: string; name: string; arguments: Record<string, any> }>;
}

export interface AgentRunRequest {
  workspace?: string | null;
  task: string;
  model?: string | null;
  provider_id?: string | null;
  refs?: string[];
}

export interface AgentRunResponse {
  answer: string;
  iterations: number;
  tokens: number;
  tool_calls: Array<{ id: string; name: string; arguments: Record<string, any> }>;
}

export class ApiClient {
  constructor(private readonly cfg: Config, private readonly logger: Logger) {}

  private headers(): Record<string, string> {
    return {
      'Content-Type': 'application/json',
      ...(this.cfg.apiKey ? { 'X-API-Key': this.cfg.apiKey } : {}),
    };
  }

  async chat(req: ChatRequest): Promise<ChatResponse> {
    const r = await fetch(`${this.cfg.serverUrl}/v1/chat`, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify(req),
    });
    if (!r.ok) {
      const text = await r.text();
      throw new Error(`chat ${r.status}: ${text}`);
    }
    return (await r.json()) as ChatResponse;
  }

  async agentRun(req: AgentRunRequest): Promise<AgentRunResponse> {
    const r = await fetch(`${this.cfg.serverUrl}/v1/agent/run`, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify(req),
    });
    if (!r.ok) {
      const text = await r.text();
      throw new Error(`agent ${r.status}: ${text}`);
    }
    return (await r.json()) as AgentRunResponse;
  }

  async complete(prefix: string, suffix: string, language: string): Promise<string> {
    const r = await fetch(`${this.cfg.serverUrl}/v1/completion`, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ prefix, suffix, language, max_tokens: 200 }),
    });
    if (!r.ok) return '';
    const data = (await r.json()) as { text: string };
    return data.text ?? '';
  }

  async listModels(): Promise<{ providers: Array<{ id: string; default_model: string }> }> {
    const r = await fetch(`${this.cfg.serverUrl}/v1/models`, { headers: this.headers() });
    if (!r.ok) throw new Error(`models ${r.status}`);
    return (await r.json()) as any;
  }

  async indexBuild(workspace: string, full = false): Promise<{ files: number; chunks: number }> {
    const r = await fetch(`${this.cfg.serverUrl}/v1/agent/run`, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ workspace, task: 'use index_build tool', refs: [] }),
    });
    if (!r.ok) throw new Error(`index ${r.status}`);
    return { files: 0, chunks: 0 };
  }
}