"""probe_seat 的接口契约 —— 只做声明，**不要建模**。

`cad mates` 会执行本文件读 `PORTS`，但它不执行 `src/main.py`。判定必须能在几何存在
之前发生，所以这里只允许声明与推导（`shaft_dimensions` 这类返回字典的调用），
不允许出现 `stepped_shaft` 这种真正建实体的调用。

轴颈尺寸的唯一真源在这里：它由「哪个轴承装在这个位号上」推导，本文件与 `main.py`
都不出现 ⌀25 这个字面量。

`PORTS` 形状为 `{实例名: [接口, ...]}`，字段与 `cadparts.interfaces` 发射的一致。
"""

from cadparts import Free, Seat, ShaftSpec, shaft_dimensions
from cadparts.interfaces import resolve_interfaces

# === 库件位号 ===
# 轴的轴颈尺寸来源于这个型号的 `shaft_bore` 接口，不是字面量。
BEARING_CODE = "6305"

# === 无库件依据的段（只有这些段允许显式给尺寸）===
# 轴肩：给轴承内圈一个轴向定位面。轴承外形不定义内圈挡边直径（raceway 属 omitted），
# 所以这个台阶直径没有库件依据，只能用 Free 显式给出。
# 上限是轴承外径 ⌀62（碰到外圈就压死）与轴颈之间取一个保守台阶。
SHOULDER_DIAMETER = 32.0
SHOULDER_LENGTH = 8.0

# 轴伸端：轴承装在轴的中段而不是轴端，是常规布置；轴端与轴颈同径，直接沿用推导出的
# 轴颈直径，所以这里不引入新的直径字面量，只有长度是设计选择。
SHAFT_END_LENGTH = 15.0

# 轴颈直径的真源：向轴承接口问一次，供同径的轴伸端复用（不是为了绕过 Seat，
# Seat 仍是生成 seat 接口的那一处）。
_BORE_SEAT = Seat("bearing.deep_groove", {"code": BEARING_CODE}, "shaft_bore", role="bearing_a")
JOURNAL_DIAMETER = shaft_dimensions(ShaftSpec(stations=(_BORE_SEAT,)))["stations"][0]["diameter"]

SPEC = ShaftSpec(stations=(
    Free(SHOULDER_DIAMETER, SHOULDER_LENGTH, role="collar"),
    _BORE_SEAT,
    Free(JOURNAL_DIAMETER, SHAFT_END_LENGTH, role="shaft_end"),
))

# 推导结果（供 main.py 读，避免两处各写一份轴向链）
DERIVED = shaft_dimensions(SPEC)

PORTS = {
    "shaft": resolve_interfaces("shaft.stepped", {}, DERIVED),
}
