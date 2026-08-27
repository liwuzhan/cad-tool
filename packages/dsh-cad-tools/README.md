# cad-studio —— DSH CAD 工场插件（阶段 A：vendored preset）

让 DSH 会话内的 agent 通过 `cad_*` 工具完成完整 AI CAD 工作流：
`init → 编写 src/main.py → run → validate → inspect → review → commit → log/checkout/export`。
Python 侧仍以 CAD CLI（build123d）为唯一几何真源；本插件只做编排与展示。

## 文件结构

```
cad-studio/
├── preset.yml                     # 显示元数据（name/description/order）
├── agent.cordis.yml               # 标准 Agent 组合 + cad-studio 插件行 + skills 目录
├── cad-studio-plugin.mjs          # Host 半件：P1 CadRuntime + P2 16 个 cad_* 工具
├── cad-studio-client.mjs          # Client 半件：P3 CADPreviewNode（ESM 形态）
├── cad-studio-client.code.js      # Client 半件 cordis_define 的 code.client 函数体（由 .mjs 派生）
├── tool-bootstrap.mjs             # 首个请求小工具面，之后展开完整 catalog
├── skills/
│   ├── cad-modeling/              # 建模工作流 + Checkpoint 模板 + 5 致命陷阱
│   ├── cad-build123d-reference/   # build123d API 速查
│   └── cad-checkpoint/            # Checkpoint 特征级验证系统用法
└── README.md
```

## 工具清单（16 个）

| 组 | 工具 | 对应 CLI | Client 预览 meta |
|----|------|----------|------------------|
| 环境 | `cad_env_status` / `cad_env_bootstrap` | — | 状态卡 |
| 包 | `cad_pkg_list` / `cad_init` | — / `cad init` | 包列表 / 创建卡 |
| 建模 | `cad_run` / `cad_validate` / `cad_inspect` | 同名 | **Checkpoint 图 + metrics** |
| 版本 | `cad_commit` / `cad_log` / `cad_status` / `cad_checkout` / `cad_branch` | 同名 | **commit 缩略图 + metrics** |
| 输出 | `cad_render` / `cad_review` / `cad_export` / `cad_artifact` | 同名 | **多视图 PNG 网格** |

## 安装

### 1. Host 半件（Agent Preset）

```bash
cp -R plugin/cad-studio ~/.dsh/.agent-presets/cad-studio
```

启动新 DSH 会话时在 Agent Preset 选择 **CAD 工场**（id: `cad-studio`）。
运行中的会话保持启动时的 preset，切换后需新建会话。

### 2. Client 半件（特化工具卡 / CADPreviewNode）

Client 半件是动态插件的 `code.client` 函数体，需要在 **Creator mode**（`cordis` preset）
会话中用 `cordis_define` 定义一次：

1. 把 `cad-studio-client.code.js` 的完整内容作为 `code.client`（host 不填）；
2. `pluginId` 建议 `cad-studio-client`；
3. `cordis_run` 激活（首次需在浏览器审批 Client Package）；
4. 激活后，所有 `cad_*` 工具调用卡会替换为 CAD 预览卡：状态点、metrics 行、
   Checkpoint 通过/失败 chips、≤200KB 渲染图内联网格、失败原因高亮。

> 阶段 B 已搭好 npm 包骨架（`packages/`）。发布后安装：
> `dsh plugin --profile <profile> add -w @deepseek-ai/dsh-cad-tools @deepseek-ai/dsh-cad-client`
> （loader 从 profile 根解析裸包名，pnpm 不提升传递依赖，tools/client 必须都作为直接依赖；
> 再把 `@deepseek-ai/dsh-cad-bundle` 加入该 profile 的 `dsh.profile.bundles`）。

### 3. 冒烟验证（headless，不需要浏览器）

```bash
dsh --profile headless --patch cad-studio.verify.patch.yml \
  "直接用 cad_env_status 检查环境并汇报"
```

`verify.patch.yml` 是 insert 补丁示例（把插件行插入 headless 组合根层；
`--patch` 只接受 id 覆盖或 `insert:`，不能直接新增非 insert 行）。

## P1 CadRuntime 设计

- **环境解析**：显式 `python` 参数 → `CAD_PYTHON` → 工作区向上 `.cad-venv`/`.venv` → `~/.cache/dsh-cad/venv`（conda 渠道为 `~/.cache/dsh-cad/conda-env`）→ `python3`；CLI 源码根沿工作区向上找 `src/cad_cli/__main__.py`。
- **CLI runner**：`ctx.subprocess.spawn`（collect stdio + spill + `graceMs` + `exec.signal` 取消）；写入类命令经 `ctx.sandbox.confine` + `ctx.sandboxPolicy.resolve({session})` 按会话策略约束；argv 全数组化，不拼 shell。
- **JSONL 规范化**：事件去 `ts`、保留 `event/payload`；Checkpoint 摘取为 `{name,event,passed,total,image,state,checks}`；metrics 与 `*_error.hint` 结构化返回；原始事件落 `<package>/runlog/<tag>_<ts>.jsonl`。
- **presentationMeta**：`cad_run`/`cad_commit`/`cad_render`/`cad_review` 投影
  `{kind, ok, metrics, checkpoints, preview}` 到 `tool/result` 事件的 `meta` 字段；
  `preview[]` 里 ≤200KB 的 PNG 以 dataUrl 内联，供 Client 渲染网格。
- **错误契约**：CLI 非零退出 → `{ok:false, error:{code,message,hint}}`；仅基础设施错误（subprocess 服务缺失、沙箱后端不可用、spawn 失败）throw 进入 isError 通道。
- **路径边界**：模型包、脚本、导出目标均必须位于会话工作区内（越界返回 `E-PATH`）。

## 权限（部署层配置建议）

| 工具组 | 建议策略 |
|--------|----------|
| `cad_env_status` / `cad_pkg_list` / `cad_inspect` / `cad_log` / `cad_status` / `cad_artifact list` | allow（纯读） |
| `cad_run` / `cad_validate` / `cad_render` / `cad_review` | allow（写包内 runlog） |
| `cad_init` / `cad_commit` / `cad_checkout` / `cad_branch` / `cad_export` / `cad_artifact clean` | ask |
| `cad_env_bootstrap` | ask（安装库） |

## 验证记录（本机 macOS arm64 / Python 3.14.2 / DSH 0.1.0-rc.6）

| 层 | 验证 | 结果 |
|----|------|------|
| M0 | build123d 0.11 STEP 回归 Compound fallback + `/var`↔`/private/var` 归一化 | `pytest test/` **66/66** |
| M0 | `cad commit` 冒烟（model.step + 4 视图 + metrics） | 通过 |
| P1/P2 | `test-harness.mjs`：真实 CLI 子进程跑 16 工具全流程 | 通过 |
| P1 | `test-bootstrap.mjs`：真实 pip 安装到 `~/.cache/dsh-cad/venv` + `--help`/import 冒烟 | 通过（6/6 步） |
| P1/P2 | 16 工具 parameters/output schema 过 `assertSupportedJsonSchema` | 通过 |
| Preset | `discoverPresets` → `cad-studio`，`broken: null` | 通过 |
| 真机 Host | `dsh --profile headless --patch`：真实 agent 不敲 shell 完成 `env_status/pkg_list/run` 与 `init→run→validate→commit` | 通过（commit `ac5cbe8fbf55` 工件齐全） |
| Client | `test-client.mjs`：按 dsh-cordis-client-runner 的 `new Function` 包装解析 `code.client`，mock slots 挂载并渲染 running/done 两种 block | 通过 |
| Jobs | `run_in_background` 按 JobRegistry 契约 mock 验证 `{kind,label,owner,run}` + done → completed | 通过 |
| Lock | `test-lock.mjs`：live lock → `E-LOCK`；stale lock 回收；正常释放无残留 | 通过 |
| npm 包 | `npm pack` 四个包 → 临时项目 `npm install *.tgz` → 裸包名解析 tools/client/bundle/preset 清单 | 通过 |

## 已知限制 / 下一步

- Client 半件在阶段 A 需 Creator mode 手工 `cordis_define`（已通过真机 define + `awaiting-approval` 校验）；
  阶段 B npm 包骨架见 `packages/`（`@deepseek-ai/dsh-cad-tools/client/bundle/preset`）。
- 大图（>200KB）暂无 `host.call('cad.image')` 通道（静态 Host 插件拿不到 dynamic `harness`）；
  当前降级为路径文本。阶段 B 用动态插件形态补 RPC。
- `cad_env_bootstrap` 支持 `channel: pip`（已实测通过）与 `channel: conda`（conda-forge 兜底；
  缺失 conda 时返回 E-CHANNEL，成功路径待有 conda 的机器实测）。
- `run_in_background` 的 `ctx.jobs.start` 接线已按真实 JobRegistry 契约用 mock harness 验证
  （completed/killed 状态机）；待真实会话观察 UI 进度。
- 多会话并发写同一模型包：写操作（run/commit/render/review/checkout/branch 写 op/artifact clean）
  使用 `<package>/.cad-lock` 目录锁，等待 30s 后返回 `E-LOCK`，超 5 分钟的孤儿锁自动回收
  （`test-lock.mjs` 已验证阻塞、回收、释放三路径）。
