# 设计审查

## 渲染图

- iso: `/Users/liwuzhan/Desktop/cad tools v2/models/fidelity_probe.456d/runlog/review_iso.png`
- front: `/Users/liwuzhan/Desktop/cad tools v2/models/fidelity_probe.456d/runlog/review_front.png`
- top: `/Users/liwuzhan/Desktop/cad tools v2/models/fidelity_probe.456d/runlog/review_top.png`
- right: `/Users/liwuzhan/Desktop/cad tools v2/models/fidelity_probe.456d/runlog/review_right.png`

## 按需审查图

> 以下尺寸、标注和剖切由模型主动指定，只提供观察证据，不作合格判定。

- ports_top2 (top): PNG `/Users/liwuzhan/Desktop/cad tools v2/models/fidelity_probe.456d/runlog/review_drawing_ports_top2.png` · SVG `/Users/liwuzhan/Desktop/cad tools v2/models/fidelity_probe.456d/runlog/review_drawing_ports_top2.svg` · 数据 `/Users/liwuzhan/Desktop/cad tools v2/models/fidelity_probe.456d/runlog/review_drawing_ports_top2.json`

## 几何指标

- 体积: 27675.25 mm³
- 表面积: 9540.02 mm²
- 面数: 11
- 边数: 27
- 顶点数: 18
- 实体数: 1
- 边界框: X[-30.0, 30.0] Y[-30.0, 30.0] Z[-4.0, 4.0]
- 外形尺寸: 60.0 x 60.0 x 8.0 mm

## 面类型分布

| 类型 | 数量 | 占比 | 总面积 |
|------|------|------|--------|
| planar | 6 | 55% | 8838.81 mm² |
| cylindrical | 5 | 45% | 701.20 mm² |

平面方向分布: +X: 1面, +Y: 1面, +Z: 1面, -X: 1面, -Y: 1面, -Z: 1面

圆柱面: 5 个 (索引: [6, 7, 8, 9, 10])

## 几何结构文本描述

```
=== Geometry Description ===

Overall size: X=60.0 x Y=60.0 x Z=8.0 mm
Bounding box: X[-30.0..30.0]  Y[-30.0..30.0]  Z[-4.0..4.0]
Volume: 27675.25 mm³
Solids: 1
Total faces: 11

--- Face Type Breakdown ---
  planar: 6 faces (55%), total area=8838.81 mm²
    face directions: +X: 1, +Y: 1, +Z: 1, -X: 1, -Y: 1, -Z: 1
  cylindrical: 5 faces (45%), total area=701.20 mm²
    face indices: [6, 7, 8, 9, 10]

--- Key Faces ---
  Face[2]: planar (+Z), area=3459.41 mm², center=(-0.0, 0.0, 4.0)
  Face[4]: planar (-Z), area=3459.41 mm², center=(-0.0, 0.0, -4.0)
  Face[0]: planar (-X), area=480.00 mm², center=(-30.0, 0.0, 0.0)
  Face[1]: planar (-Y), area=480.00 mm², center=(-0.0, -30.0, 0.0)
  Face[3]: planar (+Y), area=480.00 mm², center=(-0.0, 30.0, 0.0)
  Face[5]: planar (+X), area=480.00 mm², center=(30.0, 0.0, 0.0)
  Face[9]: cylindrical (+X), area=248.81 mm², center=(-5.0, -0.0, 0.0)
  Face[6]: cylindrical (+X), area=113.10 mm², center=(-24.2, -22.0, 0.0)
  Face[7]: cylindrical (+X), area=113.10 mm², center=(19.8, -22.0, 0.0)
  Face[8]: cylindrical (+X), area=113.10 mm², center=(-24.2, 22.0, 0.0)
  ... and 1 more faces (total area=113.10 mm²)

--- Cylindrical Features (possible holes/bosses) ---
  5 cylindrical faces detected
  Face[6]: center=(-24.2, -22.0, 0.0), area=113.10 mm²
  Face[7]: center=(19.8, -22.0, 0.0), area=113.10 mm²
  Face[8]: center=(-24.2, 22.0, 0.0), area=113.10 mm²
  Face[9]: center=(-5.0, -0.0, 0.0), area=248.81 mm²
  Face[10]: center=(19.8, 22.0, 0.0), area=113.10 mm²

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

### 特征: [名称]
- **意图**: 
- **观察**: 
- **物理**: 
- **判定**: ✓ / ✗

## 总体判定

- [ ] 所有特征物理上可行
- [ ] 渲染结果与 design.md 一致
- [ ] 可以 commit
