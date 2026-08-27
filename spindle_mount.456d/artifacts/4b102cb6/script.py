"""
Spindle Mount / 主轴夹持座
Version 1: 基础形状
"""
from build123d import *
from cad_cli.feedback import Checkpoint

Checkpoint.reset()

# === 参数 ===
base_width = 76       # 底座宽度 (X)
base_depth = 54       # 底座深度 (Y)
base_height = 26      # 底座高度

total_height = 51.5   # 总高度
upper_width = 54      # 上部宽度

bore_diameter = 42    # 中心孔直径
bore_center_z = 42    # 中心孔圆心高度

hole_dia = 6.5        # 安装孔直径
hole_spacing_y = 20   # 安装孔 Y 方向间距

# === 建模 ===
with BuildPart() as part:
    # Step 1: 底座
    Box(base_width, base_depth, base_height,
        align=(Align.CENTER, Align.CENTER, Align.MIN))
    Checkpoint(part, "base").expect_solids(1).verify()

    # Step 2: 上部块体
    upper_height = total_height - base_height  # 25.5mm
    with Locations((0, 0, base_height)):
        Box(upper_width, base_depth, upper_height,
            align=(Align.CENTER, Align.CENTER, Align.MIN))
    Checkpoint(part, "upper_block").expect_solids(1).verify()

    # Step 3: 圆柱形顶部（形成圆弧外轮廓）
    # 圆心在 Z=42，顶部在 Z=51.5，所以露出部分 = 9.5mm
    # 外半径需要 > 9.5mm，取 upper_width/2 = 27
    outer_radius = upper_width / 2  # 27mm
    with Locations((0, 0, bore_center_z)):
        Cylinder(outer_radius, base_depth,
                 rotation=(90, 0, 0),
                 align=(Align.CENTER, Align.CENTER, Align.CENTER))
    Checkpoint(part, "with_arc_top").expect_solids(1).verify()

    # Step 4: 中心孔 Φ42
    with Locations((0, 0, bore_center_z)):
        Cylinder(bore_diameter / 2, base_depth + 10,
                 rotation=(90, 0, 0),
                 align=(Align.CENTER, Align.CENTER, Align.CENTER),
                 mode=Mode.SUBTRACT)
    Checkpoint(part, "bore_hole").expect_volume_decreased().expect_solids(1).verify()

    # Step 5: 顶部安装孔 4x Φ6.5
    # 从俯视图：54 x 40 范围内，Y间距20mm
    # 假设 X 间距约 40mm（需要根据渲染调整）
    hole_x = 20  # 暂定
    hole_y = hole_spacing_y / 2  # 10mm

    hole_positions = [
        (hole_x, hole_y),
        (hole_x, -hole_y),
        (-hole_x, hole_y),
        (-hole_x, -hole_y),
    ]

    for x, y in hole_positions:
        with Locations((x, y, total_height)):
            Cylinder(hole_dia / 2, total_height,
                     align=(Align.CENTER, Align.CENTER, Align.MAX),
                     mode=Mode.SUBTRACT)
    Checkpoint(part, "mounting_holes").expect_volume_decreased().expect_solids(1).verify()

result = part.part
