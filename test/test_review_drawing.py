import json
from pathlib import Path

import pytest
from build123d import Box, Compound, Cylinder, Mode, Pos

from cad_cli.feedback.review_drawing import (
    ReviewDrawingError,
    _apply_section,
    _section_fill_polygons,
    measure_declared_port,
    render_review_drawings,
)


def _assembly():
    base = Box(30, 20, 10)
    base.label = "base"
    slider = Pos(20, 0, 10) * Box(10, 10, 10)
    slider.label = "slider"
    result = Compound(children=[base, slider])
    result.label = "fixture"
    return result


def test_review_drawing_outputs_neutral_dimension_and_section_evidence(tmp_path):
    spec = {
        "schema": "cad.review-drawing/v1",
        "title": "Fixture diagnostic",
        "views": [
            {
                "name": "front_check",
                "view": "front",
                "hidden_lines": True,
                "dimensions": [
                    {
                        "id": "overall_width",
                        "from": [-15, 0, -5],
                        "to": [25, 0, -5],
                        "offset_mm": -8,
                    }
                ],
                "callouts": [
                    {"id": "joint", "at": [15, 0, 5], "text": "joint", "offset_mm": [5, 5]}
                ],
            },
            {
                "name": "center_cut",
                "view": "right",
                "hidden_lines": False,
                "section": {"origin": [0, 0, 0], "normal": [1, 0, 0], "keep": "bottom"},
            },
        ],
    }

    results = render_review_drawings(_assembly(), spec, tmp_path, source_commit="abc123")

    assert [result["name"] for result in results] == ["front_check", "center_cut"]
    assert results[0]["dimensions"][0]["projected_distance_mm"] == pytest.approx(40)
    assert results[0]["dimensions"][0]["true_distance_mm"] == pytest.approx(40)
    assert results[1]["section"] == {
        "origin": [0.0, 0.0, 0.0],
        "normal": [1.0, 0.0, 0.0],
        "keep": "bottom",
    }
    assert {component["label"] for component in results[0]["components"]} == {"base", "slider"}

    for result in results:
        for key in ("png_path", "svg_path", "json_path"):
            output = Path(result[key])
            assert output.is_file()
            assert output.stat().st_size > 500
        metadata = json.loads(Path(result["json_path"]).read_text())
        assert metadata["schema"] == "cad.review-drawing/v1"
        assert metadata["source_commit"] == "abc123"
        assert "verdict" not in metadata


def test_review_drawing_rejects_dimension_hidden_by_view(tmp_path):
    spec = {
        "views": [
            {
                "view": "front",
                "dimensions": [
                    {"from": [0, 0, 0], "to": [0, 10, 0], "offset_mm": 5}
                ],
            }
        ]
    }

    with pytest.raises(ReviewDrawingError, match="zero-length"):
        render_review_drawings(_assembly(), spec, tmp_path)


# --------------------------------------------------------------------------
# Declared ports: measure the geometry, do not restate the declaration
# --------------------------------------------------------------------------


def _plate_with_bore(actual_diameter: float = 9.9):
    """A plate whose real bore differs from what a declaration might claim."""

    plate = Box(60, 60, 8)
    bore = Cylinder(actual_diameter / 2, 10, mode=Mode.SUBTRACT)
    return plate - bore


def test_declared_port_is_measured_not_restated():
    """A declaration of 10.0 over a 9.9 bore must read 9.9.

    The face is located by axis and position only. Selecting it by the value we
    are about to report would make the reading a restatement of the claim.
    """

    shape = _plate_with_bore(9.9)
    port = {
        "id": "central_bore",
        "type": "cylindrical_bore",
        "frame": {"origin_mm": [0.0, 0.0, 0.0], "axis": [0.0, 0.0, 1.0]},
        "dimensions_mm": {"diameter": 10.0},
    }
    reading = measure_declared_port(shape, port)
    assert reading["declared_mm"] == 10.0
    assert reading["measured_mm"] == [9.9]


def test_faithful_declaration_and_drifted_declaration_read_differently():
    port = {
        "id": "central_bore",
        "type": "cylindrical_bore",
        "frame": {"origin_mm": [0.0, 0.0, 0.0], "axis": [0.0, 0.0, 1.0]},
        "dimensions_mm": {"diameter": 10.0},
    }
    faithful = measure_declared_port(_plate_with_bore(10.0), port)
    drifted = measure_declared_port(_plate_with_bore(9.9), port)
    assert faithful["measured_mm"] == [10.0]
    assert drifted["measured_mm"] == [9.9]


def test_port_off_the_axis_is_not_claimed_by_a_distant_cylinder():
    """Position decides, so a neighbouring hole is never mistaken for the port."""

    shape = _plate_with_bore(9.9)
    off_axis = {
        "id": "not_here",
        "type": "cylindrical_bore",
        "frame": {"origin_mm": [0.0, 0.0, 0.0], "axis": [1.0, 0.0, 0.0]},
        "dimensions_mm": {"diameter": 10.0},
    }
    reading = measure_declared_port(shape, off_axis)
    assert reading["measured_mm"] == []
    assert reading["note"] == "no matching cylindrical face"


def test_port_type_without_a_measurement_rule_says_so():
    port = {
        "id": "mounting_face",
        "type": "planar_face",
        "frame": {"origin_mm": [0.0, 0.0, -4.0], "axis": [0.0, 0.0, -1.0]},
        "dimensions_mm": {"face_size": 60.0},
    }
    reading = measure_declared_port(_plate_with_bore(), port)
    assert reading["measured_mm"] == []
    assert "no measurement rule" in reading["note"]


def test_annotate_ports_draws_declaration_beside_measurement(tmp_path):
    shape = _plate_with_bore(9.9)
    spec = {
        "schema": "cad.review-drawing/v1",
        "title": "ports",
        "annotate_ports": True,
        "views": [{"name": "ports_top", "view": "top", "hidden_lines": False}],
    }
    ports = {
        "plate": [
            {
                "id": "central_bore",
                "type": "cylindrical_bore",
                "frame": {"origin_mm": [0.0, 0.0, 0.0], "axis": [0.0, 0.0, 1.0]},
                "dimensions_mm": {"diameter": 10.0},
            }
        ]
    }
    results = render_review_drawings(
        shape, spec, tmp_path, declared_ports=ports
    )
    callouts = results[0]["callouts"]   # one entry per view, callouts inline
    drawn = [item for item in callouts if item["id"].startswith("port_")]
    assert len(drawn) == 1
    assert drawn[0]["text"] == "plate.central_bore: 10 -> 9.9  (-0.1)"
    assert drawn[0]["measured_mm"] == [9.9]

    rendered = json.loads((tmp_path / "review_drawing_ports_top.json").read_text())
    assert rendered["callouts"]


def test_ports_are_not_annotated_unless_requested(tmp_path):
    shape = _plate_with_bore(9.9)
    spec = {
        "schema": "cad.review-drawing/v1",
        "views": [{"name": "plain", "view": "top", "hidden_lines": False}],
    }
    ports = {
        "plate": [
            {
                "id": "central_bore",
                "type": "cylindrical_bore",
                "frame": {"origin_mm": [0.0, 0.0, 0.0], "axis": [0.0, 0.0, 1.0]},
                "dimensions_mm": {"diameter": 10.0},
            }
        ]
    }
    results = render_review_drawings(shape, spec, tmp_path, declared_ports=ports)
    assert results[0]["callouts"] == []


# --------------------------------------------------------------------------
# A section must show material, not just outlines
# --------------------------------------------------------------------------


def test_section_faces_are_filled():
    """Outlines alone cannot separate material from void."""

    shape = Box(20, 20, 20)
    section = {"origin": [0.0, 0.0, 0.0], "normal": [0.0, 1.0, 0.0], "keep": "bottom"}
    working, parsed = _apply_section(shape, section, "section")
    target, right, up = (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)

    polygons = _section_fill_polygons(
        working, parsed, target=target, screen_right=right, screen_up=up
    )
    assert polygons, "the cut face must be reported for filling"

    xs = [point[0] for triangle in polygons for point in triangle]
    ys = [point[1] for triangle in polygons for point in triangle]
    # The cut through a 20 mm cube kept below y=0 is the full 20x20 square.
    assert max(xs) - min(xs) == pytest.approx(20.0, abs=1e-6)
    assert max(ys) - min(ys) == pytest.approx(20.0, abs=1e-6)


def test_no_section_means_nothing_to_fill():
    assert _section_fill_polygons(
        Box(10, 10, 10), None, target=(0.0, 0.0, 0.0),
        screen_right=(1.0, 0.0, 0.0), screen_up=(0.0, 0.0, 1.0)
    ) == []
