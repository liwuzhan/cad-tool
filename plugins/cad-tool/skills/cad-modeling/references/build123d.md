# build123d API 速查参考
> LLM 建模参考：可用操作 + 致命陷阱 + 建模模板。所有代码默认 `from build123d import *`。

## Section 1: API 速查参考

### 1.1 3D 原语

```python
Box(50, 30, 10, align=(Align.CENTER, Align.CENTER, Align.MIN))
Cylinder(15, 20)                        # Z: -10 to +10 (centered by default)
Cylinder(15, 20, align=(Align.CENTER, Align.CENTER, Align.MIN))  # Z: 0 to +20
Cone(20, 10, 30)                        # truncated cone
Sphere(25)
Torus(20, 5)                            # donut, R=20 tube r=5
Wedge(10, 10, 10, 0, 0, 10, 10)        # triangular wedge
```

### 1.2 2D 草图形状

```python
# All inside BuildSketch context
with BuildSketch():
    Circle(10)                           # circle r=10
    Rectangle(40, 20)                    # 40x20
    Ellipse(20, 10)                      # major=20, minor=10
    RegularPolygon(15, 6)                # hexagon inscribed in r=15
    Polygon([(0,0), (10,0), (5,8)])      # triangle from points
    Trapezoid(30, 15, 70)                # width=30, height=15, angle=70°
    RoundedRectangle(30, 20, 3)          # rectangle with r=3 fillets
    SlotOverall(20, 5)                   # total length=20, width=5
    SlotCenterToCenter(30, 5)            # center-to-center=30, width=5
    SlotCenterPoint(20, (5, 0))          # width=20, center at (5,0)
    SlotArc(5, 20, 0, 180)              # arc slot, height=5, r=20
```

### 1.3 曲线构建 (BuildLine context)

```python
with BuildLine():
    Line((0, 0), (10, 0))               # straight line
    Polyline((0,0), (10,0), (10,5))     # connected segments
    FilletPolyline((0,0), (10,0), (10,10), radius=2)  # polyline with fillets
    ThreePointArc((0,0), (5,5), (10,0))  # arc through 3 points
    RadiusArc((0,0), (10,0), radius=8)   # arc with specific radius
    Spline((0,0), (3,5), (7,3), (10,0))  # smooth spline
    Bezier((0,0), (3,10), (7,10), (10,0))  # Bezier curve
    Helix(pitch=2, height=20, radius=5)  # helical curve
    JernArc((0,0), (1,0), radius=5, angle=90)  # from point + tangent direction

# TangentArc: arc tangent to existing line end
with BuildLine():
    l1 = Line((0,0), (10,0))
    TangentArc(l1 @ 1, (15, 5), tangent=l1 % 1)
```

### 1.4 3D 特征操作

```python
# extrude(amount=, mode=, both=, taper=)
with BuildPart():
    with BuildSketch(): Circle(10)
    extrude(amount=20)                   # default Mode.ADD, Z: 0 to 20
    # extrude(amount=10, both=True)       # both directions (total 20)
    # extrude(amount=15, taper=5)         # tapered (degrees)

# revolve(axis=, angle=)
with BuildPart():
    with BuildSketch(Plane.XZ): Rectangle(10, 5)
    revolve(axis=Axis.Z, angle=360)      # full revolution

# loft() - sketches must be on DIFFERENT planes
with BuildPart():
    with BuildSketch(Plane.XY): Circle(20)
    with BuildSketch(Plane.XY.offset(30)): Circle(10)
    loft()

# sweep() - extrude along path
with BuildPart():
    with BuildLine(): Polyline((0,0), (30,0), (30,20))
    with BuildSketch(Plane.XZ): Circle(3)  # cross-section
    sweep()

# fillet / chamfer
with BuildPart():
    Box(20, 20, 10)
    fillet(edges().filter_by(Axis.Z), radius=2)

# Holes (inside BuildPart, use Locations for position)
Hole(radius=3, depth=8)                # through if depth omitted
CounterBoreHole(radius=3, counter_bore_radius=5, counter_bore_depth=3, depth=8)
CounterSinkHole(radius=3, counter_sink_radius=6, depth=8)
```

### 1.5 变换操作

```python
offset(amount=2)                         # offset sketch outline
mirror(about=Plane.XZ)                   # mirror across plane
split(keep=Split.TOP)                    # keep top/bottom half
scale(factor=2)                          # uniform scale
draft(faces(), angle=3, direction=Axis.Z)  # draft angle
thicken(amount=2)                        # surface to solid
section(plane=Plane.XY.offset(5))        # cross-section at Z=5
```

### 1.6 定位系统

```python
with Locations([(10, 20), (-10, 20)]):   # custom positions
    Circle(3, mode=Mode.SUBTRACT)

with PolarLocations(radius=25, count=6, start_angle=0, angular_range=360):
    Circle(4, mode=Mode.SUBTRACT)        # 6 holes on r=25 circle

with GridLocations(x_spacing=20, y_spacing=20, x_count=3, y_count=3):
    Circle(2, mode=Mode.SUBTRACT)        # 3x3 grid

with HexLocations(radius=5, x_count=4, y_count=3):
    Circle(1.5, mode=Mode.SUBTRACT)      # hex-packed
```

### 1.7 选择器系统

```python
# Topology queries (inside BuildPart)
edges()          # all edges
faces()          # all faces
vertices()       # all vertices
solids()         # all solids

# Filter by axis/direction
edges().filter_by(Axis.Z)               # parallel to Z
edges().filter_by(GeType.LINE)          # straight edges

# Sort by position
faces().sort_by(Axis.X)[-1]             # rightmost face (max X)
edges().sort_by(Axis.Z)[0]              # lowest edge (min Z)

# Group by direction (returns list of lists)
edges().group_by(Axis.Z)[-1]            # topmost group

# Area filter
faces() > 100                           # faces with area > 100
```

### 1.8 @ 和 % 运算符 (曲线端点/切线)

```python
with BuildLine():
    l = Line((0,0), (10,5))
    l @ 0          # start point  -> Vector(0, 0, 0)
    l @ 1          # end point    -> Vector(10, 5, 0)
    l % 0          # start tangent
    l % 1          # end tangent

# Usage: chain curves with tangent continuity
with BuildLine():
    l1 = Line((0,0), (10,0))
    TangentArc(l1 @ 1, (15,5), tangent=l1 % 1)
```

### 1.9 工作平面

```python
Plane.XY                # default, Z=0
Plane.XZ                # Y=0
Plane.YZ                # X=0
Plane.XY.offset(10)     # Z=10
Plane.XZ.offset(-5)     # Y=-5

with BuildSketch(Plane.XZ): Rectangle(10, 5)      # draw in XZ plane
with BuildSketch(Plane.XY.offset(15)): Circle(8)   # draw at Z=15
```

### 1.10 布尔模式

```python
Mode.ADD        # union (default)
Mode.SUBTRACT   # difference (cut)
Mode.INTERSECT  # intersection
Mode.REPLACE    # replace current geometry
Mode.PRIVATE    # auxiliary, no boolean

with BuildSketch():
    Circle(30)                          # outer
    Circle(10, mode=Mode.SUBTRACT)      # cut hole
```

### 1.11 对齐

```python
# Tuple (X_align, Y_align, Z_align)
# CENTER = symmetric  |  MIN = starts at origin  |  MAX = ends at origin
Box(10, 10, 10)                                              # all CENTER
Box(10, 10, 10, align=(Align.MIN, Align.MIN, Align.MIN))    # corner at origin
Cylinder(10, 20, align=(Align.CENTER, Align.CENTER, Align.MIN))  # bottom at Z=0
```

## Section 2: 致命陷阱

### 陷阱 1: extrude() 默认 Mode.ADD

`extrude()` 默认添加。想打孔必须 `mode=Mode.SUBTRACT`。

```python
# WRONG: volume increases instead of decreasing
with BuildPart() as p:
    Cylinder(30, 10)
    with BuildSketch(): Circle(10)
    extrude(amount=10)                   # ADD!

# FIX
    extrude(amount=10, mode=Mode.SUBTRACT)
```

### 陷阱 2: Loft 需要不同平面

`Locations` 不改变 sketch 平面。两个 sketch 在同一平面上，loft 体积为 0。

```python
# WRONG: both sketches on Plane.XY despite different Locations
with BuildPart():
    with Locations((0,0,0)): with BuildSketch(): Circle(20)
    with Locations((0,0,30)): with BuildSketch(): Circle(10)
    loft()                               # volume = 0!

# FIX: use Plane.XY.offset()
with BuildPart():
    with BuildSketch(Plane.XY): Circle(20)
    with BuildSketch(Plane.XY.offset(30)): Circle(10)
    loft()                               # works
```

### 陷阱 3: Mode.ADD 不合并不相交实体

无重叠的实体保持独立。必须确保重叠，或用 2D profile 一次性挤出。

```python
# WRONG: Box at r=32, half-size 2, nearest edge r=30. Cylinder r=30. No overlap -> 2 solids
with BuildPart():
    Cylinder(30, 10)
    with Locations((32, 0, 0)): Box(4, 4, 10, mode=Mode.ADD)   # solids=2

# FIX: ensure overlap
    with Locations((28, 0, 0)): Box(8, 4, 10, mode=Mode.ADD)   # solids=1
```

### 陷阱 4: Cylinder 居中 vs extrude 从 Z=0

`Cylinder(r,h)` Z: -h/2 to +h/2。`extrude(amount=h)` Z: 0 to h。混用导致位置错。

```python
# WRONG: cylinder -5 to +5, cut 0 to +10
with BuildPart() as p:
    Cylinder(30, 10)                    # Z: -5 to +5
    with BuildSketch(): Rectangle(5, 5)
    extrude(amount=10, mode=Mode.SUBTRACT)   # partial overlap only

# FIX: align cylinder to Z=0
    Cylinder(30, 10, align=(Align.CENTER, Align.CENTER, Align.MIN))  # Z: 0 to 10
```

### 陷阱 5: 循环中布尔运算不可靠

用手动循环 + 旋转做布尔运算容易出错。用 PolarLocations / GridLocations 替代。

```python
# WRONG: loop with manual rotation
for i in range(20):
    with Locations((30, 0, 0)):
        Rectangle(7, 4, mode=Mode.SUBTRACT, rotation=(0, 0, i*18))

# FIX: PolarLocations (one-shot)
with BuildSketch() as profile:
    Circle(33)
    with PolarLocations(30, 20, start_angle=9):
        Rectangle(7, 4, mode=Mode.SUBTRACT)
    Circle(7.5, mode=Mode.SUBTRACT)
with BuildPart(): extrude(profile.sketch, amount=10)
```

## Section 3: 建模模板

### 模板 1: 2D Profile + 单次挤出 (推荐默认)

```python
from build123d import *
from cad_cli.feedback import Checkpoint
Checkpoint.reset()

outer_r, inner_r, thickness = 30, 10, 8
hole_r, hole_offset, hole_count = 3, 18, 6

with BuildSketch() as profile:
    Circle(outer_r)
    Circle(inner_r, mode=Mode.SUBTRACT)
    with PolarLocations(hole_offset, hole_count):
        Circle(hole_r, mode=Mode.SUBTRACT)

with BuildPart() as part:
    extrude(profile.sketch, amount=thickness)
    Checkpoint(part, "done").expect_solids(1) \
        .expect_bbox_size(outer_r*2, outer_r*2, thickness, tolerance=1).verify()
result = part.part
```

### 模板 2: Sweep 沿路径扫掠 (管道)

```python
from build123d import *
from cad_cli.feedback import Checkpoint
Checkpoint.reset()

pipe_r, wall_t, bend_r, straight_l = 12, 2, 20, 40

with BuildLine():
    FilletPolyline((0,0,0), (straight_l,0,0), (straight_l,straight_l,0), radius=bend_r)
with BuildSketch(Plane.XZ):
    Circle(pipe_r)
    Circle(pipe_r - wall_t, mode=Mode.SUBTRACT)
with BuildPart() as part:
    sweep()
    Checkpoint(part, "pipe").expect_solids(1).verify()
result = part.part
```

### 模板 3: Revolve 旋转体 (轴/皮带轮)

```python
from build123d import *
from cad_cli.feedback import Checkpoint
Checkpoint.reset()

shaft_r, shaft_l, pulley_r, pulley_t, bore_r = 8, 50, 25, 12, 5

with BuildSketch(Plane.XZ) as profile:
    with Locations((shaft_r + 1, 0)):
        Rectangle(pulley_r - shaft_r - 1, pulley_t)
    Rectangle(shaft_r * 2, shaft_l)
    with Locations((0, 0)): Circle(bore_r, mode=Mode.SUBTRACT)
with BuildPart() as part:
    revolve(axis=Axis.Z)
    Checkpoint(part, "pulley").expect_solids(1).verify()
result = part.part
```

## Section 4: 选择器速查

```python
# Edge selection
edges().filter_by(Axis.Z)                     # all vertical edges
edges().sort_by(Axis.Z)[-1]                   # topmost edge

# Face selection
faces().sort_by(Axis.Z)[-1]                   # top face (max Z)
faces().sort_by(Axis.X)[0]                    # leftmost face (min X)
faces() > 100                                 # faces with area > 100
faces().filter_by(GeType.PLANE)               # planar faces only

# Grouping (list of groups)
groups = edges().group_by(Axis.Z)
top_edges = groups[-1]                        # highest Z group
fillet(top_edges, radius=1)

# Combined filter + sort
vert = edges().filter_by(Axis.Z)
longest = sorted(vert, key=lambda e: e.length)[-1]
```

## Section 5: Checkpoint 验证

```python
from cad_cli.feedback import Checkpoint
Checkpoint.reset()

with BuildPart() as part:
    Box(100, 60, 20)
    Checkpoint(part, "base").expect_volume(120000, tolerance=100) \
        .expect_solids(1).expect_bbox_size(100, 60, 20, tolerance=0.1).verify()
    Cylinder(5, 20, mode=Mode.SUBTRACT)
    Checkpoint(part, "hole").expect_volume_decreased().expect_solids(1).verify()
result = part.part
```

| Method | Purpose |
|-------|---------|
| `.expect_volume(val, tolerance=1.0)` | Assert exact volume |
| `.expect_volume_decreased()` | Volume less than previous checkpoint |
| `.expect_volume_increased()` | Volume greater than previous checkpoint |
| `.expect_solids(n)` | Assert solid count (use 1 for single body) |
| `.expect_faces(n)` | Assert face count |
| `.expect_bbox_size(x, y, z, tolerance=1.0)` | Assert bounding box dimensions |
| `.verify()` | Execute all assertions, raise on failure |

Always chain `.verify()` last. Always check `.expect_solids(1)` after boolean ops.
