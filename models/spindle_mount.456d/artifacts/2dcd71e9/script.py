"""
Spindle Mount / 主轴夹持座
Version 4: 修正底座台阶高度为 26mm
"""
from build123d import *
from cad_cli.feedback import Checkpoint

Checkpoint.reset()

# === 参数 ===
base_width = 76       # 底座宽度 (X)
base_depth = 54       # 底座深度 (Y)
base_height = 26      # 底座高度（台阶位置）

total_height = 51.5   # 总高度
upper_width = 54      # 上部宽度

bore_diameter = 42    # 中心孔直径
bore_center_z = 42    # 中心孔圆心高度

hole_dia = 6.5        # 安装孔直径
hole_spacing_y = 20   # 安装孔 Y 方向间距

slot_width = 3        # 分割槽宽度（Y方向）
slot_depth = 15       # 分割槽深度

# === 建模 ===
with BuildPart() as part:
    # Step 1: 底座（76 × 54 × 26）
    Box(base_width, base_depth, base_height,
        align=(Align.CENTER, Align.CENTER, Align.MIN))
    Checkpoint(part, "base").expect_solids(1).verify()

    # Step 2: 上部块体（54 × 54 × 25.5）
    upper_height = total_height - base_height  # 25.5mm
    with Locations((0, 0, base_height)):
        Box(upper_width, base_depth, upper_height,
            align=(Align.CENTER, Align.CENTER, Align.MIN))
    Checkpoint(part, "upper_block").expect_solids(1).verify()

    # Step 3: 圆柱形顶部（形成圆弧外轮廓）
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

    # Step 5: 顶部分割槽
    with Locations((0, 0, total_height)):
        Box(upper_width + 10, slot_width, slot_depth,
            align=(Align.CENTER, Align.CENTER, Align.MAX),
            mode=Mode.SUBTRACT)
    Checkpoint(part, "top_slot").expect_volume_decreased().verify()

    # Step 6: 顶部安装孔 4x Φ6.5
    # 从图纸俯视图分析，孔位于上部 54×54 区域
    # Y 方向：±10mm（总间距 20mm）
    # X 方向：估计 ±19mm
    hole_x = 19
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
    Checkpoint(part, "mounting_holes").expect_volume_decreased().verify()

result = part.part
