---
name: cad-modeling
description: 使用 CAD 工场工具创建、装配、查看、保存或导出 build123d 参数化模型和 .456d 模型包；可选复用 cad-parts 标准件。
---

# CAD 建模

这是一组能力，不是一条必须执行完的流水线。模型根据任务选择工具，也可以直接读取源码或编写
临时诊断代码。

## 工具目录

| 用途 | 工具 | 提供的能力 |
|---|---|---|
| 环境 | `cad_env_status` / `cad_env_bootstrap` | 查看或安装隔离的 Python CAD 环境 |
| 模型包 | `cad_pkg_list` / `cad_init` | 发现或创建 `.456d` 包 |
| 建模 | `cad_run` | 执行 `src/main.py`，读取 JSONL 和可选 Checkpoint |
| 观察 | `cad_validate` / `cad_inspect` | BRep、尺寸、体积和拓扑信息 |
| 图像 | `cad_render` / `cad_review` | 普通视图，以及按需尺寸、标注或剖切 |
| 历史 | `cad_commit` / `cad_log` / `cad_status` / `cad_checkout` / `cad_branch` | 保存和访问版本 |
| 输出 | `cad_export` / `cad_artifact` | STEP/STL 和已保存工件 |

标准件库存在时，可在当前平台 shell 中运行 `cadparts search/compare/describe`；没有它也不影响
普通 CAD。工具目录是默认省力入口，不禁止模型查看库源码或采取其他合理方法。

## 最少约定

- 可编辑几何通常在 `<name>.456d/src/main.py`，最终 build123d 对象赋给 `result`。
- `design.md` 可保存意图、命名尺寸和坐标语义，但不要求固定结构。
- 装配体通常用带稳定 label 的独立组件组成 `Compound`，避免无意融合。
- 多个模型包并存时，明确传入 `package`，不要猜测目标。
- Checkpoint 是模型按需放置的探针，不要求每个特征都使用。
- validate、inspect 和 Review 只提供证据；最终设计判断属于模型。
- 版本操作会改变包历史或源码，必要时先查看状态并保留用户修改。

## 按需参考

- 初次接触工具或想看实例时，读取 `references/model_walkthrough.md`；它用轮毂和 6204 轴承座
  装配演示一次完整生成过程，可以跳过。
- 涉及装配、采购件、接口或坐标时，读取 `references/assemblies.md`。
- 普通视图已经暴露疑点但不易定位时，读取 `references/review_drawing.md`。

参考资料不是强制步骤。模型可以使用其中一部分，也可以根据任务自行组织建模和检查方法。
