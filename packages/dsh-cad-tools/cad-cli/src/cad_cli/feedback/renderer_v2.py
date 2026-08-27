"""Offscreen renderer v2 - with JSON metadata output"""

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Tuple, Any, Optional

if TYPE_CHECKING:
    from build123d import Shape

from ..package import ModelPackage
from .camera import CameraView


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
        }

        # v2: Save metadata JSON
        if output_json is None:
            output_json = output_png.with_suffix('.json')

        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

        metadata["json_path"] = str(output_json)
        return metadata
