"""Geometry validator for BRep checking"""

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from build123d import Shape

from ..constants import ErrorCode
from ..models import ErrorInfo
from ..utils.geometry import aggregate_volume


class GeometryValidator:
    """Validates geometry using BRep checks"""

    def validate(
        self,
        shape: "Shape",
        *,
        allow_multiple_solids: bool = False,
    ) -> List[ErrorInfo]:
        """
        Execute BRep validation checks

        Args:
            shape: build123d Shape object

        Returns:
            List of ErrorInfo for any validation failures
        """
        errors: List[ErrorInfo] = []

        # Basic validity check
        try:
            if hasattr(shape, 'is_valid') and not shape.is_valid:
                errors.append(ErrorInfo(
                    file="",
                    line=0,
                    type="BRepValidation",
                    code=ErrorCode.E_BREP,
                    message="Invalid BRep: Shape failed basic validity check",
                    hint="Check for self-intersections or degenerate geometry"
                ))
        except Exception as e:
            errors.append(ErrorInfo(
                file="",
                line=0,
                type="BRepValidation",
                code=ErrorCode.E_BREP,
                message=f"Could not check shape validity: {e}",
                hint=None
            ))

        # Detailed BRep check using OCP
        try:
            from OCP.BRepCheck import BRepCheck_Analyzer

            if hasattr(shape, 'wrapped'):
                analyzer = BRepCheck_Analyzer(shape.wrapped)
                if not analyzer.IsValid():
                    errors.append(ErrorInfo(
                        file="",
                        line=0,
                        type="BRepAnalyzer",
                        code=ErrorCode.E_BREP,
                        message="BRep validation failed: Geometry has structural issues",
                        hint="The shape may have invalid topology or geometry"
                    ))
        except ImportError:
            # OCP not available, skip detailed check
            pass
        except Exception as e:
            errors.append(ErrorInfo(
                file="",
                line=0,
                type="BRepAnalyzer",
                code=ErrorCode.E_BREP,
                message=f"BRep analysis error: {e}",
                hint=None
            ))

        # Check for zero volume (might indicate degenerate geometry)
        try:
            if aggregate_volume(shape) <= 0:
                errors.append(ErrorInfo(
                    file="",
                    line=0,
                    type="VolumeCheck",
                    code=ErrorCode.E_CONSTRAINT,
                    message="Shape has zero or negative volume",
                    hint="Check that the shape is a valid solid"
                ))
        except Exception:
            pass

        # Check for multiple disconnected solids
        try:
            if hasattr(shape, 'solids'):
                solids = list(shape.solids())
                if len(solids) > 1 and not allow_multiple_solids:
                    errors.append(ErrorInfo(
                        file="",
                        line=0,
                        type="MultipleDisconnectedSolids",
                        code=ErrorCode.E_BREP,
                        message=f"Shape contains {len(solids)} disconnected solids (expected 1)",
                        hint="Check boolean operations - some geometry may not have been properly subtracted or merged"
                    ))
        except Exception as e:
            pass

        # Check if shape is manifold (no self-intersections or overlaps)
        try:
            if hasattr(shape, 'is_manifold'):
                if not shape.is_manifold:
                    errors.append(ErrorInfo(
                        file="",
                        line=0,
                        type="NonManifold",
                        code=ErrorCode.E_BREP,
                        message="Shape is non-manifold (contains self-intersections or overlapping geometry)",
                        hint="Check that all boolean operations completed successfully"
                    ))
        except Exception:
            pass

        return errors
