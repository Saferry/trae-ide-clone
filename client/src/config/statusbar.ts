/**
 * Status bar: 显示 Trae 服务连接状态与当前模型。
 */

import * as vscode from 'vscode';
import { ApiClient } from '../api/client';
import { Config } from './config';

export class StatusBar {
  private readonly item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);

  constructor(private readonly cfg: Config, private readonly api: ApiClient) {
    this.refresh();
    this.item.show();
  }

  async refresh(): Promise<void> {
    try {
      const models = await this.api.listModels();
      this.item.text = `$(robot) Trae: ${models.providers?.[0]?.id ?? 'no-model'}`;
      this.item.tooltip = `${this.cfg.serverUrl}\n${models.providers?.length ?? 0} providers`;
      this.item.command = 'trae.openChat';
    } catch (e: any) {
      this.item.text = `$(warning) Trae: offline`;
      this.item.tooltip = `${this.cfg.serverUrl}\n${e?.message ?? e}`;
    }
  }

  dispose(): void {
    this.item.dispose();
  }
}