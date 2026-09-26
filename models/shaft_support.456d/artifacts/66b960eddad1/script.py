"""装配脚本：按 `ports.py` 里的契约实现几何。

关键关系是**方向**：契约（`ports.py`）在前，实现（本文件）在后。本文件不重新声明
轴颈尺寸，而是读契约来建几何——所以契约改了，几何必然跟着改，不会各说各话。

摆位也走声明好的接口：轴承装在轴颈接口的 frame 原点上，而不是从 STEP 反推坐标。
"""

import importlib.util
import sys
from pathlib import Path

from build123d import Compound, Pos

from cad_cli.feedback import Checkpoint
from cadparts import deep_groove_bearing, stepped_shaft

Checkpoint.reset()

# === 读契约（唯一真源，不在此重新声明轴颈尺寸） ===
_package = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("_contract", _package / "ports.py")
_contract = importlib.util.module_from_spec(_spec)
sys.modules["_contract"] = _contract
_spec.loader.exec_module(_contract)

BEARING_CODE = _contract.BEARING_CODE
shaft_ports = _contract.PORTS["shaft"]
seat = next(item for item in shaft_ports if item["id"] == "seat_support_a")

# === 参数（实测值 + 公差，见 design.md） ===
ASSEMBLY_VOLUME = 24289.22    # 轴 + 轴承单实体之和，由 cad run 实测
VOLUME_TOLERANCE = 1.0        # mm³

# === 几何 ===
shaft = stepped_shaft(_contract.SPEC)
shaft.label = "shaft"

bearing = deep_groove_bearing(BEARING_CODE)
bearing.label = f"bearing_{BEARING_CODE}"
# 用声明好的接口 frame 定位，不从装配后的形状反推
bearing = Pos(*seat["frame"]["origin_mm"]) * bearing

assembly = Compound(children=[shaft, bearing], label="shaft_support")

Checkpoint(assembly, "assembly") \
    .expect_solids(2) \
    .expect_volume(ASSEMBLY_VOLUME, tolerance=VOLUME_TOLERANCE) \
    .verify(render=False)

result = assembly
