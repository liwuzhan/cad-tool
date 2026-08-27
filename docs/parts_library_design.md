# 标准件库（Parts Library）设计文档

- 版本：v1（设计稿，未实施）
- 日期：2026-08-17
- 状态：待评审
- 前置阅读：`docs/assembly_design.md`（装配体设计，本文与其 M2 依赖模型联动）
- 定位：**先有零件库，再有装配体**——库是装配的依赖底座，也是 LLM 的上下文压缩器

---

## 1. 动机

### 1.1 行业现状

机械零件库三条路都不通：收费（TraceParts/Misumi 订阅）、破解版（法务风险）、
无 LLM 可用接口（网页/桌面软件，模型调不了）。而 build123d 本身就是参数化几何
内核，自建库在技术上完全可行。

### 1.2 为什么零件库对 LLM 尤其重要（第一性论证）

**库 = 上下文压缩器。**

| | 手画（无库） | 调库 |
|---|---|---|
| 代码量 | 渐开线齿轮 80~150 行、六角螺栓+螺纹 100+ 行 | 1 行函数调用 |
| 出错模式 | 齿廓画反、螺距算错、六角对边距查错 | 参数选错（一查表即知） |
| 上下文成本 | 写+debug 多轮，每轮数千 token | 目录查询几百 token |
| 模型注意力花在 | 几何实现细节 | **工程决策**（规格选择、摆位、配合） |

模型上下文注意力是稀缺资源，要省着用——库把"怎么画"封装掉，只暴露"选什么参数"。

### 1.3 对装配体的意义

- 装配 deps 引用的是**有语义的零件**（`bearing 6204`），不是匿名几何块；
- BOM、干涉豁免对（轴-轴承配合面）、镜像实例都依赖零件身份；
- 没有库，`assembly_design.md` 的依赖图只能指向一堆自画 STEP，工程价值减半。

---

## 2. 目标与非目标

### 2.1 目标

1. 用 build123d 实现**参数化标准件库**，首批覆盖高频机械件（齿轮/轴承/紧固件/型材…）；
2. 每个 family（参数化零件族）带**验证基准**：Checkpoint 断言 + pytest 数值测试，
   LLM 生成的代码不过测试不入库；
3. **发现机制**：模型用极小上下文成本知道库里有什么、怎么调（skill 目录 + `cad_parts` 工具）;
4. 与装配体集成：装配 deps 支持"参数化库引用"，版本可复现。

### 2.2 非目标

- 不做真实螺纹螺旋面为默认（贵且装配无用，见 §4.2 简化原则）；
- 不做材料/热处理/采购信息（BOM 先只给几何+规格代号）；
- 不接第三方库格式（STEP 目录导入后续再说）；
- 不追求 CAD 级细节外观（渲染用途的倒角/圆角纹理后续可选加）。

---

## 3. 架构：两层模型

关键洞察：**标准件是"参数化族"，.456d 包是"具体实例"**，粒度不同，必须分层。

```
L1  参数化族库（Python，随 cad_cli 版本管理）
    cad_cli/parts/
      gear.py      spur_gear(module, teeth, bore, width, pressure_angle=20, ...)
      bearing.py   deep_groove(code="6204", detail="simplified"|"rings")
      fastener.py  bolt(M8, length=30, head="hex"), hex_nut(M8), washer(M8)
      profile.py   square_tube(40, 40, wall=3, length=1000), angle_steel(...), ...
      key.py, ring.py, pulley.py ...
    ↓ 实例化（装配包脚本内一行调用）
L2  实例 = 装配 deps 条目 或 脚本内直接调用
    装配引用：{ name: "wheel_bearing", std: { family: "bearing.deep_groove",
                params: {code: "6204"}, lib: "0.2.0" } }
    包引用：  { name: "road_wheel", pkg: { package: "road_wheel.456d", commit: "a52ab574" } }
```

- L1 是**代码库**：版本随 `cad_cli.__version__`（pyproject 单一版本源），装配引用
  记录库版本即可复现；库不做成 .456d（它不是模型，是能力）。
- L2 装配 deps 同时支持 `std:`（库族+参数）与 `pkg:`（既有包 pin），一条 manifest
  管两类依赖（`assembly_design.md` §5.1 的 deps 模型据此升级）。

---

## 4. 核心设计原则

### 4.1 参数即规格，禁止隐式默认漂移

每个 family 的参数表 = 工程规格表。默认值必须来自标准（齿轮压力角 20°、轴承
尺寸系列），不确定的默认值不设（强制显式传参），避免模型无意识用错默认。

### 4.2 简化表示原则（simplified by default）

装配场景需要的是：**占位正确、干涉正确、BOM 正确**，不是制造图纸。因此：

| 零件 | 默认（simplified） | 可选（detailed） |
|---|---|---|
| 螺栓/螺母 | 圆柱杆+六角头，无螺纹面 | 真实 helix 螺纹（渲染/制造用） |
| 轴承 | 单实体环（内外圈合并，D/d/B 精确） | 内外圈+保持架+滚珠多实体 |
| 挡圈 | 环片 | 开口+耳部 |
| 齿轮 | **真实渐开线齿廓**（这个不简化——啮合与干涉依赖它） | 修缘/变位 |

`detail` 参数显式开，默认 simplified。库把"要多细"封装掉——这也是上下文经济性。

### 4.3 查表数据驱动，数据即代码

标准件尺寸是查表型（6204 → d20/D47/B14）。尺寸表作为 Python 常量表与 family
同文件，**每行数据必须有出处注释**（GB/T 276、DIN 933…），并配 pytest 断言。
系列规律优先公式化（轴承 62xx 的 d=5×xx、D/B 按直径系列），LLM 补表、测试把关。

### 4.4 验证即入库门槛（复用既有 Checkpoint 体系）

每个 family 一个验证 fixture（`test/parts/test_<family>.py` + 示例脚本）：

```python
def test_bearing_6204():
    b = deep_groove("6204")
    Checkpoint(...).expect_bbox_size(47, 47, 14, tol=0.01).expect_solids(1).verify()

@pytest.mark.parametrize("m,z", [(1,20),(2,24),(3,40)])
def test_gear_volume_monotonic(m, z):   # 体积随模数/齿数单调
    ...
```

规则：**无测试的 family 不能合入**。LLM 批量生产零件代码 → pytest 闸门 →
人抽查。这是我们相对"手工建库"和"AI 直出"的双重优势。

---

## 5. 首批零件族清单（按 LLM 手画出错率 × 装配频率排序）

| 优先级 | family | 关键参数 | 难点/来源 | 验证要点 |
|---|---|---|---|---|
| P0 | `gear.spur_gear` 直齿轮 | module, teeth, bore, width, pressure_angle | 渐开线齿廓（build123d 有 involute 参考） | 齿数=齿数断言、体积单调、分度圆直径=m·z |
| P0 | `bearing.deep_groove` 深沟球 62/63xx | code（6204）, detail | 尺寸表 GB/T 276 | bbox 三向精确、内径=代号×5 |
| P0 | `fastener.bolt / hex_nut / washer` | M 规格, length | DIN 933/934/125 尺寸表 | 六角对边 s、头高 k 查表断言 |
| P0 | `profile.square_tube` 方管 | 边长, 壁厚, length | GB/T 6728 | 壁厚断言（剖切或体积反解） |
| P1 | `profile.round_tube / rod` | OD, ID/—, length | — | 体积解析式 |
| P1 | `profile.angle_steel` 角钢 | 边长×边长×厚, length | GB/T 706 | 截面积查表 |
| P1 | `key.parallel` 平键 A/B 型 | b×h, length | GB/T 1096 | 截面断言 |
| P1 | `ring.shaft_retaining` 轴用挡圈 | 轴径 | GB/T 894 | 内径过盈量方向断言 |
| P2 | `pulley.timing` 同步带轮 | 齿型 MXL/XL/T5, 齿数, 宽 | — | 齿距断言 |
| P2 | `sprocket.chain` 链轮 | 链号 08A, 齿数 | GB/T 1243 | 分度圆断言 |
| P2 | `profile.alu_extrusion` 铝型材 | 2020/3030, length | 欧标槽简化 | 槽宽断言 |
| P3 | `motor.flange_adapter` 电机法兰板 | 电机型号 N20/N30/57 | 常见安装孔距表 | 孔距断言 |

P0 四族已覆盖履带底盘案例全部外购件需求（轴承、螺栓、方管）+ 齿轮这个最难件。

---

## 6. 发现机制（模型的"库目录"）

### 6.1 Skill 目录（零工具成本）

`cad-build123d-reference` skill 增加"标准件库速查表"：一行一 family
（名称/关键参数/默认 detail 行为/示例一行代码），全表 ~300 token，模型可常驻。

### 6.2 `cad_parts` 工具（第 17 个 cad_* 工具，P2 里程碑）

```
cad_parts op=list                 → family 目录（名称/一句话/参数名）
cad_parts op=describe family=...  → 参数表 + 默认值 + 出处标准 + 验证状态 + 最小示例
```

- 返回紧凑 JSON，describe 单 family ≤500 token；
- 模型装配前 `list` 一跳获取全部能力，比翻 skill 更精准；
- 插件层新增工具 schema 走既有 16 工具同套校验（canonical schema 规范）。

### 6.3 路由规则（写进 skill）

```
需求中出现标准件信号（轴承型号/螺栓规格/型材/齿轮参数）
  → 先 cad_parts describe 查库 → 有则调库实例化 → 无再手画（并在 design.md 记录"自画原因"）
```

"查库优先于手画"是硬规则，反模式清单加一条：**A9 有库不用手画标准件**。

---

## 7. 与装配体的集成

1. **deps 模型升级**（改 `assembly_design.md` §5.1）：

```json
"deps": [
  { "name": "wheel_bearing", "std":  { "family": "bearing.deep_groove", "params": {"code": "6204"}, "lib": "0.2.0" } },
  { "name": "road_wheel",    "pkg":  { "package": "road_wheel.456d", "commit": "a52ab574" } }
]
```

2. 解析：`std:` 条目由 CLI 在 `.deps/<name>/model.step` 生成实例（调库导出），
   `pkg:` 条目复制既有工件——对装配脚本两种来源等价（都是读 STEP）；
3. BOM 天然带规格代号（`6204`、`M8×30`、`40×40×3 方管`）；
4. 干涉豁免对可引用库身份（`allow=[("shaft:*", "bearing.deep_groove:*")]`）。

## 8. 版本与复现

- 库版本 = `cad_cli.__version__`（单一版本源）；装配 commit 元数据记录
  `lib` 版本，重建时 venv pip pin 同版本即复现；
- family 破坏性参数变更 → minor bump + CHANGELOG 记录迁移；
- 库代码进 `src/cad_cli/parts/`，与 CLI 同仓同测（无独立仓库管理成本）。

---

## 9. 实施里程碑

| 里程碑 | 内容 | 验收 |
|---|---|---|
| PL-M0 内核 | `parts/` 包骨架、family 注册表、验证 fixture 框架、1 个样例族（square_tube） | pytest 绿 |
| PL-M1 P0 四族 | gear / bearing / fastener / square_tube + 尺寸表 + 全部验证 | pytest 绿；履带底盘外购件全覆盖 |
| PL-M2 集成 | 装配 deps `std:` 引用、skill 速查表+路由规则、反模式 A9 | 装配引用库件跑通干涉检查 |
| PL-M3 P1 族 + `cad_parts` 工具 | round_tube/angle/key/ring + 第 17 工具 | describe 返回 ≤500 token |
| PL-M4 P2/P3 族 | pulley/sprocket/extrusion/motor_flange | 按需 |

**总顺序建议**：PL-M0 → PL-M1 ∥（装配 M1 验证基建）→ 装配 M2 与 PL-M2 合流
→ 装配 M3/M4。库先行但不阻塞装配的验证基建。

---

## 10. 风险与未决

1. **尺寸数据正确性**：LLM 补表可能错 → 每行有出处注释 + pytest 断言 + 人工抽查
   P0 族全量；错的代价（装配返工）远大于校对成本。
2. **版权边界**：标准中的数值（尺寸表）本身不受版权保护；不抄录第三方整理的
   数据库内容，按标准号自行整理。
3. **简化精度声明**：simplified 模式的干涉语义（螺纹面按光杆算）必须在 skill 与
   describe 里写明，防止模型把螺栓光杆当螺纹判断配合。
4. **渐开线实现**：build123d 无内置 gear；参考 CadQuery/involute 公式自写，
   齿形精度用啮合测试（两齿轮 pitch 圆相切、中心距=m(z1+z2)/2）断言。
5. **库膨胀**：family 无限增长会稀释目录可读性 → 目录按类分层
   （gear./bearing./fastener./profile. 前缀），`list` 支持类过滤。
