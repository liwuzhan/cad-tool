import pytest
from build123d import Box, Compound, Pos

from cad_cli.package import ModelPackage
from cad_cli.feedback.camera import STANDARD_VIEWS
from cad_cli.feedback.renderer_v2 import OffscreenRendererV2
from cad_cli.runtime.executor_v2 import ScriptExecutorV2
from cad_cli.runtime.validator import GeometryValidator
from cad_cli.utils.geometry import compute_metrics


def test_assembly_package_template_runs_and_allows_multiple_solids(tmp_path):
    package = ModelPackage.create(tmp_path / "fixture", name="Fixture", kind="assembly")

    assert package.get_manifest().kind == "assembly"
    assert "Compound(children=components)" in package.get_default_script().read_text(encoding="utf-8")
    assert "组件表" in package.get_design_doc().read_text(encoding="utf-8")

    shape, error = ScriptExecutorV2(package).execute(package.get_default_script())

    assert error is None
    assert len(shape.solids()) == 1
    assert GeometryValidator().validate(shape, allow_multiple_solids=True) == []


def test_assembly_metrics_aggregate_disconnected_solids():
    first = Box(10, 10, 10)
    second = Pos(20, 0, 0) * Box(10, 10, 10)
    assembly = Compound(children=[first, second])

    metrics = compute_metrics(assembly)

    assert metrics.solid_count == 2
    assert metrics.volume == pytest.approx(2000)
    assert metrics.bbox == (-5.0, -5.0, -5.0, 25.0, 5.0, 5.0)

    strict_errors = GeometryValidator().validate(assembly)
    assert any(error.type == "MultipleDisconnectedSolids" for error in strict_errors)
    assert GeometryValidator().validate(assembly, allow_multiple_solids=True) == []


def test_existing_packages_default_to_part(tmp_path):
    package = ModelPackage.create(tmp_path / "part", name="Part")
    assert package.get_manifest().kind == "part"


def test_headless_renderer_colors_solids_without_vtk(tmp_path, monkeypatch):
    package = ModelPackage.create(tmp_path / "render", name="Render", kind="assembly")
    assembly = Compound(children=[Box(10, 10, 10), Pos(20, 0, 0) * Box(10, 10, 10)])
    output = tmp_path / "assembly.png"
    monkeypatch.setenv("CAD_RENDER_BACKEND", "matplotlib")

    metadata = OffscreenRendererV2(package).render(assembly, STANDARD_VIEWS["iso"], output)

    assert output.is_file()
    assert output.stat().st_size > 1000
    assert metadata["backend"] == "matplotlib"
