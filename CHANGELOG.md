# Changelog

## Unreleased

- 一键安装：新增 `install.sh`（macOS/Linux）与 `install.ps1`（Windows）——探测
  Python 3.11–3.14 → 隔离 venv（默认仓库内 `.venv`，`INSTALL_VENV` 可覆盖并与
  DSH 插件共享）→ `pip install -e .` → 冒烟验证；README（中英）新增「AI 代装」
  提示词，用户把链接发给语言模型即可自动完成安装。
- 零件库独立仓占位：工作区新增 `cad-parts/`（独立 git，主仓 .gitignore 排除），
  含 README + DESIGN（`docs/parts_library_design.md` 同步副本）+ 包骨架；
  装配体设计定稿 `docs/assembly_design.md`（deps 支持 `std:`/`pkg:` 双条目）。
- 修复渲染投影 bug：pyvista 默认透视相机导致 top/front/right 等工程视图带透视
  变形。`CameraView` 增加 `orthographic` 标志（iso 保持透视，其余视图正交），
  `feedback/renderer_v2.py`、`feedback/checkpoint.py`、`feedback/renderer.py`、
  `v1/feedback/renderer.py` 按视图调用 `enable_parallel_projection()`；
  钢笔画风格本就存在（浅灰填充 + 特征边 + silhouette）。
- 修复面类型分类器 bug：build123d 0.11 将 `Face.geom_type()` 方法改为 `GeomType`
  枚举属性，`feedback/inspector.py` 与 `feedback/checkpoint.py` 按旧 API 调用导致
  `cad inspect face_types/geometry_summary` 与 Checkpoint `face_types` 全部报
  `unknown`；已适配 0.11 属性写法（`planar/cylindrical/...` 恢复），pytest 66/66。
- 修复 canonical 输出 schema 违规（9 处）：render=False 的 Checkpoint `image:null`、
  CLI error 透传携带 `hint:null`/`file/line/type` 附加键、失败路径
  `metrics/commit/package/policy:null`；统一改为缺省省略 + `sanitizeError()` 清洗。
- test-harness 增加 canonical 输出 JSON-Schema 校验（每次调用）、render=False 与
  失败脚本回归用例。
- 真机 web 会话 16 工具全量实测 15/16 通过（cad_artifact list 受上述 bug 影响，
  已修复待重启生效）；Client 半件经 cordis_define + 浏览器审批激活成功。

## 0.1.0-alpha.1 (2026-08-16)
- M0: build123d 0.11 STEP 再导出 Compound fallback；macOS `/var`↔`/private/var` 路径归一化；pytest 66/66。
- P1/P2: CadRuntime（环境解析/沙箱子进程/JSONL 规范化/runlog）+ 16 个 cad_* 工具。
- P3: presentationMeta + ≤200KB 图片内联 preview；16 工具 CADPreviewNode Client 半件。
- P4: cad-modeling / cad-build123d-reference / cad-checkpoint 三个 SKILL。
- P5: cad-studio Agent Preset（vendored 阶段 A）。
- Phase B: @deepseek-ai/dsh-cad-tools/client/bundle/preset npm 包骨架；真实 pnpm profile 安装路径验证。
- 模型包写锁（.cad-lock，E-LOCK + 陈旧锁回收）；bootstrap pip/conda 渠道与后台任务接线。
