"""Offscreen renderer using pyvista - Pen/Line drawing style"""

from pathlib import Path
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from build123d import Shape

from ..config import Config
from .camera import CameraView


class OffscreenRenderer:
    """Offscreen renderer for generating technical drawings (pen style)"""

    def __init__(self, project_dir: Path):
        """
        Initialize renderer

        Args:
            project_dir: Project root directory
        """
        self.project_dir = project_dir
        self.config = Config(project_dir)
        self.config.load()
        self.resolution: Tuple[int, int] = tuple(self.config.get("render.resolution", [800, 600]))

    def render(self, shape: "Shape", view: CameraView, output_path: Path) -> None:
        """
        Render shape to image file using pen/line drawing style

        Args:
            shape: Shape to render
            view: Camera view
            output_path: Output image path

        Raises:
            ImportError: If pyvista is not available
            Exception: If rendering fails
        """
        try:
            import pyvista as pv
        except ImportError:
            raise ImportError("pyvista is required for rendering. Install with: pip install pyvista")

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

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
        # feature_angle: edges with angle > this are considered sharp
        feature_edges = poly_data.extract_feature_edges(
            boundary_edges=True,
            feature_edges=True,
            manifold_edges=False,
            non_manifold_edges=True,
            feature_angle=30  # Angle threshold for sharp edges
        )

        # Add the solid mesh with light gray fill, no edges
        plotter.add_mesh(
            poly_data,
            color='#f0f0f0',  # Very light gray
            show_edges=False,
            lighting=True,
            ambient=0.3,
            diffuse=0.6,
            specular=0.1
        )

        # Add feature edges as black lines (pen strokes)
        if feature_edges.n_points > 0:
            plotter.add_mesh(
                feature_edges,
                color='black',
                line_width=2,
                render_lines_as_tubes=False
            )

        # Add silhouette for outline effect
        plotter.add_silhouette(poly_data, color='black', line_width=2)

        # Calculate bounding box for auto-scaling
        bbox = shape.bounding_box()
        bbox_size = max(bbox.size.X, bbox.size.Y, bbox.size.Z)
        scale_factor = bbox_size / 100.0  # Normalize to 100 units reference

        # Scale camera position based on model size
        scaled_position = tuple(p * scale_factor * 2.5 for p in view.position)

        # Set camera
        plotter.camera.position = scaled_position
        plotter.camera.focal_point = view.focal_point
        plotter.camera.up = view.view_up

        # Reset camera to fit bounds
        plotter.reset_camera()

        # Render and save
        plotter.screenshot(str(output_path))
        plotter.close()
