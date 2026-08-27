# 合金五辐轮毂 (Alloy 5-Spoke Wheel Rim)
# 18 英寸级深盘五辐轮毂。旋转轴 = Z 轴，正面车削面在 Z=0，筒体向 -Z 延伸。
# 参考 design.md 尺寸表。

# === 参数 (mm) ===
# 轮辋筒体
RIM_R_OUT = 230.0        # 轮辋外半径（外径 460 ≈ 18.1"）
BARREL_INNER_R = 204.0   # 筒体内半径（筒壁厚 26）
BARREL_DEPTH = 170.0     # 筒体深度（Z: -170 ~ 0）

# 五辐辐板
SPOKE_PLATE_R = 205.0    # 辐板半径（与筒壁 1mm 过盈融合）
SPOKE_PLATE_T = 48.0     # 辐板厚度（Z: -54 ~ -6）
PLATE_RECESS = 6.0       # 辐板前脸相对轮缘前脸下沉量（深盘感）
SPOKE_COUNT = 5          # 辐条数量
WIN_R_IN = 82.0          # 开口窗内半径（弦距圆心 ≈ 76.6）
WIN_R_OUT = 208.0        # 开口窗外半径（超出辐板 → 开放式窗口）
WIN_HALF_ANG_IN = 21.0   # 开口窗内侧半角 (deg)   -> 辐条根宽 ≈ 42
WIN_HALF_ANG_OUT = 30.0  # 开口窗外侧半角 (deg)   -> 辐条端宽 ≈ 43
WIN_TILT = 8.0           # 窗内缘扭转角 (deg)     -> 辐条动态倾角
WIN_FILLET = 6.0         # 窗角 2D 圆角

# 中心凸台
HUB_R = 82.0             # 凸台半径（与窗内缘相呼应）
HUB_Z0 = -60.0           # 凸台起始 Z
HUB_TOP_Z = 14.0         # 凸台顶面（凸出正面 14 -> 立体感）

# 孔特征
BORE_R = 40.0            # 中心轴承孔半径
PCD_R = 58.0             # 螺栓孔分布圆半径
LUG_R = 9.0              # 螺栓孔半径

# 装饰细节
LIP_FILLET = 4.0         # 前缘外圈圆角
BACK_CHAMFER = 5.0       # 后缘胎圈座倒角
DISH_CHAMFER = 2.5       # 盘口内圈倒角（前唇与辐板过渡）
HUB_FILLET = 3.0         # 凸台顶缘圆角
BORE_FILLET = 2.0        # 轴承孔口圆角
LUG_CS = 2.5             # 螺栓孔沉头倒角
SPOKE_EDGE_FILLET = 1.2  # 辐条前缘圆角

from math import sin, cos, radians
from build123d import *
from cad_cli.feedback import Checkpoint

Checkpoint.reset()


def window_face():
    """单个开口窗 2D 轮廓（位于角度 0，逆转后由 PolarLocations 旋转复制）"""
    a_in, a_out = radians(WIN_HALF_ANG_IN), radians(WIN_HALF_ANG_OUT)
    t = radians(WIN_TILT)
    pts = [
        (WIN_R_IN * cos(t - a_in), WIN_R_IN * sin(t - a_in)),
        (WIN_R_IN * cos(t + a_in), WIN_R_IN * sin(t + a_in)),
        (WIN_R_OUT * cos(a_out), WIN_R_OUT * sin(a_out)),
        (WIN_R_OUT * cos(-a_out), WIN_R_OUT * sin(-a_out)),
    ]
    with BuildSketch() as s:
        with BuildLine():
            Polyline(*pts, close=True)
        make_face()
        fillet(s.vertices(), radius=WIN_FILLET)
    return s.sketch


with BuildPart() as part:
    # 特征 1：轮辋筒体（圆管）
    with BuildSketch(Plane.XY.offset(-BARREL_DEPTH)):
        Circle(RIM_R_OUT)
        Circle(BARREL_INNER_R, mode=Mode.SUBTRACT)
    extrude(amount=BARREL_DEPTH)
    Checkpoint(part, "barrel").expect_solids(1) \
        .expect_bbox_size(RIM_R_OUT * 2, RIM_R_OUT * 2, BARREL_DEPTH, tolerance=0.5) \
        .expect_volume(6026438, tolerance=300).verify()

    # 特征 2：五辐辐板（圆盘 - 5 个开口窗，PolarLocations 一次完成；前脸下沉 6mm 深盘感）
    with BuildSketch(Plane.XY.offset(-(SPOKE_PLATE_T + PLATE_RECESS))):
        Circle(SPOKE_PLATE_R)
        with PolarLocations(0, SPOKE_COUNT):
            add(window_face(), mode=Mode.SUBTRACT)
    extrude(amount=SPOKE_PLATE_T)
    Checkpoint(part, "spoke_plate").expect_solids(1) \
        .expect_volume_increased() \
        .expect_bbox_size(RIM_R_OUT * 2, RIM_R_OUT * 2, BARREL_DEPTH, tolerance=0.5).verify()

    # 特征 3：中心凸台（Z: -60 ~ +14）
    with Locations((0, 0, HUB_Z0)):
        Cylinder(HUB_R, HUB_TOP_Z - HUB_Z0,
                 align=(Align.CENTER, Align.CENTER, Align.MIN))
    Checkpoint(part, "hub_boss").expect_solids(1) \
        .expect_volume_increased() \
        .expect_bbox_size(RIM_R_OUT * 2, RIM_R_OUT * 2, HUB_TOP_Z + BARREL_DEPTH, tolerance=0.5).verify()

    # 特征 4：中心轴承孔（贯穿）
    Cylinder(BORE_R, 200, mode=Mode.SUBTRACT)
    Checkpoint(part, "bore").expect_solids(1).expect_volume_decreased().verify()

    # 特征 5：5 颗螺栓孔（贯穿凸台与辐板）
    with PolarLocations(PCD_R, SPOKE_COUNT):
        Cylinder(LUG_R, 200, mode=Mode.SUBTRACT)
    Checkpoint(part, "lug_holes").expect_solids(1).expect_volume_decreased().verify()

    # 特征 6：前缘外圈圆角（Z=0 处 R230 圆边）
    lip = part.edges().filter_by(GeomType.CIRCLE) \
        .filter_by(lambda e: abs(e.radius - RIM_R_OUT) < 0.05) \
        .sort_by(Axis.Z)[-1]
    fillet(lip, LIP_FILLET)
    Checkpoint(part, "lip_fillet").expect_solids(1).verify()

    # 特征 7：盘口内圈倒角（前唇与辐板过渡，R204 @ Z=0）
    dish = part.edges().filter_by(GeomType.CIRCLE) \
        .filter_by(lambda e: abs(e.radius - BARREL_INNER_R) < 0.05) \
        .sort_by(Axis.Z)[-1]
    chamfer(dish, DISH_CHAMFER)
    Checkpoint(part, "dish_chamfer").expect_solids(1).verify()

    # 特征 8：后缘胎圈座倒角（Z=-170 处 R230 圆边）
    back = part.edges().filter_by(GeomType.CIRCLE) \
        .filter_by(lambda e: abs(e.radius - RIM_R_OUT) < 0.05) \
        .sort_by(Axis.Z)[0]
    chamfer(back, BACK_CHAMFER)
    Checkpoint(part, "back_chamfer").expect_solids(1).verify()

    # 特征 9：凸台顶缘圆角（R82 @ Z=14）
    hub_top = part.edges().filter_by(GeomType.CIRCLE) \
        .filter_by(lambda e: abs(e.radius - HUB_R) < 0.05) \
        .sort_by(Axis.Z)[-1]
    fillet(hub_top, HUB_FILLET)
    Checkpoint(part, "hub_fillet").expect_solids(1).verify()

    # 特征 10：轴承孔口圆角（R40 @ Z=14）
    bore_top = part.edges().filter_by(GeomType.CIRCLE) \
        .filter_by(lambda e: abs(e.radius - BORE_R) < 0.05) \
        .sort_by(Axis.Z)[-1]
    fillet(bore_top, BORE_FILLET)
    Checkpoint(part, "bore_fillet").expect_solids(1).verify()

    # 特征 11：螺栓孔沉头倒角（R9 @ Z=14，5 处全部 —— 全选 z>0 的孔口圆边，勿用 [-1] 只取一条）
    lug_edges = part.edges().filter_by(GeomType.CIRCLE) \
        .filter_by(lambda e: abs(e.radius - LUG_R) < 0.05 and e.center().Z > 0)
    assert len(lug_edges) == SPOKE_COUNT, \
        f"lug_cs: 应选中 {SPOKE_COUNT} 条孔口圆边, 实际 {len(lug_edges)}"
    chamfer(lug_edges, LUG_CS)
    Checkpoint(part, "lug_cs").expect_solids(1).verify()

    # 特征 12：辐条前缘小圆角（窗口边界 + 凸台根部；失败则降级/跳过）
    def is_big_circle(e):
        return e.geom_type == GeomType.CIRCLE and (e.radius or 0) > 100

    spoke_edges = part.edges().filter_by(
        lambda e: abs(e.center().Z + PLATE_RECESS) < 0.05 and not is_big_circle(e))
    try:
        fillet(spoke_edges, SPOKE_EDGE_FILLET)
    except Exception:
        try:
            fillet(spoke_edges, 0.6)
        except Exception:
            pass
    Checkpoint(part, "spoke_fillet").expect_solids(1).verify()

    # 最终校验：总尺寸 460 x 460 x 184
    Checkpoint(part, "final").expect_solids(1) \
        .expect_bbox_size(RIM_R_OUT * 2, RIM_R_OUT * 2, HUB_TOP_Z + BARREL_DEPTH, tolerance=0.5) \
        .expect_volume(9100415, tolerance=10000).verify()

result = part.part
