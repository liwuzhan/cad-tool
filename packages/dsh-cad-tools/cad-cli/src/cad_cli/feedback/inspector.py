"""Geometry inspector for querying shape properties"""

import re
from collections import Counter
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from ..utils.geometry import aggregate_area, aggregate_volume

if TYPE_CHECKING:
    from build123d import Shape


# Mapping from build123d 0.11 GeomType enum names to human-readable labels
_GEOM_TYPE_LABELS = {
    "PLANE": "planar",
    "CYLINDER": "cylindrical",
    "CONE": "conical",
    "SPHERE": "spherical",
    "TORUS": "toroidal",
    "BEZIER": "bezier",
    "BSPLINE": "bspline",
    "REVOLUTION": "revolution",
    "EXTRUSION": "extrusion",
    "OFFSET": "offset",
    "OTHER": "other",
}


def classify_face_type(face) -> str:
    """Classify a build123d Face into a human-readable geometry type.

    build123d >= 0.11 exposes ``geom_type`` as a GeomType enum attribute;
    we read the enum member name (e.g. ``PLANE``) and map it to a label.
    """
    try:
        gt = face.geom_type
        name = getattr(gt, "name", None) or str(gt)
        return _GEOM_TYPE_LABELS.get(name, name.lower())
    except Exception:
        return "unknown"


def _get_face_normal(face) -> tuple:
    """Get the normal vector at the center of a face. Returns (x, y, z) or None."""
    try:
        center = face.center()
        normal = face.normal_at(center)
        return (normal.X, normal.Y, normal.Z)
    except Exception:
        return None


def _normal_to_direction(normal: tuple) -> str:
    """Convert a normal vector to a human-readable direction label."""
    if normal is None:
        return "unknown"
    x, y, z = normal
    abs_x, abs_y, abs_z = abs(x), abs(y), abs(z)
    if abs_x >= abs_y and abs_x >= abs_z:
        return "+X" if x > 0 else "-X"
    elif abs_y >= abs_x and abs_y >= abs_z:
        return "+Y" if y > 0 else "-Y"
    else:
        return "+Z" if z > 0 else "-Z"


class GeometryInspector:
    """Inspector for querying geometry properties and topology"""

    def get_bounds(self, shape: "Shape") -> Tuple[float, float, float, float, float, float]:
        """
        Get bounding box

        Args:
            shape: Shape to inspect

        Returns:
            Tuple of (xmin, ymin, zmin, xmax, ymax, zmax)
        """
        bb = shape.bounding_box()
        return (bb.min.X, bb.min.Y, bb.min.Z, bb.max.X, bb.max.Y, bb.max.Z)

    def get_volume(self, shape: "Shape") -> float:
        """
        Get volume

        Args:
            shape: Shape to inspect

        Returns:
            Volume value
        """
        return aggregate_volume(shape)

    def get_area(self, shape: "Shape") -> float:
        """
        Get surface area

        Args:
            shape: Shape to inspect

        Returns:
            Surface area value
        """
        return aggregate_area(shape)

    def get_faces(self, shape: "Shape") -> List[Dict[str, Any]]:
        """
        Get list of faces with properties including type classification.

        Args:
            shape: Shape to inspect

        Returns:
            List of face dictionaries with keys:
                index, area, center, type, normal, direction
        """
        faces = []
        for i, face in enumerate(shape.faces()):
            center = face.center()
            normal = _get_face_normal(face)
            face_type = classify_face_type(face)
            faces.append({
                "index": i,
                "area": face.area,
                "center": (center.X, center.Y, center.Z),
                "type": face_type,
                "normal": normal,
                "direction": _normal_to_direction(normal) if normal else None,
            })
        return faces

    def get_face_types(self, shape: "Shape") -> Dict[str, Any]:
        """
        Get breakdown of face types with counts and key faces.

        Args:
            shape: Shape to inspect

        Returns:
            Dict with 'breakdown' (type->count), 'total', and 'faces_by_type'
        """
        all_faces = self.get_faces(shape)
        type_counts = Counter(f["type"] for f in all_faces)

        # Group faces by type for detailed inspection
        faces_by_type: Dict[str, list] = {}
        for f in all_faces:
            ft = f["type"]
            if ft not in faces_by_type:
                faces_by_type[ft] = []
            faces_by_type[ft].append(f)

        # For each type, find the largest face and key characteristics
        type_summary = {}
        for ft, flist in faces_by_type.items():
            largest = max(flist, key=lambda x: x["area"])
            total_area = sum(f["area"] for f in flist)

            summary = {
                "count": len(flist),
                "total_area": total_area,
                "largest_face": {
                    "index": largest["index"],
                    "area": largest["area"],
                    "center": largest["center"],
                },
            }

            # Add direction info for planar faces
            if ft == "planar":
                directions = Counter(f["direction"] for f in flist if f["direction"])
                summary["directions"] = dict(directions)

            # For cylindrical faces, note the center axis
            if ft == "cylindrical":
                # Cylindrical faces tend to have centers around the hole axis
                centers = [f["center"] for f in flist]
                summary["face_indices"] = [f["index"] for f in flist]
                summary["avg_radius"] = sorted([f["area"] for f in flist])[-1] if flist else 0

            type_summary[ft] = summary

        return {
            "total": len(all_faces),
            "breakdown": dict(type_counts),
            "faces_by_type": type_summary,
            "all_faces": all_faces,
        }

    def get_edges(self, shape: "Shape") -> List[Dict[str, Any]]:
        """
        Get list of edges with properties

        Args:
            shape: Shape to inspect

        Returns:
            List of edge dictionaries
        """
        edges = []
        for i, edge in enumerate(shape.edges()):
            edges.append({
                "index": i,
                "length": edge.length
            })
        return edges

    def get_vertices(self, shape: "Shape") -> List[Dict[str, Any]]:
        """
        Get list of vertices with positions

        Args:
            shape: Shape to inspect

        Returns:
            List of vertex dictionaries
        """
        vertices = []
        for i, vertex in enumerate(shape.vertices()):
            pos = vertex.to_tuple()
            vertices.append({
                "index": i,
                "position": pos
            })
        return vertices

    def list_targets(self, shape: "Shape") -> Dict[str, List[Dict[str, Any]]]:
        """
        List all topology targets

        Args:
            shape: Shape to inspect

        Returns:
            Dictionary with faces, edges, and vertices
        """
        return {
            "faces": self.get_faces(shape),
            "edges": self.get_edges(shape),
            "vertices": self.get_vertices(shape)
        }

    def get_geometry_summary(self, shape: "Shape") -> str:
        """
        Generate a human-readable text description of the geometry.

        This is designed for text-only AI models to understand the shape
        without needing to view rendered images.

        Args:
            shape: Shape to describe

        Returns:
            Multi-line text description of the geometry
        """
        bounds = self.get_bounds(shape)
        x_size = bounds[3] - bounds[0]
        y_size = bounds[4] - bounds[1]
        z_size = bounds[5] - bounds[2]

        face_data = self.get_face_types(shape)
        vol = aggregate_volume(shape)

        lines = []
        lines.append("=== Geometry Description ===")
        lines.append("")

        # Overall dimensions
        lines.append(f"Overall size: X={x_size:.1f} x Y={y_size:.1f} x Z={z_size:.1f} mm")
        lines.append(f"Bounding box: X[{bounds[0]:.1f}..{bounds[3]:.1f}]  Y[{bounds[1]:.1f}..{bounds[4]:.1f}]  Z[{bounds[2]:.1f}..{bounds[5]:.1f}]")
        lines.append(f"Volume: {vol:.2f} mm³")
        lines.append(f"Solids: {len(list(shape.solids())) if hasattr(shape, 'solids') else 0}")
        lines.append(f"Total faces: {face_data['total']}")
        lines.append("")

        # Face type breakdown
        lines.append("--- Face Type Breakdown ---")
        for ftype, count in sorted(face_data["breakdown"].items(), key=lambda x: -x[1]):
            info = face_data["faces_by_type"][ftype]
            pct = count / face_data["total"] * 100
            lines.append(f"  {ftype}: {count} faces ({pct:.0f}%), total area={info['total_area']:.2f} mm²")

            if ftype == "planar" and "directions" in info:
                dirs = ", ".join(f"{d}: {c}" for d, c in sorted(info["directions"].items()))
                lines.append(f"    face directions: {dirs}")

            if ftype == "cylindrical":
                lines.append(f"    face indices: {info.get('face_indices', [])}")

        lines.append("")

        # Key faces (large planar faces, holes, etc.)
        lines.append("--- Key Faces ---")
        all_faces = sorted(face_data["all_faces"], key=lambda f: f["area"], reverse=True)

        for f in all_faces[:10]:  # Top 10 largest faces
            dir_str = f" ({f['direction']})" if f.get("direction") else ""
            lines.append(
                f"  Face[{f['index']}]: {f['type']}{dir_str}, "
                f"area={f['area']:.2f} mm², "
                f"center=({f['center'][0]:.1f}, {f['center'][1]:.1f}, {f['center'][2]:.1f})"
            )

        # If there are many faces, summarize the rest
        if len(all_faces) > 10:
            remaining_area = sum(f["area"] for f in all_faces[10:])
            lines.append(f"  ... and {len(all_faces) - 10} more faces (total area={remaining_area:.2f} mm²)")

        lines.append("")

        # Hole detection (cylindrical faces likely indicate holes/bosses)
        cylindrical = face_data["faces_by_type"].get("cylindrical", {})
        if cylindrical and cylindrical.get("count", 0) > 0:
            cyl_faces = cylindrical.get("face_indices", [])
            lines.append(f"--- Cylindrical Features (possible holes/bosses) ---")
            lines.append(f"  {cylindrical['count']} cylindrical faces detected")
            for fi in cyl_faces[:8]:
                face = next((f for f in all_faces if f["index"] == fi), None)
                if face:
                    lines.append(
                        f"  Face[{face['index']}]: center=({face['center'][0]:.1f}, "
                        f"{face['center'][1]:.1f}, {face['center'][2]:.1f}), "
                        f"area={face['area']:.2f} mm²"
                    )

        lines.append("")
        lines.append("--- Interpretation Guide ---")
        lines.append("  planar faces = flat surfaces (bases, walls, cut faces)")
        lines.append("  cylindrical faces = holes, bores, shafts, fillets")
        lines.append("  conical faces = chamfers, tapers, countersinks")
        lines.append("  spherical faces = ball ends, spherical cuts")
        lines.append("  toroidal faces = fillets, rounds, O-ring grooves")
        lines.append("  The largest planar faces typically define the part envelope.")
        lines.append("  Cylindrical face area / (2*pi) approximates radius*height for a hole.")

        return "\n".join(lines)

    def query_target(self, shape: "Shape", target: str, prop: str) -> Any:
        """
        Query a specific target property

        Args:
            shape: Shape to inspect
            target: Target specification (e.g., "face[0]", "edge[2]")
            prop: Property to query (e.g., "center", "area", "length", "type", "normal")

        Returns:
            Property value

        Raises:
            ValueError: If target or property is invalid
        """
        target_type, index = self._parse_target(target)

        if target_type == "face":
            faces = list(shape.faces())
            if index >= len(faces):
                raise ValueError(f"Face index {index} out of range (0-{len(faces)-1})")

            face = faces[index]
            if prop == "center":
                center = face.center()
                return (center.X, center.Y, center.Z)
            elif prop == "area":
                return face.area
            elif prop == "type":
                return classify_face_type(face)
            elif prop == "normal":
                normal = _get_face_normal(face)
                return normal if normal else "unknown"
            elif prop == "direction":
                normal = _get_face_normal(face)
                return _normal_to_direction(normal) if normal else "unknown"
            else:
                raise ValueError(f"Unknown property '{prop}' for face")

        elif target_type == "edge":
            edges = list(shape.edges())
            if index >= len(edges):
                raise ValueError(f"Edge index {index} out of range (0-{len(edges)-1})")

            edge = edges[index]
            if prop == "length":
                return edge.length
            else:
                raise ValueError(f"Unknown property '{prop}' for edge")

        elif target_type == "vertex":
            vertices = list(shape.vertices())
            if index >= len(vertices):
                raise ValueError(f"Vertex index {index} out of range (0-{len(vertices)-1})")

            vertex = vertices[index]
            if prop == "position":
                return vertex.to_tuple()
            else:
                raise ValueError(f"Unknown property '{prop}' for vertex")

        else:
            raise ValueError(f"Unknown target type '{target_type}'")

    def _parse_target(self, target: str) -> Tuple[str, int]:
        """
        Parse target string into type and index

        Args:
            target: Target string (e.g., "face[0]")

        Returns:
            Tuple of (type, index)

        Raises:
            ValueError: If target format is invalid
        """
        match = re.match(r'(face|edge|vertex)\[(\d+)\]', target)
        if not match:
            raise ValueError(f"Invalid target format: {target}. Use 'face[N]', 'edge[N]', or 'vertex[N]'")

        target_type = match.group(1)
        index = int(match.group(2))

        return target_type, index
