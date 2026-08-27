from build123d import Align, Box, BuildPart, Compound, Cylinder, Mode, Pos
from cadparts import instantiate

# === Assembly parameters (mm) ===
housing_x = 90
housing_y = 70
housing_z = 20
bearing_code = "6204"
bearing_z = 3
shaft_diameter = 20
shaft_length = 60
shaft_z = -20

# Spend modeling attention on the non-standard housing.
with BuildPart() as housing_builder:
    Box(
        housing_x,
        housing_y,
        housing_z,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    )
    Cylinder(
        47 / 2,
        housing_z,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
        mode=Mode.SUBTRACT,
    )
housing = housing_builder.part
housing.label = "custom_housing"

# Reuse catalog geometry and keep the purchasing selection in code.
bearing = instantiate(
    bearing_code,
    selections={"closure": "2RS", "clearance": "normal"},
)
bearing_shape = Pos(0, 0, bearing_z) * bearing.shape
bearing_shape.label = "bearing_6204_2RS"

shaft = Pos(0, 0, shaft_z) * Cylinder(
    shaft_diameter / 2,
    shaft_length,
    align=(Align.CENTER, Align.CENTER, Align.MIN),
)
shaft.label = "custom_shaft"

# Assembly components stay separate so their labels survive into STEP.
assembly = Compound(children=[housing, bearing_shape, shaft])
assembly.label = "bearing_block_assembly"

result = assembly
