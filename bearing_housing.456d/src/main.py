# CAD model script - L型轴承座
# 1. 先完成 design.md
# 2. 参数定义在顶部
# 3. 每个特征后添加 Checkpoint

from build123d import *
from cad_cli.feedback import Checkpoint

Checkpoint.reset()

# === 参数（从 design.md 尺寸表） ===
# 前板尺寸
front_plate_length = 76   # X 方向长度
front_plate_height = 51.5 # Z 方向高度

# 底座尺寸
base_length = 54   # X 方向长度
base_width = 40    # Y 方向宽度

# 通用尺寸
thickness = 2             # 板厚度

# 中心孔
bore_diameter = 42

# 安装孔
mount_hole_diameter = 6.5

# === 建模 ===
with BuildPart() as part:
    # 方法：先在 XZ 平面创建 L 型草图，然后沿 Y 方向拉伸
    with BuildSketch(Plane.XZ):
        # 前板：竖直部分
        Rectangle(front_plate_length, front_plate_height)
        # 底座：水平部分 (在前板底部)
        with Locations((0, -front_plate_height/2 + thickness/2)):
            Rectangle(base_length, thickness)

    # 沿 Y 方向拉伸厚度
    extrude(amount=thickness)

    Checkpoint(part, 'l_shape_base') \
        .expect_solids(1) \
        .verify()

    # 挖中心圆柱孔（在前板中心）
    # 前板中心在原点，厚度方向沿 Y 轴
    with Locations((0, 0, 0)):
        Cylinder(bore_diameter/2, thickness*2, mode=Mode.SUBTRACT)

    Checkpoint(part, 'center_bore') \
        .expect_volume_decreased() \
        .expect_solids(1) \
        .verify()

    # 打4个安装孔（底座四角）
    hole_offset_x = 20  # 从底座边缘的距离
    hole_offset_y = 10  # 从底座侧边的距离（在底座平面上）

    # 底座在 XZ 平面上，中心在 Z = -front_plate_height/2 + thickness/2
    base_center_z = -front_plate_height/2 + thickness/2
    base_y = thickness/2  # 孔的 Y 位置（底座厚度中心）

    # 四个孔的位置 (x, y, z)
    hole_positions = [
        (-base_length/2 + hole_offset_x, base_y, base_center_z - base_width/2 + hole_offset_y),
        (base_length/2 - hole_offset_x, base_y, base_center_z - base_width/2 + hole_offset_y),
        (-base_length/2 + hole_offset_x, base_y, base_center_z + base_width/2 - hole_offset_y),
        (base_length/2 - hole_offset_x, base_y, base_center_z + base_width/2 - hole_offset_y),
    ]

    for pos in hole_positions:
        with Locations(pos):
            Cylinder(mount_hole_diameter/2, thickness*2, mode=Mode.SUBTRACT)

    Checkpoint(part, 'mount_holes') \
        .expect_volume_decreased() \
        .expect_solids(1) \
        .verify()

result = part.part
