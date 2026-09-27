# 设计审查

## 渲染图

- iso: `/Users/liwuzhan/Desktop/cad tools v2/models/probe_resize.456d/runlog/review_iso.png`
- front: `/Users/liwuzhan/Desktop/cad tools v2/models/probe_resize.456d/runlog/review_front.png`
- right: `/Users/liwuzhan/Desktop/cad tools v2/models/probe_resize.456d/runlog/review_right.png`
- top: `/Users/liwuzhan/Desktop/cad tools v2/models/probe_resize.456d/runlog/review_top.png`

## 几何指标

- 体积: 51324.20 mm³
- 表面积: 12019.73 mm²
- 面数: 7
- 边数: 9
- 顶点数: 6
- 实体数: 2
- 边界框: X[-31.0, 31.0] Y[-31.0, 31.0] Z[0.0, 17.0]
- 外形尺寸: 62.0 x 62.0 x 17.0 mm

## 面类型分布

| 类型 | 数量 | 占比 | 总面积 |
|------|------|------|--------|
| planar | 4 | 57% | 6038.14 mm² |
| cylindrical | 3 | 43% | 5981.59 mm² |

平面方向分布: +Z: 2面, -Z: 2面

圆柱面: 3 个 (索引: [1, 3, 6])

## 几何结构文本描述

```
=== Geometry Description ===

Overall size: X=62.0 x Y=62.0 x Z=17.0 mm
Bounding box: X[-31.0..31.0]  Y[-31.0..31.0]  Z[0.0..17.0]
Volume: 51324.20 mm³
Solids: 2
Total faces: 7

--- Face Type Breakdown ---
  planar: 4 faces (57%), total area=6038.14 mm²
    face directions: +Z: 2, -Z: 2
  cylindrical: 3 faces (43%), total area=5981.59 mm²
    face indices: [1, 3, 6]

--- Key Faces ---
  Face[3]: cylindrical (-X), area=3311.24 mm², center=(-31.0, -0.0, 8.5)
  Face[4]: planar (+Z), area=2528.20 mm², center=(0.0, 0.0, 17.0)
  Face[5]: planar (-Z), area=2528.20 mm², center=(0.0, 0.0, 0.0)
  Face[6]: cylindrical (+X), area=1335.18 mm², center=(-12.5, -0.0, 8.5)
  Face[1]: cylindrical (-X), area=1335.18 mm², center=(-12.5, 0.0, 8.5)
  Face[0]: planar (-Z), area=490.87 mm², center=(-0.0, 0.0, 0.0)
  Face[2]: planar (+Z), area=490.87 mm², center=(-0.0, 0.0, 17.0)

--- Cylindrical Features (possible holes/bosses) ---
  3 cylindrical faces detected
  Face[1]: center=(-12.5, 0.0, 8.5), area=1335.18 mm²
  Face[3]: center=(-31.0, -0.0, 8.5), area=3311.24 mm²
  Face[6]: center=(-12.5, -0.0, 8.5), area=1335.18 mm²

--- Interpretation Guide ---
  planar faces = flat surfaces (bases, walls, cut faces)
  cylindrical faces = holes, bores, shafts, fillets
  conical faces = chamfers, tapers, countersinks
  spherical faces = ball ends, spherical cuts
  toroidal faces = fillets, rounds, O-ring grooves
  The largest planar faces typically define the part envelope.
  Cylindrical face area / (2*pi) approximates radius*height for a hole.
```

## 逐特征审查

### 特征: assembly  [PASS]
- **体积**: 51324.20 mm³
- **面数**: 7
- **实体数**: 2
- **面类型**: planar:4, cylindrical:3
- **边界框**: X[-31.0..31.0] Y[-31.0..31.0] Z[0.0..17.0]

**断言结果:**
- ✓ Solid count: expected 2, got 2
- ✓ Volume: expected 51324.2±1.0, got 51324.20

- **意图**: 一根 ⌀25×17 的轴颈被一个 6305 深沟球轴承（d25/D62/B17）支撑；
  两者都是回转体，轴承套在轴颈上、端面齐平（`seat_support_a` 的 frame 在 Z=0）。
- **分析**（视觉 + 数值，逐视图）:
  - `iso`：一个扁圆柱（轴承外圈，⌀62）上端面可见一个同心圆孔；量像素直径比
    孔/外圈 ≈ 165/410 ≈ 0.40 ≈ 25/62 = 0.403，与 6305 的 d/D 一致。
  - `top`：两个同心圆（外 ⌀62、孔 ⌀25），没有第三个轮廓——因为轴颈 ⌀25 与
    轴承孔 ⌀25 公称相等、侧面完全重合（与 6204 版同样的情形：轴被轴承遮住）。
  - `front` / `right`：矩形 62 宽 × 17 高，看不到轴——轴与轴承同高（都是 17），
    完全被外圈挡住。这是**公称尺寸相等**的正常结果，不是漏件。
  - 数值：Face[3] 是 ⌀62 的圆柱面（面积 π·62·17 = 3311.2 mm² ✓），Face[1]/[6]
    是 ⌀25 的圆柱面（π·25·17 = 1335.2 mm²，正反两半 ✓），±Z 各 2528.2 mm²
    = π/4·(62²−25²) ✓。体积 51324.20 = 轴 8344.86 + 轴承 42979.34 ✓。
- **判定**: ✓ 几何与 `design.md` 的 6305 声明（轴孔 ⌀25、外径 ⌀62、宽 17）一致；
  与 `manifest.json` 的 `deps.code = 6305` 一致（`cadparts derive` 报 d25/D62/B17）。

## 总体判定

- **断言通过率**: 2/2
- [x] 所有特征物理上可行
- [x] 渲染结果与 design.md 一致（6305：⌀25 孔 / ⌀62 外径 / 高 17）
- [x] 可以 commit（已提交 `bf9cdd2dacbf`，文档提交 `d8ba9b72f37f`）
