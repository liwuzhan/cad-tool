"""本包自建零件的接口契约 —— 只做声明，**不要建模**。

`cad mates` 会执行本文件来读 PORTS，但它不执行 `src/main.py`。这个分工是刻意的：
接口图必须在几何存在之前就能被判定，否则检查就只能发生在它本该守住的那一步之后。
所以这里只允许出现声明与推导（`derive` / `shaft_dimensions` 这类返回字典的调用），
不允许出现 `stepped_shaft` 这种真正建实体的调用。

`PORTS` 的形状是 `{实例名: [接口, ...]}`，接口字段与 `cadparts.interfaces` 发射的
完全一致，所以库件与自建件在这里没有区别。
"""

from cadparts import Seat, ShaftSpec, shaft_dimensions
from cadparts.interfaces import resolve_interfaces

# 轴颈尺寸由「哪个轴承装在这里」决定，不是字面量。
# 注意：这一行与 manifest.json 的 deps[0].std.params.code 是**同一件事的两份声明**，
# 两者必须一起改；cad mates 只能发现轴孔直径层面的漂移（见 design.md「明确不做」）。
BEARING_CODE = "6305"

SPEC = ShaftSpec(stations=(
    Seat("bearing.deep_groove", {"code": BEARING_CODE}, "shaft_bore", role="support_a"),
))

PORTS = {
    "shaft": resolve_interfaces("shaft.stepped", {}, shaft_dimensions(SPEC)),
}
