# DSH 插件开发进展（本会话）

更新：2026-08-17（round 7）
目标：把 CAD CLI 体系做成 DSH 插件群（P1–P6），本会话持续开发。

## Round 7 新增

- **修复面类型分类器 bug（Round 6 已知观察关闭）**：build123d 0.11 将
  `Face.geom_type()` 方法改为 `GeomType` 枚举属性，CLI 分类器按旧 API 调用导致
  `cad_inspect geometry_summary/face_types` 与 Checkpoint `face_types` 全部
  `unknown`。已直接适配 0.11（不做旧版兼容）：`feedback/inspector.py` 读取
  `face.geom_type.name` 并按枚举名映射，`feedback/checkpoint.py` 复用同一分类函数。
  实测 plug_smoke：11 面分类为 planar 6 + cylindrical 5；pytest **66/66**。
- **修复渲染透视 bug**：pyvista 默认透视相机，top/front/right 等工程视图带
  透视变形。`CameraView` 增加 `orthographic` 标志：**iso 保持透视，其余视图
  正交**；`feedback/renderer_v2.py`、`feedback/checkpoint.py`、
  `feedback/renderer.py`、`v1/feedback/renderer.py` 按视图调用
  `enable_parallel_projection()`。spy 实测：top/front/right 各启用 1 次，iso 0 次。
  钢笔画风格（浅灰填充 + 特征边 + silhouette）本已实现，无需改动。

## Round 6 新增

- **P3 浏览器实测（待办 1 关闭）**：真实 web 会话中 `cordis_define`（code.client =
  `cad-studio-client.code.js` 全文）→ `cadst-1/pkg-1` → `cordis_run` → 用户在浏览器
  审批通过 → **run-1 completed successfully**。`tool.call.toolview` 实测确认：
  keyed/open 域，profile 里的 `@deepseek-ai/dsh-cad-client`（registrant x6）已占用
  16 个 cad_* key，动态插件注册同 key 后替换之（shadows-shipped-ui 语义，符合预期）。
- **16 工具真机全量实测**：新包 `plug_smoke.456d`（带孔方块+顶面圆角）走完
  init→run→validate→commit(a52ab574488a)→log/status/inspect/branch/render/review/
  checkout/export；渲染图目视确认正确。**15/16 通过**。
- **发现并修复 canonical 输出 schema 违规（一类 bug，9 处）**：
  DSH 严格校验工具 canonical 输出，`null` 不得落在 string/object 型键上。
  - `normalizeCli`：render=False 的 Checkpoint `image:null`（**实测触发**）；
    CLI 透传的 error 含 `hint:null` + `file/line/type` 附加键（**实测触发**）；
  - 潜在路径：cad_run/cad_commit/cad_review/cad_checkout 失败时 `metrics:null`、
    cad_commit `commit:null`、cad_init `package:null`、cad_artifact list 时
    `policy:null`（**实测触发**）。
  - 修法：缺失即省略键（conditional spread）；新增 `sanitizeError()` 统一清洗
    CLI 错误对象。
- **harness 增强防回归**：`test-harness.mjs` 内置最小 JSON-Schema 校验器，
  每次工具调用后校验 canonical 输出；新增 render=False Checkpoint 与坏脚本失败
  路径两个回归用例；16 工具全流程 + schema 校验 **ALL-OK**。
- **分发同步**：修复已 `cp` 到 `packages/dsh-cad-tools/lib/index.js` 并重打
  `/tmp/cad-packs` tarball；web profile 的 pnpm 解包目录已**热替换** index.js
  （lockfile 对 file: 依赖不存 integrity，无需更新）。**下次 DSH 重启生效**。
- 已知观察：`cad_inspect geometry_summary` 的面类型分类全部报 `unknown`
  （11/11）——CLI 侧面分类器在 fillet 后的零件上失效（非插件层问题）。
  **→ Round 7 已修复**。

## Round 5 新增

- **真实 pnpm 安装路径验证（Phase B 分发关键结论）**：
  - `dsh plugin add` 转发 pnpm 成功（pnpm 不在 PATH 时 dsh 会明确报错；
    未发布包名的 registry 404 属预期，与我们的包质量无关）；
  - 临时 profile + 本地 tarball + `pnpm.overrides` 模拟 registry 完成安装；
  - **关键发现**：DSH loader 从 profile 根解析组合行裸包名，pnpm hoisted linker
    不把传递依赖提升到根 —— 若只直接安装 bundle，`@deepseek-ai/dsh-cad-tools`
    无法从 profile 根解析。正确姿势：tools/client 作为 profile **直接依赖**
    `dsh plugin add -w`，bundle 只负责 insert 行；
  - 4 包全部为直接依赖后，`dsh --profile cad-test` 经 bundle patch 从裸包名
    加载 Host 插件，真实 agent 调用 `cad_env_status` 成功（`exit=0`）；
  - 文档已更新（`packages/README.md`、`plugin/cad-studio/README.md`）。


## Round 4 新增

- **模型包写锁（开放问题 8）**：`<package>/.cad-lock` 目录锁（mkdir 原子），
  写操作 run/commit/render/review/checkout/branch(非 list)/artifact clean 统一加锁；
  默认等待 30s → `E-LOCK` + hint；孤儿锁超 5 分钟自动回收（可用 plugin config
  `lockTimeoutMs`/`lockStaleMs` 调整）。`test-lock.mjs` 实测三条路径：
  活锁阻塞、陈旧锁回收、正常释放无残留；16 工具全流程 harness 回归通过。
- **npm 打包验证**：`npm pack` 产出 4 个 tarball（tools/client/bundle/preset），
  在干净临时项目 `npm install *.tgz` 后以**裸包名**验证：
  - `@deepseek-ai/dsh-cad-tools` 默认导出 apply 注册 16 工具；
  - `@deepseek-ai/dsh-cad-client/client` 子路径解析到 lib/client.js，
    package.json `dsh.client={platform:"web",inject:[...]}` 合法；
  - `@deepseek-ai/dsh-cad-bundle` 的 `dsh.bundle.patch` 含 tools+client 两行；
  - `@deepseek-ai/dsh-cad-preset` 的 `npm run install` 入口存在。


## Round 3 新增

- **真机 cordis 工具链验证 Client 半件**：给 headless 组合 insert
  `@deepseek-ai/dsh-cordis-host-runner` + `@deepseek-ai/dsh-tool-cordis` 后，
  真实 agent 完成：
  - `cordis_define`（kind new，code.client = `cad-studio-client.code.js` 全文）→
    `cadst-1/pkg-1`，无校验错误；
  - 同会话 `cordis_run` → **`awaiting user approval (run-1)`**（浏览器审批，
    与文档预期一致；headless 无 UI 不能完成最后一步）。
- **Phase B npm 包骨架**（`packages/`，同源代码）：
  - `@deepseek-ai/dsh-cad-tools`：Host 插件包（`exports["."]`）；
  - `@deepseek-ai/dsh-cad-client`：双面包（`dsh.client={platform:"web",inject:[...]}` +
    `exports["./client"]`；`build.mjs` 从单源生成 `window.__ModuleLoader__.load` bundle）；
  - `@deepseek-ai/dsh-cad-bundle`：profile bundle（`dsh.bundle.patch → cordis.patch.yml`
    insert tools+client 两行）；
  - `@deepseek-ai/dsh-cad-preset`：`npm run install` 复制 preset 到
    `~/.dsh/.agent-presets/cad-studio`，composition 行引用 npm 包名。
- **Phase B 包入口真机验证**：`file://…/packages/dsh-cad-tools/lib/index.js`
  作为 loader row 在 headless 真实会话加载，agent 调 `cad_env_status` 成功；
  生成的浏览器 bundle 在 mock `window.__ModuleLoader__` 下挂载 16 toolview 并渲染成功。
- **`cad_env_bootstrap` conda 渠道**：conda-forge 创建 `~/.cache/dsh-cad/conda-env`
  分支 + PATH 自动探测 conda/mamba/micromamba；本机无 conda →
  `E-CHANNEL` + hint 已实测（成功路径待有 conda 的机器）。


## 已完成（已验证）

### M0 — CAD CLI 前置适配 ✅
- 修复 build123d 0.11.x STEP 再导出回归：`src/cad_cli/utils/geometry.py::export_step_safe`
  （先直导，失败时 `Compound(children=[shape])` fallback），覆盖
  `package/artifact.py`、`feedback/exporter.py`、`runtime/executor_v2.py` 子进程模板、`v1/feedback/exporter.py`。
- 修复 macOS `/var`↔`/private/var` 路径问题：`runtime/workflow.py`、`vcs/repository_v2.py`
  的 `relative_to` 前 `resolve()`。
- `pyproject.toml`：删除重复 `cadquery-ocp`（build123d 0.11 自带 `cadquery-ocp-novtk`）。
- 验收：`pytest test/` **66/66**；`cad commit` 产出 model.step + 4 视图 thumb + metrics.json + validate.json。

### M1/M2 — P1 CadRuntime + P2 工具 ✅
- 单文件 Host 插件 `plugin/cad-studio/cad-studio-plugin.mjs`：
  - P1：环境解析、`ctx.subprocess`+`ctx.sandbox`+`ctx.sandboxPolicy` runner、
    JSONL 规范化、runlog 落盘、`.456d` 包索引、路径边界（`E-PATH`）。
  - P2：16 个 `cad_*` 工具（env_status/env_bootstrap/pkg_list/init/run/validate/inspect/
    commit/log/status/render/review/checkout/branch/export/artifact）。
  - `presentationMeta` 为 run/commit/render/review 投影 `{kind,ok,metrics,checkpoints,preview}`；
    ≤200KB 渲染图以 dataUrl 内联进 canonical `preview`。
- 验收：
  - 16/16 schema 过 `@deepseek-ai/dsh-tools` `assertSupportedJsonSchema`；
  - `test-harness.mjs`（真实 CLI 子进程）跑通 16 工具；
  - `test-bootstrap.mjs`：真实 pip 安装 `~/.cache/dsh-cad/venv` + `--help`/import 冒烟 6/6 步；
  - `run_in_background` 按 JobRegistry 契约 mock 验证（`{kind,label,owner,run}` → done `completed`）；
  - 真机 headless DSH 会话：agent 不用 bash 完成
    `env_status/pkg_list` 与 `init→run→validate→commit`（commit `ac5cbe8fbf55`）。

### P3 — Client 半件（原型）✅
- `plugin/cad-studio/cad-studio-client.mjs`（ESM 形态）+ `cad-studio-client.code.js`
  （cordis_define `code.client` 函数体，由 .mjs 派生）。
- 挂载 `tool.call.toolview`（keyed by tool name，contract 来自
  `@deepseek-ai/dsh-client-ui-tool` 真实声明：owner `{callId,toolName,block,openFile,cwd,inspect}`），
  为全部 16 个 cad_* 工具注册 `CadRow`：
  状态点 / metrics 行 / Checkpoint chips / 内联渲染图网格 / 错误高亮 / open script。
- `block.meta` 数据来源：`tool/result` 事件携带 `presentationMeta`，
  Client `ToolResultNode.meta` 原样投影（contract 来自 `dsh-client-runtime` types）。
- 验收：`test-client.mjs` 用 dsh-cordis-client-runner 的 `new Function` 包装方式解析
  `code.client`，mock `slots` 挂载 16 个 key，渲染 running/done 两种 block 无运行时错误。

### P4 — 技能 ✅
- `skills/cad-modeling`：四步流程 + Checkpoint 模板 + 5 致命陷阱 + 错误码。
- `skills/cad-build123d-reference`：完整 build123d API 速查。
- `skills/cad-checkpoint`：Checkpoint 快速上手。
- preset `agent.cordis.yml` 的 `skill-filesystem.customSkillDirs` 指向 `skills/`。

### P5 — Agent Preset ✅
- `~/.dsh/.agent-presets/cad-studio/`：preset.yml + agent.cordis.yml（standard 组合 +
  bootstrap + skills + cad-studio 行）+ host/client 源码 + skills + README。
- `discoverPresets` → `{id:"cad-studio", name:"CAD 工场", order:6, broken:null}`。

## 待办（后续轮次）

- [ ] **P3 浏览器实测**：Creator mode `cordis_define` 定义 `cad-studio-client`，
      审批后跑一次真实会话看工具卡网格。
- [ ] 大图 `host.call('cad.image')` RPC（需要动态 Host 半件的 `harness`；阶段 B）。
- [ ] `cad_env_bootstrap` 的 conda 渠道 + `run_in_background` 的 `ctx.jobs` 真机验证。
- [ ] M4：阶段 B npm 包化（`@deepseek-ai/dsh-cad-*`）、跨平台 bootstrap 矩阵、
      安装文档终稿（README 已具备阶段 A 全流程）。
- [ ] 多会话并发写同一模型包的 `.lock` 策略（开放问题 8）。

## 证据文件

- `plugin/cad-studio/test-harness.mjs` — Host 16 工具全流程 harness
- `plugin/cad-studio/test-client.mjs` — Client code.client 解析/挂载/渲染 harness
- `plugin/cad-studio/verify.patch.yml` — headless 真机验证 insert patch
- `/tmp/dsh_cad_agent5.log`、`/tmp/dsh_cad_e2e.log` — 真机会话记录（临时文件，见内容）
