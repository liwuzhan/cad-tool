"""
齿轮示例 - 带特征级验证

演示如何使用 Checkpoint 在每个特征操作后验证结果。
如果某个特征的结果不符合预期，会立即报错，而不是等到最后才发现。
"""
from build123d import *
from cad_cli.feedback.checkpoint import Checkpoint

# 参数
num_teeth = 20
module = 3
thickness = 10
bore_radius = 7.5

# 计算值
pitch_radius = num_teeth * module / 2
outer_radius = pitch_radius + module
tooth_width = module * 1.5
tooth_depth = module * 2.2

# 重置检查点状态
Checkpoint.reset()

# ========== 方法 1: 正确的做法（2D profile + 单次挤出）==========
with BuildSketch() as gear_profile:
    # 外圆
    Circle(outer_radius)

    # 验证：2D 轮廓面积应该约等于 π * r²
    # （这个是 sketch，没有 volume，跳过检查）

    # 减去齿槽
    with PolarLocations(outer_radius - tooth_depth/2, num_teeth, start_angle=360/num_teeth/2):
        Rectangle(tooth_depth, tooth_width, mode=Mode.SUBTRACT)

    # 中心孔
    Circle(bore_radius, mode=Mode.SUBTRACT)

# 挤出成 3D
with BuildPart() as gear:
    extrude(gear_profile.sketch, amount=thickness)

    # 检查点 1: 挤出后
    Checkpoint(gear, name="after_extrude") \
        .expect_solids(1) \
        .expect_bbox_size(66, 66, 10, tolerance=1.0) \
        .verify()

result = gear.part

# 最终检查
Checkpoint(result, name="final") \
    .expect_solids(1) \
    .expect_faces(83) \
    .expect_volume(26500, tolerance=500) \
    .verify()

print(f"✓ Gear validation passed!")
print(f"  Volume: {result.volume:.1f} mm³")
print(f"  Faces: {len(list(result.faces()))}")
print(f"  BBox: {result.bounding_box()}")
