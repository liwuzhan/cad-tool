# 特征级检查点系统（Checkpoint）

## 概述

**问题**：传统的验证器只在脚本执行完毕后检查最终结果，无法定位哪一步出了问题。

**解决方案**：在每个特征操作后插入检查点（Checkpoint），立即验证该特征是否符合预期。

## 设计理念

### 契约式设计（Design by Contract）

每个特征操作都有预期的效果：
- **添加特征**：体积增加、面数增加
- **减除特征**：体积减少、可能面数增加（孔）
- **布尔运算**：solid 数量保持为 1

通过在代码中明确声明这些预期，可以：
1. **立即检测错误**：在错误发生时就报告，而不是等到最后
2. **精确定位**：知道是哪一步出了问题
3. **文档化意图**：代码即文档，表达设计意图

### 类比

类似于软件工程中的：
- 单元测试中的断言（`assert`）
- 契约式编程（Eiffel, D 语言）
- Property-based testing

## 使用方式

### 基础用法

```python
from build123d import *
from cad_cli.feedback.checkpoint import Checkpoint

with BuildPart() as part:
    # 创建基础圆柱
    Cylinder(30, 10)

    # 检查点：验证基础特征
    Checkpoint(part, name="base") \
        .expect_volume(28274, tolerance=100) \
        .expect_solids(1) \
        .verify()

    # 减去一个孔
    Cylinder(10, 10, mode=Mode.SUBTRACT)

    # 检查点：验证孔被正确切除
    Checkpoint(part, name="after_hole") \
        .expect_volume_decreased() \
        .expect_faces(4) \
        .verify()

result = part.part
```

### 链式调用

```python
Checkpoint(part, "check1") \
    .expect_volume(1000, tolerance=10) \
    .expect_faces(6) \
    .expect_solids(1) \
    .expect_bbox_size(10, 10, 10) \
    .verify()
```

### 比较型检查

检查点会自动保存状态，供下一个检查点比较：

```python
# 第一个检查点
Checkpoint(part, "before").verify()

# 添加特征
Box(10, 10, 10, mode=Mode.ADD)

# 第二个检查点：自动和 "before" 比较
Checkpoint(part, "after") \
    .expect_volume_increased(min_increase=900) \
    .verify()
```

## API 参考

### 构造函数

```python
Checkpoint(part_or_shape, name="checkpoint")
```

- `part_or_shape`: BuildPart 对象或 Shape 对象
- `name`: 检查点名称（用于错误报告）

### 体积检查

```python
.expect_volume(expected, tolerance=1.0)
```
断言体积等于预期值（±误差范围）。

```python
.expect_volume_decreased(min_decrease=0.1)
```
断言体积相比上一个检查点减少了至少 `min_decrease`。

```python
.expect_volume_increased(min_increase=0.1)
```
断言体积相比上一个检查点增加了至少 `min_increase`。

### 拓扑检查

```python
.expect_faces(expected)
```
断言面的数量等于 `expected`。

```python
.expect_faces_increased(min_increase=1)
```
断言面数相比上一个检查点增加了。

```python
.expect_solids(expected)
```
断言 solid 数量（通常应该是 1）。

### 边界框检查

```python
.expect_bbox_within(x_range, y_range, z_range)
```
断言边界框在指定范围内。
- 示例：`.expect_bbox_within((-50, 50), (-50, 50), (0, 10))`

```python
.expect_bbox_size(x, y, z, tolerance=1.0)
```
断言边界框尺寸等于预期值。
- 示例：`.expect_bbox_size(100, 50, 10, tolerance=1.0)`

### 执行验证

```python
.verify(raise_on_fail=True)
```
执行所有检查，返回结果列表。
- `raise_on_fail=True`: 如果有检查失败，抛出 `AssertionError`
- `raise_on_fail=False`: 不抛出异常，仅返回结果

### 重置状态

```python
Checkpoint.reset()
```
重置全局状态。通常在脚本开始时调用。

## JSONL 输出

检查点会输出 JSONL 事件：

### 检查通过

```json
{
  "event": "checkpoint_passed",
  "ts": "2026-01-30T...",
  "payload": {
    "name": "after_hole",
    "passed": 3,
    "total": 3,
    "checks": [
      {
        "type": "volume_decreased",
        "passed": true,
        "expected": "decrease >= 0.1",
        "actual": "decreased by 3141.59",
        "message": "Volume change: 28274 -> 25132 (Δ=-3142)"
      },
      ...
    ]
  }
}
```

### 检查失败

```json
{
  "event": "checkpoint_failed",
  "ts": "2026-01-30T...",
  "payload": {
    "name": "wrong_operation",
    "passed": 0,
    "total": 1,
    "checks": [
      {
        "type": "volume_decreased",
        "passed": false,
        "expected": "decrease >= 0.1",
        "actual": "decreased by -186.20",
        "message": "Volume change: 34211.94 -> 34398.14 (Δ=186.20)"
      }
    ]
  }
}
```

## 实战示例

### 案例 1：检测错误的布尔运算

**问题**：在 BuildPart 中使用 `extrude()` 时忘记指定 `mode=Mode.SUBTRACT`。

```python
with BuildPart() as part:
    Cylinder(30, 10)
    Checkpoint(part, "base").expect_volume(28274, tolerance=100).verify()

    # 错误：extrude() 默认 mode=ADD！
    with BuildSketch(Plane.XY) as sk:
        Circle(10)
    extrude(sk.sketch, amount=10)

    # 检查点会立即捕捉到体积增加而不是减少
    Checkpoint(part, "after_hole").expect_volume_decreased().verify()
    # AssertionError: Checkpoint 'after_hole' failed:
    #   - Volume change: 28274 -> 31415 (Δ=3141)
```

### 案例 2：检测几何偏移

**问题**：Cylinder 默认居中对齐，但 extrude 从 Z=0 开始，导致几何错位。

```python
with BuildPart() as gear:
    Cylinder(30, 10)  # Z: -5 到 +5

    Checkpoint(gear, "base") \
        .expect_bbox_size(60, 60, 10, tolerance=0.1) \
        .verify()

    # 错误：extrude 从 Z=0 开始，会超出圆柱
    with BuildSketch(Plane.XY) as sk:
        with Locations([(25, 0)]):
            Rectangle(10, 5)
    cut = extrude(sk.sketch, amount=10)  # Z: 0 到 10

    # 检查点会检测到边界框 Z 方向异常
    Checkpoint(gear, "after_cut") \
        .expect_bbox_within((-30, 30), (-30, 30), (-5, 5)) \
        .verify()
    # AssertionError: Checkpoint 'after_cut' failed:
    #   - BBox check: FAIL (Z extends to 10, not 5)
```

### 案例 3：齿轮错误检测

完整示例见 `examples/gear_wrong_with_checkpoints.py`。

**关键代码**：

```python
with BuildPart() as gear:
    Cylinder(outer_radius, thickness)
    Checkpoint(gear, "base").expect_volume(34000, tolerance=500).verify()

    for i in range(num_teeth):
        # ... 创建切割块 ...
        cut_part = extrude(cut_sketch.sketch, amount=thickness)

        # 立即检查：切割块不应该增加体积！
        Checkpoint(gear, f"after_extrude_{i}") \
            .expect_volume_decreased() \
            .verify()
        # ^^^ 在第一次循环就会捕捉到错误
```

**输出**：

```
checkpoint_failed: after_extrude_0
  - Volume change: 34211.94 -> 34398.14 (Δ=186.20)
  - Expected: decrease >= 0.1
  - Actual: decreased by -186.20
```

## 最佳实践

### 1. 在关键特征后添加检查点

```python
# 基础特征
Cylinder(30, 10)
Checkpoint(part, "base").expect_solids(1).verify()

# 关键特征（孔、槽、布尔运算等）
Cylinder(10, 10, mode=Mode.SUBTRACT)
Checkpoint(part, "hole").expect_volume_decreased().verify()
```

### 2. 使用描述性名称

```python
Checkpoint(part, "base_cylinder")
Checkpoint(part, "after_mounting_holes")
Checkpoint(part, "after_fillet")
```

### 3. 在循环中使用序号

```python
for i, pos in enumerate(hole_positions):
    Cylinder(5, 10, mode=Mode.SUBTRACT)
    Checkpoint(part, f"hole_{i}").expect_volume_decreased().verify()
```

### 4. 组合多个检查

```python
Checkpoint(part, "final") \
    .expect_volume(1000, tolerance=50) \
    .expect_faces(6) \
    .expect_solids(1) \
    .expect_bbox_size(10, 10, 10, tolerance=1.0) \
    .verify()
```

### 5. 在脚本开始时重置

```python
from cad_cli.feedback.checkpoint import Checkpoint

Checkpoint.reset()  # 清除之前的状态

with BuildPart() as part:
    # ...
```

## 与传统验证器的对比

| 特性 | 传统验证器 | Checkpoint 系统 |
|------|-----------|----------------|
| 时机 | 脚本结束后 | 每个特征后 |
| 定位 | 无法定位 | 精确到特征 |
| 预期 | 只检查有效性 | 声明设计意图 |
| 语义 | 仅几何检查 | 支持语义检查 |
| 调试 | 需要手动排查 | 自动定位错误 |

## 限制与未来改进

### 当前限制

1. **手动插入**：需要在代码中手动添加检查点
2. **无法回溯**：检查点无法修复错误，只能报告
3. **性能开销**：每个检查点都会计算几何属性

### 未来改进（v2.0）

1. **自动注入**：通过装饰器或上下文管理器自动添加检查点
2. **可视化调试**：每个检查点自动生成截图
3. **智能提示**：基于错误模式提供修复建议
4. **性能优化**：缓存几何计算结果

## 总结

Checkpoint 系统提供了一种**契约式 CAD 建模**方法：

1. **声明意图**：每个特征操作后声明预期结果
2. **立即验证**：在错误发生时就捕捉，不是事后检查
3. **精确定位**：知道是哪一步出了问题
4. **文档化**：代码即文档，清晰表达设计意图

这对 AI 辅助 CAD 建模特别有价值，因为 AI 可以：
- 根据特征类型自动生成检查点
- 从检查点失败中学习正确模式
- 使用检查点输出改进下一次生成

**Checkpoint 不是替代传统验证器，而是补充。** 两者结合使用效果最好。
