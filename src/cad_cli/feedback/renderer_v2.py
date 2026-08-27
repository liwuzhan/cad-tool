"""Offscreen renderer v2 - with JSON metadata output"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Tuple, Any, Optional

if TYPE_CHECKING:
    from build123d import Shape

from ..package import ModelPackage
from .camera import CameraView


_ASSEMBLY_COLORS = (
    "#d9e6f2",
    "#f2d9b5",
    "#cfe8cf",
    "#e5d4ef",
    "#f2caca",
    "#d6e5e3",
    "#eee1a8",
    "#d7d7d7",
)

_MATPLOTLIB_VIEWS = {
    "iso": (25, -45),
    "front": (0, -90),
    "back": (0, 90),
    "right": (0, 0),
    "left": (0, 180),
    "top": (90, -90),
    "bottom": (-90, -90),
}


def use_matplotlib_backend() -> bool:
    """Select a process-safe renderer before VTK can touch a missing display."""

    requested = os.environ.get("CAD_RENDER_BACKEND", "auto").strip().lower()
    if requested == "matplotlib":
        return True
    if requested == "pyvista":
        return False
    return sys.platform.startswith("linux") and not (
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    )


def render_shape_matplotlib(
    shape: "Shape",
    view: CameraView,
    output_png: Path,
    *,
    resolution: Tuple[int, int] = (800, 600),
) -> dict[str, Any]:
    """Render each assembly solid separately so Compound meshes stay readable."""

    try:
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib import pyplot as plt
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    except ImportError as exc:
        raise ImportError("matplotlib is required for headless CAD rendering") from exc

    solids = list(shape.solids()) if hasattr(shape, "solids") else []
    renderables = solids or [shape]
    assembly_alpha = 0.78 if len(renderables) > 1 else 1.0
    width, height = resolution
    dpi = 120
    figure = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    axis = figure.add_subplot(111, projection="3d")

    for index, solid in enumerate(renderables):
        vertices, triangles = solid.tessellate(0.08)
        if not vertices or not triangles:
            continue
        points = [(point.X, point.Y, point.Z) for point in vertices]
        faces = [[points[vertex_index] for vertex_index in triangle] for triangle in triangles]
        axis.add_collection3d(Poly3DCollection(
            faces,
            facecolor=_ASSEMBLY_COLORS[index % len(_ASSEMBLY_COLORS)],
            edgecolor="none",
            linewidth=0,
            alpha=assembly_alpha,
        ))
        for edge in solid.edges():
            try:
                samples = [edge.position_at(step / 24) for step in range(25)]
            except Exception:
                try:
                    samples = [vertex.center() for vertex in edge.vertices()]
                except Exception:
                    continue
            if len(samples) < 2:
                continue
            axis.plot(
                [point.X for point in samples],
                [point.Y for point in samples],
                [point.Z for point in samples],
                color="#263238",
                linewidth=0.9,
            )

    bbox = shape.bounding_box()
    bounds = (
        (bbox.min.X, bbox.max.X),
        (bbox.min.Y, bbox.max.Y),
        (bbox.min.Z, bbox.max.Z),
    )
    centers = [(low + high) / 2 for low, high in bounds]
    span = max(high - low for low, high in bounds) or 1.0
    radius = span * 0.58
    axis.set_xlim(centers[0] - radius, centers[0] + radius)
    axis.set_ylim(centers[1] - radius, centers[1] + radius)
    axis.set_zlim(centers[2] - radius, centers[2] + radius)
    axis.set_box_aspect((1, 1, 1))
    axis.set_proj_type("ortho" if view.orthographic else "persp")
    elevation, azimuth = _MATPLOTLIB_VIEWS.get(view.name, _MATPLOTLIB_VIEWS["iso"])
    axis.view_init(elev=elevation, azim=azimuth)
    axis.set_axis_off()
    axis.set_title(f"{getattr(shape, 'label', 'model')} · {view.name}", fontsize=10)

    output_png.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_png, bbox_inches="tight", pad_inches=0.08, facecolor="white")
    plt.close(figure)
    return {
        "backend": "matplotlib",
        "position": list(view.position),
        "focal_point": list(view.focal_point),
        "view_up": list(view.view_up),
    }


class OffscreenRendererV2:
    """
    Offscreen renderer for generating technical drawings (pen style)

    v2 enhancement: Outputs JSON metadata alongside PNG
    """

    def __init__(self, package: ModelPackage):
        """
        Initialize renderer

        Args:
            package: ModelPackage instance
        """
        self.package = package
        manifest = package.get_manifest()
        self.resolution: Tuple[int, int] = tuple(manifest.render.get("resolution", [800, 600]))

    def render(
        self,
        shape: "Shape",
        view: CameraView,
        output_png: Path,
        output_json: Optional[Path] = None,
    ) -> dict[str, Any]:
        """
        Render shape to image file using pen/line drawing style

        v2: Also outputs JSON metadata with camera params and timestamp

        Args:
            shape: Shape to render
            view: Camera view
            output_png: Output PNG path
            output_json: Output JSON path (optional, auto-generated if None)

        Returns:
            Metadata dictionary

        Raises:
            ImportError: If pyvista is not available
            Exception: If rendering fails
        """
        if use_matplotlib_backend():
            camera = render_shape_matplotlib(
                shape,
                view,
                output_png,
                resolution=self.resolution,
            )
            metadata = {
                "view": view.name,
                "camera": camera,
                "resolution": list(self.resolution),
                "timestamp": datetime.now().isoformat(),
                "png_path": str(output_png),
                "backend": "matplotlib",
            }
            if output_json is None:
                output_json = output_png.with_suffix('.json')
            output_json.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            metadata["json_path"] = str(output_json)
            return metadata

        try:
            import pyvista as pv
        except ImportError:
            raise ImportError("pyvista is required for rendering. Install with: pip install pyvista")

        # Ensure output directory exists
        output_png.parent.mkdir(parents=True, exist_ok=True)

        # Convert shape to VTK polydata using STL as intermediate
        import tempfile
        from build123d import export_stl

        with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            export_stl(shape, str(tmp_path))
            poly_data = pv.read(str(tmp_path))
        finally:
            tmp_path.unlink(missing_ok=True)

        # Verify we got valid mesh data
        if poly_data.n_points == 0:
            raise Exception("Generated mesh has no points - shape may be invalid")

        # Create offscreen plotter with white background
        plotter = pv.Plotter(off_screen=True, window_size=self.resolution)
        plotter.set_background('white')

        # Orthographic projection for technical views (top/front/right/...);
        # iso keeps pyvista's default perspective projection.
        if view.orthographic:
            plotter.enable_parallel_projection()

        # Extract feature edges for pen drawing style
        feature_edges = poly_data.extract_feature_edges(
            boundary_edges=True,
            feature_edges=True,
            manifold_edges=False,
            non_manifold_edges=True,
            feature_angle=30
        )

        # Add the solid mesh with light gray fill
        plotter.add_mesh(
            poly_data,
            color='#f0f0f0',
            show_edges=False,
            lighting=True,
            ambient=0.3,
            diffuse=0.6,
            specular=0.1
        )

        # Add feature edges as black lines
        if feature_edges.n_points > 0:
            plotter.add_mesh(
                feature_edges,
                color='black',
                line_width=2,
                render_lines_as_tubes=False
            )

        # Add silhouette for outline
        plotter.add_silhouette(poly_data, color='black', line_width=2)

        # Calculate bounding box for auto-scaling
        bbox = shape.bounding_box()
        bbox_size = max(bbox.size.X, bbox.size.Y, bbox.size.Z)
        scale_factor = bbox_size / 100.0

        # Scale camera position based on model size
        scaled_position = tuple(p * scale_factor * 2.5 for p in view.position)

        # Set camera
        plotter.camera.position = scaled_position
        plotter.camera.focal_point = view.focal_point
        plotter.camera.up = view.view_up

        # Reset camera to fit bounds
        plotter.reset_camera()

        # Render and save PNG
        plotter.screenshot(str(output_png))

        # Get final camera parameters after reset
        final_camera_params = {
            "position": list(plotter.camera.position),
            "focal_point": list(plotter.camera.focal_point),
            "view_up": list(plotter.camera.up),
        }

        plotter.close()

        # v2: Create metadata
        metadata = {
            "view": view.name,
            "camera": final_camera_params,
            "resolution": list(self.resolution),
            "timestamp": datetime.now().isoformat(),
            "png_path": str(output_png),
            "backend": "pyvista",
        }

        # v2: Save metadata JSON
        if output_json is None:
            output_json = output_png.with_suffix('.json')

        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

        metadata["json_path"] = str(output_json)
        return metadata
