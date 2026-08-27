---
name: cad-checkpoint
description: 在难以观察的 build123d 特征附近按需放置 Checkpoint 数值探针，检查体积、实体数、面数或边界框变化；简单模型通常不需要。
---

# Checkpoint 数值探针

Checkpoint 是可选的特征级观察手段，适合复杂布尔、循环特征或关键尺寸。它提供局部证据，
不替代模型对源码、渲染图和最终几何的判断，也不要求每个特征都放置。

```python
from build123d import *
from cad_cli.feedback import Checkpoint

Checkpoint.reset()

with BuildPart() as part:
    Cylinder(30, 10)
    Checkpoint(part, "base") \
        .expect_bbox_size(60, 60, 10, tolerance=1) \
        .verify()

    Cylinder(10, 10, mode=Mode.SUBTRACT)
    Checkpoint(part, "after_hole") \
        .expect_volume_decreased() \
        .expect_solids(1) \
        .verify()

result = part.part
```

## 可用检查

```python
.expect_volume(expected, tolerance=1.0)
.expect_volume_decreased(min_decrease=0.1)
.expect_volume_increased(min_increase=0.1)
.expect_faces(expected)
.expect_faces_increased(min_increase=1)
.expect_solids(expected)
.expect_bbox_size(x, y, z, tolerance=1.0)
.expect_bbox_within(x_range, y_range, z_range)
.verify(raise_on_fail=True)
```

`cad_run` 会在结构化结果中返回探针名称、检查项和通过状态。断言失败时，可修改预期、删除
已经失去价值的探针，或直接检查对应源码与几何；不要为了消除报警而改变本来正确的设计。
