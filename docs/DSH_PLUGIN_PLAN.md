# CAD CLI → DSH 插件化规划

- 版本：v0.1（规划稿）
- 日期：2026-08-16
- 状态：待评审
- 范围：把现有「AI 建模 + 模型版本管理」体系改造为 DeepSeek Harness（DSH）插件群

---

## 1. 背景与已确认的事实

### 1.1 CAD CLI 现状

| 能力 | 现状 |
|------|------|
| 建模执行 | `cad run [script]`，子进程隔离 + Unix signal 超时 / Windows ctypes 超时，跨平台 |
| 几何验证 | `cad validate`，BRep 有效性检查 |
| 属性查询 | `cad inspect --prop=volume/area/bounds/faces/edges` |
| 版本管理 | `cad commit/log/status/checkout` + branch 管理 + `.456d` 自包含模型包 |
| 渲染 | pyvista 离屏渲染 PNG（iso/top/front/right），无显示器依赖 |
| 特征级验证 | Checkpoint：体积/实体数/bbox 断言 + 自动渲染 |
| 视觉审查 | `cad review` 生成 review.md 模板 |
| 导出 | STEP / STL |
| 输出协议 | 全命令 JSONL，机器可解析 |

### 1.2 Mac 平台验证结论（2026-08-16 实测）

- ✅ 结论：**框架在 macOS 上可运行，跨平台能力可接受**。
- 验证环境：Apple M4 (arm64)，Python 3.14.2 venv（`.venv/`），pip 安装成功。
- 通过项：`cad --help`、`import build123d/OCP`、布尔运算、STL 导出、pyvista 离屏渲染、`cad run`、`cad validate`、pytest `test/` 57/66 通过。
- **遗留问题 1（阻塞 commit，规划为 M0 前置修复）**：
  - `cad commit` 保存 STEP 失败：`Failed to save STEP artifact: Failed to write STEP file`。
  - 根因：build123d 0.11.x 上游回归（[Issue #1356](https://github.com/gumyr/build123d/issues/1356)）：`import_step()` 返回的 Solid 无法再 `export_step()`；0.10.0 正常。
  - 三个已验证 workaround：① `Compound(children=[shape])` 包装再导出；② 布尔运算重新拓扑；③ 直接 OCP `STEPControl_Writer`。
  - 建议修法：`ArtifactManager.save_step()` 增加 Compound fallback（改动最小，Windows 无副作用）；或 pyproject pin `build123d<0.11`。
- 遗留问题 2：裸跑 `pytest` 会收集 `reference/` 第三方源码导致 collection error，应始终 `pytest test/`。
- 遗留问题 3：当前 pyproject 会同时安装 `cadquery-ocp` 与 `cadquery-ocp-novtk`，暂无症状，插件化时应整理为单一 OCP 变体。

### 1.3 DSH 插件机制调研结论

依据：官方 [architecture](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.zh.md)、[extension-cookbook](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/cookbook/extension-cookbook.md)、[adding-a-tool](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/cookbook/adding-a-tool.md)、[adding-a-package](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/cookbook/adding-a-package.md)，以及本机 `~/.dsh/.agent-presets/novel-studio/` 实例与 `cordis-plugin-development` SKILL。本机 DSH 版本 0.1.0-rc.6。

关键结论：

1. **一切皆插件**：DSH 没有特权内核；工具、UI、技能、预设都是 Cordis 插件，通过共享上下文贡献服务并自动随插件卸载撤销。
2. **工具注册**：`ctx.tools.register(defineTool({name, description, parameters, output:{schema, render}, execute}))`。execute 返回唯一 canonical JSON；`output.render` 负责模型可见文本；UI 卡片由 `presentCall`/`presentResult` 单独声明（现有卡片类型：generic / terminal / diff / search / web）。
3. **长任务**：`ctx.jobs.start({kind, label, owner, run})` 注册后台任务，返回 jobId，配合现有 `job_output`/`job_kill` 工具使用。
4. **子进程与沙箱**：`ctx.subprocess` spawn 进程、`ctx.sandbox` 包装 argv（与 bash 工具同一执行世界）；`tools/pre-execute` 做权限策略。
5. **前端 UI**：Client 插件经 `Slots` 注册；Web Client 业务节点 = `ConversationNodeDefinition` + `conversation.chat.node` keyed renderer（CAD 预览的正确挂载点）；Client→Host 私有调用用 `harness.handle(method, handler)` + `host.call(method, args)`，只传无损 JSON。
6. **技能**：skill 目录 + `skill-filesystem.customSkillDirs` + `tool-skill`；技能内容在调用时注入。
7. **组装与分发**：
   - Agent Preset：`preset.yml` + `agent.cordis.yml` + 插件 `.mjs` + `skills/`，放在 `~/.dsh/.agent-presets/`；
   - Profile/bundle：npm 包 + `dsh.bundle` 指向 cordis patch，`dsh plugin add <package>` 安装；
   - 动态插件：`cordis_define`/`cordis_run`（临时、进程局部，适合原型验证）。
8. **实现纪律**：实现前必须用 `cordis_inspect_list` / `cordis_inspect_query` 查询真实 Provider 签名，不得凭猜测写 API。

---

## 2. 目标与非目标

### 2.1 目标

1. 让模型在 DSH 内完成完整 CAD 工作流：`init → 编写 main.py → run → validate → inspect → review → commit → log/checkout/export`，全部通过类型化工具调用完成，不再手敲 CLI。
2. 把「建模结果的版本管理」作为一等能力暴露：模型包、提交历史、分支、工件、指标，均结构化返回。
3. 提供**特化前端**：渲染图预览、指标卡、Checkpoint 状态、版本时间线、模型包面板。
4. 提供**一键式库安装**：跨 macOS / Windows / Linux 的 Python 环境检测、venv 创建、依赖安装与冒烟验证。
5. 保持 CAD CLI 本身独立可测：插件只是 CLI 的适配层，不做双份业务逻辑。

### 2.2 非目标（本期不做）

- 不把 build123d 几何内核重写成 JS/TS。
- 不做 Web 端参数化建模编辑器（只做预览 + 审查，不编辑）。
- 不做多人协作、远端仓库。
- 不在 v1 支持云端渲染服务；全部本地离屏渲染。
- 不改动 DSH 核心循环（插件化遵守 `feature → mechanism` 映射，不碰 agent loop）。

---

## 3. 总体架构

```
┌──────────────────────────────────────────────────────────────────┐
│                        DSH Web Client（浏览器）                     │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ dsh-cad-client（Client 插件）                                │  │
│  │  · conversation.chat.node  → CADPreviewNode（渲染图/指标/CP） │  │
│  │  · sidebar  → 模型包面板（版本时间线/分支/工件）               │  │
│  │  · host.call('cad.preview', {path}) ←→ harness.handle       │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                          ↑ host.call（JSON RPC，base64 图片）
┌──────────────────────────────────────────────────────────────────┐
│                        DSH Host（Node.js）                        │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ dsh-cad-tools（Host 插件，注册 cad_* 工具）                  │  │
│  │  · cad_env_bootstrap / cad_init / cad_run / cad_validate    │  │
│  │  · cad_inspect / cad_render / cad_commit / cad_log ...      │  │
│  │  · presentCall/presentResult → terminal/diff/generic 卡片    │  │
│  └───────────────┬────────────────────────────────────────────┘  │
│  ┌───────────────▼────────────────────────────────────────────┐  │
│  │ dsh-cad-core（Host 服务：CadRuntime / CadRegistry / Preview）│  │
│  │  · 环境解析（venv/python 版本/依赖检查）                      │  │
│  │  · CLI runner（ctx.subprocess + ctx.sandbox + 超时/信号）     │  │
│  │  · JSONL 事件流解析 → 规范化事件对象                          │  │
│  │  · 模型包索引（工作区内 .456d 发现/manifest/metrics 读取）    │  │
│  │  · 预览（PNG 读取 → base64 / 静态文件策略）                   │  │
│  └───────────────┬────────────────────────────────────────────┘  │
│                  │ spawn (.venv/bin/python -m cad_cli ...)        │
│  ┌───────────────▼────────────────────────────────────────────┐  │
│  │ CAD CLI（Python 3.11+，现有项目，仅做 M0 适配）              │  │
│  │  · build123d / OCP / pyvista venv                            │  │
│  │  · .456d 模型包：src/vcs/artifacts/runlog                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
        安装期：cad_env_bootstrap → 创建 venv → pip install
        技能层：dsh-cad-skills（建模工作流 + build123d 参考 + 陷阱）
```

原则：
- **Python 侧只做几何与持久化，Node 侧只做编排与展示**；跨语言边界只有两种数据：JSONL 事件流与文件路径/PNG。
- **CLI 是唯一真源**：插件不重新实现任何 CAD 逻辑，保证 `cad` 命令、pytest、插件三条路径行为一致。

---

## 4. 插件清单与拆分

用户视角是一个「CAD 工场」预设；工程视角是 1 个仓库多插件（"不只是一个插件"）：

| # | 插件/包 | 平面 | 职责 | 依赖 |
|---|---------|------|------|------|
| P1 | `dsh-cad-core` | Host（Service） | `CadRuntime`：环境解析、CLI runner、JSONL 规范化、包索引、图片读取 | `ctx.subprocess`、`ctx.sandbox`、`ctx.fs` |
| P2 | `dsh-cad-tools` | Host（Tool） | 注册全部 `cad_*` 工具 + 工具卡片；调用 P1 | P1 |
| P3 | `dsh-cad-client` | Client（UI） | 预览节点、侧栏面板、图片渲染；`harness.handle('cad.*')` 由 P1 提供 | P1（经 host.call） |
| P4 | `dsh-cad-skills` | 资源 | `SKILL.md` × 4：建模工作流 / API 速查 / Checkpoint 用法 / 致命陷阱 | 无 |
| P5 | `dsh-cad-preset` | 组装 | `preset.yml` + `agent.cordis.yml` + `tool-bootstrap` 配置，把 P1–P4 挂成一个 Agent Preset | P1–P4 |
| P6 | `cad-cli`（现有项目） | Python | M0 适配：修 STEP 回归、固定版本矩阵、补充 `--json` 兼容性测试 | 无 |

**实现形态路线**：
- 阶段 A（原型，本次迭代）：用 vendored `.mjs`（参考 novel-studio 的单文件插件形态）放入 `~/.dsh/.agent-presets/cad-studio/`，配 `agent.cordis.yml` + `skills/`。
- 阶段 B（正式化）：拆成 npm 包 `@deepseek-ai/dsh-cad-*`（或私有 registry），用 `dsh plugin add` / repository plugin 分发；Agent Preset 的 cordis 行改为包名。
- 两条路线共享同一份 P1/P2/P3 核心代码，仅打包方式不同。

### 4.1 为什么拆成多插件而不是一个大文件

1. Host 服务（P1）无模型面，Client（P3）只做展示，生命周期与故障域不同；拆开可独立启停、独立审批、独立回滚。
2. 工具插件（P2）需要 `isolate` realm 语义时（状态按会话隔离）与全局服务（P1 可 host-plane 单例）的挂载规则不同。
3. 技能（P4）与代码插件版本节奏不同；技能文本经常迭代，不应触发代码插件重新审批。
4. 用户可能只想要「工具 + 预览」而不装完整预设；拆分后可按需 patch 组装。

---

## 5. 工具调用设计（P2）

### 5.1 命名与总览

所有工具以 `cad_` 前缀注册。工具参数用统一 `ParameterSchemaSpec`；输出用 `ValueSchemaSpec`；长任务（run/commit/render）支持 `run_in_background` 分支。

| 工具 | 对应 CLI | 读/写 | 后台支持 |
|------|----------|-------|----------|
| `cad_env_status` | —（新增） | 读 | 否 |
| `cad_env_bootstrap` | —（新增） | 写（仅 venv） | ✅ |
| `cad_pkg_list` | —（新增，索引） | 读 | 否 |
| `cad_init` | `cad init` | 写 | 否 |
| `cad_run` | `cad run` | 写（runlog） | ✅ |
| `cad_validate` | `cad validate` | 读 | ✅ |
| `cad_inspect` | `cad inspect` | 读 | 否 |
| `cad_render` | `cad render` | 写（工件） | ✅ |
| `cad_review` | `cad review` | 写 | ✅ |
| `cad_commit` | `cad commit` | 写（工件/历史） | ✅ |
| `cad_log` | `cad log` | 读 | 否 |
| `cad_status` | `cad status` | 读 | 否 |
| `cad_checkout` | `cad checkout` | 写（工作区脚本） | 否 |
| `cad_branch` | `cad branch list/create/switch/delete` | 写 | 否 |
| `cad_export` | `cad export` | 写 | ✅ |
| `cad_artifact` | `cad artifacts list/clean` | 读/写 | 否 |

原则：
- 一个工具一个动词，避免 `action` 子命令式的含糊参数；分支与工件用两个工具分别收口（`cad_branch {op: list|create|switch|delete}`、`cad_artifact {op: list|clean}` 属于 CLI 已有子命令映射，保留 action 参数）。
- `cad_run` 的 `script` 参数**默认不填**（用包内 `src/main.py`），显式传路径时校验其在当前工作区内。

### 5.2 关键工具 schema（节选，其余在实现时按同一模式展开）

```
cad_run {
  parameters: {
    script?: string          // 相对/绝对路径，缺省用当前包的 src/main.py
    cwd?: string             // 缺省 = 会话工作区
    run_in_background?: bool
    timeout_seconds?: number // 缺省读 manifest.timeout_seconds，上限 300
  }
  output.schema: {
    events: CadEvent[],      // 规范化后的 JSONL 事件流
    metrics?: {volume, area, bbox, face_count, edge_count, vertex_count},
    checkpoints: CheckpointResult[],
    runlog: string           // 落盘路径
  }
  output.render: 指标摘要 + 失败时的 hint 提示
  presentResult: { card: 'generic' }（成功）/ { card: 'terminal' }（失败带 stderr）
}

cad_render {
  parameters: {
    views?: string[]         // ['iso','top','front','right']
    commit?: string          // 缺省 HEAD
    run_in_background?: bool
  }
  output.schema: {
    images: [{view, path, json}],
    preview: [{view, dataUrl}],   // ≤ 200 KB/张才内联，大图走 host.call 按需取
  }
}

cad_commit {
  parameters: { message: string, script?: string, views?: string[], run_in_background?: bool }
  output.schema: {
    commit: {hash, message, ts, branch},
    artifacts: {step, thumbs, metrics, validate},
    metrics, checkpoints
  }
  presentResult: { card: 'diff' } 展示 main.py 快照 diff；历史时间线由 Client 面板承担
}

cad_env_status {
  output.schema: {
    ready: bool,
    python: {path, version, arch},
    venv: {path, exists},
    packages: [{name, version, required}],
    missing: string[],
    platform: {os, arch},
    hint: string                // 下一步建议（安装命令/切换解释器）
  }
}

cad_env_bootstrap {
  parameters: {
    python?: string,            // 解释器路径；缺省自动探测
    channel?: 'pip'|'conda',    // 缺省 pip
    upgrade?: bool
  }
  output.schema: { ok, venv, steps: [{phase,status,detail}], smoke: {import_ok, render_ok, commit_ok} }
  // 后台任务：创建 venv + pip install 可能 3–10 分钟
}
```

### 5.3 错误契约

- 工具 execute 不把 CLI 非零退出当异常抛出；返回 canonical value，内部字段 `ok: false + error {code,message,hint}`（与 CLI `E-SYNTAX/E-RUNTIME/E-BREP/E-RENDER/E-IO` 对齐），`output.render` 把 hint 翻译成人话。
- 只有基础设施错误（venv 缺失、子进程 spawn 失败、结果文件丢失）才 throw → 进入 `isError` 通道。
- `exec.signal` 必须传给 `ctx.subprocess` 的 spawn 调用；取消时向子进程发 SIGTERM（Unix）/ taskkill（Windows）。
- 后台任务用 `ctx.jobs.start`：producer 提供 `cancel`/`done`/`readOutput`，返回 `{kind:'background', jobId}`；`job_output` 复用 DSH 现有工具。

### 5.4 JSONL 规范化（P1 职责）

CLI 的 JSONL 原样转发会浪费 token。P1 做两件事：
1. 事件流压缩为结构化对象（`run_start/checkpoint_*/run_success/run_error` 等，去掉时间戳冗余字段，保留 `image` 路径、`payload.metrics`、`payload.error.hint`）。
2. 只把「模型需要」的字段进 `output.render`；完整事件落到 runlog 文件，模型需要时用 `cad_log`/读取文件获取。

---

## 6. 库安装设计（P2 工具 + P1 安装器）

### 6.1 安装矩阵（2026-08 实测 + PyPI 查询）

| 平台 | 推荐 | Python | OCP wheel | 说明 |
|------|------|--------|-----------|------|
| macOS arm64 | venv + pip | 3.11–3.14 | ✅ cp311–cp314 arm64 | 本次实测 3.14 可用 |
| Windows x64 | venv + pip | 3.11–3.13（3.14 视 wheel 发布） | ✅ cp310–cp314 win | CLI 原生于 Windows 开发 |
| Linux x64 | venv + pip | 3.11–3.13 | ✅ manylinux wheel | |
| 任意平台兜底 | conda-forge | 3.11/3.12 | conda 自动解析 | pip 失败时切换 |

版本 pin（M0 决定，二选一）：
- **方案 A（推荐）**：保持 `build123d>=0.5.0` 可浮动，但项目代码修 STEP 回归（Compound fallback）。收益：吃上游修复，且 0.11 的 API 与旧代码已验证兼容。
- **方案 B**：`pyproject.toml` 改为 `build123d>=0.5.0,<0.11`。收益：不依赖 workaround；代价：永远停在 0.10.x。
- 无论 A/B，pyproject 增加 `numpy<3`（若 build123d 0.11 要求）、固定 `vtk` 由 pyvista 约束（`<9.7` 已被 pyvista 自身约束）。

### 6.2 bootstrap 状态机

```
cad_env_status
   │ ready=true ──────────────→ 结束
   ▼ ready=false
cad_env_bootstrap
   1. detect: python3 --version（要求 3.11–3.14；优先已有解释器）
   2. create: <workspace>/.cad-venv 或 ~/.cache/dsh-cad/venv（幂等，存在即复用）
   3. install: pip install -e "<plugin 引用的 cad-cli 路径>"（复制 Windows/Unix 两套命令）
   4. verify: cad --help → cad run smoke.py → 离屏渲染 1 张 PNG
   5. report: 每步 {phase,status,detail}；失败给出可重试的最小命令
```
- 安装日志逐行写入 `~/.cache/dsh-cad/bootstrap.log`，`cad_env_status` 可回读尾部。
- 网络失败/无 wheel 时：提示改用 `channel: 'conda'`（检测 miniforge），或提示安装 Python 3.12。
- 插件不自带 OCP 二进制（体积约 100–300 MB）；只提供脚本与清单，wheel 从 PyPI 拉取。

### 6.3 安全性

- venv 建在**插件私有目录**（`~/.cache/dsh-cad/`），不污染用户全局 site-packages。
- `pip install` 属于写操作：`cad_env_bootstrap` 注册为需审批工具（`tools/pre-execute` 默认 ask），用户授权一次后，`cad_run` 等运行类工具独立计权。
- 安装命令内不得拼接用户输入的 shell 文本；全部走 argv 数组 + `ctx.sandbox` 包装。

---

## 7. 特化前端设计（P3）

### 7.1 三层预览

| 层 | 挂载点 | 内容 | 优先级 |
|----|--------|------|--------|
| L1 工具卡 | `presentCall`/`presentResult` | 命令 terminal 卡 / commit diff 卡 / generic 指标卡 | P0（与工具同步交付） |
| L2 CAD 业务节点 | `conversation.chat.node` keyed renderer | **每次建模操作的预览节点**：等轴 + 三视图 PNG、体积/面数/bbox、Checkpoint 状态图标、失败原因高亮 | P0 |
| L3 模型面板 | 侧栏/设置区 Slots（实现时 `Slots.listSubTree` 选定） | 模型包列表、版本时间线（log）、当前 HEAD 大图、分支、工件大小、一键 checkout | P1 |

### 7.2 CADPreviewNode 内容协议

每次 `cad_run`/`cad_commit`/`cad_review` 完成后，工具结果内携带：

```json
{
  "node": {
    "kind": "cad-preview",
    "package": {"name": "轴承座", "path": ".../bearing_housing.456d"},
    "images": [{"view":"iso","path":"...","dataUrl":"data:image/png;base64,..."}],
    "metrics": {"volume": 123456, "bbox": [...], "face_count": 8},
    "checkpoints": [{"name":"base","passed":2,"total":2,"image":"..."}],
    "status": "ok" | "checkpoint_failed" | "error"
  }
}
```

渲染规则：
- 多视图用 `<img>` 网格（2×2），iso 优先大图；
- 图片 ≤ 200 KB 走 dataUrl 内联；大图经 `host.call('cad.image', {path})` 按需加载；
- Checkpoint 失败时节点边框红色 + 逐条列出失败断言；
- 纯文本模型（无多模态）退化路径：节点仍展示指标与断言文本，图片位置显示文件路径，模型可读 `read_image` 风格说明。

### 7.3 模型面板（L3）

- 发现机制：P1 扫描会话工作区内的 `*.456d/manifest.json`，缓存索引（含 head、branch、artifact 大小、最近 commit）。
- 面板操作：选中包 → 显示版本时间线 → 「预览此版本」（host.call 取该 commit 的 thumb_*.png）→「切到此版本」按钮（触发 DSH 权限流程后调 `cad_checkout`）。
- 刷新：监听 `tools/result` 事件中 `cad_*` 工具的完成结果，自动更新索引。

### 7.4 3D 预览路线图（本期不做，留扩展口）

- 阶段 1（P0）：PNG 多视图（已有渲染器，零新依赖）。
- 阶段 2（P1+）：`cad_export --format=stl` → three.js 在 Client 内渲染旋转模型；或引入 occt-web/ocp-vscode 生态做 STEP 在线查看。
- 接口预留：`cad_render` 输出里增加 `mesh: {format:'stl', path}` 字段，Client 端后续消费，工具 schema 不破坏。

---

## 8. 数据流与安全

### 8.1 调用链

```
模型调用 cad_run({script})
  → P2 校验参数 + 权限（只读/写分类）
  → P1 CadRuntime.resolve()：确认 venv 可用，否则返回 env_not_ready（hint 调 cad_env_bootstrap）
  → P1 spawn：ctx.sandbox(argv=[venv_python, '-m', 'cad_cli', 'run', script], cwd=package)
  → 逐行解析 JSONL → 规范化事件 → 落 runlog
  → 子进程退出：收集 metrics/checkpoint/image 路径
  → P2 返回 canonical value → output.render → presentResult
  → P3 监听 tools/result 中的 node 数据 → 渲染 CADPreviewNode
```

### 8.2 权限策略（tools/pre-execute）

| 工具组 | 默认策略 |
|--------|----------|
| `cad_env_status` / `cad_pkg_list` / `cad_inspect` / `cad_log` / `cad_status` | allow（纯读） |
| `cad_run` / `cad_validate` / `cad_render` / `cad_review` | allow（写 runlog/工件，工作区内） |
| `cad_init` / `cad_commit` / `cad_checkout` / `cad_branch` / `cad_export` / `cad_artifact clean` | ask 一次后允许（改历史/工作区文件） |
| `cad_env_bootstrap` | ask（安装库） |

### 8.3 边界

- 脚本路径必须解析后位于会话工作区或模型包内（`..` 逃逸被拒绝）。
- Python 子进程 cwd 固定为模型包目录；环境变量只注入 `PYTHONUTF8=1`、`CAD_CLI_NO_TELEMETRY=1`，不透传宿主全部 env。
- 超时双保险：CLI 自身 `timeout_seconds`（signal/ctypes）+ 插件侧 `exec.signal` 取消。
- PNG/STEP 文件由 P1 读取时限制大小（PNG ≤ 5 MB，STEP ≤ 50 MB），超限拒绝进模型上下文，只给路径。

---

## 9. 实施阶段与验收

### M0 — CAD CLI 前置适配（0.5–1 天）
- [ ] 修 STEP 导出回归（fallback 或 pin，见 §6.1），`cad commit` 全绿
- [ ] `pytest test/` 66/66 通过（Mac）；Windows 侧 CI 或手工回归一次
- [ ] pyproject 版本约束整理（OCP 单变体、numpy 上限）
- **验收**：`cad commit` 产出 model.step + 4 视图 thumb + metrics.json

### M1 — P1/P2 工具插件原型（1–2 天）
- [ ] `cordis_inspect_list` 查询 `subprocess`/`sandbox`/`fs`/`jobs` 真实签名
- [ ] P1：runner + JSONL 规范化 + 包索引
- [ ] P2：先注册 6 个核心工具（env_status/bootstrap、init、run、validate、inspect、commit）
- [ ] 工具卡 presentCall/presentResult
- **验收**：对话中模型从零 `cad_init → cad_run → cad_commit`，不敲任何 shell；失败路径 hint 正确

### M2 — 工具补全 + 技能（1 天）
- [ ] 补齐 render/review/log/status/checkout/branch/export/artifact/pkg_list
- [ ] P4 技能迁移：CLAUDE.md 工作流 + `docs/build123d_skills.md` → SKILL.md 四件套
- [ ] Agent Preset（P5）：persona + bootstrap 工具目录 + customSkillDirs
- **验收**：`skill` 工具能加载 cad 技能；模型在预设内完成「带孔盒」全流程

### M3 — 特化前端（1–2 天）
- [ ] `Slots.listSubTree` 确定 `conversation.chat.node` 与侧栏目标 Slot 协议
- [ ] P3 Client 插件：L1 卡片 + L2 CADPreviewNode（图片网格/指标/Checkpoint）
- [ ] `harness.handle('cad.image')` + `host.call` 图片通道
- **验收**：用户/模型每次 run 后看到渲染图；checkpoint 失败红框可见；历史版本可点看缩略图

### M4 — 分发与打磨（1 天）
- [ ] 整理成可安装预设：`~/.dsh/.agent-presets/cad-studio/`
- [ ] 跨平台自测矩阵：macOS arm64 / Windows x64 / Linux x64 各跑一遍 bootstrap + smoke
- [ ] 文档：README + 安装说明 + 故障排除；CLAUDE.md 更新为插件上下文
- **验收**：新机器按文档 ≤ 15 分钟完成「装 DSH 预设 → 装库 → 第一个模型包 commit」

---

## 10. 开放问题（实现前用 cordis_inspect 确认）

1. `ctx.subprocess` / `ctx.sandbox` 的精确方法签名与信号传递方式。
2. `conversation.chat.node` 的注册协议、props（是否已有图片/文件路径能力）与 keyed renderer 规则。
3. 侧栏/设置区实际可用 Slot 名（不猜测 `sidebar` 等名字）。
4. 工具卡片枚举是否可直接渲染图片；若不能，是否用 generic content 兜底或仅走 ConversationNode。
5. 宿主是否有本地静态文件服务可复用（避免 base64 大图）；`web` service 的 fetch 限制。
6. 插件正式分发渠道：repository plugin 面板 / npm 私有包 / `dsh plugin add`，以及审批模型（单次授权 vs 双勾永久）。
7. Windows 下 `dsh` 默认启用 pwsh 工具；CAD 插件应同时兼容 bash/pwsh 环境（P1 不依赖 shell，直接 subprocess）。
8. 多会话并发写同一模型包时的锁策略（当前 CLI 无锁，插件层是否加 `.lock` 文件）。

---

## 11. 参考

- DSH 架构：https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.zh.md
- DSH 扩展实操：https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/cookbook/extension-cookbook.md
- DSH 工具参考：https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/cookbook/adding-a-tool.md
- DSH 包清单：https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/cookbook/adding-a-package.md
- 本机实例：`~/.dsh/.agent-presets/novel-studio/`（单文件 Host 插件 + preset + skills）
- 本机开发 SKILL：`~/.dsh/.agent-presets/novel-studio/skills/cordis-plugin-development/SKILL.md`
- build123d 回归：https://github.com/gumyr/build123d/issues/1356
- 本项目：`INSTALL.md` / `README_CN.md` / `CLAUDE.md` / `docs/build123d_skills.md`
