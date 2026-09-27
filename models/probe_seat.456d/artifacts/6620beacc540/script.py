"""probe_seat 装配脚本：按 `ports.py` 的契约实现几何。

契约在前、实现在后。本文件**不重新声明轴颈尺寸**，而是 import 契约里的
`SPEC` / `DERIVED` 来建几何，所以换轴承型号时，轴颈、轴向链、轴肩位置一起跟随，
不会出现契约与几何各说各话。

轴承按声明好的接口 frame 定位（`seat_bearing_a` 的 origin），不从 STEP 或渲染图反推坐标。
"""

import importlib.util
import sys
from pathlib import Path

from build123d import Compound, Pos

from cad_cli.feedback import Checkpoint
from cadparts import deep_groove_bearing, stepped_shaft

Checkpoint.reset()

# === 读契约（唯一真源） ===
_package = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("_contract", _package / "ports.py")
_contract = importlib.util.module_from_spec(_spec)
sys.modules["_contract"] = _contract
_spec.loader.exec_module(_contract)

BEARING_CODE = _contract.BEARING_CODE
shaft_ports = _contract.PORTS["shaft"]
seat = next(item for item in shaft_ports if item["id"] == "seat_bearing_a")

# 契约推导出来的数字（用于 Checkpoint 断言，不在这里另立一个真源）
JOURNAL_DIAMETER = seat["dimensions_mm"]["diameter"]
JOURNAL_LENGTH = seat["dimensions_mm"]["length"]
SEAT_ORIGIN = seat["frame"]["origin_mm"]
SHOULDER_DIAMETER = _contract.SHOULDER_DIAMETER
SHOULDER_LENGTH = _contract.SHOULDER_LENGTH
TOTAL_LENGTH = _contract.DERIVED["total_length"]

# === 实测值（由 cad run 实测，见 design.md） ===
# 解析值 π/4·(32²·8 + 25²·32) = 22141.15、π/4·(62²−25²)·17 = 42979.68，
# OCC 回转/布尔的实际体积与此有 1e-3 量级偏差，以实测值为准。
SHAFT_VOLUME = 22141.945   # mm³
BEARING_VOLUME = 42979.344 # mm³
VOLUME_TOLERANCE = 0.1     # mm³

# === 几何 ===
shaft = stepped_shaft(_contract.SPEC)
shaft.label = "shaft"

bearing = deep_groove_bearing(BEARING_CODE)
bearing.label = f"bearing_{BEARING_CODE}"
# 用声明好的接口 frame 定位，不从装配后的形状反推
bearing = Pos(*SEAT_ORIGIN) * bearing

Checkpoint(shaft, "shaft") \
    .expect_solids(1) \
    .expect_volume(SHAFT_VOLUME, tolerance=VOLUME_TOLERANCE) \
    .expect_bbox_size(SHOULDER_DIAMETER, SHOULDER_DIAMETER, TOTAL_LENGTH, tolerance=0.01) \
    .verify(render=False)

Checkpoint(bearing, "bearing") \
    .expect_solids(1) \
    .expect_volume(BEARING_VOLUME, tolerance=VOLUME_TOLERANCE) \
    .expect_bbox_size(62.0, 62.0, 17.0, tolerance=0.01) \
    .verify(render=False)

assembly = Compound(children=[shaft, bearing], label="probe_seat")

Checkpoint(assembly, "assembly") \
    .expect_solids(2) \
    .expect_volume(SHAFT_VOLUME + BEARING_VOLUME, tolerance=VOLUME_TOLERANCE) \
    .expect_bbox_size(62.0, 62.0, TOTAL_LENGTH, tolerance=0.01) \
    .verify(render=False)

result = assembly

# 供人工核对：契约推导出来的关键数字（不是断言，只是打印）
print(f"journal: d={JOURNAL_DIAMETER} L={JOURNAL_LENGTH} @z={SEAT_ORIGIN[2]}")
print(f"shaft:   shoulder d={SHOULDER_DIAMETER} L={SHOULDER_LENGTH}, total={TOTAL_LENGTH}")
