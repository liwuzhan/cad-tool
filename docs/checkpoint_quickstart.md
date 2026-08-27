# Checkpoint System - Quick Start

## What is it?

Checkpoint 是一个**特征级验证系统**，让你在每个建模步骤后立即验证结果是否符合预期。

类似于编程中的断言（assert），但用于 CAD 特征。

## Why use it?

**传统方式**：
```python
# 创建复杂模型
# ... 100 行代码 ...

# 最后验证
cad validate
# ❌ 错误！但不知道是哪一步出了问题
```

**使用 Checkpoint**:
```python
from cad_cli.feedback import Checkpoint

# 步骤 1
Cylinder(30, 10)
Checkpoint(part).expect_volume(28274, tolerance=100).verify()
# ✓ 通过

# 步骤 2
Cylinder(10, 10, mode=Mode.SUBTRACT)
Checkpoint(part).expect_volume_decreased().verify()
# ❌ 失败！立即知道是步骤 2 出了问题
```

## Basic Example

```python
from build123d import *
from cad_cli.feedback import Checkpoint

Checkpoint.reset()  # 开始前重置

with BuildPart() as part:
    # 创建基础圆柱
    Cylinder(30, 10)
    Checkpoint(part, "base") \
        .expect_volume(28274, tolerance=100) \
        .expect_solids(1) \
        .verify()

    # 减去孔
    Cylinder(10, 10, mode=Mode.SUBTRACT)
    Checkpoint(part, "after_hole") \
        .expect_volume_decreased() \
        .expect_faces(4) \
        .verify()

result = part.part
```

## Quick API Reference

### 体积检查
```python
.expect_volume(expected, tolerance=1.0)
.expect_volume_decreased(min_decrease=0.1)
.expect_volume_increased(min_increase=0.1)
```

### 拓扑检查
```python
.expect_faces(expected)
.expect_faces_increased(min_increase=1)
.expect_solids(expected)
```

### 边界框检查
```python
.expect_bbox_size(x, y, z, tolerance=1.0)
.expect_bbox_within(x_range, y_range, z_range)
```

### 执行
```python
.verify(raise_on_fail=True)  # 抛出异常（默认）
.verify(raise_on_fail=False)  # 仅返回结果
```

## Real Example: Catching Gear Error

完整代码见 `examples/gear_wrong_with_checkpoints.py`

```python
with BuildPart() as gear:
    Cylinder(outer_radius, thickness)
    Checkpoint(gear, "base").expect_volume(34000, tolerance=500).verify()

    for i in range(num_teeth):
        # 错误的代码：extrude 在 BuildPart 中默认 ADD
        cut_part = extrude(cut_sketch.sketch, amount=thickness)

        # Checkpoint 立即捕捉错误！
        Checkpoint(gear, f"after_extrude_{i}") \
            .expect_volume_decreased() \
            .verify()
        # AssertionError: Volume increased by 186mm³, expected decrease!
```

**输出**:
```json
{
  "event": "checkpoint_failed",
  "payload": {
    "name": "after_extrude_0",
    "checks": [{
      "passed": false,
      "message": "Volume change: 34211.94 -> 34398.14 (Δ=186.20)"
    }]
  }
}
```

## When to Use

✅ **使用 Checkpoint**:
- 复杂的布尔运算
- 循环中的特征操作
- 关键尺寸验证
- 调试新模型

❌ **不需要 Checkpoint**:
- 简单的单一特征
- 经过充分测试的模板

## Documentation

完整文档：`docs/checkpoint_system.md`

## Examples

- `examples/gear_with_checkpoints.py` - 正确的齿轮（带验证）
- `examples/gear_wrong_with_checkpoints.py` - 错误检测演示
