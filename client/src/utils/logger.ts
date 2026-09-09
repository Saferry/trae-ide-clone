/**
 * Logger: 输出到 Trae 输出通道。
 */

import * as vscode from 'vscode';

export class Logger {
  private channel: vscode.OutputChannel;
  constructor(name: string) {
    this.channel = vscode.window.createOutputChannel(`Trae: ${name}`);
  }
  info(msg: string, ...rest: any[]): void {
    const line = `[INFO] ${msg} ${rest.map((x) => JSON.stringify(x)).join(' ')}`;
    this.channel.appendLine(line);
  }
  warn(msg: string, ...rest: any[]): void {
    this.channel.appendLine(`[WARN] ${msg} ${rest.map((x) => JSON.stringify(x)).join(' ')}`);
  }
  error(msg: string, ...rest: any[]): void {
    this.channel.appendLine(`[ERROR] ${msg} ${rest.map((x) => JSON.stringify(x)).join(' ')}`);
  }
}