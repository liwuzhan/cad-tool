# === 参数 ===
BASE_W = 60.0   # 基体 X 总尺寸 mm
BASE_D = 40.0   # 基体 Y 总尺寸 mm
BASE_H = 20.0   # 基体 Z 总尺寸 mm
HOLE_R = 8.0    # 通孔半径 mm
FILLET_R = 2.0  # 顶面棱边圆角 mm

from build123d import *
from cad_cli.feedback import Checkpoint

Checkpoint.reset()

with BuildPart() as part:
    # 特征 1：基体方块
    Box(BASE_W, BASE_D, BASE_H)
    Checkpoint(part, "base").expect_bbox_size(BASE_W, BASE_D, BASE_H, tolerance=0.5).expect_solids(1).verify()

    # 特征 2：中心通孔
    Cylinder(HOLE_R, BASE_H, mode=Mode.SUBTRACT)
    Checkpoint(part, "hole").expect_volume_decreased().expect_solids(1).verify()

    # 特征 3：顶面四条棱边圆角
    top_edges = part.edges().filter_by(Axis.Z).group_by(Axis.Z)[-1]
    fillet(top_edges, FILLET_R)
    Checkpoint(part, "fillet").expect_solids(1).verify()

result = part.part
