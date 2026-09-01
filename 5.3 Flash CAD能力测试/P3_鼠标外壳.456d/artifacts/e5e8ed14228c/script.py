# P3 人体工学鼠标外壳
# 建模策略：椭圆截面放样 → offset 底面开口抽壳 → 前部滚轮椭圆槽贯穿
# 注：offset 抽壳的 BRep 体积积分失真（虚高约 20%，见 DOCS/问题记录.md），
#     故抽壳后特征仅断言 solids/bbox/faces；真实体积用 STL 网格离线复核。
# 尺寸来源：design.md

from build123d import *
from cad_cli.feedback import Checkpoint

Checkpoint.reset()

# === 参数（从 design.md 尺寸表） ===
wall_t = 1.8          # 壁厚
wheel_slot_x = 3.0    # 滚轮槽 X 半轴 (Ø6)
wheel_slot_y = 13.0   # 滚轮槽 Y 半轴 (长 26)
wheel_y = 22.0        # 滚轮槽中心（前端方向 +Y）
cutter_z_top = 40.0   # 切削起点（高于拱顶）
cutter_depth = 26.0   # 切削深度（穿透拱面）

# 外壳放样截面表：(z, 宽W, 长L) 椭圆截面
sections = [
    (0.0,  62.0, 115.0),
    (8.0,  63.0, 112.0),
    (18.0, 60.0, 100.0),
    (26.0, 52.0, 80.0),
    (32.0, 38.0, 54.0),
    (35.5, 16.0, 24.0),
]
max_w = max(s[1] for s in sections)   # 63
max_l = max(s[2] for s in sections)   # 115
max_h = max(s[0] for s in sections)   # 35.5

# === 建模 ===
with BuildPart() as part:
    # 特征 1：多截面放样拱背实体（普通放样体积积分可靠，保留体积断言）
    for z, w, l in sections:
        with BuildSketch(Plane.XY.offset(z)):
            Ellipse(w / 2, l / 2)
    loft()
    Checkpoint(part, "outer_loft") \
        .expect_solids(1) \
        .expect_bbox_size(max_w, max_l, max_h, tolerance=0.2) \
        .verify()

    # 特征 2：底面开口抽壳（体积积分失真，只断言 solids/bbox）
    offset(amount=-wall_t, openings=faces().sort_by(Axis.Z)[0])
    Checkpoint(part, "shell") \
        .expect_solids(1) \
        .expect_bbox_size(max_w, max_l, max_h, tolerance=0.2) \
        .expect_faces(5) \
        .verify()

    # 特征 3：滚轮槽（前部 y=22，竖直贯穿拱面；切后出现 3 条新边界面）
    with BuildSketch(Plane.XY.offset(cutter_z_top)):
        with Locations((0, wheel_y)):
            Ellipse(wheel_slot_x, wheel_slot_y)
    extrude(amount=-cutter_depth, mode=Mode.SUBTRACT)
    Checkpoint(part, "wheel_slot") \
        .expect_solids(1) \
        .expect_bbox_size(max_w, max_l, max_h, tolerance=0.2) \
        .expect_faces(6) \
        .verify()

result = part.part
