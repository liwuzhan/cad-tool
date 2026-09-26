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

## 声明式轴（非标件优先用它）

标准件库还提供轴生成器：`cadparts.Seat` / `Free` / `ShaftSpec` / `shaft_dimensions` /
`stepped_shaft`。用法是**声明装配关系，不写轴颈尺寸**：

```python
spec = ShaftSpec(stations=(
    Seat("bearing.deep_groove", {"code": "6204"}, "shaft_bore", role="support_a"),
    Free(26.0, 22.0, role="spacer"),          # 无库件依据的段才显式给尺寸
    Seat("bearing.deep_groove", {"code": "6204"}, "shaft_bore", role="support_b"),
))
derived = shaft_dimensions(spec)   # 直径/长度/轴向链/轴肩全部推导出来
result = stepped_shaft(spec)       # 半剖轮廓回转成单一实体
```

`Seat` 的直径与长度来自所引用库件接口（轴承 `shaft_bore` → 轴颈），所以换一个轴承型号，
整根轴连同轴向链和轴肩位置一起跟随。`Free` 只用于确实没有库件依据的段。

轴颈**不建模配合公差**：`diameter_delta` 是调用者显式给的余量，发射的名义直径恒为名义值。
键槽、挡圈槽、倒角、螺纹与材料同样不在范围内。轴是最容易形式化的一类非标件，优先用生成器
而不是手画回转轮廓。

## 装配接口判定：先于几何

装配包的依赖与配对关系声明在 `manifest.json`，自建件的接口声明在同包 `ports.py`；
`cad mates` 读这两处来判定接口是否配套，**不执行 `src/main.py`、不建任何实体**：

```jsonc
// manifest.json
"deps":  [{ "name": "bearing_a", "std": { "family": "bearing.deep_groove",
                                          "params": { "code": "6204" } } }],
"mates": [{ "a": "shaft.seat_support_a", "b": "bearing_a.shaft_bore",
            "why": "轴颈由该轴承轴孔尺寸决定" }]
```

```python
# ports.py —— 只做声明，不要建模；PORTS 形状为 {实例名: [接口, ...]}
PORTS = {"shaft": resolve_interfaces("shaft.stepped", {}, shaft_dimensions(SPEC))}
```

判定结果为**四档**，`UNKNOWN` 是一等结果而不是静默通过：

| 判决 | 含义 |
|---|---|
| `PASS` | 公称相符 |
| `WARN` | 装得上但公称尺寸不符（可能是间隙配合，也可能选错件——仅凭声明无法判定）|
| `FAIL` | 装不进去 / 声明本身有错（引用不存在的实例或接口）|
| `UNKNOWN` | 没有适用于该类型组合的规则，此项**未被验证** |

输出还含**覆盖率**（哪些已声明接口没有任何 mate 引用，逐个列出）与**验证边界**
（明说未查公差、强度、工艺、可达性）。**不要把 `PASS` 读成「全都验过了」。**

这个检查的价值在于它是**跨声明的一致性检查**：`manifest` 说装 6205、`ports.py` 却按
6204 给轴定尺寸时，它会报 `WARN` —— 两处本应一致的声明不再一致。所以改了型号记得
两处都改，或者干脆让 `ports.py` 从同一处推导。

一个要知道的边界：**它只看成品零件之间的关系，看不到特征顺序**。`(A∪B)−C` 与
`(A−C)∪B` 结果不同、先倒角后抽壳与先抽壳后倒角结果不同，这类顺序问题不会在这里
暴露——它检查的是关系，而关系与顺序无关（先车轮廓还是先铣键槽，轴颈都还是 ⌀20）。
反过来，M5 螺栓配 M6 螺母这类规格错配也不会在图上看得出来，它只会在这里暴露。
两者互补，四类错误通常在这几处冒头：

| 错误类别 | 通常在哪一层暴露 |
|---|---|
| 特征顺序 / 布尔顺序导致的结果差异 | 几何指标、渲染看图 |
| 尺寸、体积、实体数与预期偏差 | Checkpoint（按特征放置）|
| 成品零件之间的接口不配套 | `cad mates` |
| 该连的没连、出现了未登记的零件 | `cad mates` 的覆盖率一栏 |

这只是它们通常冒头的地方，不是必须走的路：`cad mates` 的 `PASS` 只覆盖它自己声明的
那一类，其余各层用不用、怎么用，由任务决定。

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
