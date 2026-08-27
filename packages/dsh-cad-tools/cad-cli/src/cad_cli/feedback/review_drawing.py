"""Model-directed annotated drawings for optional CAD review.

The renderer reports geometry chosen by the caller.  It deliberately does not
choose important dimensions, classify findings, or modify the model.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

from build123d import (
    ColorIndex,
    Compound,
    Draft,
    ExportSVG,
    ExtensionLine,
    Keep,
    LineType,
    Plane,
    Shape,
    Vector,
)

from .camera import STANDARD_VIEWS


SCHEMA = "cad.review-drawing/v1"
SUPPORTED_VIEWS = tuple(STANDARD_VIEWS)
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")


class ReviewDrawingError(ValueError):
    """Raised when a model-directed drawing specification is invalid."""


def load_drawing_spec(
    *,
    path: Path | None = None,
    json_text: str | None = None,
) -> dict[str, Any]:
    """Load exactly one JSON drawing specification."""

    if bool(path) == bool(json_text):
        raise ReviewDrawingError("provide exactly one of --drawing-spec or --drawing-spec-json")
    try:
        raw = path.read_text(encoding="utf-8") if path else str(json_text)
        spec = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewDrawingError(f"cannot read drawing specification: {exc}") from exc
    if not isinstance(spec, dict):
        raise ReviewDrawingError("drawing specification must be a JSON object")
    return spec


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReviewDrawingError(f"{field} must be a number")
    if not math.isfinite(float(value)):
        raise ReviewDrawingError(f"{field} must be finite")
    return float(value)


def _vector3(value: Any, field: str) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ReviewDrawingError(f"{field} must contain three coordinates")
    return tuple(_number(item, f"{field}[{index}]") for index, item in enumerate(value))


def _vector2(value: Any, field: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ReviewDrawingError(f"{field} must contain two coordinates")
    return tuple(_number(item, f"{field}[{index}]") for index, item in enumerate(value))


def _tuple(vector: Vector) -> tuple[float, float, float]:
    return (float(vector.X), float(vector.Y), float(vector.Z))


def _add(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(left + right for left, right in zip(a, b))


def _sub(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(left - right for left, right in zip(a, b))


def _scale(vector: tuple[float, ...], factor: float) -> tuple[float, ...]:
    return tuple(item * factor for item in vector)


def _dot(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum(left * right for left, right in zip(a, b))


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(vector: tuple[float, ...]) -> float:
    return math.sqrt(_dot(vector, vector))


def _unit(vector: tuple[float, ...], field: str) -> tuple[float, ...]:
    length = _length(vector)
    if length <= 1e-12:
        raise ReviewDrawingError(f"{field} must not be a zero vector")
    return _scale(vector, 1.0 / length)


def _bbox_dict(shape: Shape) -> dict[str, list[float]]:
    bbox = shape.bounding_box()
    return {
        "min": [bbox.min.X, bbox.min.Y, bbox.min.Z],
        "max": [bbox.max.X, bbox.max.Y, bbox.max.Z],
        "size": [bbox.size.X, bbox.size.Y, bbox.size.Z],
    }


def _collect_components(shape: Shape) -> list[dict[str, Any]]:
    """Describe top-level instances whose STEP locations are already resolved."""

    parent = str(getattr(shape, "label", "") or "assembly")
    return [
        {
            "label": str(getattr(child, "label", "") or f"component_{index}"),
            "parent": parent,
            "solid_count": len(child.solids()),
            "bbox": _bbox_dict(child),
        }
        for index, child in enumerate(list(getattr(shape, "children", []) or []))
    ]


def _view_basis(
    shape: Shape,
    view_name: str,
) -> tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]:
    """Return eye, target, screen-right and screen-up in world coordinates."""

    view = STANDARD_VIEWS[view_name]
    bbox = shape.bounding_box()
    target = _tuple(bbox.center())
    span = max(float(bbox.size.X), float(bbox.size.Y), float(bbox.size.Z), 1.0)
    camera_vector = _unit(_sub(view.position, view.focal_point), f"view {view_name}")
    eye = _add(target, _scale(camera_vector, span * 5.0))
    forward = _unit(_sub(target, eye), f"view {view_name}")
    up_hint = _unit(tuple(float(item) for item in view.view_up), f"view {view_name} up")
    screen_right = _unit(_cross(forward, up_hint), f"view {view_name} right")
    screen_up = _unit(_cross(screen_right, forward), f"view {view_name} screen up")
    return eye, target, screen_right, screen_up


def _project_point(
    point: tuple[float, float, float],
    target: tuple[float, float, float],
    screen_right: tuple[float, float, float],
    screen_up: tuple[float, float, float],
) -> tuple[float, float]:
    relative = _sub(point, target)
    return (_dot(relative, screen_right), _dot(relative, screen_up))


def _apply_section(shape: Shape, raw: Any, field: str) -> tuple[Shape, dict[str, Any] | None]:
    if raw is None:
        return shape, None
    if not isinstance(raw, dict):
        raise ReviewDrawingError(f"{field} must be an object")
    origin = _vector3(raw.get("origin"), f"{field}.origin")
    normal = _vector3(raw.get("normal"), f"{field}.normal")
    _unit(normal, f"{field}.normal")
    keep_name = str(raw.get("keep", "bottom")).lower()
    if keep_name not in {"top", "bottom"}:
        raise ReviewDrawingError(f"{field}.keep must be top or bottom")
    plane = Plane(origin=origin, z_dir=normal)
    clipped = shape.split(plane, keep=Keep.TOP if keep_name == "top" else Keep.BOTTOM)
    if clipped is None:
        raise ReviewDrawingError(f"{field} does not leave any geometry")
    if isinstance(clipped, (list, tuple)):
        clipped = Compound(children=list(clipped))
    return clipped, {"origin": list(origin), "normal": list(normal), "keep": keep_name}


def _edge_points(edge: Shape, samples: int = 40) -> tuple[list[float], list[float]]:
    points: list[Vector] = []
    try:
        points = [edge.position_at(index / samples) for index in range(samples + 1)]
    except Exception:
        try:
            points = [vertex.center() for vertex in edge.vertices()]
        except Exception:
            points = []
    return ([point.X for point in points], [point.Y for point in points])


def _normalize_dimensions(
    raw_dimensions: Any,
    *,
    target: tuple[float, float, float],
    screen_right: tuple[float, float, float],
    screen_up: tuple[float, float, float],
    field: str,
) -> list[dict[str, Any]]:
    if raw_dimensions is None:
        return []
    if not isinstance(raw_dimensions, list):
        raise ReviewDrawingError(f"{field} must be an array")
    dimensions: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_dimensions):
        item_field = f"{field}[{index}]"
        if not isinstance(raw, dict):
            raise ReviewDrawingError(f"{item_field} must be an object")
        start_3d = _vector3(raw.get("from"), f"{item_field}.from")
        end_3d = _vector3(raw.get("to"), f"{item_field}.to")
        start_2d = _project_point(start_3d, target, screen_right, screen_up)
        end_2d = _project_point(end_3d, target, screen_right, screen_up)
        projected = _length(_sub(end_2d, start_2d))
        if projected <= 1e-9:
            raise ReviewDrawingError(f"{item_field} projects to a zero-length dimension")
        true_distance = _length(_sub(end_3d, start_3d))
        label = raw.get("label")
        if label is not None and not isinstance(label, str):
            raise ReviewDrawingError(f"{item_field}.label must be a string")
        dimensions.append({
            "id": str(raw.get("id") or f"dimension_{index + 1}"),
            "from": list(start_3d),
            "to": list(end_3d),
            "from_2d": list(start_2d),
            "to_2d": list(end_2d),
            "offset_mm": _number(raw.get("offset_mm", 10.0), f"{item_field}.offset_mm"),
            "label": label,
            "projected_distance_mm": projected,
            "true_distance_mm": true_distance,
        })
    return dimensions


def _normalize_callouts(
    raw_callouts: Any,
    *,
    target: tuple[float, float, float],
    screen_right: tuple[float, float, float],
    screen_up: tuple[float, float, float],
    field: str,
) -> list[dict[str, Any]]:
    if raw_callouts is None:
        return []
    if not isinstance(raw_callouts, list):
        raise ReviewDrawingError(f"{field} must be an array")
    callouts: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_callouts):
        item_field = f"{field}[{index}]"
        if not isinstance(raw, dict):
            raise ReviewDrawingError(f"{item_field} must be an object")
        point_3d = _vector3(raw.get("at"), f"{item_field}.at")
        text = raw.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ReviewDrawingError(f"{item_field}.text must be a non-empty string")
        offset = _vector2(raw.get("offset_mm", [8.0, 8.0]), f"{item_field}.offset_mm")
        point_2d = _project_point(point_3d, target, screen_right, screen_up)
        callouts.append({
            "id": str(raw.get("id") or f"callout_{index + 1}"),
            "at": list(point_3d),
            "at_2d": list(point_2d),
            "offset_mm": list(offset),
            "text": text,
        })
    return callouts


def _write_svg(
    path: Path,
    visible: Iterable[Shape],
    hidden: Iterable[Shape],
    dimensions: list[dict[str, Any]],
    *,
    show_hidden: bool,
    font_size: float,
) -> None:
    annotations: list[Shape] = []
    draft = Draft(
        font="DejaVu Sans",
        font_size=font_size,
        arrow_length=max(font_size * 0.8, 1.0),
        line_width=max(font_size * 0.10, 0.15),
        decimal_precision=2,
        display_units=True,
    )
    for dimension in dimensions:
        start = dimension["from_2d"]
        end = dimension["to_2d"]
        annotations.append(ExtensionLine(
            [Vector(*start), Vector(*end)],
            offset=dimension["offset_mm"],
            draft=draft,
            label=dimension["label"],
        ))

    exporter = ExportSVG(scale=3.0, margin=max(font_size * 3.0, 6.0))
    exporter.add_layer("visible", line_color=ColorIndex.BLACK, line_weight=0.30)
    exporter.add_layer(
        "hidden",
        line_color=ColorIndex.GRAY,
        line_weight=0.18,
        line_type=LineType.DASHED,
    )
    exporter.add_layer("dimensions", line_color=ColorIndex.BLUE, line_weight=0.20)
    exporter.add_shape(list(visible), "visible")
    if show_hidden:
        exporter.add_shape(list(hidden), "hidden")
    if annotations:
        exporter.add_shape(annotations, "dimensions")
    exporter.write(path)


def _write_png(
    path: Path,
    visible: Iterable[Shape],
    hidden: Iterable[Shape],
    dimensions: list[dict[str, Any]],
    callouts: list[dict[str, Any]],
    *,
    show_hidden: bool,
    title: str,
) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib import pyplot as plt
    except ImportError as exc:
        raise ImportError("matplotlib is required for annotated review PNGs") from exc

    figure, axis = plt.subplots(figsize=(10, 7.5), dpi=140)
    for edge in hidden if show_hidden else []:
        xs, ys = _edge_points(edge)
        if len(xs) >= 2:
            axis.plot(xs, ys, color="#8a8f98", linewidth=0.65, linestyle=(0, (4, 3)))
    for edge in visible:
        xs, ys = _edge_points(edge)
        if len(xs) >= 2:
            axis.plot(xs, ys, color="#20242a", linewidth=1.05)

    for dimension in dimensions:
        start = tuple(dimension["from_2d"])
        end = tuple(dimension["to_2d"])
        direction = _unit(_sub(end, start), dimension["id"])
        normal = (-direction[1], direction[0])
        offset = _scale(normal, dimension["offset_mm"])
        dim_start = _add(start, offset)
        dim_end = _add(end, offset)
        axis.plot([start[0], dim_start[0]], [start[1], dim_start[1]], color="#1b63d9", linewidth=0.8)
        axis.plot([end[0], dim_end[0]], [end[1], dim_end[1]], color="#1b63d9", linewidth=0.8)
        axis.annotate(
            "",
            xy=dim_end,
            xytext=dim_start,
            arrowprops={"arrowstyle": "<->", "color": "#1b63d9", "linewidth": 1.0},
        )
        label = dimension["label"] or f"{dimension['projected_distance_mm']:.2f} mm"
        midpoint = _scale(_add(dim_start, dim_end), 0.5)
        axis.text(
            midpoint[0],
            midpoint[1],
            label,
            color="#134ba3",
            fontsize=9,
            ha="center",
            va="bottom",
            bbox={"boxstyle": "round,pad=0.16", "facecolor": "white", "edgecolor": "none", "alpha": 0.9},
        )

    for callout in callouts:
        point = tuple(callout["at_2d"])
        text_point = _add(point, tuple(callout["offset_mm"]))
        axis.annotate(
            callout["text"],
            xy=point,
            xytext=text_point,
            color="#9c3f00",
            fontsize=9,
            ha="left",
            va="center",
            arrowprops={"arrowstyle": "->", "color": "#d45b08", "linewidth": 0.9},
            bbox={"boxstyle": "round,pad=0.18", "facecolor": "#fff8ef", "edgecolor": "#d45b08", "linewidth": 0.6},
        )

    axis.set_aspect("equal", adjustable="datalim")
    axis.autoscale_view()
    axis.margins(0.12)
    axis.set_axis_off()
    axis.set_title(title, fontsize=11)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, bbox_inches="tight", pad_inches=0.08, facecolor="white")
    plt.close(figure)


def render_review_drawings(
    shape: Shape,
    spec: dict[str, Any],
    output_dir: Path,
    *,
    source_commit: str | None = None,
) -> list[dict[str, Any]]:
    """Generate model-directed annotated SVG/PNG views and neutral readings."""

    if spec.get("schema", SCHEMA) != SCHEMA:
        raise ReviewDrawingError(f"unsupported drawing schema: {spec.get('schema')}")
    raw_views = spec.get("views")
    if not isinstance(raw_views, list) or not raw_views:
        raise ReviewDrawingError("drawing specification requires a non-empty views array")

    output_dir.mkdir(parents=True, exist_ok=True)
    components = _collect_components(shape)
    seen_names: set[str] = set()
    results: list[dict[str, Any]] = []
    base_title = str(spec.get("title") or getattr(shape, "label", "CAD review"))

    for index, raw_view in enumerate(raw_views):
        field = f"views[{index}]"
        if not isinstance(raw_view, dict):
            raise ReviewDrawingError(f"{field} must be an object")
        view_name = str(raw_view.get("view", "front")).lower()
        if view_name not in STANDARD_VIEWS:
            raise ReviewDrawingError(
                f"{field}.view must be one of {', '.join(SUPPORTED_VIEWS)}"
            )
        requested_name = str(raw_view.get("name") or view_name)
        safe_name = _SAFE_NAME.sub("_", requested_name).strip("._") or f"view_{index + 1}"
        if safe_name in seen_names:
            raise ReviewDrawingError(f"duplicate drawing name: {safe_name}")
        seen_names.add(safe_name)

        working_shape, section = _apply_section(shape, raw_view.get("section"), f"{field}.section")
        eye, target, screen_right, screen_up = _view_basis(shape, view_name)
        visible, hidden = working_shape.project_to_viewport(
            eye,
            STANDARD_VIEWS[view_name].view_up,
            look_at=target,
        )
        dimensions = _normalize_dimensions(
            raw_view.get("dimensions"),
            target=target,
            screen_right=screen_right,
            screen_up=screen_up,
            field=f"{field}.dimensions",
        )
        callouts = _normalize_callouts(
            raw_view.get("callouts"),
            target=target,
            screen_right=screen_right,
            screen_up=screen_up,
            field=f"{field}.callouts",
        )
        show_hidden = bool(raw_view.get("hidden_lines", True))
        span = max(_bbox_dict(shape)["size"] + [1.0])
        title = str(raw_view.get("title") or f"{base_title} · {requested_name}")

        prefix = output_dir / f"review_drawing_{safe_name}"
        svg_path = prefix.with_suffix(".svg")
        png_path = prefix.with_suffix(".png")
        json_path = prefix.with_suffix(".json")
        _write_svg(
            svg_path,
            visible,
            hidden,
            dimensions,
            show_hidden=show_hidden,
            font_size=max(span * 0.035, 2.5),
        )
        _write_png(
            png_path,
            visible,
            hidden,
            dimensions,
            callouts,
            show_hidden=show_hidden,
            title=title,
        )

        metadata = {
            "schema": SCHEMA,
            "name": requested_name,
            "view": view_name,
            "title": title,
            "source_commit": source_commit,
            "projection": "orthographic",
            "hidden_lines": show_hidden,
            "visible_edge_count": len(visible),
            "hidden_edge_count": len(hidden),
            "camera": {
                "eye": list(eye),
                "target": list(target),
                "screen_right": list(screen_right),
                "screen_up": list(screen_up),
            },
            "section": section,
            "dimensions": dimensions,
            "callouts": callouts,
            "components": components,
            "png_path": str(png_path),
            "svg_path": str(svg_path),
            "json_path": str(json_path),
        }
        json_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
        results.append(metadata)

    return results
