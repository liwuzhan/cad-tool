#!/usr/bin/env bash
# 同步 Host、Client 与 cad-cli 到所有发行目录。
# npm/Codex 插件只能打包自身目录内文件，所以 CLI 以副本形式随插件分发。
# 用法：在仓库根执行  bash packages/sync-vendor.sh
# 发布 npm 前必跑一次，保证 vendor 与 src/ 一致。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI_DESTS=(
  "$ROOT/packages/dsh-cad-tools/cad-cli"
  "$ROOT/packages/dsh-cad-studio/cad-cli"
  "$ROOT/plugins/cad-tool/cad-cli"
)

mkdir -p "$ROOT/packages/dsh-cad-tools/lib" "$ROOT/packages/dsh-cad-studio/lib"
cp "$ROOT/plugin/cad-studio/cad-studio-plugin.mjs" "$ROOT/packages/dsh-cad-tools/lib/index.js"
cp "$ROOT/plugin/cad-studio/cad-studio-plugin.mjs" "$ROOT/packages/dsh-cad-studio/lib/index.js"
node "$ROOT/packages/dsh-cad-client/build.mjs"

for dest in "${CLI_DESTS[@]}"; do
  echo "[sync-vendor] src/ -> $dest"
  mkdir -p "$dest"
  rsync -a --delete --exclude='__pycache__/' --exclude='*.pyc' "$ROOT/src/" "$dest/src/"
  rm -rf "$dest/src/cad_cli.egg-info"
  find "$dest" -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
  cp "$ROOT/pyproject.toml" "$ROOT/install.sh" "$ROOT/install.ps1" "$ROOT/README.md" "$dest/"
  diff -r --exclude='__pycache__' --exclude='*.pyc' "$ROOT/src" "$dest/src" >/dev/null || {
    echo "[sync-vendor] 校验失败: $dest" >&2; exit 1; }
  du -sh "$dest"
done

echo "[sync-vendor] OK（Host、Client 与全部 CLI vendor 一致）"
