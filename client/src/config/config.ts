/**
 * Config: 包装 vscode.workspace.getConfiguration，集中所有配置读写。
 */

import * as vscode from 'vscode';

export class Config {
  private readonly root = vscode.workspace.getConfiguration('trae');

  get serverUrl(): string {
    return (this.root.get<string>('server.url') ?? 'http://127.0.0.1:8080').replace(/\/$/, '');
  }
  get apiKey(): string {
    return this.root.get<string>('server.apiKey') ?? '';
  }
  get wsPath(): string {
    return this.root.get<string>('server.wsPath') ?? '/v1/chat/ws';
  }
  get modelProvider(): string {
    return this.root.get<string>('model.provider') ?? 'openai-default';
  }
  get modelName(): string {
    return this.root.get<string>('model.name') ?? '';
  }
  get completionEnabled(): boolean {
    return this.root.get<boolean>('completion.enabled') ?? true;
  }
  get rulesAutoLoad(): boolean {
    return this.root.get<boolean>('rules.autoLoad') ?? true;
  }
  get rulesPath(): string {
    return this.root.get<string>('rules.path') ?? '.trae/rules.md';
  }

  async setCompletionEnabled(v: boolean): Promise<void> {
    await this.root.update('completion.enabled', v, vscode.ConfigurationTarget.Global);
  }

  async setApiKey(v: string): Promise<void> {
    await this.root.update('server.apiKey', v, vscode.ConfigurationTarget.Global);
  }

  async setServerUrl(v: string): Promise<void> {
    await this.root.update('server.url', v, vscode.ConfigurationTarget.Global);
  }
}