"""
Spindle Mount / 主轴夹持座
Version 5: 修正深度为 40mm（从俯视图标注）
"""
from build123d import *
from cad_cli.feedback import Checkpoint

Checkpoint.reset()

# === 参数（重新对照图纸） ===
# 俯视图：54(X) × 40(Y)
# 前视图：76(X) × 51.5(Z)，底座高 26
base_width = 76       # 底座宽度 (X)
depth = 40            # 整体深度 (Y) ← 修正：从 54 改为 40
base_height = 26      # 底座高度 (Z)

total_height = 51.5   # 总高度 (Z)
upper_width = 54      # 上部宽度 (X)

bore_diameter = 42    # 中心孔直径
bore_center_z = 42    # 中心孔圆心高度

hole_dia = 6.5        # 安装孔直径
hole_spacing_y = 20   # 安装孔 Y 方向间距

slot_width = 2        # 分割槽宽度（从前视图 "2" 标注）
slot_depth = 12       # 分割槽深度（从顶部向下到孔壁附近）

# === 建模 ===
with BuildPart() as part:
    # Step 1: 底座（76 × 40 × 26）
    Box(base_width, depth, base_height,
        align=(Align.CENTER, Align.CENTER, Align.MIN))
    Checkpoint(part, "base").expect_solids(1).verify()

    # Step 2: 上部块体（54 × 40 × 25.5）
    upper_height = total_height - base_height  # 25.5mm
    with Locations((0, 0, base_height)):
        Box(upper_width, depth, upper_height,
            align=(Align.CENTER, Align.CENTER, Align.MIN))
    Checkpoint(part, "upper_block").expect_solids(1).verify()

    # Step 3: 圆柱形顶部（形成圆弧外轮廓）
    outer_radius = upper_width / 2  # 27mm
    with Locations((0, 0, bore_center_z)):
        Cylinder(outer_radius, depth,
                 rotation=(90, 0, 0),
                 align=(Align.CENTER, Align.CENTER, Align.CENTER))
    Checkpoint(part, "with_arc_top").expect_solids(1).verify()

    # Step 4: 中心孔 Φ42（完全贯穿 Y 方向）
    with Locations((0, 0, bore_center_z)):
        Cylinder(bore_diameter / 2, depth + 10,
                 rotation=(90, 0, 0),
                 align=(Align.CENTER, Align.CENTER, Align.CENTER),
                 mode=Mode.SUBTRACT)
    Checkpoint(part, "bore_hole").expect_volume_decreased().expect_solids(1).verify()

    # Step 5: 顶部分割槽（沿 X 方向，宽度 2mm）
    # 槽从顶部向下切，穿透到中心孔附近
    with Locations((0, 0, total_height)):
        Box(upper_width + 10, slot_width, slot_depth,
            align=(Align.CENTER, Align.CENTER, Align.MAX),
            mode=Mode.SUBTRACT)
    Checkpoint(part, "top_slot").expect_volume_decreased().verify()

    # Step 6: 顶部安装孔 4x Φ6.5（完全贯穿 Z 方向）
    # 俯视图：Y 间距 20mm → ±10mm
    # X 间距：从俯视图看，孔在 54mm 宽度内偏两侧
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
