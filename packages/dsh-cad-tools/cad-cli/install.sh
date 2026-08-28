#!/usr/bin/env bash
# cad-cli 一键安装脚本（macOS / Linux）
#
# 用法：在仓库根目录执行
#   bash install.sh
#
# 行为：
#   1. 探测 Python 3.11–3.14（可用 CAD_PYTHON=/path/to/python3 覆盖）
#   2. 创建隔离虚拟环境（默认 <repo>/.venv，可用 INSTALL_VENV=/path 覆盖；
#      设 INSTALL_VENV=~/.cache/dsh-cad/venv 可与 DSH cad-studio 插件共享）
#   3. pip install -e . （build123d / OCP / pyvista 等，约 200–400MB 下载）
#   4. 冒烟验证：cad --help + import build123d
#
# 不需要 sudo，不污染全局 site-packages。失败时给出针对性提示后以非零码退出。

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${INSTALL_VENV:-$REPO_ROOT/.venv}"

say()  { printf '\033[1;32m[cad-install]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[cad-install]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[cad-install]\033[0m %s\n' "$*" >&2; exit 1; }

# ---------- 1. 探测 Python ----------
pick_python() {
  if [[ -n "${CAD_PYTHON:-}" ]]; then
    [[ -x "$CAD_PYTHON" ]] || die "CAD_PYTHON=$CAD_PYTHON 不可执行"
    command -v "$CAD_PYTHON" >/dev/null 2>&1 || die "CAD_PYTHON=$CAD_PYTHON 不在 PATH 中（请给绝对路径）"
    echo "$CAD_PYTHON"; return
  fi
  for cand in python3.14 python3.13 python3.12 python3.11 python3; do
    command -v "$cand" >/dev/null 2>&1 || continue
    if "$cand" -c 'import sys; sys.exit(0 if (3,11)<=sys.version_info[:2]<=(3,14) else 1)' 2>/dev/null; then
      echo "$cand"; return
    fi
  done
  echo ""
}

say "1/5 探测 Python（3.11–3.14）..."
PY="$(pick_python)"
if [[ -z "$PY" ]]; then
  warn "未找到 Python 3.11–3.14。安装方式："
  warn "  macOS:  brew install python@3.12"
  warn "  Ubuntu: sudo apt install python3.12 python3.12-venv"
  warn "  或已有解释器时: CAD_PYTHON=/path/to/python bash install.sh"
  die "缺少可用的 Python 解释器"
fi
PYVER="$("$PY" --version 2>&1)"
say "使用 $PYVER ($PY)"

# ---------- 2. 创建 venv ----------
say "2/5 创建虚拟环境 $VENV_DIR ..."
if [[ -x "$VENV_DIR/bin/python" ]]; then
  say "复用已有 venv：$VENV_DIR"
else
  "$PY" -m venv "$VENV_DIR" || die "venv 创建失败（Ubuntu 需 python3.x-venv 包）"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ---------- 3. 安装依赖 ----------
say "3/5 安装依赖（build123d/OCP 约 200–400MB，请耐心）..."
python -m pip install --upgrade pip >/dev/null
pip install -e "$REPO_ROOT" || die "pip install 失败；可重试或换镜像：PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple bash install.sh"

# ---------- 3.5 可选联动：cad-parts 标准件库（软依赖，存在才装）----------
# 姐妹仓布局（cad-tool 与 cad-parts 同级 clone）或工作区内联布局都会被探测到；
# 也可用 CAD_PARTS_ROOT=/path/to/cad-parts 显式指定。未找到则静默跳过，不影响 CLI。
for parts_dir in "${CAD_PARTS_ROOT:-}" "$REPO_ROOT/cad-parts" "$REPO_ROOT/../cad-parts"; do
  [[ -n "$parts_dir" && -f "$parts_dir/src/cadparts/__init__.py" ]] || continue
  say "3.5/5 检测到标准件库 cad-parts（${parts_dir}），联动安装..."
  pip install -e "$parts_dir" || warn "cad-parts 安装失败（不影响 CAD CLI，可稍后手动 pip install -e）"
  break
done

# ---------- 4. 冒烟验证 ----------
say "4/5 冒烟验证..."
cad --help >/dev/null 2>&1 || die "cad 命令不可用——安装异常，请把上方 pip 输出反馈给维护者"
python -c "import build123d, cad_cli; print('build123d', __import__('build123d').__version__ if hasattr(__import__('build123d'),'__version__') else 'ok', '/ cad_cli ok')" \
  || die "import build123d 失败"

# ---------- 5. 完成 ----------
say "5/5 安装完成 ✔"
cat <<EOF

  CLI 入口     : $VENV_DIR/bin/cad
  激活环境     : source $VENV_DIR/bin/activate
  第一个模型包 : cad init demo.456d --name=demo && cd demo.456d && cad run
  验证安装     : cad --help && cad env-status 2>/dev/null || true

  （DSH 用户：INSTALL_VENV=~/.cache/dsh-cad/venv bash install.sh 可与 cad-studio 插件共享环境）
EOF
