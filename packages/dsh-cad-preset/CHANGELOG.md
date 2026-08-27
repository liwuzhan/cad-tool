# Changelog

## 0.1.0-alpha.2 (2026-08-27)
- 对齐自带完整 Python CLI 的 `dsh-cad-tools` alpha.2。

## 0.1.0-alpha.1 (2026-08-16)
- M0: build123d 0.11 STEP 再导出 Compound fallback；macOS `/var`↔`/private/var` 路径归一化；pytest 66/66。
- P1/P2: CadRuntime（环境解析/沙箱子进程/JSONL 规范化/runlog）+ 16 个 cad_* 工具。
- P3: presentationMeta + ≤200KB 图片内联 preview；16 工具 CADPreviewNode Client 半件。
- P4: cad-modeling / cad-build123d-reference / cad-checkpoint 三个 SKILL。
- P5: cad-studio Agent Preset（vendored 阶段 A）。
- Phase B: @deepseek-ai/dsh-cad-tools/client/bundle/preset npm 包骨架；真实 pnpm profile 安装路径验证。
- 模型包写锁（.cad-lock，E-LOCK + 陈旧锁回收）；bootstrap pip/conda 渠道与后台任务接线。
