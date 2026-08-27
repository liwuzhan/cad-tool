"""Model exporter for various formats"""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from build123d import Shape

from ..constants import ErrorCode
from ..models import ErrorInfo


class ModelExporter:
    """Exporter for CAD file formats"""

    SUPPORTED_FORMATS = ['step', 'stl']

    def export(self, shape: "Shape", format: str, output_path: Path) -> None:
        """
        Export shape to file

        Args:
            shape: Shape to export
            format: Export format ('step' or 'stl')
            output_path: Output file path

        Raises:
            ValueError: If format is not supported
            Exception: If export fails
        """
        if format not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {format}. Supported: {', '.join(self.SUPPORTED_FORMATS)}")

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Use build123d's export functions
            from build123d import export_step, export_stl, Compound

            if format == 'step':
                try:
                    export_step(shape, str(output_path))
                except Exception:
                    # build123d 0.11 regression (#1356): Compound fallback
                    export_step(Compound(children=[shape]), str(output_path))
            elif format == 'stl':
                export_stl(shape, str(output_path))
        except Exception as e:
            raise Exception(f"Failed to export {format}: {e}")
