# @deepseek-ai/dsh-cad-* —— Phase B npm 包（脚手架）

阶段 A 的 vendored preset 在 `../plugin/cad-studio/` 已可运行；
本目录是阶段 B 的 npm 分发骨架，代码与阶段 A 同源。

| 包 | 职责 | 关键清单 |
|----|------|----------|
| `dsh-cad-tools` | Host 插件：P1 CadRuntime + P2 16 工具 | `exports["."] → lib/index.js`，composition 行直接 `name: '@deepseek-ai/dsh-cad-tools'` |
| `dsh-cad-client` | 双面插件：Host 无操作 + 浏览器 CADPreviewNode | `dsh.client = {platform:'web', inject:[runtime, ui-tool, ui-conversation]}`，`exports["./client"] → lib/client.js`（`window.__ModuleLoader__.load` bundle） |
| `dsh-cad-bundle` | profile bundle | `dsh.bundle.patch → cordis.patch.yml`，insert 上面两行；加入 profile 的 `dsh.profile.bundles` 或 `dsh plugin add` |
| `dsh-cad-preset` | Agent Preset 资源包 | `npm run install` 复制到 `~/.dsh/.agent-presets/cad-studio`，composition 行引用 npm 包名 |

## 安装（未发布前本地验证）

```bash
# 1) Host 工具包：打包
npm pack ./dsh-cad-tools

# 2) Client 双面包：构建浏览器 bundle（生成物已提交）
node dsh-cad-client/build.mjs

# 3) preset 资源
cd dsh-cad-preset && npm run install
```

## 已实测的 pnpm 安装路径（round 5）

DSH loader 从 **profile 根**解析组合行里的裸包名，而 pnpm 的 hoisted linker
不会把传递依赖提升到根 —— 因此 **必须把 tools/client 作为 profile 的直接依赖安装**，
bundle 只负责 `cordis.patch.yml` 的 insert 行：

```bash
dsh plugin --profile <profile> add -w \
  @deepseek-ai/dsh-cad-tools \
  @deepseek-ai/dsh-cad-client
# 可选：把 @deepseek-ai/dsh-cad-bundle 加入该 profile 的 dsh.profile.bundles
```

本机验证（发布前用 tarball + `pnpm.overrides` 模拟 registry）：
- `dsh plugin add` 转发 pnpm 成功（未发布包名的 registry 404 属预期）；
- profile 根 `node_modules/@deepseek-ai/` 下出现 4 个包后，
  `dsh --profile cad-test` 通过 bundle patch 加载 `@deepseek-ai/dsh-cad-tools`，
  真实 agent 调用 `cad_env_status` 成功。

## 单源原则

- `dsh-cad-tools/lib/index.js` 由 `../plugin/cad-studio/cad-studio-plugin.mjs` 复制；
- `dsh-cad-client/lib/client.js` 由 `dsh-cad-client/build.mjs` 从
  `../plugin/cad-studio/cad-studio-client.mjs` 生成（不要手改生成物）；
- 改动先落在 `plugin/cad-studio/`，再跑 `node packages/dsh-cad-client/build.mjs`
  并 `cp` 工具包。

## 本机已验证

- `file://…/packages/dsh-cad-tools/lib/index.js` 作为 loader row 在
  `dsh --profile headless --patch` 真实会话加载，agent 调用 `cad_env_status` 成功；
- 生成的 `lib/client.js` 在 mock `window.__ModuleLoader__` 下挂载 16 个 toolview
  并渲染成功；
- 4 个 tarball 装入临时 profile（`dsh plugin add` + pnpm overrides）后，
  `dsh --profile cad-test` 经 bundle patch 从裸包名加载 Host 插件并真实调用成功。
