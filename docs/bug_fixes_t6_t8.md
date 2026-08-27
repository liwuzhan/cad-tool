# Bug 修复：T6 Loft 和 T8 齿轮

## Bug #2: T6 Loft 操作体积为 0

### 问题分析

**错误代码**:
```python
with Locations((0, 0, 0)):
    with BuildSketch() as sketch1: Circle(20)
with Locations((0, 0, 30)):
    with BuildSketch() as sketch2: Circle(10)
loft()  # 体积 = 0
```

**问题**：
- `Locations` 改变的是几何体的摆放位置，**不改变 BuildSketch 的工作平面**
- 两个 sketch 都在默认的 `Plane.XY`（Z=0）上绘制
- Loft 两个重叠的 2D 轮廓 → 体积为 0

### 修复方案

**方案 1：使用 Plane.offset()（推荐）**

```python
from build123d import *
from cad_cli.feedback import Checkpoint

Checkpoint.reset()

with BuildPart() as part:
    # 在 Z=0 平面创建底部轮廓（半径 20）
    with BuildSketch(Plane.XY) as sketch1:
        Circle(20)

    # 在 Z=30 平面创建顶部轮廓（半径 10）
    with BuildSketch(Plane.XY.offset(30)) as sketch2:
        Circle(10)

    loft()

    # 验证：截锥体积 = π*h/3*(r1² + r2² + r1*r2)
    # = π*30/3*(400 + 100 + 200) ≈ 21991
    Checkpoint(part, "loft").expect_volume(21991, tolerance=500).expect_solids(1).verify()

result = part.part
```

**方案 2：简化为两段挤出（如果不需要平滑过渡）**

```python
from build123d import *
from cad_cli.feedback import Checkpoint

Checkpoint.reset()

with BuildPart() as part:
    # 底段：半径 20，高 15
    with BuildSketch(Plane.XY) as sketch1:
        Circle(20)
    extrude(amount=15)
    Checkpoint(part, "base").expect_volume(18850, tolerance=500).expect_solids(1).verify()

    # 顶段：半径 10，高 15（在 Z=15 平面上）
    with BuildSketch(part.faces().sort_by(Axis.Z)[-1]) as sketch2:
        Circle(10)
    extrude(amount=15)
    Checkpoint(part, "top").expect_volume_increased().expect_solids(1).verify()

result = part.part
```

---

## Bug #3: T8 Mode.ADD 未合并实体

### 问题分析

**错误代码**:
```python
with BuildPart() as part:
    Cylinder(30, 10)  # 基体圆柱，r=30

    for i in range(12):
        angle = 2 * math.pi * i / 12
        x = 32 * math.cos(angle)
        y = 32 * math.sin(angle)
        with Locations((x, y, 0)):
            Box(3, 4, 10, mode=Mode.ADD)
    # 结果：5 个 solid（未合并）
```

**问题**：
- 齿中心位于 r=32
- Box 尺寸 3×4×10（宽×深×高）
- Box 最近边距离原点：r=32 - max(3/2, 4/2) = 32 - 2 = 30
- 圆柱半径：r=30
- **几何分析**：齿与圆柱之间无重叠体积，`Mode.ADD` 不会合并

**为什么产生 5 个 solid**？
- 原始圆柱：1 个
- 12 个齿中，某些齿之间相互重叠合并成若干组
- 总计 5 个独立 solid

### 修复方案

**方案 1：2D Profile + PolarLocations（强烈推荐）**

```python
from build123d import *
from cad_cli.feedback import Checkpoint
import math

Checkpoint.reset()

# 参数
gear_teeth = 12
tooth_depth = 4
tooth_width = 3
gear_radius = 34  # 齿顶圆半径
tooth_center_radius = 32  # 齿中心位置

with BuildSketch() as profile:
    # 齿顶圆
    Circle(gear_radius)

    # 齿槽（减去）
    with PolarLocations(tooth_center_radius, gear_teeth, start_angle=15):
        Rectangle(tooth_depth, tooth_width, mode=Mode.SUBTRACT)

    # 中心孔
    Circle(8, mode=Mode.SUBTRACT)

with BuildPart() as part:
    extrude(profile.sketch, amount=10)
    Checkpoint(part, "gear").expect_solids(1).verify()

result = part.part
```

**方案 2：增大齿尺寸，确保重叠**

```python
from build123d import *
from cad_cli.feedback import Checkpoint
import math

Checkpoint.reset()

gear_teeth = 12

with BuildPart() as part:
    # 齿轮基体
    Cylinder(30, 10)
    Checkpoint(part, "gear_body").expect_volume(28274, tolerance=100).expect_solids(1).verify()

    # 中心孔
    Cylinder(8, 10, mode=Mode.SUBTRACT)
    Checkpoint(part, "center_hole").expect_volume_decreased().expect_solids(1).verify()

    # 齿（增大尺寸，确保与基体重叠）
    tooth_depth = 8  # 增加到 8（原 4）
    tooth_width = 3
    tooth_radius = 28  # 减小半径到 28（原 32），向内移动

    for i in range(gear_teeth):
        angle = 2 * math.pi * i / gear_teeth
        x = tooth_radius * math.cos(angle)
        y = tooth_radius * math.sin(angle)
        with Locations((x, y, 0)):
            # Box 向外延伸：从 r=28 - 4 = 24 到 r=28 + 4 = 32
            # 与基体 r=30 有重叠区域 [24, 30]
            Box(tooth_width, tooth_depth, 10,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
                rotation=(0, 0, math.degrees(angle)),
                mode=Mode.ADD)

    Checkpoint(part, "teeth").expect_volume_increased().expect_solids(1).verify()

result = part.part
```

**方案 3：使用径向排列的旋转 Box**

```python
from build123d import *
from cad_cli.feedback import Checkpoint
import math

Checkpoint.reset()

gear_teeth = 12

with BuildPart() as part:
    Cylinder(30, 10, align=(Align.CENTER, Align.CENTER, Align.MIN))
    Checkpoint(part, "gear_body").expect_volume(28274, tolerance=100).expect_solids(1).verify()

    Cylinder(8, 10, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
    Checkpoint(part, "center_hole").expect_volume_decreased().expect_solids(1).verify()

    # 齿：在 Y=29 位置（靠近圆柱边缘），旋转摆放
    for i in range(gear_teeth):
        angle = i * 360 / gear_teeth
        with Locations((0, 29, 0)):
            Box(3, 6, 10,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
                rotation=(0, 0, angle),
                mode=Mode.ADD)

    Checkpoint(part, "teeth").expect_volume_increased().expect_solids(1).verify()

result = part.part
```

---

## 推荐选择

### T6 Loft
- **首选**：方案 1（Plane.offset）- 真正的 loft
- **备选**：方案 2（两段挤出）- 简单但无平滑过渡

### T8 齿轮
- **首选**：方案 1（2D Profile）- 最安全、最清晰
- **备选**：方案 2 或 3（修正 3D 布尔）- 适用于必须在 3D 中操作的情况

---

## 关键要点

1. **Loft 陷阱**：`Locations` 不改变 BuildSketch 平面，用 `Plane.XY.offset(z)` 指定高度
2. **Mode.ADD 陷阱**：只有重叠的实体才会合并，不相交的实体保持独立
3. **调试技巧**：使用 `Checkpoint(...).expect_solids(1)` 立即发现多实体问题

---

*生成于：2026-01-31*
*来源：CAD CLI v2.0 测试 bug 修复*
