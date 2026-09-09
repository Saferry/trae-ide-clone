/**
 * Chat Webview Panel.
 *
 * 负责：
 *  - 渲染对话 UI（input + messages + tool events）
 *  - 与服务端 WS 长连接发送 / 接收事件
 *  - 显示 plan / tool_call / tool_result 等中间态
 */

import * as vscode from 'vscode';

import { ApiClient } from '../api/client';
import { WsClient, WsEvent } from '../api/websocket';
import { Config } from '../config/config';
import { RulesLoader } from '../rules/loader';
import { Logger } from '../utils/logger';

export class ChatPanel implements vscode.WebviewPanelSerializer {
  static readonly viewType = 'trae.chatPanel';

  private panel?: vscode.WebviewPanel;
  private currentSessionId: string | null = null;

  constructor(
    private readonly context: vscode.ExtensionContext,
    private readonly cfg: Config,
    private readonly api: ApiClient,
    private readonly ws: WsClient,
    private readonly rules: RulesLoader,
    private readonly logger: Logger,
  ) {
    this.ws.onEvent((e) => this.handleWsEvent(e));
  }

  async reveal(): Promise<void> {
    if (this.panel) {
      this.panel.reveal(vscode.ViewColumn.Beside);
      return;
    }
    this.panel = vscode.window.createWebviewPanel(
      ChatPanel.viewType,
      'Trae Chat',
      vscode.ViewColumn.Beside,
      { enableScripts: true, retainContextWhenHidden: true },
    );
    this.panel.webview.html = this.renderHtml();
    this.panel.webview.onDidReceiveMessage(async (m) => this.onWebviewMessage(m));
    this.panel.onDidDispose(() => (this.panel = undefined));
  }

  async runOnSelection(text: string): Promise<void> {
    if (!this.panel) await this.reveal();
    this.postMessage({ type: 'prefill', content: text });
  }

  async deserializeWebviewPanel(webviewPanel: vscode.WebviewPanel): Promise<void> {
    this.panel = webviewPanel;
    this.panel.webview.html = this.renderHtml();
    this.panel.webview.onDidReceiveMessage(async (m) => this.onWebviewMessage(m));
  }

  private postMessage(m: any): void {
    this.panel?.webview.postMessage(m);
  }

  private async onWebviewMessage(m: any): Promise<void> {
    if (m.type === 'send') {
      const content: string = m.content ?? '';
      if (!content.trim()) return;
      await this.send(content);
    } else if (m.type === 'reset') {
      this.currentSessionId = null;
      this.postMessage({ type: 'cleared' });
    } else if (m.type === 'setApiKey') {
      await this.cfg.setApiKey(m.value ?? '');
      this.postMessage({ type: 'info', content: 'API Key saved.' });
    } else if (m.type === 'setServerUrl') {
      await this.cfg.setServerUrl(m.value ?? '');
      this.postMessage({ type: 'info', content: 'Server URL saved.' });
    } else if (m.type === 'loadConfig') {
      this.postMessage({
        type: 'config',
        apiKey: this.cfg.apiKey,
        serverUrl: this.cfg.serverUrl,
        rules: this.rules.current()?.content ?? '',
        model: this.cfg.modelName,
        provider: this.cfg.modelProvider,
      });
    }
  }

  private async send(content: string): Promise<void> {
    const folders = vscode.workspace.workspaceFolders;
    const workspace = folders?.[0]?.uri.fsPath ?? '';

    this.postMessage({ type: 'user', content });
    this.postMessage({ type: 'assistantStart' });

    this.ws.connect();
    this.ws.send({
      session_id: this.currentSessionId,
      workspace,
      message: content,
      provider_id: this.cfg.modelProvider,
      model: this.cfg.modelName || undefined,
      refs: [],
    });
  }

  private handleWsEvent(e: WsEvent): void {
    if (!this.panel) return;
    if (e.session_id && !this.currentSessionId) {
      this.currentSessionId = e.session_id;
    }
    if (e.type === 'session') {
      this.postMessage({ type: 'session', sessionId: e.session_id });
    } else if (e.type === 'text') {
      this.postMessage({ type: 'assistantDelta', content: e.content ?? '' });
    } else if (e.type === 'tool_call') {
      this.postMessage({ type: 'toolCall', tool: e.tool, args: e.args });
    } else if (e.type === 'tool_result') {
      this.postMessage({ type: 'toolResult', tool: e.tool, result: e.result });
    } else if (e.type === 'plan') {
      this.postMessage({ type: 'plan', content: e.plan ?? '' });
    } else if (e.type === 'finish') {
      this.postMessage({ type: 'assistantEnd' });
    } else if (e.type === 'error') {
      this.postMessage({ type: 'error', content: e.content ?? '' });
    } else if (e.type === 'done') {
      this.postMessage({ type: 'assistantEnd' });
    }
  }

  private renderHtml(): string {
    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta http-equiv="Content-Security-Policy" content="default-src 'self' 'unsafe-inline';" />
<style>
  :root {
    --bg: var(--vscode-editor-background, #1e1e1e);
    --fg: var(--vscode-editor-foreground, #d4d4d4);
    --accent: var(--vscode-textLink-foreground, #3794ff);
    --muted: var(--vscode-descriptionForeground, #8a8a8a);
    --border: var(--vscode-editorWidget-border, #3a3a3a);
  }
  html, body { background: var(--bg); color: var(--fg); font-family: var(--vscode-font-family); margin: 0; padding: 0; }
  body { display: flex; flex-direction: column; height: 100vh; }
  #messages { flex: 1; overflow-y: auto; padding: 12px; }
  .msg { margin-bottom: 12px; padding: 8px 10px; border-radius: 6px; white-space: pre-wrap; word-break: break-word; }
  .user { background: rgba(55,148,255,0.15); border: 1px solid var(--accent); }
  .assistant { background: rgba(127,127,127,0.1); border: 1px solid var(--border); }
  .tool { background: rgba(255,213,79,0.1); border-left: 3px solid #ffd54f; padding: 4px 8px; margin: 4px 0; font-size: 12px; font-family: monospace; }
  .result { background: rgba(76,175,80,0.1); border-left: 3px solid #4caf50; padding: 4px 8px; margin: 4px 0; font-size: 12px; font-family: monospace; white-space: pre-wrap; max-height: 200px; overflow-y: auto; }
  .plan { background: rgba(171,71,188,0.1); border: 1px dashed #ab47bc; padding: 8px; margin: 8px 0; font-size: 12px; }
  .error { background: rgba(244,67,54,0.15); border-left: 3px solid #f44336; padding: 4px 8px; }
  #inputBar { display: flex; border-top: 1px solid var(--border); padding: 8px; gap: 6px; }
  textarea { flex: 1; resize: vertical; min-height: 60px; background: var(--bg); color: var(--fg); border: 1px solid var(--border); border-radius: 4px; padding: 6px; font-family: inherit; }
  button { padding: 6px 12px; background: var(--accent); color: white; border: none; border-radius: 4px; cursor: pointer; }
  button.secondary { background: var(--muted); }
  .toolbar { display: flex; gap: 6px; padding: 6px 12px; border-bottom: 1px solid var(--border); }
  .small { font-size: 11px; color: var(--muted); }
  .tool-args { color: var(--accent); }
</style>
</head>
<body>
<div class="toolbar">
  <button class="secondary" onclick="resetChat()">Reset</button>
  <span class="small" id="sessionInfo"></span>
</div>
<div id="messages"></div>
<div id="inputBar">
  <textarea id="prompt" placeholder="Ask Trae to do something... (Ctrl+Enter to send)"></textarea>
  <button onclick="send()">Send</button>
</div>
<script>
const vscode = acquireVsCodeApi();
const messages = document.getElementById('messages');
const promptEl = document.getElementById('prompt');
const sessionEl = document.getElementById('sessionInfo');

function append(html) {
  const div = document.createElement('div');
  div.className = 'msg';
  div.innerHTML = html;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
  return div;
}

let currentAssistant = null;

window.addEventListener('message', (e) => {
  const m = e.data;
  switch (m.type) {
    case 'session':
      sessionEl.textContent = 'session: ' + m.sessionId;
      break;
    case 'user':
      append('<div class="user">' + escapeHtml(m.content) + '</div>');
      break;
    case 'assistantStart':
      currentAssistant = append('<div class="assistant"></div>');
      break;
    case 'assistantDelta':
      if (!currentAssistant) currentAssistant = append('<div class="assistant"></div>');
      currentAssistant.textContent += m.content;
      messages.scrollTop = messages.scrollHeight;
      break;
    case 'assistantEnd':
      currentAssistant = null;
      break;
    case 'toolCall':
      append('<div class="tool">🔧 <b>' + escapeHtml(m.tool) + '</b> <span class="tool-args">' + escapeHtml(JSON.stringify(m.args ?? {})) + '</span></div>');
      break;
    case 'toolResult':
      append('<div class="result">✓ <b>' + escapeHtml(m.tool) + '</b><br>' + escapeHtml((m.result ?? '').slice(0, 1500)) + '</div>');
      break;
    case 'plan':
      append('<div class="plan">📋 Plan:<br>' + escapeHtml(m.content) + '</div>');
      break;
    case 'error':
      append('<div class="error">⚠️ ' + escapeHtml(m.content ?? '') + '</div>');
      currentAssistant = null;
      break;
    case 'cleared':
      messages.innerHTML = '';
      break;
    case 'prefill':
      promptEl.value = m.content;
      break;
    case 'config':
      // could render a config UI here
      break;
  }
});

function send() {
  const v = promptEl.value.trim();
  if (!v) return;
  vscode.postMessage({ type: 'send', content: v });
  promptEl.value = '';
}

function resetChat() {
  vscode.postMessage({ type: 'reset' });
}

promptEl.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    send();
  }
});

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c] ?? c));
}

vscode.postMessage({ type: 'loadConfig' });
</script>
</body>
</html>`;
  }

  dispose(): void {
    this.panel?.dispose();
  }
}