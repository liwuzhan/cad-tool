"""安装板：带一个中心定位孔和四个安装通孔。

中心孔按「轴径 + 配合间隙」算出来。所有尺寸取自包根 `params.py` —— 与 `ports.py`
共用同一来源，因此「声明一个直径、建出另一个直径」的漂移不再可能发生。
"""

import importlib.util
import math
from pathlib import Path

from build123d import Box, BuildPart, Cylinder, Locations, Mode
from cad_cli.feedback import Checkpoint

# === 参数（唯一来源：<包根>/params.py）===
_spec = importlib.util.spec_from_file_location(
    "probe_params", Path(__file__).resolve().parents[1] / "params.py"
)
params = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(params)

PLATE_SIZE = params.PLATE_SIZE
PLATE_THICKNESS = params.PLATE_THICKNESS
SHAFT_OD = params.SHAFT_OD
FIT_CLEARANCE = params.FIT_CLEARANCE
BORE_DIAMETER = params.BORE_DIAMETER
BOLT_HOLE_DIAMETER = params.BOLT_HOLE_DIAMETER
BOLT_HOLE_CENTERS = params.BOLT_HOLE_CENTERS


def _expected_volume_after_bore() -> float:
    """闭解：板 − 中心孔（四个安装孔尚未挖）。"""
    return (
        PLATE_SIZE * PLATE_SIZE * PLATE_THICKNESS
        - math.pi * (BORE_DIAMETER / 2) ** 2 * PLATE_THICKNESS
    )


def _expected_volume_final() -> float:
    """闭解：板 − 中心孔 − 四个安装孔。"""
    return _expected_volume_after_bore() - 4 * math.pi * (
        BOLT_HOLE_DIAMETER / 2
    ) ** 2 * PLATE_THICKNESS


Checkpoint.reset()

with BuildPart() as part:
    Box(PLATE_SIZE, PLATE_SIZE, PLATE_THICKNESS)
    Checkpoint(part, "blank").expect_volume(
        PLATE_SIZE * PLATE_SIZE * PLATE_THICKNESS, tolerance=1e-9
    ).expect_solids(1).expect_bbox_size(
        PLATE_SIZE, PLATE_SIZE, PLATE_THICKNESS, tolerance=1e-9
    ).verify(render=False)

    with Locations((0.0, 0.0, 0.0)):
        Cylinder(BORE_DIAMETER / 2, PLATE_THICKNESS, mode=Mode.SUBTRACT)
    Checkpoint(part, "central_bore").expect_volume(
        _expected_volume_after_bore(), tolerance=1e-6
    ).expect_solids(1).verify(render=False)

    with Locations(*[(x, y, 0.0) for x, y in BOLT_HOLE_CENTERS]):
        Cylinder(BOLT_HOLE_DIAMETER / 2, PLATE_THICKNESS, mode=Mode.SUBTRACT)
    Checkpoint(part, "bolt_holes").expect_volume(
        _expected_volume_final(), tolerance=1e-6
    ).expect_solids(1).expect_face_type_count(
        "cylindrical", 5
    ).verify(render=False)

result = part.part
result.label = "mounting_plate"
