# AI-Native CAD CLI 工具设计文档 (v1.0)

## 1. 项目愿景

构建一个基于特征树（Feature Tree）和 Git 理念的 CAD 命令行工具。该工具专为 AI 代理（Agents）设计，使其能够通过 Python 代码（build123d）参与 3D 建模工作，具备版本控制、错误检查和视觉反馈能力。

**v1.0 目标**：实现"写码 → 执行 → 验证 → 渲染 → 导出"的最短闭环，聚焦核心建模流程。

## 2. 环境要求

*   **Python**: >= 3.10
*   **核心依赖**:
    *   `build123d` — 参数化建模内核
    *   `OCP` (opencascade-python) — 几何内核，build123d 的底层依赖
    *   `pyvista` 或 `vtk` — 离屏渲染
    *   `click` — CLI 框架
*   **推荐安装方式**: `conda`（OCP 的 pip 安装在部分平台不可靠）

## 3. 核心架构

系统由三个主要模块组成：
1.  **VCS Core (Version Control System)**: 管理特征树和线性提交历史。
2.  **Runtime Environment (Interpreter)**: 执行 build123d 代码，生成几何体。
3.  **Feedback System (反馈系统)**: 提供错误信息、几何数据和视觉图像。

## 4. 详细功能模块

### 4.1 命令行接口 (CLI)

AI 将通过标准输入/输出与工具交互。

*   **版本控制（线性历史）**:
    *   `init`: 初始化项目，生成 `.cad/` 目录和 `config.json`。
    *   `status`: 查看当前状态（当前提交、是否有未提交的修改）。
    *   `commit -m "message"`: 保存当前特征树状态快照。
    *   `log`: 查看提交历史列表（提交哈希、消息、时间戳、几何指标摘要）。

*   **建模操作**:
    *   `run <script_path>`: 执行指定的 Python 建模脚本。
    *   `render --views="top,front,iso"`: 生成当前模型的多视图截图。
    *   `validate`: 执行参数完整性检查、运行时错误提炼和基础 BRep 检查，返回结构化结果。
    *   `export --format=step|stl --output=<path>`: 导出当前模型到指定格式文件。

*   **几何探针**:
    *   `inspect --prop=bounds`: 获取 Bounding Box (xmin, ymin, zmin, xmax, ymax, zmax)。
    *   `inspect --prop=volume`: 获取体积。
    *   `inspect --prop=area`: 获取总表面积。
    *   `inspect --prop=faces|edges|vertices`: 获取面/边/点计数。
    *   `inspect --list-targets`: 枚举当前模型中可选的拓扑目标（按索引编号）。
    *   `inspect --target=face[0] --prop=center`: 获取指定拓扑元素的属性。

### 4.1.1 输出与错误约定

*   **格式**: 统一采用 JSONL 事件流输出（每行一个 JSON，对象含 `event`、`ts`、`payload`）。
*   **错误码分层**: `E-SYNTAX`、`E-RUNTIME`、`E-CONSTRAINT`、`E-BREP`、`E-RENDER`、`E-IO`；进程退出码与短消息固定。
*   **Payload**: 长文本与图像路径均置于 `payload`，便于重放与审计。

### 4.2 解释器与验证器 (Runtime & Validator)

这是 AI 的"编译器"。

*   **唯一解检查 (Unique Solution Check)**:
    *   **欠定义 (Under-defined)**: 检查是否缺少必要参数（如圆缺少半径）。
    *   **过定义 (Over-defined)**: 捕获几何内核抛出的约束冲突异常。
    *   **运行时错误**: 捕获 Python Traceback，并精简为 AI 可读的格式（文件、行号、错误类型）。
*   **几何有效性 (BRep Check)**:
    *   调用 OCCT `BRepCheck_Analyzer`。
    *   报告非流形（Non-manifold）、自相交（Self-intersection）、未闭合（Open Shell）等错误。
*   **结构化返回**:
    *   错误对象字段：`file`、`line`、`type`、`code`、`message`、`hint`；与 JSONL 事件流对齐。
*   **超时与资源限制**:
    *   `run` 和 `render` 命令受 `config.json` 中 `timeout_seconds` 限制，默认 60 秒。
    *   超时后进程被终止，返回 `E-RUNTIME` 错误。

### 4.3 视觉反馈 (Visual Feedback)

为多模态模型提供"眼睛"。

*   **多视图渲染**:
    *   标准三视图 (Top, Front, Right)。
    *   等轴测图 (Isometric)。
*   **缩略图管理**:
    *   每次 Commit 自动生成缩略图，存储在 `.cad/thumbs/` 下，方便快速预览历史。
    *   同步记录几何指标（体积、BBox、面/边/点计数），用于历史追踪。
*   **输出契约**:
    *   渲染写出 PNG + JSON（记录视图名、相机位姿、时间戳、单位），默认保存到 `.cad/thumbs/`。

### 4.4 几何探针 (Geometry Inspector)

截图只能看大概，无法获取精确数值。AI 需要"尺子"。

*   **目标选择机制**: 使用索引编号引用拓扑元素，格式为 `face[i]`、`edge[i]`、`vertex[i]`。通过 `inspect --list-targets` 获取当前模型的可选目标列表及其摘要信息。
*   **v1 支持的属性**: `bounds`、`volume`、`area`、`center`、`faces`、`edges`、`vertices`。
*   **用途**: 帮助 AI 在进行下一步建模时，能够基于上一步的真实几何尺寸进行计算，而不是盲猜。

## 5. 数据结构设计

### 5.1 项目配置 (`config.json`)

```json
{
  "unit": "mm",
  "timeout_seconds": 60,
  "render": {
    "default_views": ["top", "front", "right", "iso"],
    "image_format": "png",
    "resolution": [800, 600]
  }
}
```

### 5.2 文件存储

```text
project_root/
├── .cad/               # 工具元数据
│   ├── config.json     # 项目配置（单位、超时、渲染参数）
│   ├── commits/        # 提交快照（线性历史）
│   ├── runlog/         # 事件日志（JSONL，可重放）
│   └── thumbs/         # 缩略图缓存
├── main.py             # 入口脚本 (Driver Code)
├── features/           # 特征定义
│   ├── base_plate.py
│   ├── mount_holes.py
│   └── enclosure.py
└── output/             # 导出的模型 (STEP, STL)
```

### 5.3 特征树代码规范 (Feature Protocol)

每个 Feature 类必须实现以下接口：

```python
from typing import Protocol
from build123d import Part

class Feature(Protocol):
    """所有特征类必须遵循的接口。"""

    def build(self, context: Part | None = None) -> Part:
        """执行建模操作，返回结果实体。

        Args:
            context: 上一步的实体，首个特征可为 None。
        Returns:
            构建完成的 Part 实体。
        """
        ...
```

入口脚本示例：

```python
# main.py
from build123d import *
from features.base_plate import BasePlate
from features.mount_holes import MountHoles

# 1. Base Feature
part = BasePlate(length=100, width=50).build()

# 2. Feature A
part = MountHoles(part, diameter=5).build()

# 3. Export
part.export_step("output/final.step")
```

## 6. v2+ 规划 (Deferred)

以下功能已从 v1 范围中移出，计划在后续版本实现：

*   **分支与合并**: `branch`、`checkout`、`merge` 命令。
*   **几何差异比较**: `diff <commitA> <commitB>` — 比较体积、BBox、面数等几何指标。
*   **深度验证**: `validate --level=full` — 容差分析、法线一致性、壳体闭合路径检查。
*   **高级几何查询**: `inspect --query="distance(edge1, edge2)"` 等空间关系查询。
*   **API 助手**: `doc <function_name>` — 返回 build123d 函数签名与文档。
*   **上下文压缩器**: `tree --depth=N` — 特征树骨架的精简文本输出。
*   **自定义渲染视角**: 45度角透视图等非标准视角。

## 7. 下一步计划 (Roadmap)

1.  搭建 Python CLI 骨架（基于 `click`）。
2.  集成 `build123d` 环境，实现 `run` 命令。
3.  实现 `validate` 命令（捕获异常和 BRepCheck）。
4.  实现 `render` 命令（使用 `pyvista` 进行离屏渲染）。
5.  实现 `inspect` 命令（基础几何探针）。
6.  实现 `export` 命令。
7.  实现线性版本控制（`init`、`commit`、`status`、`log`）。
