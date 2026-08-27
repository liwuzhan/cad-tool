"""Data models for CAD CLI"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Optional
from .constants import ErrorCode


@dataclass
class Event:
    """Event for JSONL output"""
    event: str
    ts: str  # ISO 8601 timestamp
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ErrorInfo:
    """Error information with location and hints"""
    file: str
    line: int
    type: str
    code: ErrorCode
    message: str
    hint: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "type": self.type,
            "code": self.code.value if isinstance(self.code, ErrorCode) else self.code,
            "message": self.message,
            "hint": self.hint
        }


@dataclass
class GeometryMetrics:
    """Geometry metrics for a shape"""
    volume: float
    area: float
    bbox: tuple[float, float, float, float, float, float]  # xmin, ymin, zmin, xmax, ymax, zmax
    face_count: int
    edge_count: int
    vertex_count: int
    solid_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
