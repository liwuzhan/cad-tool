# Probe seat: 6305 journal - 装配设计文档

## 装配目标

一根轴 + 一个 6305 深沟球轴承。轴的**轴颈直径不是设计者选的**，而是由所装轴承的
`shaft_bore` 接口推导：换一个轴承型号，轴颈、轴向链与轴肩位置一起跟随。
本包用来验证「接口 → 几何」这条链在装配包里是否真的闭合。

## 关键尺寸（全部来自推导，不是字面量）

| 量 | 值 | 来源 |
|---|---|---|
| 轴承 `d / D / B` | 25 / 62 / 17 | `cadparts derive bearing.deep_groove code=6305` |
| 轴颈（seat）⌀ × 长 | **⌀25 × 17** | `Seat("bearing.deep_groove", {"code":"6305"}, "shaft_bore")` |
| 轴肩（collar）⌀ × 长 | ⌀32 × 8 | `Free`，无库件依据（轴承外形不含内圈挡边直径） |
| 轴伸端 ⌀ × 长 | ⌀25 × 15 | `Free`，直径复用推导出的轴颈直径，仅长度为设计选择 |
| 轴总长 | 40 | 8 + 17 + 15，轴向链由 `shaft_dimensions` 推出 |
| 装配总体包络 | 62 × 62 × 40 | 轴承外径决定 X/Y，轴长决定 Z |

轴向链：轴肩 z=0..8 → 轴颈 z=8..25（轴承同段，z=8..25）→ 轴伸端 z=25..40。
轴承按接口 frame `shaft.seat_bearing_a`（origin z=8）落位，不从 STEP 反推坐标。

## 坐标与接口

- 世界坐标：X 长、Y 宽、Z 高；装配轴线为 +Z。
- 每个实例唯一 label（`shaft` / `bearing_6305`）；位姿显式写出（`Pos(*seat["frame"]["origin_mm"])`）。
- 标准件按 cadparts 命名接口定位，不从 STEP 或图片猜接口。

## 组件表

| 实例 label | 来源 | 数量 | 接口 | BOM/采购描述 |
|---|---|---:|---|---|
| `shaft` | 非标（本包 `ports.py` 声明） | 1 | `seat_bearing_a`（`cylindrical_surface` ⌀25×17） | 车削件，⌀32/⌀25 台阶轴 |
| `bearing_a` | cadparts `bearing.deep_groove` | 1 | `shaft_bore`（`cylindrical_bore` ⌀25） | 6305（GB/T 276-2013），simplified 包络 |

## 声明在哪

| 内容 | 文件 | 为什么在这 |
|---|---|---|
| 依赖与配对关系 | `manifest.json` 的 `deps` / `mates` | 纯 JSON，读取不需要执行任何脚本 |
| 自建件的接口 | `ports.py` 的 `PORTS` | 契约与实现分家，`cad mates` 才能先于几何运行 |
| 几何实现 | `src/main.py` | 从 `ports.py` 读契约与推导值，不重新声明轴颈尺寸 |

## 装配校验

`cad mates`（不建几何，先于建模运行）实测结果：

| mate | 类型配对 | 判决 |
|---|---|---|
| `shaft.seat_bearing_a` ↔ `bearing_a.shaft_bore` | cylindrical_surface ↔ cylindrical_bore | `PASS` |
| `shaft.shoulder_collar_bearing_a` ↔ `bearing_a.axial_face_min` | planar_face ↔ planar_face | `PASS` |

`overall = PASS`（PASS 2 / WARN 0 / FAIL 0 / UNKNOWN 0）。覆盖率：声明 11 个接口，
被 mate 引用 4 个，未引用 7 个（`bearing_a.housing_seat`、`shaft.rotation_axis` 等）；
未被引用的接口**不在本次判定范围内**，`PASS` 不等于「全都验过了」。

几何断言（`cad run`，全部通过）：

- `expect_solids(2)` — 轴与轴承是两个独立实体，未融合
- `expect_volume(65121.289 ± 0.1)` — 轴 22141.945 + 轴承 42979.344
- `expect_bbox_size(62, 62, 40)` — 与推导出的包络一致
- `cad validate` / `cad review` 通过；渲染图人工核对过外形比例

## 看过图之后的判断（iso / front / top）

- iso：一个大而扁的圆盘（轴承 ⌀62×17）平放，中央立起一根较细的圆柱（轴伸端 ⌀25），
  轴顶面与轴承顶面是两块亮色平面，轴承外圈是深色柱面。
- front：左右对称的十字/T 形轮廓 —— 上 ⌀25（轴伸端）、中 ⌀62×17（轴承）、下 ⌀32×8（轴肩）；
  像素实测比值 156:390:206 ≈ 25:62:32，与设计一致。
- top：两个同心圆，外 ⌀62、内 ⌀25，像素比 405:165 = 2.45 ≈ 62:25。

结论：轴承包住轴颈、轴肩在轴承下端面处顶住内圈，几何与声明一致。

## 明确不做

- **不建模配合公差**：轴颈 ⌀25 与轴承孔 ⌀25 是公称相同，实际配合需另选 ISO 286 配合带
  （如 25k6/h5）。`cad mates` 的边界里明说未查公差。
- **无外壳/座孔**：轴承外圈 `housing_seat` 未被任何 mate 引用，本包不含轴承座。
- **无轴向锁紧**：轴伸端没有螺母/挡圈，轴承只被轴肩单向定位。
- **强度、寿命、润滑、工艺均未验证**。
