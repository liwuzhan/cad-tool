"""Camera views for rendering"""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class CameraView:
    """Camera view definition"""
    name: str
    position: Tuple[float, float, float]
    focal_point: Tuple[float, float, float]
    view_up: Tuple[float, float, float]
    orthographic: bool = True  # iso keeps perspective; others use orthographic


# Standard orthographic and isometric views
STANDARD_VIEWS = {
    "top": CameraView(
        name="top",
        position=(0, 0, 100),
        focal_point=(0, 0, 0),
        view_up=(0, 1, 0)
    ),
    "bottom": CameraView(
        name="bottom",
        position=(0, 0, -100),
        focal_point=(0, 0, 0),
        view_up=(0, 1, 0)
    ),
    "front": CameraView(
        name="front",
        position=(0, -100, 0),
        focal_point=(0, 0, 0),
        view_up=(0, 0, 1)
    ),
    "back": CameraView(
        name="back",
        position=(0, 100, 0),
        focal_point=(0, 0, 0),
        view_up=(0, 0, 1)
    ),
    "left": CameraView(
        name="left",
        position=(-100, 0, 0),
        focal_point=(0, 0, 0),
        view_up=(0, 0, 1)
    ),
    "right": CameraView(
        name="right",
        position=(100, 0, 0),
        focal_point=(0, 0, 0),
        view_up=(0, 0, 1)
    ),
    "iso": CameraView(
        name="iso",
        position=(50, -50, 50),
        focal_point=(0, 0, 0),
        view_up=(0, 0, 1),
        orthographic=False  # 45° isometric keeps perspective; others are orthographic
    ),
}
