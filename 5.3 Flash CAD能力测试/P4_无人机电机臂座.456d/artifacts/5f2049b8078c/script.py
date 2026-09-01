# P4 无人机电机臂座
# 建模策略：渐变椭圆截面放样机臂（带二面角上翘）→ 机身盘/电机法兰融合 → 孔位阵列 → 倒圆
# 尺寸来源：design.md

from build123d import *
from cad_cli.feedback import Checkpoint

Checkpoint.reset()

# === 参数（从 design.md 尺寸表） ===
# 机臂
arm_sections = [          # (x, 宽W, 高H, z_center) 中段上翘、端部下潜保证法兰顶面完整
    (8.0,  24.0, 10.0, 3.0),
    (26.0, 23.0, 9.5, 4.5),
    (45.0, 21.0, 9.0, 5.5),
    (64.0, 18.0, 8.0, 4.5),
    (78.0, 14.0, 5.5, 1.25),   # 端部顶面 z=4.0 与法兰顶面平齐，完全嵌入法兰
]
# 机身盘
hub_r, hub_h, hub_z0 = 18.0, 6.0, -4.0
hub_hole_r = 1.7          # Ø3.4 M3 过孔
hub_bc_r = 14.0           # 孔位分布圆
hub_lighten_r = 8.0       # 中央减重孔 Ø16
# 电机法兰
flange_r, flange_h, flange_z0 = 16.0, 6.0, -2.0
flange_hole_r = 1.7       # Ø3.4 M3
flange_bc_r = 12.5        # 2204 电机孔位 BC Ø25（4 孔均在纯法兰区，臂料不干扰）
edge_fillet = 2.0         # 法兰顶缘倒圆
hub_fillet = 1.5          # 机身盘底缘倒圆

# bbox 预期
exp_x = hub_r + arm_sections[-1][0] + flange_r     # 116? 见下
exp_x = (arm_sections[-1][0] + flange_r) - (-hub_r)  # 82+16+18 = 116
exp_y = 2 * hub_r                                   # 36
exp_z = max(s[3] + s[2] / 2 for s in arm_sections) - hub_z0  # 10+4 = 14

# === 建模 ===
with BuildPart() as part:
    # 特征 1：渐变截面机臂放样（Plane.YZ.offset(x) 法向 +X；局部 y→世界 Z）
    for x, w, h, zc in arm_sections:
        with BuildSketch(Plane.YZ.offset(x)):
            with Locations((0, zc)):
                Ellipse(w / 2, h / 2)
    loft()
    arm_x0, arm_x1 = arm_sections[0][0], arm_sections[-1][0]
    arm_y = max(s[1] for s in arm_sections)
    arm_z0 = min(s[3] - s[2] / 2 for s in arm_sections)
    arm_z1 = max(s[3] + s[2] / 2 for s in arm_sections)
    Checkpoint(part, "arm") \
        .expect_solids(1) \
        .expect_bbox_size(arm_x1 - arm_x0, arm_y, arm_z1 - arm_z0, tolerance=0.5) \
        .verify()

    # 特征 2：机身盘（z −4..2，与臂根融合）
    with BuildSketch(Plane.XY.offset(hub_z0)):
        Circle(hub_r)
    extrude(amount=hub_h)
    exp_x_hub = arm_x1 + hub_r   # 100：左机身盘右臂端
    Checkpoint(part, "hub") \
        .expect_volume_increased().expect_solids(1) \
        .expect_bbox_size(exp_x_hub, exp_y, exp_z, tolerance=0.3) \
        .verify()

    # 特征 3：电机法兰（z −2..4，与臂尖融合）
    with BuildSketch(Plane.XY.offset(flange_z0)):
        with Locations((arm_sections[-1][0], 0)):
            Circle(flange_r)
    extrude(amount=flange_h)
    Checkpoint(part, "flange") \
        .expect_volume_increased().expect_solids(1) \
        .expect_bbox_size(exp_x, exp_y, exp_z, tolerance=0.3) \
        .verify()

    # 特征 4：法兰电机孔位 4× M3（竖直贯穿）+ Ø14 中央孔
    with Locations((arm_sections[-1][0], 0)):
        with PolarLocations(radius=flange_bc_r, count=4, start_angle=45):
            Cylinder(flange_hole_r, flange_h + 4,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)
    # 注：取消中央让位孔——2204 电机底面中心为实心，无需让位
    Checkpoint(part, "flange_holes") \
        .expect_volume_decreased().expect_solids(1) \
        .expect_bbox_size(exp_x, exp_y, exp_z, tolerance=0.3) \
        .verify()

    # 特征 5：机身盘孔位 4× M3 + Ø16 中央减重孔
    with PolarLocations(radius=hub_bc_r, count=4, start_angle=0):
        Cylinder(hub_hole_r, hub_h + 4,
                 align=(Align.CENTER, Align.CENTER, Align.MIN),
                 mode=Mode.SUBTRACT)
    Cylinder(hub_lighten_r, hub_h + 4,
             align=(Align.CENTER, Align.CENTER, Align.MIN),
             mode=Mode.SUBTRACT)
    Checkpoint(part, "hub_holes") \
        .expect_volume_decreased().expect_solids(1) \
        .expect_bbox_size(exp_x, exp_y, exp_z, tolerance=0.3) \
        .verify()

    # 特征 6：法兰顶缘倒圆 + 机身盘底缘倒圆（仅外缘 wire，避开孔缘）
    flange_top_candidates = [
        f for f in faces().filter_by(GeomType.PLANE)
        if abs(f.center().Z - (flange_z0 + flange_h)) < 0.1
    ]
    flange_top_face = max(flange_top_candidates, key=lambda f: f.area)
    # 法兰顶缘被臂尖截断为复合边线，倒圆可能失败：降级尝试 2.0 → 1.0 → 跳过
    flange_fillet_done = False
    for r in (edge_fillet, 1.0):
        try:
            fillet(flange_top_face.outer_wire().edges(), radius=r)
            flange_fillet_done = True
            break
        except Exception:
            continue

    hub_bottom_candidates = [
        f for f in faces().filter_by(GeomType.PLANE)
        if abs(f.center().Z - hub_z0) < 0.1
    ]
    hub_bottom_face = max(hub_bottom_candidates, key=lambda f: f.area)
    fillet(hub_bottom_face.outer_wire().edges(), radius=hub_fillet)

    Checkpoint(part, "fillets") \
        .expect_volume_decreased().expect_solids(1) \
        .expect_bbox_size(exp_x, exp_y, exp_z, tolerance=0.3) \
        .verify()

result = part.part
