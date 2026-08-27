"""
错误的齿轮 - 演示 Checkpoint 如何捕捉错误

这个脚本故意使用错误的方式创建齿轮，展示 Checkpoint 如何检测问题。
"""
from build123d import *
from cad_cli.feedback.checkpoint import Checkpoint

# 参数
num_teeth = 5  # 简化
module = 3
thickness = 10
outer_radius = 33

Checkpoint.reset()

with BuildPart() as gear:
    # 基础圆柱（默认居中：Z=-5 到 +5）
    Cylinder(outer_radius, thickness)

    # 检查点 1: 基础圆柱
    Checkpoint(gear, name="base_cylinder") \
        .expect_solids(1) \
        .expect_volume(34000, tolerance=500) \
        .verify()

    # 错误的切割方式（会导致问题）
    for i in range(num_teeth):
        angle = i * (360 / num_teeth)

        with BuildSketch(Plane.XY) as cut_sketch:
            with Locations([(outer_radius - 3, 0)]):
                Rectangle(7.5, 4.5)

        # 这里会出问题：extrude 默认 ADD，且从 Z=0 开始
        cut_part = extrude(cut_sketch.sketch, amount=thickness)

        # 检查点 2: 每次 extrude 后检查体积是否意外增加
        try:
            Checkpoint(gear, name=f"after_extrude_{i}") \
                .expect_volume_decreased() \
                .verify()
        except AssertionError as e:
            print(f"!!! Checkpoint caught error: {e}")
            break

        cut_rotated = cut_part.rotate(Axis.Z, angle)
        gear.part = gear.part - cut_rotated

        # 检查点 3: 减法后检查
        Checkpoint(gear, name=f"after_subtract_{i}") \
            .expect_solids(1) \
            .verify()

result = gear.part
