# 罐装可乐易拉罐（330ml 经典款）
# 建模策略：revolve 罐体（含底凹/肩部收口/顶盖内凹）+ extrude 拉环 + 铆钉凸起
# 尺寸来源：design.md

from build123d import *
from cad_cli.feedback import Checkpoint

Checkpoint.reset()

# === 参数（从 design.md 尺寸表） ===
can_radius = 33          # 罐体外半径（直径 66mm）
dome_apex_z = 8          # 底部内凹圆顶顶点高度
dome_flat_r = 4          # dome 顶部平顶半径（避免锥面在轴上收尖→非流形）
dome_edge_z = 2          # 罐底外沿接触面高度
z_taper_start = 92       # 肩部收口起始高度
z_neck_top = 114         # 罐口颈段顶部（顶盖边沿）
neck_radius = 27         # 罐口半径
lid_center_z = 113       # 顶盖内凹中央高度
lid_inner_r = 23         # 顶盖内凹斜面内边界半径

tab_z_base = 112.8       # 拉环底面（埋入顶盖 0.2mm 保证布尔合并）
tab_thickness = 1.5      # 拉环厚度
tab_outer_a, tab_outer_b = 9.0, 4.2    # 拉环外椭圆半轴
tab_inner_a, tab_inner_b = 6.4, 2.4    # 拉环内椭圆半轴
tab_center_y = -3.0      # 拉环中心 Y 偏移（后侧）
rivet_r = 1.7            # 铆钉片半径
rivet_y = 3.2            # 铆钉中心 Y 偏移（前侧）
rivet_peg_r = 1.36       # 铆钉凸起半径
rivet_peg_h = 1.2        # 铆钉凸起高度

# 罐体半边截面轮廓点（X=半径, Z=高度），Polygon 沿 Z 轴自动闭合
profile_pts = [
    (0, dome_apex_z),                    # dome 中心（轴上）
    (dome_flat_r, dome_apex_z),          # dome 平顶外沿（锥面离开旋转轴）
    (12, 3.6), (22, 2.4),                # dome 弧折线近似
    (can_radius, dome_edge_z),           # 罐底外沿
    (can_radius, z_taper_start),         # 直壁段
    (30, 98),                            # 肩部过渡点
    (neck_radius, 106),                  # 肩部收口终点
    (neck_radius, z_neck_top),           # 颈段顶部（顶盖边沿）
    (lid_inner_r, lid_center_z),         # 顶盖内凹斜面内界
    (0, lid_center_z),                   # 顶盖中央
]

# === 建模 ===
# 特征 1：罐体旋转体（360° revolve）
with BuildPart() as part:
    with BuildSketch(Plane.XZ) as profile:
        Polygon(profile_pts)
    revolve(axis=Axis.Z, revolution_arc=360)
    Checkpoint(part, "can_body") \
        .expect_solids(1) \
        .expect_bbox_size(can_radius*2, can_radius*2, z_neck_top - dome_edge_z, tolerance=1) \
        .expect_volume(360370, tolerance=300) \
        .verify()

    # 特征 2：拉环 + 铆钉片（extrude ADD，底面埋入顶盖 0.2mm）
    with BuildSketch(Plane.XY.offset(tab_z_base)):
        with Locations((0, tab_center_y)):
            Ellipse(tab_outer_a, tab_outer_b)
            Ellipse(tab_inner_a, tab_inner_b, mode=Mode.SUBTRACT)
        with Locations((0, rivet_y)):
            Circle(rivet_r)
    extrude(amount=tab_thickness)
    Checkpoint(part, "pull_tab") \
        .expect_volume_increased() \
        .expect_solids(1) \
        .verify()

    # 特征 3：铆钉凸起（小圆柱，埋入铆钉片 0.2mm）
    with Locations((0, rivet_y, tab_z_base + tab_thickness - 0.2)):
        Cylinder(rivet_peg_r, rivet_peg_h,
                 align=(Align.CENTER, Align.CENTER, Align.MIN))
    Checkpoint(part, "rivet_peg") \
        .expect_volume_increased() \
        .expect_solids(1) \
        .verify()

result = part.part
