/**
 * WebSocket client: 与服务端 /v1/chat/ws 维持长连接，发送消息与接收流式事件。
 */

import { Config } from '../config/config';
import { Logger } from '../utils/logger';
import WebSocket from 'ws';

export interface WsEvent {
  type: string;
  content?: string;
  tool?: string;
  args?: Record<string, any>;
  result?: string;
  plan?: string;
  session_id?: string;
  iteration?: number;
}

export type EventHandler = (e: WsEvent) => void;

export class WsClient {
  private ws: WebSocket | null = null;
  private handlers = new Set<EventHandler>();
  private reconnectAttempts = 0;

  constructor(private readonly cfg: Config, private readonly logger: Logger) {}

  connect(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) return;
    const url = this.cfg.serverUrl.replace(/^http/, 'ws') + this.cfg.wsPath;
    const headers: Record<string, string> = {};
    if (this.cfg.apiKey) headers['X-API-Key'] = this.cfg.apiKey;

    try {
      // 在 Node 端运行时（Electron 主进程或扩展主机）使用 ws 包
      this.ws = new WebSocket(url, { headers });
      this.ws.on('open', () => {
        this.reconnectAttempts = 0;
        this.logger.info('WebSocket connected');
      });
      this.ws.on('message', (data) => {
        try {
          const evt = JSON.parse(data.toString()) as WsEvent;
          this.handlers.forEach((h) => h(evt));
        } catch (e: any) {
          this.logger.warn('ws message parse error', e?.message);
        }
      });
      this.ws.on('close', () => {
        this.logger.warn('WebSocket closed');
        this.scheduleReconnect();
      });
      this.ws.on('error', (e: any) => {
        this.logger.warn('WebSocket error', e?.message ?? e);
      });
    } catch (e: any) {
      this.logger.warn('Failed to connect WS', e?.message);
      this.scheduleReconnect();
    }
  }

  send(payload: Record<string, any>): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.connect();
      setTimeout(() => this.send(payload), 200);
      return;
    }
    this.ws.send(JSON.stringify(payload));
  }

  onEvent(h: EventHandler): () => void {
    this.handlers.add(h);
    return () => this.handlers.delete(h);
  }

  close(): void {
    try {
      this.ws?.close();
    } catch (e: any) {
      // ignore
    }
    this.ws = null;
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts > 5) return;
    const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 15000);
    this.reconnectAttempts += 1;
    setTimeout(() => this.connect(), delay);
  }
}