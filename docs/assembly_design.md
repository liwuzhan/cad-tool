# 装配体支持设计文档

- 版本：v1（设计稿，未实施）
- 日期：2026-08-17
- 状态：待评审
- 范围：多零部件装配建模、跨 `.456d` 包引用与版本 pin、装配验证（干涉检查）、渲染与 BOM、配套 Skill 提示词工程

---

## 1. 背景与目标

### 1.1 现状

单零件闭环已经成立：`init → design.md → main.py → run → validate → review → commit`，
模型可自主完成，回滚/分支/导出可用。插件层（16 个 `cad_*` 工具）稳定。

### 1.2 目标

1. 支持真实产品的层级结构：**机体 → 零部件 → 零件**（如：履带底盘 → 支重轮 → 轴承座/边轮/轴承）。
2. 跨包引用：装配包引用多个零件/子装配包的 **STEP 产物**，按空间关系组装。
3. 版本继承与替换：修改一个零件后，上层装配可显式级联更新；历史装配可精确复现。
4. 装配级验证：干涉检查、分件体积/数量断言、分件着色渲染、BOM。
5. **Skill 提示词工程**：引导模型把笼统需求（"1.2m×1.6m×0.6m 履带底盘"）工程化地分解为
   模块 → 零部件 → 零件，抑制"许愿式一键生成"。

### 1.3 非目标

- 运动仿真、动力学分析
- 约束求解器（不做配合约束，位姿一律显式 `Pos/Rot/mirror`）
- 自动装配规划（LLM 直接写摆位，不做自动布局搜索）
- 标准件库管理（轴承/螺栓先按普通零件建包，库化后续再说）
- 颜色在 STEP 往返中保留（渲染层配色解决，见 §3）

---

## 2. 术语

| 术语 | 含义 | 对应物 |
|---|---|---|
| 机体 / 整机 | 最终产品级装配 | `track_chassis.456d` |
| 零部件 / 子装配 | 有独立功能的装配单元 | `road_wheel.456d`（支重轮）、`track_side.456d`（履带一侧） |
| 零件 | 单一功能件，基本建模单元 | `bearing_block.456d` |
| 焊件 | 脚本内循环生成的多实体，按**一个零件**对待 | `frame_weldment.456d`（40 方管框架） |
| 装配包 | 只做引用与摆位、不建几何的包 | 机体/零部件级包 |
| 依赖 pin | manifest 中锁定的 `{package, commit}` | deps 条目 |

---

## 3. 事实依据（build123d 0.11.1 实测，2026-08-17）

| # | 结论 | 实测内容 |
|---|---|---|
| F1 | 装配树 STEP 往返**层级与 label 无损** | `track_chassis → road_wheel_asm → bearing_block / wheel_sub → side_wheel` 多级导出/读回完整 |
| F2 | `import_step` 结果不能直接再导出（上游 #1356）；**Compound 包装后成功** | CLI 已内置 `export_step_safe`（`utils/geometry.py`），链路已通 |
| F3 | 镜像实例可用 | `mirror(r, Plane.YZ)` 组装左右履带正常 |
| F4 | 运动学关节 API 存在（`RigidJoint/RevoluteJoint/...`）但无求解器 | 定位靠显式 `Pos/Rot` |
| F5 | **顶层 Compound 的 `volume` 可能返回 0**；必须按 `solids()` 聚合 | 4 件求和 5141.6 正确，顶层 0 |
| F6 | 颜色往返**不可靠**（带 color 导出时 label 也可能丢） | 分件着色放渲染层做 |
| F7 | 关节 API 与 Compound 混用语义未验证 | 本设计不依赖关节 |

---

## 4. 架构决策

### D1 跨包引用用 STEP 产物 + 版本 pin；包内复用用脚本参数化

- **跨包**：装配包 `main.py` 通过 `import_step` 读取依赖包指定 commit 的
  `artifacts/<commit>/model.step`。STEP 是每个 commit 的**不可变成品**，pin 住 hash
  即钉死版本 → 历史装配可精确复现，这是"比 SolidWorks 更方便的版本替换"的根基。
- **包内**：需要参数化变体的结构（焊件：N 根不同长度的 40 方管）在**一个包的脚本里
  循环生成**，按一个零件（多实体）管理。
- 反例（禁止）：装配脚本 `import` 其他包的 py 脚本——依赖工作区当前状态，零件包一改，
  旧装配 commit 永久不可复现。

### D2 装配包的 `main.py` 只做「引用 + 摆位 + 打标」

约定模板：

```python
# === 依赖（由 manifest.deps 解析到 .deps/<name>/model.step）===
from pathlib import Path
DEPS = Path(__file__).resolve().parent.parent / ".deps"

with BuildPart() as asm:
    wheel = import_step(str(DEPS / "road_wheel" / "model.step"))
    wheel.label = "road_wheel_L"
    add(Pos(0, 500, 0) * wheel)                    # 左
    add(Pos(0, -500, 0) * mirror(wheel, Plane.YZ)) # 右（镜像实例）
    ...
    Checkpoint(asm, "layout").expect_solids(12).expect_no_interference().verify()
```

### D3 显式重建，不自动传播

零件包 commit 新版本后，装配包**不会**自动更新；需在装配包 manifest 中改 pin 再
`run`。级联更新 = 自上而下逐层 re-pin（未来可用 `cad deps update` 辅助）。

### D4 LLM 对依赖的理解走脚本快照

模型不需要读 STEP 二进制：每个依赖 commit 已快照其 `src/main.py`（生成逻辑）与
`design.md`（设计意图），按需 checkout/读取即可理解几何来源。

---

## 5. 包与依赖模型

### 5.1 manifest 扩展

```json
{
  "kind": "assembly",
  "deps": [
    { "name": "wheel_bearing", "std":  { "family": "bearing.deep_groove", "params": {"code": "6204"}, "lib": "0.2.0" } },
    { "name": "frame",         "pkg":  { "package": "frame_weldment.456d", "commit": "1965655c" } }
  ]
}
```

- `kind: "assembly"` 的包走装配模板（init 时生成 §4.D2 骨架）；缺省仍为零件。
- deps 支持**两类条目**：`pkg:`（引用既有 .456d 包的 STEP，pin commit）与
  `std:`（引用标准件库参数化族，见 `docs/parts_library_design.md`——零件库先行，
  是装配的依赖底座与 LLM 上下文压缩器）。两类对装配脚本等价（都解析成
  `.deps/<name>/model.step`）。`std.lib` 的物理来源 = 工作区内联/姐妹仓
  `cad-parts`（[github.com/liwuzhan/cad-parts](https://github.com/liwuzhan/cad-parts)，
  `install.sh` 与 `cad_env_bootstrap` 自动探测安装的软依赖），或任何提供
  `cadparts` 包的 venv。
- deps 的 `name` 是装配脚本内引用名；`pkg.commit` 必填、`std.params` 必须完整
  （不允许"最新"——见反模式 A5）。

### 5.2 依赖解析（cad run / commit 前）

1. 校验每个依赖包存在且 commit 在其历史中；
2. 将 `artifacts/<commit>/model.step` 复制（或硬链接）到本包 `.deps/<name>/model.step`；
3. 装配 commit 时把 deps 全量快照进提交元数据（vcs 层）；
4. `cad checkout <装配commit>` 时校验依赖工件仍在，缺失给出明确 hint。

### 5.3 工具影响面（16 个 cad_* 工具）

| 工具 | 变更 |
|---|---|
| `cad_init` | 增 `kind` 参数（part/assembly），装配模板 |
| `cad_run` / `cad_commit` | 前置依赖解析（§5.2） |
| `cad_status` / `cad_log` | 展示 deps 与 pin 状态 |
| 新增 `cad_deps`（评估） | `list / update / check`（哪个依赖有新版本、循环检测） |
| 其余 | 不变 |

---

## 6. 几何与验证

### 6.1 metrics 聚合修复（前置必做）

`compute_metrics`/`cad_inspect` 对 Compound：体积、面积按 `solids()` 聚合（F5）；
增加 `per_solid: [{label, volume, bbox}]`。零件包行为不变。

### 6.2 Checkpoint 新惯例

- 零件/焊件：`expect_solids(N)`（N≥1，焊件 N>1 合法）；
- 装配：`expect_solids(N)`（N=所有实例的实体总数）+ 逐件体积抽验
  （`expect_solid_volume("road_wheel_L", 5141.6, tol=1.0)`，防引用错版本）。

### 6.3 干涉检查（装配的安全网，核心新增）

```python
Checkpoint(asm, "assembly").expect_no_interference(
    tol=1.0,                 # mm³，两两求交体积上限
    allow=[("shaft", "bearing")],  # 过盈/配合面豁免对
).verify()
```

- 实现：装配级对 `solids()` 两两 `intersect`，交集体积 > tol 即失败；
- 结果进 JSONL 事件（`checkpoint_failed` 附冲突对列表），模型据此自迭代；
- 大装配 O(n²)：>50 实体时按 bbox 预筛后再做精确布尔。

### 6.4 渲染

- **分件着色**：渲染器按 `solids()`（或依赖来源）分配固定色板，不依赖 STEP 传色（F6）；
- **爆炸视图**：新增 `explode` 视图——各 solid 沿"相对装配质心的径向"偏移
  `k × bbox 对角线`（k 默认 0.25），正交投影渲染；
- 装配包 commit 默认视图含 `explode`。

### 6.5 BOM

`cad review` / `cad_inspect geometry_summary` 对装配包输出分件表：

```
| # | label | 来源（依赖名/包@commit 或 in-package） | 实体数 | 体积 |
```

---

## 7. Skill 提示词工程（重点）

### 7.1 问题定义

笼统需求 → 可制造图纸之间隔着完整的工程分解链：

```
需求（"1米2宽1米6长高60的履带底盘，履带宽20厘米"）
  → 功能模块划分（车架 / 行走系 / 履带环 / 传动预留）
  → 零部件定义（支重轮、张紧轮、驱动轮、侧架焊件、履带）
  → 零件定义（轴承座、边轮、轴、方管段…）
  → 逐件建模 → 装配 → 干涉/预算回验
```

本质与软件工程同构：需求 → 架构 → 组件 → 实现 → 集成测试；区别只是约束系统
（物理世界：重力/强度/配合/加工 vs 计算环境：类型/内存/时序）。当前语言模型普遍
缺乏这类后训练，直接放任生成会得到"许愿式"结果：比例失真、件数随意、接口对不上。

**提示词工程目标**：用阶段化协议把分解链外化为**强制中间产物**，使模型（含 MoE
架构）在每一跳都被锚定在"工程分解"的行为模式上，而不是跳到"凭感觉画个整体"。

### 7.2 手段：中间产物外化（Externalized Chain-of-Thought）

每个阶段的产出**必须是文件**（design.md 的分节），不是聊天文本。文件即检查点：
下一阶段未拿到上一阶段产物不得开始。这是对"路由稳定性"最有效的机制——产物在
上下文里持续可见，模型不会漂移回许愿模式。

### 7.3 阶段协议（SKILL 核心内容）

```
Stage 0  需求澄清
  - 模糊量（载荷？速度？地面？电机？）用 ask_user_question 问，≤2 轮
Stage 1  整机尺寸预算表（强制，无此表不得建模）
  - 把整机三围分解为各模块的空间预算（见 §7.4 示例）
  - 产出：design.md §budget 表
Stage 2  模块划分
  - 模块表：名称 / 功能 / 数量 / 空间占位 / 接口（安装面、孔位）
Stage 3  零部件分解
  - 每个零部件 → 装配包 + 零件清单（引用图：哪些零件复用、哪些镜像）
  - 产出：依赖图（DAG），标注镜像/多实例
Stage 4  零件设计（复用既有单零件工作流）
  - 每件：design.md → main.py（Checkpoint 必含 expect_solids + bbox）
  - 焊件：单包脚本循环生成，expect_solids(N)
Stage 5  装配
  - 装配包：deps pin → 摆位（Pos/Rot/mirror）→ label
  - Checkpoint：expect_solids + expect_no_interference + 逐件体积
Stage 6  整机审查
  - 预算回验（实测 bbox vs Stage 1 预算）、BOM、爆炸图、渲染四视图
  - 偏差 >5% 回 Stage 1 修正预算
```

### 7.4 尺寸预算示例（履带底盘 1200×1600×600，履带宽 200）

> 此示例直接写入 SKILL，作为 few-shot 教学样例。

| 预算项 | 推导 | 值 (mm) |
|---|---|---|
| 履带中心距 | 整机宽 1200 − 履带宽 200 → 两侧中心线 (1200−200)/2 | 1000 |
| 车架最大宽 | 履带内侧间距 1000−200=800，留 50 间隙 | ≤750 |
| 接地长度 | 整机长 1600 − 驱动/张紧轮段各 250 | ~1100 |
| 每侧支重轮数 | 接地 1100 ÷ 轮距 250 | 4~5 |
| 支重轮直径 | 高度预算：离地 150 + 轮下缘… | ~160 |
| 车架高 | 40 方管 | 40 |
| 轮轴 | 45 钢轴，直径 | 20 |
| 轴承 | 内径 20（标准件） | 6204 |

要点：**每个数字有来源**（整机约束减法 / 标准件规格 / 经验值标注"假设"），
禁止无出处的magic number——与单零件 skill 的参数命名规则一致。

### 7.5 反模式清单（写入 SKILL）

| # | 反模式 | 正确做法 |
|---|---|---|
| A1 | 一键生成整机脚本（几百行画完所有件） | 逐件建包，装配只摆位 |
| A2 | 跳过预算表直接画 | Stage 1 强制先行 |
| A3 | 比例失真（轮径与履带周长不匹配等） | 预算回验 + 干涉检查 |
| A4 | 装配里重建零件几何 | 引用 STEP，pin 版本 |
| A5 | deps 引用"最新版" | 必须指 commit |
| A6 | 忘记镜像件（只画一侧） | 模块表显式标注左右/数量 |
| A7 | 配合面过盈被干涉检查误报卡死 | allow 豁免对，显式声明 |
| A8 | 一次 review 就 commit | 干涉清零 + 预算回验后才 commit |
| A9 | 有标准件库却手画标准件（齿轮/轴承/螺栓） | 先查库（cad_parts / skill 速查表），无对应族再手画并记录原因 |

### 7.6 路由表（模型自判入口）

```
需求信号                              → 进入
─────────────────────────────────────────────────────
单一功能件、无层级词                   → cad-modeling（单零件流）
整机/系统/机构/装配/多部件/整机三围     → cad-assembly（本协议）
焊件/框架/管材阵列                     → cad-modeling 焊件节（单包多实体）
改一个已有零件                         → 既有包新 commit（不改装配）
换版本对比                             → 装配包改 pin → A/B
```

### 7.7 Skill 文件组织

- **新增 `cad-assembly` skill**（阶段协议 + 预算样例 + 反模式 + 路由表）；
- `cad-modeling` 增补：焊件多实体惯例、`expect_solids(N)`、被装配引用时的
  "接口规范"（安装面/孔位在 design.md 中显式列出）；
- `cad-build123d-reference` 增补：`import_step`、`mirror`、Compound 层级、
  `label` 用法；
- `cad-checkpoint` 增补：`expect_no_interference` / `expect_solid_volume`；
- preset `customSkillDirs` 无需改（同目录）。

### 7.8 对 MoE 路由的落地说明

不依赖任何模型内部机制，只用可迁移的外部结构：阶段名固定（Stage 0-6）、产物模板
固定（表格式）、动词开头指令（"填写预算表"、"列出模块表"）、禁止项显式列举。
这些 token 级别的稳定结构持续把上下文锚定在工程分解域，实测对通用模型跳步行为
的抑制最有效；若模型仍跳步，review 模板里再设一道"预算表存在性检查"兜底。

---

## 8. 实施阶段

| 里程碑 | 内容 | 依赖 |
|---|---|---|
| M1 验证基建 | metrics 聚合修复（F5）、`expect_no_interference`、`expect_solid_volume`、`expect_solids(N)` 惯例 | 无 |
| M2 跨包依赖 | manifest deps（含 `std:` 库引用）、`.deps` 解析、init kind=assembly、commit/checkout 快照校验 | M1 + 零件库 PL-M0/M1（见 `parts_library_design.md` §9 联动顺序） |
| M3 渲染与 BOM | 分件着色、explode 视图、BOM 表进 review | M1 |
| M4 Skill 与模板 | cad-assembly skill、cad-modeling 增补、装配 init 模板、预算表模板 | M1–M3 |
| M5 打磨（可选） | `cad_deps list/update/check`、循环检测、大装配 bbox 预筛 | M2 |

建议顺序 M1→M2→M3→M4，M5 按需。每个里程碑独立可验收（M1 完成 = 单包多实体装配
已可用；M2 完成 = 履带底盘案例可跑通）。**与零件库的总体顺序**：PL-M0 → PL-M1 ∥ M1
→ M2 与 PL-M2 合流 → M3/M4（零件库详方案见 `docs/parts_library_design.md`）。

---

## 9. 风险与未决问题

1. **颜色/label 往返不稳**（F6）：渲染层配色绕开；label 丢失时按 deps 名回填。
2. **干涉阈值**：tol 默认 1mm³；配合面（轴-轴承、销-孔）需 allow 豁免，豁免对是否
   要在 design.md 声明？（建议：是，进装配包 design.md §fits 表）
3. **STEP 导入性能**：件数 >30 时 run 变慢；先测，慢则缓存解析结果。
4. **依赖工件清理**：`cad_artifact clean` 可能删掉被装配引用的 STEP → 清理策略需
   感知反向依赖（M2 中处理：被引用的 commit 工件标记 protected）。
5. **镜像实例语义**：`mirror` 后 label 相同 → 分件表/着色需按实例 label 覆写
   （脚本中已约定 `wheel.label = "road_wheel_L"`，渲染按 label 分色即可）。
6. **循环依赖**：A 引用 B、B 引用 A → M2 解析时做 DAG 校验，直接报错。
7. **未验证**：F7（关节 API 与 Compound 混用）；本设计不依赖，若未来做运动副再验。

---

## 10. 证据（2026-08-17 实验）

- 多级装配树 STEP 往返 label/层级保留：`/tmp/asm_test.step`、`/tmp/chassis.step`
- 顶层 Compound volume=0、per-solid 聚合正确：4 件 = 2×2570.8 = 5141.6
- 颜色往返丢失（label 同时丢失）：`/tmp/color.step`
- import_step 再导出需 Compound 包装（#1356）：`/tmp/re1.step`
