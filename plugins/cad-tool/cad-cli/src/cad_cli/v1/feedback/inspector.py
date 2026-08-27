"""Geometry inspector for querying shape properties"""

import re
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

if TYPE_CHECKING:
    from build123d import Shape


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
        return shape.volume

    def get_area(self, shape: "Shape") -> float:
        """
        Get surface area

        Args:
            shape: Shape to inspect

        Returns:
            Surface area value
        """
        return shape.area

    def get_faces(self, shape: "Shape") -> List[Dict[str, Any]]:
        """
        Get list of faces with properties

        Args:
            shape: Shape to inspect

        Returns:
            List of face dictionaries
        """
        faces = []
        for i, face in enumerate(shape.faces()):
            center = face.center()
            faces.append({
                "index": i,
                "area": face.area,
                "center": (center.X, center.Y, center.Z)
            })
        return faces

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

    def query_target(self, shape: "Shape", target: str, prop: str) -> Any:
        """
        Query a specific target property

        Args:
            shape: Shape to inspect
            target: Target specification (e.g., "face[0]", "edge[2]")
            prop: Property to query (e.g., "center", "area", "length")

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
