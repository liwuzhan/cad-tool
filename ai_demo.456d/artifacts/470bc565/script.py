import sys
from pathlib import Path
sys.path.append(str(Path(r"c:\Users\liwuz\Desktop\test\cad tools\src")))

from build123d import *
from cad_cli.feedback import Checkpoint

# Dimensions
total_width = 76
total_height = 51.5
depth = 40
center_height = 26
bore_dia = 42
wing_height = 12
hump_width = 46  # Estimated
chamfer_start_height = 42
hole_spacing_x = 54
hole_spacing_y = 20
hole_dia = 6.5
slit_width = 2

with BuildPart() as part:
    # 1. Main Body Extrusion
    with BuildSketch(Plane.XZ) as profile:
        with BuildLine():
            # Start from bottom center (0,0)
            l1 = Line((0, 0), (total_width/2, 0))
            l2 = Line(l1 @ 1, (total_width/2, wing_height))
            l3 = Line(l2 @ 1, (hump_width/2, wing_height))
            l4 = Line(l3 @ 1, (hump_width/2, chamfer_start_height))
            l5 = Line(l4 @ 1, (13.5, total_height)) # 13.5 is roughly calculated top width half
            l6 = Line(l5 @ 1, (0, total_height))
            mirror(about=Plane.YZ)
        make_face()
    
    extrude(amount=depth/2, both=True) # Extrude symmetric Y
    
    # 2. Bore
    with Locations((0, 0, center_height)):
        Cylinder(radius=bore_dia/2, height=depth, rotation=(90, 0, 0), mode=Mode.SUBTRACT)

    # 3. Mounting Holes
    # Correcting orientation confusion:
    # Sketch on XZ. Extrude Y = Depth (40)
    # Holes are vertical (along Z axis).
    with Locations([(x, y) for x in [-27, 27] for y in [-10, 10]]):
        Cylinder(radius=hole_dia/2, height=total_height*2, align=(Align.CENTER, Align.CENTER, Align.CENTER), mode=Mode.SUBTRACT)

    # 4. Slit
    # Slit is on the Left side (X < 0).
    with Locations((-total_width/2, 0, center_height)):
        Box(total_width/2, depth, slit_width, align=(Align.MIN, Align.CENTER, Align.CENTER), mode=Mode.SUBTRACT)

    # 5. Bottom Relief
    with Locations((0, 0, 0)):
        Box(20, depth, 2, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

    # 6. Checkpoints
    # Bbox check: (-38, -20, 0) to (38, 20, 51.5)
    Checkpoint(part, "bbox").expect_bbox_within(
        (-38.1, 38.1), (-20.1, 20.1), (-0.1, 51.6)
    ).verify()
    
    Checkpoint(part, "volume").expect_volume(
        104000, tolerance=10000 
    ).verify(raise_on_fail=False)

result = part.part
