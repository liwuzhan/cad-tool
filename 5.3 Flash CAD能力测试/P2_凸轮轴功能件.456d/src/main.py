# P2 凸轮轴功能件
# 建模策略：摆线运动规律参数化凸轮廓线 → 挤出盘 → 轮毂 → 孔+键槽 → 减重孔 → 径向顶丝孔
# 尺寸来源：design.md

import math

from build123d import *
from cad_cli.feedback import Checkpoint

Checkpoint.reset()

# === 参数（从 design.md 尺寸表） ===
r_base = 18.0        # 基圆半径
lift = 14.0          # 升程 → 最大半径 32
angle_rise = 150.0   # 升程角
angle_dwell = 50.0   # 远休角
angle_return = 110.0 # 回程角
plate_t = 12.0       # 凸轮盘厚 z 0..12
hub_r = 13.0         # 轮毂半径
hub_z0, hub_z1 = -10.0, 22.0   # 轮毂轴向范围
bore_r = 4.0         # Ø8 贯穿孔
key_w = 3.4          # 键槽宽（键 3 + 间隙）
key_depth = 1.3      # 键槽孔壁深（DIN 6885 t2）
lhole_r = 3.5        # 减重孔半径 (Ø7)
lhole_bc = 11.5      # 减重孔分布圆（保证 reach 15 < 各向最小轮缘半径 ~18）
lhole_n = 4          # 减重孔数
setscrew_r = 2.6     # 顶丝孔半径 (Ø5.2)
setscrew_z = 6.0     # 顶丝孔轴向位置
profile_step_deg = 2.0  # 轮廓采样步距


def cam_radius(theta_deg: float) -> float:
    """摆线运动规律凸轮半径：升-远休-回-近休。"""
    t = theta_deg % 360.0
    if t <= angle_rise:                       # 升程
        u = t / angle_rise
        return r_base + lift * (u - math.sin(2 * math.pi * u) / (2 * math.pi))
    t -= angle_rise
    if t <= angle_dwell:                      # 远休
        return r_base + lift
    t -= angle_dwell
    if t <= angle_return:                     # 回程
        u = t / angle_return
        return r_base + lift * (1 - (u - math.sin(2 * math.pi * u) / (2 * math.pi)))
    return r_base                             # 近休


# 轮廓采样点（X=半径方向 cos, Y=sin）
profile_pts = [
    (
        cam_radius(a) * math.cos(math.radians(a)),
        cam_radius(a) * math.sin(math.radians(a)),
    )
    for a in [i * profile_step_deg for i in range(int(360 / profile_step_deg))]
]

cam_max_r = r_base + lift
cam_total_height = hub_z1 - hub_z0
# 期望 bbox 由轮廓采样点直接推出（凸轮鼻朝向休止段，非对称）
exp_x = max(p[0] for p in profile_pts) - min(p[0] for p in profile_pts)
exp_y = max(p[1] for p in profile_pts) - min(p[1] for p in profile_pts)

# === 建模 ===
with BuildPart() as part:
    # 特征 1：凸轮盘（参数化轮廓挤出）
    with BuildSketch():
        Polygon(profile_pts)
    extrude(amount=plate_t)
    Checkpoint(part, "cam_plate") \
        .expect_solids(1) \
        .expect_bbox_size(exp_x, exp_y, plate_t, tolerance=0.2) \
        .verify()

    # 特征 2：轮毂（与盘融合）
    with BuildSketch(Plane.XY.offset(hub_z0)):
        Circle(hub_r)
    extrude(amount=cam_total_height)
    Checkpoint(part, "hub") \
        .expect_volume_increased().expect_solids(1) \
        .expect_bbox_size(exp_x, exp_y, cam_total_height, tolerance=0.2) \
        .verify()

    # 特征 3：贯穿孔 + 键槽（+Y，DIN 6885）
    with BuildSketch() as cut:
        Circle(bore_r)
        with Locations((0, bore_r + key_depth / 2)):
            Rectangle(key_w, key_depth)
    extrude(cut.sketch, amount=cam_total_height, mode=Mode.SUBTRACT)
    Checkpoint(part, "bore_keyway") \
        .expect_volume_decreased().expect_solids(1).verify()

    # 特征 4：4× 减重孔（分布圆在轮毂之外，只穿盘）
    with PolarLocations(radius=lhole_bc, count=lhole_n, start_angle=45):
        Cylinder(lhole_r, plate_t + 2,
                 align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
    Checkpoint(part, "lightening_holes") \
        .expect_volume_decreased().expect_solids(1).verify()

    # 特征 5：径向顶丝孔（-Y 侧，z=6；旋转后 +Z → -Y）
    with Locations(Pos(0, 0, setscrew_z) * Rotation(90, 0, 0)):
        Cylinder(setscrew_r, hub_r,
                 align=(Align.CENTER, Align.CENTER, Align.MIN),
                 mode=Mode.SUBTRACT)
    Checkpoint(part, "setscrew") \
        .expect_volume_decreased().expect_solids(1) \
        .expect_bbox_size(exp_x, exp_y, cam_total_height, tolerance=0.2) \
        .verify()

result = part.part
