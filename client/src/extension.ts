/**
 * Trae IDE Clone - VS Code Extension Entry
 *
 * 负责：
 *  1. 扩展激活 / 销毁
 *  2. 注册命令（打开 Chat、运行 Agent、补全开关、构建索引）
 *  3. 实例化 ChatPanel / CompletionProvider / RulesLoader / ApiClient
 *  4. 启动状态条
 */

import * as vscode from 'vscode';

import { ApiClient } from './api/client';
import { WsClient } from './api/websocket';
import { ChatPanel } from './chat/panel';
import { TraeCompletionProvider } from './completion/provider';
import { RulesLoader } from './rules/loader';
import { StatusBar } from './config/statusbar';
import { Config } from './config/config';
import { Logger } from './utils/logger';

let chatPanel: ChatPanel | undefined;
let completionProvider: TraeCompletionProvider | undefined;
let statusBar: StatusBar | undefined;
let rulesLoader: RulesLoader | undefined;

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  const logger = new Logger('trae');
  logger.info('Activating Trae IDE Clone extension');

  const cfg = new Config();
  const apiClient = new ApiClient(cfg, logger);
  const wsClient = new WsClient(cfg, logger);

  // Status bar
  statusBar = new StatusBar(cfg, apiClient);
  context.subscriptions.push(statusBar);

  // Rules loader
  rulesLoader = new RulesLoader(logger);
  await rulesLoader.refresh();

  // Chat panel
  chatPanel = new ChatPanel(context, cfg, apiClient, wsClient, rulesLoader, logger);
  context.subscriptions.push(
    vscode.window.registerWebviewPanelSerializer(ChatPanel.viewType, chatPanel),
  );

  // Commands
  context.subscriptions.push(
    vscode.commands.registerCommand('trae.openChat', () => chatPanel?.reveal()),
    vscode.commands.registerCommand('trae.runAgent', async () => {
      const editor = vscode.window.activeTextEditor;
      const selection = editor?.selection;
      const selectedText = selection && !selection.isEmpty ? editor!.document.getText(selection) : '';
      await chatPanel?.reveal();
      await chatPanel?.runOnSelection(selectedText);
    }),
    vscode.commands.registerCommand('trae.toggleInlineCompletion', async () => {
      const cur = cfg.completionEnabled;
      await cfg.setCompletionEnabled(!cur);
      vscode.window.showInformationMessage(`Trae completion: ${!cur ? 'ON' : 'OFF'}`);
    }),
    vscode.commands.registerCommand('trae.indexWorkspace', async () => {
      const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      if (!ws) {
        vscode.window.showWarningMessage('No workspace open.');
        return;
      }
      try {
        const r = await apiClient.indexBuild(ws, true);
        vscode.window.showInformationMessage(`Indexed: ${r.files} files, ${r.chunks} chunks`);
      } catch (e: any) {
        vscode.window.showErrorMessage(`Index failed: ${e?.message ?? e}`);
      }
    }),
  );

  // Inline completion
  completionProvider = new TraeCompletionProvider(apiClient, cfg, logger);
  if (cfg.completionEnabled) {
    context.subscriptions.push(
      vscode.languages.registerInlineCompletionItemProvider(
        { pattern: '**' },
        completionProvider,
      ),
    );
  }

  // Reload rules on workspace change
  context.subscriptions.push(
    vscode.workspace.onDidChangeWorkspaceFolders(() => rulesLoader?.refresh()),
  );

  logger.info('Trae IDE Clone activated');
}

export function deactivate(): void {
  chatPanel?.dispose();
  statusBar?.dispose();
}