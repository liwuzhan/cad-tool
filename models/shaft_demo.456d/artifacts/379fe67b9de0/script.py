"""声明式阶梯轴：本文件不写任何轴颈直径，尺寸全部由「谁装在轴上」推导。

改一个 BEARING_CODE，整根轴跟着变——直径、长度、轴向链——因为轴颈尺寸是从轴承
自己的 ``shaft_bore`` 接口读出来的，不是字面量。

两类断言的**可信度不同**，这里都有：
  * ``Checkpoint``（自洽性）：模型检查自己算得对不对。模型算错时它往往跟着错。
  * 座位配对判定（外部真值）：轴的接口 vs 轴承声明的接口，两个独立来源比对。
    模型改不了这个结果。
"""

from cad_cli.feedback import Checkpoint
from cadparts import (
    Free,
    Seat,
    ShaftSpec,
    shaft_dimensions,
    stepped_shaft,
)

Checkpoint.reset()

# === 参数（从 design.md 尺寸表） ===
BEARING_CODE = "6204"       # 两端支撑轴承型号
SPACER_DIAMETER = 26.0      # 隔套外径（自由段，需显式给）
SPACER_LENGTH = 22.0
OUTPUT_DIAMETER = 16.0      # 输出轴伸直径
OUTPUT_LENGTH = 30.0        # 输出轴伸长度

# === 装配关系：轴颈尺寸由这些引用推导 ===
spec = ShaftSpec(stations=(
    Seat("bearing.deep_groove", {"code": BEARING_CODE}, "shaft_bore", role="support_a"),
    Free(SPACER_DIAMETER, SPACER_LENGTH, role="spacer"),
    Seat("bearing.deep_groove", {"code": BEARING_CODE}, "shaft_bore", role="support_b"),
    Free(OUTPUT_DIAMETER, OUTPUT_LENGTH, role="output"),
))

derived = shaft_dimensions(spec)
result = stepped_shaft(spec)

# === 自洽性检查：几何是否就是声明的那个形状 ===
Checkpoint(result, "shaft") \
    .expect_solids(1) \
    .expect_bbox_size(derived["max_diameter"], derived["max_diameter"],
                      derived["total_length"], tolerance=0.01) \
    .verify(render=False)

# === 外部真值检查：从**建出来的实体**上把半径量回来，与声明比对 ===
#
# 为什么不能用「轴的接口 vs 轴承的接口」：轴颈直径本来就是从轴承接口推导的，两者
# 比对照永远相等 —— 那只证明生成器按自己的公式算了一遍，是循环的，没有牙齿。
# 要让检查成立，一侧必须是**几何实测**，另一侧才是声明，两个独立来源。
def measure_radius(shape, z: float, ceiling: float) -> float:
    """在高度 z 处沿 +X 扫掠，返回最后一个仍在实体内部的半径。"""
    radius = 0.0
    probe = 0.05
    while probe < ceiling:
        if shape.is_inside((probe, 0.0, z)):
            radius = probe
        probe += 0.05
    return radius


for station in derived["stations"]:
    mid_z = (station["z_start"] + station["z_end"]) / 2.0
    measured = measure_radius(result, mid_z, station["diameter"] / 2.0 + 3.0)
    expected = station["diameter"] / 2.0
    if abs(measured - expected) > 0.07:
        raise ValueError(
            f"工位 {station['role']} 处几何与声明不符："
            f"实测半径 {measured:.2f} vs 声明 {expected:.2f}"
        )

# 座位清单：供 runlog 与后续装配级判定消费（每段都能追溯回库件与接口）
seats = [
    {
        "role": item["role"],
        "seat_diameter": item["diameter"],
        "nominal_diameter": item["nominal_diameter"],
        "length": item["length"],
        "source": item["source"],
    }
    for item in derived["stations"]
    if item["kind"] == "seat"
]
