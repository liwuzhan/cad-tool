"""
Example: Box with Hole
Creates a box with a cylindrical hole through it
"""
from build123d import *

# Create base box
box = Box(100, 50, 20)

# Create cylinder for hole
cylinder = Cylinder(15, 30, align=(Align.CENTER, Align.CENTER, Align.CENTER))

# Subtract cylinder from box
result = box - cylinder
