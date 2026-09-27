"""本包自建件的接口契约 —— 只做声明，不建模。

修好的探针包：`central_bore` 的声明不再是一个孤立字面量，而是从包根 `params.py`
推导出来，和 `src/main.py` 建几何时用的是同一个 `BORE_DIAMETER`。
声明与几何之间不存在「两处各自演化」的余地。

对照（修复前 → 修复后）：
    修复前  dimensions_mm.diameter = 10.0（字面量）   vs 几何 9.9  →  差 0.1
    修复后  dimensions_mm.diameter = BORE_DIAMETER = 9.5 + 0.4 = 9.9  = 几何
"""

import importlib.util
from pathlib import Path

# 唯一来源：<包根>/params.py。用显式路径加载，不依赖 sys.path，
# 因为 cad mates 是用 spec_from_file_location 执行本文件、不会把包根加进 path。
_spec = importlib.util.spec_from_file_location(
    "probe_params", Path(__file__).resolve().parent / "params.py"
)
_params = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_params)

SHAFT_OD = _params.SHAFT_OD
FIT_CLEARANCE = _params.FIT_CLEARANCE
BORE_DIAMETER = _params.BORE_DIAMETER
PLATE_SIZE = _params.PLATE_SIZE
PLATE_THICKNESS = _params.PLATE_THICKNESS
BOLT_HOLE_DIAMETER = _params.BOLT_HOLE_DIAMETER
BOLT_HOLE_CENTERS = _params.BOLT_HOLE_CENTERS

BORE_ROLE = f"中心定位孔，配 ⌀{SHAFT_OD:g} 轴，直径间隙 {FIT_CLEARANCE:g}"

PORTS = {
    "plate": [
        {
            "id": "central_bore",
            "type": "cylindrical_bore",
            "role": BORE_ROLE,
            "frame": {"origin_mm": [0.0, 0.0, 0.0], "axis": [0.0, 0.0, 1.0]},
            "dimensions_mm": {"diameter": BORE_DIAMETER, "length": PLATE_THICKNESS},
        },
        {
            "id": "mounting_face",
            "type": "planar_face",
            "role": "安装基准面",
            "frame": {
                "origin_mm": [0.0, 0.0, -PLATE_THICKNESS / 2],
                "axis": [0.0, 0.0, -1.0],
            },
            "dimensions_mm": {"face_size": PLATE_SIZE},
        },
        *[
            {
                "id": f"bolt_hole_{'p' if x > 0 else 'm'}x_{'p' if y > 0 else 'm'}y",
                "type": "clearance_hole",
                "role": "安装通孔",
                "frame": {"origin_mm": [x, y, 0.0], "axis": [0.0, 0.0, 1.0]},
                "dimensions_mm": {"diameter": BOLT_HOLE_DIAMETER},
            }
            for x, y in BOLT_HOLE_CENTERS
        ],
    ],
}
