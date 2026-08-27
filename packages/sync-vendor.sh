#!/usr/bin/env bash
# 同步 cad-cli 源码进 dsh-cad-tools 的 vendor 目录（packages/dsh-cad-tools/cad-cli/）
# npm 包 files 声明只打包目录内文件，所以 CLI 以副本形式随插件分发。
# 用法：在仓库根执行  bash packages/sync-vendor.sh
# 发布 npm 前必跑一次，保证 vendor 与 src/ 一致。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/packages/dsh-cad-tools/cad-cli"

echo "[sync-vendor] src/ -> $DEST"
mkdir -p "$DEST"
rsync -a --delete "$ROOT/src/" "$DEST/src/"
rm -rf "$DEST/src/cad_cli.egg-info"
find "$DEST" -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
cp "$ROOT/pyproject.toml" "$ROOT/install.sh" "$ROOT/install.ps1" "$ROOT/README.md" "$DEST/"

# 一致性校验：两边文件清单应相同
diff -r "$ROOT/src" "$DEST/src" >/dev/null && echo "[sync-vendor] OK（src 与 vendor 一致）" || {
  echo "[sync-vendor] 校验失败" >&2; exit 1; }
du -sh "$DEST"
