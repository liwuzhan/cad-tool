# 验证器改进建议

## 发现的问题

### 案例：齿轮布尔运算错误

**症状**:
- 边界框不对称：`X=[-33, 33.75]` 而不是 `[-33, 33]`
- Z 方向偏移：`Z=[-5, 10]` 而不是 `[0, 10]`
- 前视图显示右侧有独立方块突出

**根本原因**:
```python
with BuildPart() as gear:
    Cylinder(outer_radius, thickness)  # 居中：Z=-5 到 +5

    for i in range(num_teeth):
        with BuildSketch(Plane.XY) as cut_sketch:
            Rectangle(...)
        cut_part = extrude(cut_sketch.sketch, amount=thickness)  # Z=0 到 10，且默认 ADD！
        cut_rotated = cut_part.rotate(Axis.Z, angle)
        gear.part = gear.part - cut_rotated  # 尝试减去，但已经混乱了
```

**问题分析**:
1. `Cylinder()` 默认居中对齐：Z ∈ [-5, +5]
2. `extrude()` 从 Z=0 挤出：Z ∈ [0, 10]
3. 在 BuildPart 上下文中，`extrude()` 默认 `mode=ADD`，自动添加到 gear
4. 切割块的 Z ∈ [5, 10] 部分超出圆柱，无法被减去
5. 最后一次循环的切割块部分留在了齿轮中

**BRep 检查器无法检测**:
- `is_valid` = True ✅
- `is_manifold` = True ✅
- `len(solids)` = 1 ✅
- `BRepCheck_Analyzer.IsValid()` = True ✅

**因为从几何角度这是一个有效的实体，只是不符合设计意图（语义错误）。**

## 正确做法

```python
with BuildSketch() as gear_profile:
    Circle(outer_radius)
    with PolarLocations(...):
        Rectangle(..., mode=Mode.SUBTRACT)  # 直接在 2D 减去
    Circle(bore_radius, mode=Mode.SUBTRACT)

with BuildPart() as gear:
    extrude(gear_profile.sketch, amount=thickness)  # 一次挤出完成
```

或者使用对齐：
```python
with BuildPart() as gear:
    Cylinder(outer_radius, thickness, align=(Align.CENTER, Align.CENTER, Align.MIN))  # Z从0开始

    with Locations(...):
        Box(..., mode=Mode.SUBTRACT)  # 直接减去
```

## 检查器改进方案

### 1. 静态分析（编译时）
无法在不执行代码的情况下检测这类错误。

### 2. 运行时检测（当前方案）
当前只检查最终结果，无法追溯过程问题。

### 3. 增强运行时检测

#### 方案 A：检测边界框异常
```python
def check_bbox_anomalies(shape) -> List[ErrorInfo]:
    """检测边界框异常"""
    errors = []
    bbox = shape.bounding_box()

    # 检测 Z 方向偏移（Cylinder 默认居中，extrude 默认从0开始）
    if bbox.min.Z < -0.1:  # 有负Z
        if bbox.max.Z > bbox.size.Z * 0.6:  # 且顶部超出
            errors.append(ErrorInfo(
                message="Z-axis bbox suggests misaligned geometry (Cylinder centered + extrude from 0?)",
                hint="Use align=(Align.CENTER, Align.CENTER, Align.MIN) or create profile in 2D first"
            ))

    # 检测轻微不对称（可能是浮点误差，也可能是错误）
    center_x = (bbox.max.X + bbox.min.X) / 2
    center_y = (bbox.max.Y + bbox.min.Y) / 2
    tolerance = 0.1  # mm

    if abs(center_x) > tolerance or abs(center_y) > tolerance:
        asymmetry = max(abs(center_x), abs(center_y))
        errors.append(ErrorInfo(
            message=f"Bounding box center offset by {asymmetry:.2f}mm from origin",
            hint="May indicate incomplete boolean operation or misaligned geometry"
        ))

    return errors
```

#### 方案 B：追踪特征操作（需要修改 executor）
在执行脚本时记录每个几何操作：
```python
class FeatureTracker:
    def track_operation(self, before: Shape, after: Shape, operation: str):
        # 检查 solid 数量变化
        solids_before = len(list(before.solids()))
        solids_after = len(list(after.solids()))

        if operation == "SUBTRACT" and solids_after > solids_before:
            warnings.append("Subtract operation increased solid count")

        # 检查体积变化
        if operation == "SUBTRACT" and after.volume >= before.volume:
            warnings.append("Subtract operation did not decrease volume")
```

**但这需要侵入式修改，难以实现。**

#### 方案 C：Strict 模式（最实用）
添加 `--strict` 标志，启用额外检查：
```bash
cad validate --strict
```

检查内容：
1. 边界框对称性警告
2. Z 轴对齐警告
3. 体积合理性（与边界框体积对比）
4. Shell/Solid 数量

## 推荐方案

**短期（v1.1）**:
1. 添加边界框异常检测（方案 A）
2. 添加文档说明常见错误模式
3. 在示例中展示正确的布尔运算方式

**中期（v2.0）**:
1. 添加 `--strict` 模式
2. 提供设计意图验证（用户声明预期体积/面数等）
3. 集成 linter 检查常见代码模式错误

**长期（v3.0）**:
1. 可视化调试器，逐步显示每个特征操作
2. 自动修复建议（"检测到 Cylinder 居中但 extrude 从 0 开始，建议使用 align=..."）

## 结论

**这类错误是代码逻辑错误，不是几何有效性错误。**

BRep 检查器只能检查"这是不是一个有效的几何体"，不能检查"这是不是你想要的几何体"。

最佳解决方案是：
1. **预防**：文档、示例、最佳实践
2. **检测**：启发式异常检测（边界框、体积等）
3. **工具**：可视化调试、逐步验证

**不能期望自动检查器理解设计意图。**
