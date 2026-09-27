"""接口尺寸的唯一来源 —— `ports.py` 与 `src/main.py` 都从这里取值。

修的是「声明与几何各自演化」这个成因，不只是那 0.1 mm 的结果：
只要 `BORE_DIAMETER` 只在这里定义一次，`ports.py` 就不可能再声明出一个
`main.py` 没建出来的直径。

几何侧参数与接口侧参数放在一起，是因为它们本来就是同一件事的两面：
轴径决定孔径，孔径就是接口。
"""

# === 配合 ===
SHAFT_OD = 9.5             # 配对轴径（名义）
FIT_CLEARANCE = 0.4        # 直径配合间隙（名义）
BORE_DIAMETER = SHAFT_OD + FIT_CLEARANCE   # 中心定位孔直径 = 9.9

# === 板 ===
PLATE_SIZE = 60.0          # 板边长
PLATE_THICKNESS = 8.0      # 板厚

# === 安装孔 ===
BOLT_HOLE_DIAMETER = 4.5   # 安装通孔直径
BOLT_HOLE_PITCH = 44.0     # 安装孔中心距

HALF_PITCH = BOLT_HOLE_PITCH / 2           # 孔位坐标 = ±22
BOLT_HOLE_CENTERS = (
    (HALF_PITCH, HALF_PITCH),
    (-HALF_PITCH, HALF_PITCH),
    (HALF_PITCH, -HALF_PITCH),
    (-HALF_PITCH, -HALF_PITCH),
)
