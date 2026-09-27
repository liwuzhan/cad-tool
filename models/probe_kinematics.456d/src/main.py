"""MGN12 直线导轨 + 滑块 + 端部挡块：行程内干涉判定。

判据不是"看起来没碰上"，而是沿全行程刚性步进滑块、逐步做布尔求交：
  * (carriage & stop).volume  -> 干涉体积（共面接触 = 0，过盈 > 0）
  * carriage.distance_to(stop) -> 最近距离

导轨族数据、行程定义（travel = rail_length - block_length）与滑块实体几何
全部取自 cadparts，脚本里没有手填的导轨/滑块尺寸。
"""

import json
import sys

from build123d import Align, Box, Compound, Pos
from cadparts import linear_guide, linear_guide_dimensions
from cadparts.interfaces import resolve_interfaces
from cad_cli.feedback import Checkpoint

Checkpoint.reset()

# === 参数（选择器 + 非标挡块，单位 mm） ==============================
SERIES = "MGN"
SIZE = "12"
RAIL_LENGTH = 300.0        # cadparts: rail_length
BLOCK_POSITION = None      # cadparts: block_position=None -> 库把滑块居中

STOP_FACE_X = 0.0          # 挡块朝向滑块的面；0.0 = 与导轨起点端面(X=0)共面
STOP_THICKNESS = 8.0       # 挡块沿 -X 的厚度
STOP_SIDE_MARGIN = 3.0     # 挡块每侧比滑块宽出的量

SWEEP_SAMPLES = 121        # 全行程扫掠采样点数
SENSITIVITY_INSETS = (-2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 5.0, 10.0)

# === 从标准件库取真实数据 ==========================================
dims = linear_guide_dimensions(
    SERIES, SIZE, rail_length=RAIL_LENGTH, block_position=BLOCK_POSITION
)

RAIL_WIDTH = float(dims["rail_width"])
RAIL_HEIGHT = float(dims["rail_height"])
BLOCK_LENGTH = float(dims["block_length"])
BLOCK_WIDTH = float(dims["block_width"])
ASSEMBLY_HEIGHT = float(dims["assembly_height"])
BLOCK_POSITION_NOMINAL = float(dims["block_position"])
SWEEP_KEEPOUT = dims["keepout_envelopes"][0]

# 行程定义：直接用库自己 resolve 出来的 motion_axis.travel，不用我自己推的公式
interfaces = {item["id"]: item for item in resolve_interfaces("linear.guide.rail", {}, dims)}
LIBRARY_TRAVEL = float(interfaces["motion_axis"]["dimensions_mm"]["travel"])
CARRIAGE_TOP_ORIGIN_X = float(interfaces["carriage_top"]["frame"]["origin_mm"][0])

TRAVEL = LIBRARY_TRAVEL
CENTER_MIN = BLOCK_LENGTH / 2.0
CENTER_MAX = RAIL_LENGTH - BLOCK_LENGTH / 2.0

assert abs((CENTER_MAX - CENTER_MIN) - TRAVEL) < 1e-9, "travel 与中心区间不自洽"
assert abs(CARRIAGE_TOP_ORIGIN_X - BLOCK_POSITION_NOMINAL) < 1e-9, "carriage_top 与 block_position 不自洽"

STOP_HEIGHT = ASSEMBLY_HEIGHT + 5.0          # > 滑块顶面，才能真正挡住
STOP_WIDTH = BLOCK_WIDTH + 2.0 * STOP_SIDE_MARGIN

# === 标准件几何：导轨 + 滑块（都来自 cadparts） =====================
guide = linear_guide(
    SERIES, SIZE, rail_length=RAIL_LENGTH, block_position=BLOCK_POSITION
)


def _z_min(shape):
    return shape.bounding_box().min.Z


rail_shape, carriage_shape = sorted(guide.children, key=_z_min)
rail_shape.label = f"rail_{SERIES}{SIZE}_l{RAIL_LENGTH:g}"

Checkpoint(rail_shape, "rail_from_cadparts") \
    .expect_solids(1) \
    .expect_volume(27876.37, tolerance=1.0) \
    .verify(render=False)

Checkpoint(carriage_shape, "carriage_from_cadparts") \
    .expect_solids(1) \
    .expect_volume(BLOCK_LENGTH * BLOCK_WIDTH * (ASSEMBLY_HEIGHT - RAIL_HEIGHT),
                   tolerance=1.0) \
    .verify(render=False)

# === 非标件：固定在导轨 -X 端的挡块 =================================
def make_stop(face_x: float):
    """挡块：朝向滑块的面在 X=face_x，材料长在 X<face_x 一侧。"""
    body = Box(
        STOP_THICKNESS, STOP_WIDTH, STOP_HEIGHT,
        align=(Align.MIN, Align.CENTER, Align.MIN),
    )
    return Pos(face_x - STOP_THICKNESS, 0, 0) * body


stop = make_stop(STOP_FACE_X)
stop.label = "end_stop"

Checkpoint(stop, "end_stop") \
    .expect_solids(1) \
    .expect_volume(STOP_THICKNESS * STOP_WIDTH * STOP_HEIGHT, tolerance=1.0) \
    .expect_bbox_size(STOP_THICKNESS, STOP_WIDTH, STOP_HEIGHT, tolerance=1e-6) \
    .verify(render=False)


# === 滑块在任意行程位置的位姿 =======================================
def carriage_at(center_x: float):
    """把 cadparts 的滑块实体刚体平移到给定中心位置。"""
    return Pos(center_x - BLOCK_POSITION_NOMINAL, 0, 0) * carriage_shape


def overlap_volume(carriage, obstacle) -> float:
    """布尔求交体积：0 表示不碰（或仅共面接触）。"""
    common = carriage & obstacle
    return 0.0 if common is None else float(common.volume)


def clearance_X(carriage, obstacle) -> float:
    """沿 X 的实测余量 = 滑块 -X 面 - 挡块朝滑块的面（两个 bbox 面都实测）。

    正值 = 有间隙；0 = 共面接触；负值 = 过盈量。
    挡块永远长在面朝滑块那一侧的 -X 方向，所以取 bbox.max.X 才是它的工作面。
    """
    return (float(carriage.bounding_box().min.X)
            - float(obstacle.bounding_box().max.X))


# === 探测 1：全行程刚性扫掠（逐步布尔求交） =========================
def sweep(obstacle, samples: int = SWEEP_SAMPLES):
    worst_gap = float("inf")
    worst_gap_at = None
    worst_volume = 0.0
    worst_volume_at = None
    first_hit = None
    for index in range(samples):
        center = CENTER_MIN + TRAVEL * index / (samples - 1)
        carriage = carriage_at(center)
        gap = float(carriage.distance_to(obstacle))
        volume = overlap_volume(carriage, obstacle)
        if gap < worst_gap:
            worst_gap, worst_gap_at = gap, center
        if volume > worst_volume:
            worst_volume, worst_volume_at = volume, center
        if volume > 0.0 and first_hit is None:
            first_hit = center
    return {
        "min_gap_mm": worst_gap,
        "min_gap_at_center_mm": worst_gap_at,
        "max_interference_mm3": worst_volume,
        "max_interference_at_center_mm": worst_volume_at,
        "first_interference_center_mm": first_hit,
    }


baseline = sweep(stop)

# === 探测 1b：把实测扫掠域和库自带的 carriage_sweep keepout 对齐 =====
_bc_lo = carriage_at(CENTER_MIN).bounding_box()
_bc_hi = carriage_at(CENTER_MAX).bounding_box()
_ko_size = SWEEP_KEEPOUT["size_mm"]
_ko_ctr = SWEEP_KEEPOUT["frame"]["center_mm"]
swept_union = {
    "x_mm": [_bc_lo.min.X, _bc_hi.max.X],
    "y_mm": [_bc_lo.min.Y, _bc_lo.max.Y],
    "z_mm": [_bc_lo.min.Z, _bc_lo.max.Z],
}
library_keepout_box = {
    "x_mm": [_ko_ctr[0] - _ko_size[0] / 2, _ko_ctr[0] + _ko_size[0] / 2],
    "y_mm": [_ko_ctr[1] - _ko_size[1] / 2, _ko_ctr[1] + _ko_size[1] / 2],
    "z_mm": [_ko_ctr[2] - _ko_size[2] / 2, _ko_ctr[2] + _ko_size[2] / 2],
}
keepout_solid = Pos(*_ko_ctr) * Box(*_ko_size)
swept_union_x_matches_keepout = (
    abs(swept_union["x_mm"][0] - library_keepout_box["x_mm"][0]) < 1e-9
    and abs(swept_union["x_mm"][1] - library_keepout_box["x_mm"][1]) < 1e-9
)

# === 探测 2：参数扫描 —— 挡块面内缩/外移 s 时的首次接触点 ===========
def first_contact_center(obstacle, tol: float = 1e-4):
    """二分法测出'零干涉'的最大滑块中心（接触边界）。无接触返回 None。"""
    if overlap_volume(carriage_at(CENTER_MIN), obstacle) <= 0.0:
        return None
    lo, hi = CENTER_MIN, CENTER_MAX
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if overlap_volume(carriage_at(mid), obstacle) > 0.0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


sensitivity = []
for inset in SENSITIVITY_INSETS:
    probe_stop = make_stop(inset)
    carriage_xmin = carriage_at(CENTER_MIN)
    contact = first_contact_center(probe_stop)
    sensitivity.append({
        "stop_face_x_mm": inset,
        "interference_at_x_min_mm3": overlap_volume(carriage_xmin, probe_stop),
        "clearance_at_x_min_mm": clearance_X(carriage_xmin, probe_stop),
        "library_keepout_intersection_mm3": overlap_volume(probe_stop, keepout_solid),
        "first_contact_center_mm": contact,
        "stroke_before_contact_mm": None if contact is None else contact - CENTER_MIN,
    })

# === 探测 3：反证 —— 滑块越过行程极限后必须立刻产生过盈 =============
# 如果 -X 极限位真的是"共面接触"，那么越程 d 后的干涉体积必须恰好是
# d × 滑块宽 × 滑块高。测出来对得上，就说明 0 余量是几何事实而不是数值巧合。
OVERRUN_PROBES = (0.01, 0.1, 1.0)
overrun = []
for over in OVERRUN_PROBES:
    measured = overlap_volume(carriage_at(CENTER_MIN - over), stop)
    predicted = over * BLOCK_WIDTH * (ASSEMBLY_HEIGHT - RAIL_HEIGHT)
    overrun.append({
        "overrun_mm": over,
        "interference_measured_mm3": measured,
        "interference_predicted_mm3": predicted,
        "relative_error": abs(measured - predicted) / predicted,
    })

# === 探测 4：建议配置 —— 挡块不动，把行程 -X 限位往里收 =============
# 挡块面保持在 X=0（导轨端面，最自然的安装位），把命令行程的 -X 限位内缩
# RECOMMENDED_CLEARANCE，用行程换余量。余量同样实测，不靠加减法。
RECOMMENDED_CLEARANCE = 2.0
recommended_center_min = CENTER_MIN + RECOMMENDED_CLEARANCE
recommended_carriage = carriage_at(recommended_center_min)
recommendation = {
    "variant": "挡块面固定在 X=0，把命令行程 -X 限位内缩",
    "recommended_clearance_mm": RECOMMENDED_CLEARANCE,
    "recommended_center_min_mm": recommended_center_min,
    "recommended_center_max_mm": CENTER_MAX,
    "original_stroke_mm": TRAVEL,
    "recommended_usable_stroke_mm": CENTER_MAX - recommended_center_min,
    "lost_stroke_mm": TRAVEL - (CENTER_MAX - recommended_center_min),
    "measured_clearance_mm": clearance_X(recommended_carriage, stop),
    "measured_min_distance_mm": float(recommended_carriage.distance_to(stop)),
    "measured_interference_mm3": overlap_volume(recommended_carriage, stop),
}

# === 装配体：滑块摆在行程 -X 极限位（干涉判定的决定性位姿） =========
carriage_at_x_min = carriage_at(CENTER_MIN)
carriage_at_x_min.label = f"carriage_{SERIES}{SIZE}_x_min"

assembly = Compound(children=[rail_shape, carriage_at_x_min, stop])
assembly.label = "probe_kinematics"

Checkpoint(assembly, "assembly") \
    .expect_solids(3) \
    .expect_volume(27876.37 + BLOCK_LENGTH * BLOCK_WIDTH * (ASSEMBLY_HEIGHT - RAIL_HEIGHT)
                   + STOP_THICKNESS * STOP_WIDTH * STOP_HEIGHT, tolerance=2.0) \
    .expect_bbox_size(RAIL_LENGTH + STOP_THICKNESS, STOP_WIDTH, STOP_HEIGHT,
                      tolerance=1e-6) \
    .verify()

Checkpoint(carriage_at_x_min, "carriage_at_travel_x_min") \
    .expect_solids(1) \
    .expect_bbox_size(BLOCK_LENGTH, BLOCK_WIDTH, ASSEMBLY_HEIGHT - RAIL_HEIGHT,
                      tolerance=1e-6) \
    .verify(render=False)

report = {
    "source": "cadparts linear.guide.rail",
    "series": SERIES,
    "size": SIZE,
    "rail_length_mm": RAIL_LENGTH,
    "block_length_mm": BLOCK_LENGTH,
    "block_width_mm": BLOCK_WIDTH,
    "assembly_height_mm": ASSEMBLY_HEIGHT,
    "block_position_nominal_mm": BLOCK_POSITION_NOMINAL,
    "travel_mm": TRAVEL,
    "travel_source": "cadparts.interfaces.resolve_interfaces('linear.guide.rail')"
                     "['motion_axis'].dimensions_mm.travel",
    "travel_equals_rail_minus_block": abs(TRAVEL - (RAIL_LENGTH - BLOCK_LENGTH)) < 1e-9,
    "center_min_mm": CENTER_MIN,
    "center_max_mm": CENTER_MAX,
    "library_carriage_sweep_keepout": SWEEP_KEEPOUT,
    "stop_face_x_mm": STOP_FACE_X,
    "stop_height_mm": STOP_HEIGHT,
    "stop_width_mm": STOP_WIDTH,
    "clearance_at_travel_x_min_mm": clearance_X(carriage_at_x_min, stop),
    "swept_union_bbox_mm": swept_union,
    "library_keepout_bbox_mm": library_keepout_box,
    "swept_union_matches_keepout_in_x": swept_union_x_matches_keepout,
    "sweep": baseline,
    "overrun": overrun,
    "recommendation": recommendation,
    "sensitivity": sensitivity,
}
print("PROBE_JSON " + json.dumps(report, ensure_ascii=False), file=sys.stdout)

# 数字落到包里，避免只活在终端输出里
from pathlib import Path

report_path = Path(__file__).resolve().parent.parent / "runlog" / "probe_report.json"
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

result = assembly
