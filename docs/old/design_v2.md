# AI-Native CAD CLI 工具设计文档 (v2.0 草案)

## 1. 背景与目标

v1.0 以“写码 → 执行 → 验证 → 渲染 → 导出”的最短闭环为目标，采用项目目录 + `.cad/` 元数据目录的形态承载线性历史与工件缓存。

v2.0 引入“模型包（Model Package）”作为一级对象：一个模型应当以自描述、自包含的形式存在于一个目录或单文件容器中，统一管理特征树源、版本历史、构建工件（STEP/缩略图/指标/验证结果）与索引目录（manifest）。

**v2.0 目标**：
1. 统一文件存储约定，消除“脚本/元数据/工件”分散在项目根与 `.cad/` 的割裂。
2. 将“几何体长期缓存”从 Pickle 转向行业标准交换工件（STEP/BREP），降低复杂模型序列化失败风险。
3. 将“执行/验证/渲染/导出”抽象为可重放的本地构建流水线（类似 CI/CD 产物管理）。
4. 支持“只保留分支最新工件”的空间策略，同时保留可选的发布（release/tag）产物。
 
当前阶段仍处于开发期，主要面向自测与快速迭代，因此 v2.0 不要求向前/向后兼容：格式、字段与目录结构允许按需求直接演进。

## 2. 核心概念

### 2.1 模型包 (Model Package)

模型包是一个逻辑单元，可采用两种等价的物理形态：
1. 目录形态：`<name>.456d/`（扩展名仅作为约定，便于识别）
2. 单文件形态：`<name>.456d`（zip 容器，内部结构与目录形态一致）

工具对两者提供一致的读写接口：目录形态便于开发与调试，单文件形态便于分发与归档。

### 2.2 源与工件

*   **源（Source）**：用户手写与维护的内容，默认仅包含 Python 脚本（特征树 Driver Code）及少量配置。
*   **工件（Artifacts）**：工具自动生成的派生输出，包括 STEP/BREP、缩略图、几何指标、验证结果、运行日志等。

约定：除 `src/` 中的脚本外，其余内容均可被删除并通过重新构建恢复（在满足依赖与确定性前提下）。

### 2.3 内部版本历史与外部 Git 的关系

*   **外部 Git**：用于协作、审查、分支合并等通用开发流程，可追踪整个模型包（目录或单文件）的变更。
*   **内部 CAD VCS**：面向 CAD 语义的历史记录（commit/message/metrics/工件引用），用于 CLI 自身的 `log/status/checkout` 等操作。

两者可独立使用：没有外部 Git 时，模型包仍然可携带完整历史与工件；有外部 Git 时，模型包作为可版本化资产融入既有工作流。

## 3. 文件存储设计

### 3.1 目录结构（目录形态）

```text
<model>.456d/
├── manifest.json            # 模型入口索引（自描述）
├── src/                     # 源：用户维护
│   ├── main.py
│   └── features/            # 可选：按模块拆分
│       ├── base_plate.py
│       └── mount_holes.py
├── vcs/                     # 内部历史：工具维护
│   └── commits.jsonl         # 线性历史（可扩展为 DAG）
├── artifacts/               # 工件：工具维护
│   ├── <commit_hash>/        # 每次构建对应一个目录
│   │   ├── model.step
│   │   ├── thumb_iso.png
│   │   ├── render_iso.json
│   │   ├── metrics.json
│   │   └── validate.json
│   └── ...
└── runlog/                  # 运行事件：工具维护
    └── <run_id>.jsonl
```

### 3.2 manifest.json（入口索引）

manifest 用于：
1. 定位源入口（默认脚本）
2. 表达 HEAD、分支指针与当前工作状态
3. 维护工件策略（空间/保留规则）
4. 为工具与 AI 提供“模型目录”（无需扫描全目录即可理解结构）

最小建议结构（示例）：

```json
{
  "format": "cad-cli-model-package",
  "version": "2.0",
  "model": {
    "name": "my_gear",
    "created_at": "2026-01-30T00:00:00Z",
    "default_script": "src/main.py"
  },
  "vcs": {
    "head": "a1b2c3d4",
    "branches": {
      "main": "a1b2c3d4"
    }
  },
  "artifacts": {
    "policy": "latest_per_branch",
    "keep_releases": true
  }
}
```

### 3.3 commits.jsonl（内部历史）

commit 记录保持“可重放、可审计”的原则：
*   必须包含：hash、parent、timestamp、message、script_path
*   建议包含：metrics 摘要、validate 摘要、artifact 引用、运行环境摘要（可选）

示例（每行一个 JSON）：

```json
{"hash":"a1b2c3d4","parent":null,"ts":"2026-01-30T01:02:03Z","message":"init","script_path":"src/main.py","metrics":{"volume":1.0,"faces":12},"artifacts":{"step":"artifacts/a1b2c3d4/model.step","thumb":"artifacts/a1b2c3d4/thumb_iso.png"}}
```

## 4. 构建流水线（本地 CI/CD 语义）

v2.0 将建模过程抽象为“构建”：
1. 执行：运行脚本，得到 shape
2. 验证：运行几何有效性检查与 checkpoint 断言，生成结构化结果
3. 渲染：生成缩略图与视角元数据
4. 导出：生成 STEP（或 BREP）作为长期工件
5. 归档：更新 commits.jsonl 与 manifest.json

流水线具备可重放性：只要源脚本未变更，可从任意 commit 重建缺失工件。

## 5. 工件策略与空间控制

v2.0 引入策略化的工件保留规则，核心目的是：
*   避免为每个 commit 持久化完整 STEP 导致空间膨胀
*   同时保留“快速预览”和“发布版交付”的能力

建议支持的策略：
1. `latest_per_branch`：每个分支仅保留最新 commit 的 STEP/缩略图/指标（适合作为“release 构建产物”）
2. `all_commits`：每个 commit 均保留工件（适用于小模型或需要完整回溯）
3. `releases_only`：仅对标记为 release/tag 的 commit 生成与保留 STEP

策略落地的行为约束：
*   `commit` 默认只记录历史与摘要，不强制生成 STEP（可配置为生成）
*   `build/release` 负责生成 STEP 并按策略清理旧工件

## 6. 特征树表达（v2+ 方向）

v2.0 默认仍以 Python 脚本作为特征树源，以保证表达能力与开发效率。

可选方向：
*   从运行事件或特征协议中提取结构化 `features.json`，作为“可读、可压缩、可编辑”的中间表示，便于 AI 检索与修改。
*   长期目标：让特征树成为一套可唯一求解的、结构化的数据模型；脚本成为编译目标之一而非唯一源。

