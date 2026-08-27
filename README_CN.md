# CAD CLI v2.0 使用指南

基于 build123d 的 AI 原生 CAD 命令行工具。

## 目录

- [系统概述](#系统概述)
- [安装](#安装)
- [快速开始](#快速开始)
- [AI 使用流程](#ai-使用流程)
- [命令参考](#命令参考)
- [已知限制](#已知限制)

---

## 系统概述

### 这是什么？

CAD CLI 是一个让 AI（如 Claude）能够进行 CAD 建模的命令行工具。它的核心理念是：

1. **脚本驱动**：用 Python 代码描述几何体，而不是手动操作
2. **JSONL 输出**：所有命令返回机器可解析的 JSON，便于 AI 理解
3. **版本控制**：类似 Git 的提交历史，可追溯设计变更
4. **自包含包**：`.456d` 模型包包含代码、工件、历史的完整快照

### 核心架构

```
my_model.456d/                    # 模型包（自包含目录）
├── manifest.json                 # 包配置（名称、设置、当前版本）
├── src/
│   └── main.py                   # CAD 脚本（定义 result 变量）
├── vcs/
│   └── commits.jsonl             # 提交历史（追加写入）
├── artifacts/
│   └── <commit_hash>/            # 每个提交的工件
│       ├── model.step            # STEP 格式几何体
│       ├── thumb_iso.png         # 渲染缩略图
│       ├── thumb_iso.json        # 渲染参数（相机位置等）
│       └── metrics.json          # 几何指标（体积、面数等）
└── runlog/                       # 执行日志
```

### 工作流程

```
编写脚本 → 执行(run) → 验证(validate) → 检查(inspect) → 提交(commit)
                                                              ↓
                                              生成 STEP + 缩略图 + 指标
```

---

## 安装

### Codex 插件

```bash
codex plugin marketplace add liwuzhan/cad-tool --ref main
codex plugin add cad-tool@cad-tool
```

安装后新建 Codex 会话。插件安装本身不会执行下载脚本；第一次真正进行 CAD
任务时，它会先检查本地环境，并在创建隔离依赖环境前请求确认。

### DSH 插件包

商店发行包位于 `packages/dsh-cad-studio`，一个 tarball 同时包含 16 个 Host
工具、浏览器结果卡和完整 Python CLI。在商店条目合并前，可用 Release tarball
或本地打包结果安装：

```bash
dsh plugin --profile <profile> add -w dsh-cad-studio
```

在平台渲染器无法生成 PNG 的无头自动化环境中，可设置
`CAD_SKIP_RENDER=1`。提交仍会完成几何检查并保存 STEP、指标、验证结果和版本
历史，只跳过缩略图。

### 一键安装

```bash
git clone https://github.com/liwuzhan/cad-tool
cd cad-tool
bash install.sh          # macOS / Linux
# Windows: powershell -ExecutionPolicy Bypass -File install.ps1
```

脚本要求 **Python 3.11–3.14**，会在仓库内创建隔离的 `.venv`
（约下载 300MB：build123d + OCP + pyvista），自带冒烟验证，
不污染全局 site-packages。

### AI 代装（复制粘贴给语言模型）

把下面这段话发给任意编程助手（Claude Code / DSH / Cursor ...），
它读这份 README 就能自己完成安装：

```text
帮我安装 CAD CLI 工具：
1. git clone https://github.com/liwuzhan/cad-tool && cd cad-tool
2. macOS/Linux 执行 bash install.sh；Windows 执行
   powershell -ExecutionPolicy Bypass -File install.ps1
   （需要 Python 3.11-3.14；脚本会建隔离 .venv，禁止装进全局环境）
3. 验证：.venv/bin/cad --help（Windows: .venv\Scripts\cad.exe --help），
   再建一个临时包冒烟：cad init /tmp/smoke.456d --name=smoke
   && cd /tmp/smoke.456d && cad run
4. 汇报安装的版本与冒烟结果。
若 install.sh 失败，按脚本打印的提示（Python 版本、pip 镜像）排查后重试，
不要一次失败就放弃。
```

### 手动安装

```bash
# conda
conda create -n cad-cli python=3.12
conda activate cad-cli
conda install -c conda-forge build123d pyvista
pip install -e .

# 或 venv + pip
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e .
```

---

## 快速开始

### 1. 创建模型包

```bash
cad init my_part --name="My Part"
cd my_part.456d
```

### 2. 编写脚本

编辑 `src/main.py`：

```python
from build123d import *

# 创建一个带孔的盒子
box = Box(100, 60, 30)
hole = Cylinder(10, 30)
result = box - hole  # 必须赋值给 result
```

### 3. 执行和检查

```bash
# 执行脚本（仅在内存中，不保存工件）
cad run

# 验证几何有效性
cad validate

# 查看几何属性
cad inspect --prop=volume
cad inspect --prop=bounds
```

### 4. 提交版本

```bash
# 提交会执行完整流程：执行 → 验证 → 保存STEP → 渲染 → 记录历史
cad commit -m "Initial design with center hole"
```

### 5. 查看和导出

```bash
# 查看历史
cad log

# 导出为 STEP 文件
cad export --format=step --output=../my_part.step
```

---

## AI 使用流程

### 典型对话流程

**人类**: "帮我设计一个 100x60x30 的盒子，中间有个直径 20 的通孔"

**AI 执行步骤**:

```bash
# 1. 如果还没有模型包，先创建
cad init box_with_hole --name="Box with Hole"
```

```bash
# 2. 修改 src/main.py（使用 Edit 工具）
```

```python
from build123d import *

box = Box(100, 60, 30)
hole = Cylinder(10, 30)  # 半径10 = 直径20
result = box - hole
```

```bash
# 3. 执行并验证
cad run
# 输出: {"event":"run_success","payload":{"metrics":{"volume":...}}}

cad validate
# 输出: {"event":"validate_success"}

# 4. 检查是否符合要求
cad inspect --prop=volume
# 输出: {"event":"inspect_result","payload":{"property":"volume","value":170685.83...}}

# 5. 确认无误后提交
cad commit -m "Box 100x60x30 with D20 center hole"
```

### AI 如何解析输出

所有命令输出 JSONL 格式，每行一个 JSON 对象：

```json
{"event": "run_start", "ts": "2026-01-31T10:00:00", "payload": {"script": "src/main.py"}}
{"event": "run_success", "ts": "2026-01-31T10:00:01", "payload": {"metrics": {"volume": 170685.83, "area": 24628.32, "face_count": 8}}}
```

**AI 应关注的字段**:
- `event`: 事件类型（`*_success` 表示成功，`*_error` 表示失败）
- `payload.metrics`: 几何指标，用于验证设计是否正确
- `payload.error`: 错误详情，包含 `code`、`message`、`hint`

### 迭代设计流程

```
人类提需求 → AI 写脚本 → run → 检查 metrics →
                              ↓
                    不符合要求？修改脚本，重新 run
                              ↓
                    符合要求？commit 保存
```

### 错误处理

当 AI 收到错误输出时：

```json
{"event": "run_error", "payload": {"error": {"code": "E-SYNTAX", "message": "...", "hint": "..."}}}
```

AI 应该：
1. 读取 `hint` 获取修复建议
2. 根据 `code` 判断错误类型：
   - `E-SYNTAX`: 语法错误，检查 Python 代码
   - `E-RUNTIME`: 运行时错误，检查变量和函数调用
   - `E-BREP`: 几何错误，检查布尔运算是否有效

---

## 命令参考

### 项目管理

| 命令 | 说明 | 示例 |
|------|------|------|
| `cad init <path> --name=<name>` | 创建模型包 | `cad init gear --name="Spur Gear"` |
| `cad status` | 显示当前状态 | `cad status` |
| `cad log` | 显示提交历史 | `cad log --limit=5` |

### 建模流程

| 命令 | 说明 | 示例 |
|------|------|------|
| `cad run [script]` | 执行脚本（不保存工件） | `cad run` |
| `cad commit -m "msg"` | 提交（执行+保存工件） | `cad commit -m "Add holes"` |
| `cad validate` | 验证几何有效性 | `cad validate` |
| `cad checkout <hash>` | 切换到指定版本 | `cad checkout abc123` |

### 检查与输出

| 命令 | 说明 | 示例 |
|------|------|------|
| `cad inspect --prop=<p>` | 查询属性 | `cad inspect --prop=volume` |
| `cad inspect --list-targets` | 列出拓扑元素 | `cad inspect --list-targets` |
| `cad render --views=<v>` | 生成渲染图 | `cad render --views=iso,top` |
| `cad export --format=<f>` | 导出模型 | `cad export --format=step --output=out.step` |

### 工件管理

| 命令 | 说明 | 示例 |
|------|------|------|
| `cad artifacts list` | 列出工件及大小 | `cad artifacts list` |
| `cad artifacts clean` | 清理旧工件 | `cad artifacts clean` |

### 分支管理

| 命令 | 说明 | 示例 |
|------|------|------|
| `cad branch list` | 列出所有分支 | `cad branch list` |
| `cad branch create <name>` | 创建新分支 | `cad branch create feature-v2` |
| `cad branch switch <name>` | 切换分支（恢复 STEP + 脚本） | `cad branch switch main` |
| `cad branch delete <name>` | 删除分支 | `cad branch delete old-feature` |

---

## 已知限制

### 1. Windows 超时无法强制中断

**问题**: 在 Windows 上，如果脚本包含死循环，超时机制无法真正终止 `exec()`。

**影响**: 脚本可能卡住整个进程。

**临时方案**: 避免编写可能无限循环的代码。AI 在生成代码时应避免 `while True` 等结构。

**计划**: v2.1 将实现子进程隔离。

### 2. `build` 命令不生成工件

**问题**: `cad build` 仅执行脚本和验证，不保存 STEP 或缩略图。

**说明**: 这是设计如此，用于快速迭代。要保存工件请使用 `cad commit`。

### 3. 无回滚机制

**问题**: 如果 `commit` 过程中途失败（如渲染失败），可能产生不完整的工件。

**影响**: 工件目录可能只有部分文件。

**临时方案**: 失败后手动删除不完整的工件目录。

### 4. `releases_only` 清理策略未实现

**问题**: `cad artifacts clean --policy=releases_only` 会错误地删除所有工件。

**临时方案**: 仅使用 `latest_per_branch` 或 `all_commits` 策略。

### 5. 分支合并未实现

**问题**: 分支管理支持创建、切换、删除，但不支持分支合并。

**现状**: 可以在不同分支上独立工作，但需要手动合并代码。

---

## 脚本编写规范

### 必须定义 `result` 变量

```python
from build123d import *

# 正确 ✓
result = Box(10, 10, 10)

# 错误 ✗ - 没有定义 result
box = Box(10, 10, 10)
```

### 使用 build123d API

```python
from build123d import *

# 基本形状
box = Box(length, width, height)
cyl = Cylinder(radius, height)
sphere = Sphere(radius)

# 布尔运算
union = box + cyl      # 并集
diff = box - cyl       # 差集
inter = box & cyl      # 交集

# 变换
moved = box.move(Location((x, y, z)))
rotated = box.rotate(Axis.Z, degrees)

# 最终结果
result = diff
```

### 参数化设计

```python
from build123d import *

# 参数定义
WIDTH = 100
HEIGHT = 50
HOLE_DIAMETER = 20

# 参数化几何
base = Box(WIDTH, WIDTH, HEIGHT)
hole = Cylinder(HOLE_DIAMETER / 2, HEIGHT)
result = base - hole
```

### 特征级检查点（Checkpoint）

Checkpoint 是检测布尔运算错误的可靠方法。在每个特征操作后添加检查点：

```python
from build123d import *
from cad_cli.feedback import Checkpoint

Checkpoint.reset()

with BuildPart() as part:
    Cylinder(30, 10)
    Checkpoint(part, "base").expect_volume(28274, tolerance=100).expect_solids(1).verify()

    Cylinder(10, 10, mode=Mode.SUBTRACT)
    Checkpoint(part, "hole").expect_volume_decreased().expect_solids(1).verify()

result = part.part
```

**Checkpoint 方法**：

| 方法 | 说明 |
|------|------|
| `.expect_volume(value, tolerance=1.0)` | 断言指定体积 |
| `.expect_volume_decreased()` | 断言体积较上个检查点减少 |
| `.expect_volume_increased()` | 断言体积较上个检查点增加 |
| `.expect_solids(count)` | 断言实体数量（必须验证 = 1） |
| `.expect_faces(count)` | 断言面数 |
| `.expect_bbox_size(x, y, z, tolerance=1.0)` | 断言边界框尺寸 |
| `.verify()` | 执行所有检查，失败时抛出异常 |

Checkpoint 结果会在 JSONL 输出中显示为 `checkpoint_passed` 或 `checkpoint_failed` 事件。

---

## 配置

`manifest.json` 中的关键配置：

```json
{
  "name": "My Model",
  "unit": "mm",
  "timeout_seconds": 60,
  "artifact_policy": "latest_per_branch",
  "render": {
    "default_views": ["top", "front", "right", "iso"],
    "resolution": [800, 600]
  }
}
```

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `timeout_seconds` | 脚本执行超时 | 60 |
| `artifact_policy` | 工件保留策略 | `latest_per_branch` |
| `render.resolution` | 渲染分辨率 | [800, 600] |

---

## 故障排除

### "Not in a model package"

确保在 `.456d` 目录内运行命令，或先执行 `cad init`。

### "Script must define 'result' variable"

脚本末尾必须有 `result = <shape>` 赋值。

### "Invalid BRep"

几何体无效，常见原因：
- 布尔运算失败（物体不相交）
- 自相交几何
- 零厚度特征

### 渲染失败

确保安装了 pyvista：`pip install pyvista`

---

## 版本信息

- **当前版本**: v2.0.0
- **Python 要求**: 3.11+
- **核心依赖**: build123d, pyvista, click
