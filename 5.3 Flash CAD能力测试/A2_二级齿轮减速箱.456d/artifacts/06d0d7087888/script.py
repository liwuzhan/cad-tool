# A2 二级齿轮减速箱（装配，26 实例）
# 布局：三轴沿 X；I(y15,z100) -45-> M(y60,z100) -52.5-> O(y60,z47.5)，module=1.5
# 非标：箱体/盖板/3 轴；cadparts：4 齿轮 + 6 轴承 + 4 平键 + 7 螺栓
# 尺寸来源：design.md

from build123d import *
from cad_cli.feedback import Checkpoint
from cadparts import instantiate

Checkpoint.reset()

# === 参数 ===
MODULE = 1.5
AXIS_I = (15.0, 100.0)    # (y, z) 输入轴
AXIS_M = (60.0, 100.0)    # 中间轴
AXIS_O = (60.0, 47.5)     # 输出轴
A1 = MODULE * (17 + 43) / 2   # 45
A2 = MODULE * (19 + 51) / 2   # 52.5
assert abs((AXIS_M[0] - AXIS_I[0]) - A1) < 1e-9
assert abs((AXIS_M[1] - AXIS_O[1]) - A2) < 1e-9

# 箱体
box_x0, box_x1 = -15.0, 140.0   # 外廓 X（轴承墙厚 15）
box_y0, box_y1 = -10.0, 110.0
box_z0, box_z1 = -10.0, 135.0
wall_side = 10.0                # 前后/左右非轴承墙厚
cav_x0, cav_x1 = 0.0, 125.0     # 内腔
cav_y0, cav_y1 = 0.0, 100.0
cav_z0, cav_z1 = 0.0, 135.0
foot_sz, foot_h = 28.0, 10.0    # 地脚
foot_hole_r = 4.5               # Ø9
drain_r, drain_hole_r = 9.0, 5.0
drain_pos = (62.0, 45.0)
rim_hole_r, rim_hole_depth = 2.5, 8.0
# 轴承
BEARINGS = {  # 轴 -> (code, 外圈半径)
    "I": ("6202", 17.5),
    "M": ("6203", 20.0),
    "O": ("6204", 23.5),
}
wall_bcx = [box_x0 + 7.5, box_x1 - 12.5]   # 轴承在墙内的放置起点 x（-13 / 127）
# 轴
shaft_len0, shaft_len1 = -10.0, 145.0      # 输入/中间轴 X 范围
shaft_out_x1 = 185.0                       # 输出轴前端伸长
KEY_DEPTH = 3.0                            # 轴键槽切深（占位）
# 齿轮
GEARS = [
    # label, teeth, bore, x0(低端面), 轴, 相位角(半齿距)
    ("gear_z17_pinion", 17, 15.0, 35.0, "I", 0.0),
    ("gear_z43_wheel", 43, 17.0, 35.0, "M", 180.0 / 43),
    ("gear_z19_pinion", 19, 17.0, 62.0, "M", 0.0),
    ("gear_z51_wheel", 51, 20.0, 62.0, "O", 180.0 / 51),
]
GEAR_W = 15.0
# 键
KEYS = [
    ("key_input", 5.0, 5.0, 20.0, "I", 34.0),
    ("key_inter_stage1", 5.0, 5.0, 20.0, "M", 34.0),
    ("key_inter_stage2", 5.0, 5.0, 20.0, "M", 71.0),
    ("key_output", 6.0, 6.0, 25.0, "O", 71.0),
]
# 盖板螺栓
cover_bolt_xy = [(10, -5), (62, -5), (115, -5), (10, 105), (62, 105), (115, 105)]
cover_t = 8.0

AXES = {"I": AXIS_I, "M": AXIS_M, "O": AXIS_O}
SHAFT_R = {"I": 7.5, "M": 8.5, "O": 10.0}

# === 非标件 1：箱体 ===
with BuildPart() as housing_bp:
    # 外廓
    with BuildSketch(Plane.XY.offset(box_z0)):
        with Locations(((box_x0 + box_x1) / 2, (box_y0 + box_y1) / 2)):
            Rectangle(box_x1 - box_x0, box_y1 - box_y0)
    extrude(amount=box_z1 - box_z0)
    # 内腔（顶部开放）
    with BuildSketch(Plane.XY.offset(cav_z0)):
        with Locations(((cav_x0 + cav_x1) / 2, (cav_y0 + cav_y1) / 2)):
            Rectangle(cav_x1 - cav_x0, cav_y1 - cav_y0)
    extrude(amount=box_z1 - cav_z0 + 10, mode=Mode.SUBTRACT)
    Checkpoint(housing_bp, "cavity") \
        .expect_solids(1) \
        .expect_bbox_size(box_x1 - box_x0, box_y1 - box_y0, box_z1 - box_z0, tolerance=0.2) \
        .verify()

    # 6× 轴承孔（贯穿前后墙）
    for key in ("I", "M", "O"):
        y, z = AXES[key]
        bore_r = BEARINGS[key][1]
        for wx in (box_x0, box_x1):
            with Locations(Pos(wx, y, z) * Rotation(0, 90, 0)):
                Cylinder(bore_r, 17,
                         align=(Align.CENTER, Align.CENTER, Align.MIN),
                         mode=Mode.SUBTRACT)
    Checkpoint(housing_bp, "bearing_bores") \
        .expect_solids(1).verify()

    # 4× 地脚 + 地脚孔
    for fx in (box_x0, box_x1 - foot_sz):
        for fy in (box_y0, box_y1 - foot_sz):
            with Locations((fx + foot_sz / 2, fy + foot_sz / 2, box_z0 - foot_h / 2)):
                Box(foot_sz, foot_sz, foot_h)
    for fx in (box_x0, box_x1 - foot_sz):
        for fy in (box_y0, box_y1 - foot_sz):
            with Locations((fx + foot_sz / 2, fy + foot_sz / 2, box_z0 - foot_h - 1)):
                Cylinder(foot_hole_r, foot_h + 2,
                         align=(Align.CENTER, Align.CENTER, Align.MIN),
                         mode=Mode.SUBTRACT)
    # 放油口凸台 + 孔
    with Locations((drain_pos[0], drain_pos[1], box_z0 - 6)):
        Cylinder(drain_r, 6, align=(Align.CENTER, Align.CENTER, Align.MIN))
    with Locations((drain_pos[0], drain_pos[1], box_z0 - 7)):
        Cylinder(drain_hole_r, 8, align=(Align.CENTER, Align.CENTER, Align.MIN),
                 mode=Mode.SUBTRACT)
    # 盖板螺栓 rim 盲孔 6×
    for bx, by in cover_bolt_xy:
        with Locations((bx, by, box_z1 - rim_hole_depth)):
            Cylinder(rim_hole_r, rim_hole_depth + 1,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)
    Checkpoint(housing_bp, "housing_features") \
        .expect_solids(1) \
        .expect_bbox_size(box_x1 - box_x0, box_y1 - box_y0,
                          box_z1 - box_z0 + foot_h, tolerance=0.2) \
        .verify()

housing = housing_bp.part
housing.label = "housing"
components = [housing]

# === 非标件 2：盖板 ===
with BuildPart() as cover_bp:
    with BuildSketch(Plane.XY.offset(box_z1)):
        with Locations(((box_x0 + box_x1) / 2, (box_y0 + box_y1) / 2)):
            Rectangle(box_x1 - box_x0, box_y1 - box_y0)
    extrude(amount=cover_t)
    for bx, by in cover_bolt_xy:
        with Locations((bx, by, box_z1)):
            Cylinder(3.3, cover_t + 2,
                     align=(Align.CENTER, Align.CENTER, Align.MIN),
                     mode=Mode.SUBTRACT)
    Checkpoint(cover_bp, "top_cover") \
        .expect_solids(1) \
        .expect_bbox_size(box_x1 - box_x0, box_y1 - box_y0, cover_t, tolerance=0.2) \
        .verify()
cover = cover_bp.part
cover.label = "top_cover"
components.append(cover)

# === 非标件 3-5：轴（含键槽）===
def build_shaft(label, axis_key, x0, x1, key_x0, key_l):
    y, z = AXES[axis_key]
    r = SHAFT_R[axis_key]
    with BuildPart() as sb:
        with Locations(Pos(x0, y, z) * Rotation(0, 90, 0)):
            Cylinder(r, x1 - x0, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # 键槽：轴顶切槽（占位）
        with Locations((key_x0, y, z + r - KEY_DEPTH)):
            Box(key_l, 5.6 if r < 10 else 6.6, KEY_DEPTH + 1,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
                mode=Mode.SUBTRACT)
        Checkpoint(sb, label) \
            .expect_solids(1) \
            .expect_bbox_size(x1 - x0, 2 * r, 2 * r, tolerance=0.2) \
            .verify()
        part = sb.part
    part.label = label
    return part

components.append(build_shaft("shaft_input", "I", shaft_len0, shaft_len1, 34.0, 20.0))
components.append(build_shaft("shaft_intermediate", "M", shaft_len0, shaft_len1, 34.0, 20.0))
components.append(build_shaft("shaft_output", "O", shaft_len0, shaft_out_x1, 71.0, 25.0))

# === cadparts：齿轮（绕 X 轴放置 + 半齿距相位）===
for label, teeth, bore, gx, axis_key, phase in GEARS:
    inst = instantiate("gear.spur", module=MODULE, teeth=teeth, bore=bore, width=GEAR_W)
    y, z = AXES[axis_key]
    shape = Pos(gx, y, z) * Rot(0, 90, 0) * Rot(0, 0, phase) * inst.shape
    shape.label = label
    components.append(shape)

# === cadparts：轴承（墙内，轴 +X 放置）===
for axis_key, (code, _) in BEARINGS.items():
    y, z = AXES[axis_key]
    for side, wx in zip(("in", "out"), wall_bcx):
        inst = instantiate(code)
        shape = Pos(wx, y, z) * Rot(0, 90, 0) * inst.shape
        shape.label = f"bearing_{code}_{axis_key}_{side}"
        components.append(shape)

# === cadparts：平键（轴顶键槽内）===
for label, kw, kh, kl, axis_key, kx in KEYS:
    y, z = AXES[axis_key]
    r = SHAFT_R[axis_key]
    inst = instantiate("key.parallel", width=kw, height=kh, length=kl, end_type="A")
    shape = Pos(kx, y, z + r - kh / 2) * inst.shape
    shape.label = label
    components.append(shape)

# === cadparts：盖板螺栓 M6×30（头朝上，螺杆向下）===
for i, (bx, by) in enumerate(cover_bolt_xy):
    inst = instantiate("fastener.hex_bolt_metric", size="M6", length=30)
    shape = Pos(bx, by, box_z1 + cover_t + 5.5) * Rot(180, 0, 0) * inst.shape
    shape.label = f"cover_bolt_m6_{i + 1}"
    components.append(shape)

# === cadparts：放油塞 M12×16（头在凸台下方，螺杆向上与箱底平齐）===
inst = instantiate("fastener.hex_bolt_metric", size="M12", length=16)
shape = Pos(drain_pos[0], drain_pos[1], box_z0 - foot_h) * inst.shape
shape.label = "drain_plug_m12"
components.append(shape)

# === 装配 ===
assembly = Compound(children=components)
assembly.label = "gearbox_assembly"
exp_x = shaft_out_x1 - box_x0      # 200
exp_y = box_y1 - box_y0            # 120
exp_z = (box_z1 + cover_t + 5.5) - (box_z0 - foot_h)   # 148.5+20 = 168.5
# Y 实测 121.6：M6 螺栓头对角 ±5.8 超出箱侧 0.8（板边正常悬出）
Checkpoint(assembly, "layout") \
    .expect_solids(26) \
    .expect_bbox_size(exp_x, 121.6, exp_z, tolerance=0.6) \
    .verify()

result = assembly
