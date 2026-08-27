"""
Correct Spur Gear - Best Practice

IMPORTANT: This demonstrates the correct way to create parametric features
with boolean operations in build123d.

Common Mistake:
    In BuildPart context, extrude() defaults to mode=ADD, which automatically
    adds geometry to the part. Combined with Cylinder's default center alignment
    and extrude's default Z=0 start, this can cause geometry misalignment.

Correct Approach:
    1. Create 2D profile with all features (cuts included)
    2. Extrude once to create 3D part
    OR
    3. Use consistent alignment for all operations
"""
from build123d import *

# Parameters
num_teeth = 20
module = 3
thickness = 10
bore_radius = 7.5

# Calculated
pitch_radius = num_teeth * module / 2
outer_radius = pitch_radius + module
tooth_angle = 360 / num_teeth
tooth_width = module * 1.5
tooth_depth = module * 2.2

# CORRECT METHOD: Create 2D profile first, then extrude once
with BuildSketch() as gear_profile:
    # Outer circle
    Circle(outer_radius)

    # Cut tooth valleys using polar pattern
    # All cuts happen in 2D - no alignment issues
    with PolarLocations(outer_radius - tooth_depth/2, num_teeth, start_angle=tooth_angle/2):
        Rectangle(tooth_depth, tooth_width, mode=Mode.SUBTRACT)

    # Center bore
    Circle(bore_radius, mode=Mode.SUBTRACT)

# Single extrusion from completed 2D profile
with BuildPart() as gear:
    extrude(gear_profile.sketch, amount=thickness)

result = gear.part
