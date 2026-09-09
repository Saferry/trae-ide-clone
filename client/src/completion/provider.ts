/**
 * 行内补全 Provider（CUE 风格）。
 *
 * 触发时机：用户在编辑器内停止输入 ~200ms 后，向服务端发送上下文前后缀，索取一个续写。
 * 仅在 trae.completion.enabled = true 时被注册。
 */

import * as vscode from 'vscode';

import { ApiClient } from '../api/client';
import { Config } from '../config/config';
import { Logger } from '../utils/logger';

export class TraeCompletionProvider implements vscode.InlineCompletionItemProvider {
  private lastRequestAt = 0;
  private lastDoc: vscode.TextDocument | null = null;

  constructor(
    private readonly api: ApiClient,
    private readonly cfg: Config,
    private readonly logger: Logger,
  ) {}

  async provideInlineCompletionItems(
    document: vscode.TextDocument,
    position: vscode.Position,
    context: vscode.InlineCompletionContext,
    token: vscode.CancellationToken,
  ): Promise<vscode.InlineCompletionItem[] | vscode.InlineCompletionList | null> {
    // 避免重复请求：仅在用户停顿且 triggerKind 为 Invoke 时主动返回
    if (context.triggerKind === vscode.InlineCompletionTriggerKind.Invoke) {
      // 显式触发（用户主动）必返
    } else if (context.triggerKind === vscode.InlineCompletionTriggerKind.Automatic) {
      // 自动触发：加 200ms 防抖
      const now = Date.now();
      if (now - this.lastRequestAt < 200) return null;
      this.lastRequestAt = now;
    }

    const offset = document.offsetAt(position);
    const prefix = document.getText(new vscode.Range(new vscode.Position(0, 0), position));
    // 仅取光标后 800 字符作为 suffix
    const endPos = document.positionAt(Math.min(offset + 800, document.getText().length));
    const suffix = document.getText(new vscode.Range(position, endPos));

    try {
      const text = await this.api.complete(prefix, suffix, document.languageId);
      if (!text) return null;
      const item = new vscode.InlineCompletionItem(text, new vscode.Range(position, position));
      item.insertText = text;
      return [item];
    } catch (e: any) {
      this.logger.warn('completion failed', e?.message);
      return null;
    }
  }
}