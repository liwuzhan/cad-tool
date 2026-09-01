# P1 六角垫块
# 建模策略：六角草图挤出 → 中心通孔 → 顶部沉孔 → 极定位 3 通孔 → 顶面外缘倒角
# 尺寸来源：design.md

from build123d import *
from cad_cli.feedback import Checkpoint

Checkpoint.reset()

# === 参数（从 design.md 尺寸表） ===
across_flats = 40.0        # 六角对边距
hex_r = across_flats / 3**0.5   # 外接圆半径 23.094
height = 20.0              # 总高
center_hole_r = 5.25       # 中心通孔半径 (Ø10.5)
counterbore_r = 8.0        # 沉孔半径 (Ø16)
counterbore_depth = 5.0    # 沉孔深度
mount_hole_r = 3.25        # 安装孔半径 (Ø6.5)
bolt_circle_r = 15.0       # 分布圆半径
mount_hole_count = 3       # 安装孔数量
chamfer_size = 1.5         # 顶面外缘倒角

hex_area = (3**0.5 / 2) * across_flats**2   # 1385.64

# === 建模 ===
with BuildPart() as part:
    # 特征 1：六角基体
    with BuildSketch():
        RegularPolygon(radius=hex_r, side_count=6)
    extrude(amount=height)
    Checkpoint(part, "hex_body") \
        .expect_volume(hex_area * height, tolerance=50) \
        .expect_solids(1) \
        .expect_bbox_size(2 * hex_r, across_flats, height, tolerance=0.1) \
        .verify()

    # 特征 2：中心通孔
    Cylinder(center_hole_r, height + 2,
             align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
    Checkpoint(part, "center_hole") \
        .expect_volume_decreased().expect_solids(1).verify()

    # 特征 3：顶部沉孔
    with Locations((0, 0, height - counterbore_depth)):
        Cylinder(counterbore_r, counterbore_depth + 1,
                 align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
    Checkpoint(part, "counterbore") \
        .expect_volume_decreased().expect_solids(1).verify()

    # 特征 4：3× 极定位安装通孔
    with PolarLocations(radius=bolt_circle_r, count=mount_hole_count):
        Cylinder(mount_hole_r, height + 2,
                 align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
    Checkpoint(part, "mount_holes") \
        .expect_volume_decreased().expect_solids(1).verify()

    # 特征 5：顶面外缘倒角（仅六条直线边，避开孔缘圆弧）
    top_face = faces().sort_by(Axis.Z)[-1]
    outer_edges = top_face.edges().filter_by(GeomType.LINE)
    chamfer(outer_edges, length=chamfer_size)
    Checkpoint(part, "chamfer") \
        .expect_volume_decreased().expect_solids(1) \
        .expect_bbox_size(2 * hex_r, across_flats, height, tolerance=0.1) \
        .verify()

result = part.part
