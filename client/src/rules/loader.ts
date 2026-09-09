/**
 * RulesLoader: 加载工作区 .trae/rules.md 并维护一份缓存。
 */

import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';

import { Logger } from '../utils/logger';

export interface RulesContent {
  workspace: string;
  content: string;
  loadedAt: number;
}

export class RulesLoader {
  private cache: RulesContent | null = null;
  constructor(private readonly logger: Logger) {}

  async refresh(): Promise<RulesContent | null> {
    const folders = vscode.workspace.workspaceFolders;
    if (!folders || folders.length === 0) {
      this.cache = null;
      return null;
    }
    const root = folders[0].uri.fsPath;
    const rulesFile = path.join(root, '.trae', 'rules.md');
    if (!fs.existsSync(rulesFile)) {
      this.cache = { workspace: root, content: '', loadedAt: Date.now() };
      return this.cache;
    }
    try {
      const content = fs.readFileSync(rulesFile, 'utf-8');
      this.cache = { workspace: root, content, loadedAt: Date.now() };
      this.logger.info(`Loaded rules from ${rulesFile} (${content.length} chars)`);
      return this.cache;
    } catch (e: any) {
      this.logger.warn(`Failed to read rules: ${e?.message}`);
      return null;
    }
  }

  current(): RulesContent | null {
    return this.cache;
  }
}