"""Geometry calculation utilities"""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from build123d import Shape

from ..models import GeometryMetrics


def aggregate_volume(shape: "Shape") -> float:
    """Return the material volume of a part or multi-body assembly."""

    try:
        solids = list(shape.solids())
        if solids:
            return sum(float(solid.volume) for solid in solids)
    except Exception:
        pass
    return float(getattr(shape, "volume", 0.0))


def aggregate_area(shape: "Shape") -> float:
    """Return the summed surface area of every solid in an assembly."""

    try:
        solids = list(shape.solids())
        if solids:
            return sum(float(solid.area) for solid in solids)
    except Exception:
        pass
    return float(getattr(shape, "area", 0.0))


def export_step_safe(shape: "Shape", output_path: str | Path) -> None:
    """Export a shape to STEP with a Compound fallback.

    build123d 0.11.x has an upstream regression (gumyr/build123d#1356):
    a Shape/Solid read back by ``import_step()`` (or otherwise re-topologized)
    cannot be re-exported with ``export_step()``.  Wrapping it in a
    ``Compound(children=[shape])`` before exporting is a verified workaround.

    Raises the original export error if both attempts fail.
    """
    from build123d import Compound, export_step

    try:
        export_step(shape, str(output_path))
    except Exception as first_error:
        try:
            export_step(Compound(children=[shape]), str(output_path))
        except Exception:
            raise first_error


def compute_metrics(shape: "Shape") -> GeometryMetrics:
    """
    Compute geometry metrics for a shape

    Args:
        shape: build123d Shape object

    Returns:
        GeometryMetrics object with computed values
    """
    # Get bounding box
    bb = shape.bounding_box()
    bbox = (bb.min.X, bb.min.Y, bb.min.Z, bb.max.X, bb.max.Y, bb.max.Z)

    solids = list(shape.solids()) if hasattr(shape, "solids") else []

    # Count topology elements
    face_count = len(list(shape.faces()))
    edge_count = len(list(shape.edges()))
    vertex_count = len(list(shape.vertices()))

    return GeometryMetrics(
        volume=aggregate_volume(shape),
        area=aggregate_area(shape),
        bbox=bbox,
        face_count=face_count,
        edge_count=edge_count,
        vertex_count=vertex_count,
        solid_count=len(solids),
    )
