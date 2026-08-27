import json
from pathlib import Path

import pytest
from build123d import Box, Compound, Pos

from cad_cli.feedback.review_drawing import ReviewDrawingError, render_review_drawings


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
