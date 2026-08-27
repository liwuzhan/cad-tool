"""
Example: Parametric Bracket
Creates a parametric mounting bracket
"""
from build123d import *

# Parameters
width = 80
height = 60
thickness = 10
hole_diameter = 8
fillet_radius = 5

# Create base plate
base = Box(width, height, thickness)

# Create mounting holes
hole1 = Cylinder(hole_diameter/2, thickness*2,
                 align=(Align.CENTER, Align.CENTER, Align.CENTER))
hole1 = hole1.translate((width/3, height/3, 0))

hole2 = Cylinder(hole_diameter/2, thickness*2,
                 align=(Align.CENTER, Align.CENTER, Align.CENTER))
hole2 = hole2.translate((-width/3, -height/3, 0))

# Subtract holes
bracket = base - hole1 - hole2

# Apply fillets (if supported)
try:
    result = bracket.fillet(fillet_radius, bracket.edges())
except:
    result = bracket
