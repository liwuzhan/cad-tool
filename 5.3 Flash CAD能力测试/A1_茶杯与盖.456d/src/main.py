# A1 茶杯与盖（装配）
# 杯体：锥度旋转体 + 三点弧扫掠把手；盖：盖裙+穹顶旋转体 + 球钮
# 装配：盖 Pos(0,0,86)，盖裙 Ø73 插入杯嘴内径 Ø74（间隙 0.5）
# 尺寸来源：design.md

from build123d import *
from cad_cli.feedback import Checkpoint

Checkpoint.reset()

# === 参数 ===
# 杯体
cup_r_bottom = 28.0     # 底部外半径（Ø56）
cup_r_top = 40.0        # 嘴部外半径（Ø80）
cup_h = 90.0            # 杯高
wall_t = 3.0            # 壁厚
bottom_t = 4.0          # 底厚
handle_r = 3.5          # 把手杆半径（Ø7）
handle_arc = [(cup_r_top - 1, 0, 45), (cup_r_top + 13, 0, 56), (cup_r_top - 1, 0, 67)]
# 盖子
lid_skirt_r = 36.5      # 盖裙半径（Ø73，配杯嘴内径 Ø74）
lid_skirt_h = 8.0       # 盖裙高
dome_top_r = 12.0       # 穹顶收口半径
dome_top_z = 20.0       # 穹顶收口高度（局部）
knob_r = 5.5            # 珠钮半径
knob_cz = 24.0          # 珠钮球心高度（局部）
lid_insert_z = 86.0     # 盖装配位姿 z（插入杯嘴 4mm）

# === 杯体 ===
with BuildPart() as cup:
    # 锥度杯壁旋转体（含内腔，截面沿轴线闭合）
    with BuildSketch(Plane.XZ) as profile:
        Polygon([
            (0, 0),
            (cup_r_bottom, 0),
            (cup_r_top, cup_h - 2),
            (cup_r_top, cup_h),
            (cup_r_top - wall_t, cup_h),
            (cup_r_top - wall_t - 1, bottom_t + 2),
            (cup_r_bottom + 1, bottom_t),
            (0, bottom_t),
        ])
    revolve(axis=Axis.Z, revolution_arc=360)
    Checkpoint(cup, "cup_shell") \
        .expect_solids(1) \
        .expect_bbox_size(2 * cup_r_top, 2 * cup_r_top, cup_h, tolerance=0.3) \
        .verify()

    # 把手：弧线路径 + 圆截面扫掠（两端嵌入杯壁）
    with BuildLine() as path:
        ThreePointArc(*handle_arc)
    with BuildSketch(Plane.XY.offset(handle_arc[0][2])):
        with Locations((handle_arc[0][0], 0)):
            Circle(handle_r)
    sweep()
    # 把手在 XZ 面内鼓出：X 到弧顶+杆半径 ≈ 54.3，Y 仍由杯身 Ø80 决定
    Checkpoint(cup, "cup_with_handle") \
        .expect_volume_increased().expect_solids(1) \
        .expect_bbox_size(94.5, 2 * cup_r_top, cup_h, tolerance=1.2) \
        .verify()

cup_body = cup.part
cup_body.label = "cup_body"

# === 盖子（局部坐标，z0 = 盖裙底面）===
with BuildPart() as lid_bp:
    with BuildSketch(Plane.XZ) as lid_profile:
        Polygon([
            (0, 0),
            (lid_skirt_r, 0),
            (lid_skirt_r, lid_skirt_h),
            (24, 14),
            (dome_top_r, dome_top_z),
            (0, dome_top_z),
        ])
    revolve(axis=Axis.Z, revolution_arc=360)
    # 珠钮（与穹顶收口融合）
    with Locations((0, 0, knob_cz)):
        Sphere(knob_r)
    Checkpoint(lid_bp, "lid") \
        .expect_solids(1) \
        .expect_bbox_size(2 * lid_skirt_r, 2 * lid_skirt_r, knob_cz + knob_r, tolerance=0.3) \
        .verify()

lid_shape = Pos(0, 0, lid_insert_z) * lid_bp.part
lid_shape.label = "lid"

# === 装配 ===
assembly = Compound(children=[cup_body, lid_shape])
assembly.label = "cup_with_lid"
exp_total_h = lid_insert_z + knob_cz + knob_r
Checkpoint(assembly, "layout") \
    .expect_solids(2) \
    .expect_bbox_size(94.5, 2 * cup_r_top, exp_total_h, tolerance=1.2) \
    .verify()

result = assembly
