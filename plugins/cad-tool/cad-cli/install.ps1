# cad-cli 一键安装脚本（Windows PowerShell 5.1+ / pwsh）
#
# 用法：在仓库根目录执行
#   powershell -ExecutionPolicy Bypass -File install.ps1
#
# 行为：
#   1. 探测 Python 3.11-3.14（可用 $env:CAD_PYTHON 覆盖）
#   2. 创建隔离虚拟环境（默认 <repo>\.venv，可用 $env:INSTALL_VENV 覆盖）
#   3. pip install -e . （build123d / OCP / pyvista 等，约 200-400MB 下载）
#   4. 冒烟验证：cad --help + import build123d
#
# 不污染全局 site-packages。

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = if ($env:INSTALL_VENV) { $env:INSTALL_VENV } else { Join-Path $RepoRoot ".venv" }

function Say($msg)  { Write-Host "[cad-install] $msg" -ForegroundColor Green }
function Die($msg)  { Write-Host "[cad-install] $msg" -ForegroundColor Red; exit 1 }

# ---------- 1. 探测 Python ----------
Say "1/5 探测 Python (3.11-3.14)..."
$py = $null
if ($env:CAD_PYTHON) {
    $py = $env:CAD_PYTHON
    if (-not (Test-Path $py)) { Die "CAD_PYTHON=$py 不存在" }
} else {
    foreach ($cand in @("py -3.14", "py -3.13", "py -3.12", "py -3.11", "python3", "python")) {
        try {
            $ver = & ([scriptblock]::Create("$cand --version")) 2>$null
            if ($ver -match "Python (3\.1[1-4])\.") { $py = $cand; break }
        } catch { continue }
    }
}
if (-not $py) {
    Write-Host "[cad-install] 未找到 Python 3.11-3.14。请从 https://www.python.org/downloads/ 安装（勾选 Add to PATH）" -ForegroundColor Yellow
    Die "缺少可用的 Python 解释器"
}
Say "使用 ($py)"

# ---------- 2. 创建 venv ----------
Say "2/5 创建虚拟环境 $VenvDir ..."
if (Test-Path (Join-Path $VenvDir "Scripts\python.exe")) {
    Say "复用已有 venv：$VenvDir"
} else {
    & ([scriptblock]::Create("$py -m venv `"$VenvDir`"")) || Die "venv 创建失败"
}

$venvPy = Join-Path $VenvDir "Scripts\python.exe"
$venvCad = Join-Path $VenvDir "Scripts\cad.exe"

# ---------- 3. 安装依赖 ----------
Say "3/5 安装依赖（build123d/OCP 约 200-400MB，请耐心）..."
& $venvPy -m pip install --upgrade pip 2>$null | Out-Null
& $venvPy -m pip install -e "$RepoRoot"
if ($LASTEXITCODE -ne 0) { Die "pip install 失败；可重试或换镜像：`$env:PIP_INDEX_URL='https://pypi.tuna.tsinghua.edu.cn/simple'" }

# ---------- 4. 冒烟验证 ----------
Say "4/5 冒烟验证..."
& $venvCad --help | Out-Null
if ($LASTEXITCODE -ne 0) { Die "cad 命令不可用——安装异常" }
& $venvPy -c "import build123d, cad_cli"
if ($LASTEXITCODE -ne 0) { Die "import build123d 失败" }

# ---------- 5. 完成 ----------
Say "5/5 安装完成"
Write-Host ""
Write-Host "  CLI 入口     : $venvCad"
Write-Host "  激活环境     : $VenvDir\Scripts\Activate.ps1"
Write-Host "  第一个模型包 : cad init demo.456d --name=demo; cd demo.456d; cad run"
Write-Host "  （DSH 用户：`$env:INSTALL_VENV=`"$HOME\.cache\dsh-cad\venv`" 后重跑可与 cad-studio 插件共享环境）"
