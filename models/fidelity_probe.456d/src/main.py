"""安装板：带一个中心定位孔和四个安装通孔。

中心孔按「轴径 + 配合间隙」算出来，参数在顶部。
"""

from build123d import Align, Box, BuildPart, Cylinder, Locations, Mode

# === 参数 ===
PLATE_SIZE = 60.0          # 板边长
PLATE_THICKNESS = 8.0      # 板厚
SHAFT_OD = 9.5             # 配对轴径
FIT_CLEARANCE = 0.4        # 配合间隙
BOLT_HOLE_DIAMETER = 4.5   # 安装通孔
BOLT_HOLE_PITCH = 44.0     # 安装孔中心距

BORE_DIAMETER = SHAFT_OD + FIT_CLEARANCE

half_pitch = BOLT_HOLE_PITCH / 2

with BuildPart() as part:
    Box(PLATE_SIZE, PLATE_SIZE, PLATE_THICKNESS)

    with Locations((0.0, 0.0, 0.0)):
        Cylinder(BORE_DIAMETER / 2, PLATE_THICKNESS, mode=Mode.SUBTRACT)

    with Locations(
        (half_pitch, half_pitch, 0.0),
        (-half_pitch, half_pitch, 0.0),
        (half_pitch, -half_pitch, 0.0),
        (-half_pitch, -half_pitch, 0.0),
    ):
        Cylinder(BOLT_HOLE_DIAMETER / 2, PLATE_THICKNESS, mode=Mode.SUBTRACT)

result = part.part
result.label = "mounting_plate"
