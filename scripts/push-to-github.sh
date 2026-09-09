#!/usr/bin/env bash
# 一键推送 trae-ide-clone 到 GitHub(适用于本仓库)
#
# 用法(任选其一):
#   ./scripts/push-to-github.sh ghp_xxxxxxxx          # 直接传 Token
#   GH_TOKEN=ghp_xxxxxxxx ./scripts/push-to-github.sh  # 或走环境变量
#
# 说明:仅适用于账号 Saferry / 仓库 trae-ide-clone。
#       脚本不把 Token 写入任何配置文件(用后即弃的临时 URL)。

set -euo pipefail

USER="Saferry"
REPO="trae-ide-clone"
CLEAN_URL="https://github.com/${USER}/${REPO}.git"

TOKEN="${1:-${GH_TOKEN:-}}"
if [ -z "${TOKEN}" ]; then
  echo "错误:未提供 GitHub Token。用法: GH_TOKEN=ghp_xxx $0" >&2
  exit 1
fi

# 1. 固定远程地址(干净、不含凭据)
if ! git remote get-url origin >/dev/null 2>&1; then
  git remote add origin "${CLEAN_URL}"
else
  git remote set-url origin "${CLEAN_URL}"
fi

# 2. 带凭据的一次性推送(Token 只出现在命令行,不落盘)
AUTH_URL="https://${TOKEN}@github.com/${USER}/${REPO}.git"
git push "${AUTH_URL}" main:main

# 3. 恢复干净远程并绑定 upstream
git remote set-url origin "${CLEAN_URL}"
git branch --set-upstream-to=origin/main main 2>/dev/null || true

echo
echo "OK,推送完成: https://github.com/${USER}/${REPO}"
