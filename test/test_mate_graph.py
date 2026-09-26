"""Tests for the package-side mate graph builder.

The property that matters most: the check reads declarations only. If it ever
starts executing ``src/main.py``, the "type-check before codegen" ordering is
gone and the whole point of P2 with it — so that is asserted directly, not
assumed.
"""

import json
from pathlib import Path

import pytest

from cad_cli.package.mates import (
    MateCheckError,
    build_instances,
    check_package,
    load_declared_ports,
)


def make_package(tmp_path: Path, *, deps=None, mates=None, ports=None, main=None) -> Path:
    """Create a minimal .456d package tree for the checker to read."""

    package = tmp_path / "demo.456d"
    (package / "src").mkdir(parents=True)
    manifest = {
        "name": "demo",
        "kind": "assembly",
        "deps": deps or [],
        "mates": mates or [],
    }
    (package / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    if ports is not None:
        (package / "ports.py").write_text(ports, encoding="utf-8")
    (package / "src" / "main.py").write_text(
        main if main is not None else "raise RuntimeError('should never run')\n",
        encoding="utf-8",
    )
    return package


class Metadata:
    """Stand-in for PackageMetadata with just the fields the builder reads."""

    def __init__(self, deps=None, mates=None, name="demo"):
        self.deps = deps or []
        self.mates = mates or []
        self.name = name


SIMPLE_PORTS = '''
PORTS = {
    "shaft": [
        {"id": "seat", "type": "cylindrical_surface",
         "frame": {"origin_mm": [0, 0, 0], "axis": [0, 0, 1]},
         "dimensions_mm": {"diameter": 20.0, "length": 14.0}},
    ],
}
'''

BEARING_DEP = [{
    "name": "bearing_a",
    "std": {"family": "bearing.deep_groove", "params": {"code": "6204"}, "lib": "0.2.0"},
}]
SEAT_MATE = [{"a": "shaft.seat", "b": "bearing_a.shaft_bore", "why": "seat"}]


# --------------------------------------------------------------------------
# The ordering guarantee
# --------------------------------------------------------------------------

def test_check_runs_even_when_main_py_cannot_execute(tmp_path):
    """main.py raises on import; the mate check must not care."""

    package = make_package(
        tmp_path, deps=BEARING_DEP, mates=SEAT_MATE, ports=SIMPLE_PORTS,
        main="raise RuntimeError('geometry cannot be produced')\n",
    )
    result = check_package(package, Metadata(deps=BEARING_DEP, mates=SEAT_MATE))
    assert result["overall"] == "PASS"


def test_check_does_not_import_the_main_script(tmp_path):
    """A main.py with an import side effect must never fire."""

    marker = tmp_path / "executed.marker"
    package = make_package(
        tmp_path, deps=BEARING_DEP, mates=SEAT_MATE, ports=SIMPLE_PORTS,
        main=f"open({str(marker)!r}, 'w').close()\n",
    )
    check_package(package, Metadata(deps=BEARING_DEP, mates=SEAT_MATE))
    assert not marker.exists()


# --------------------------------------------------------------------------
# ports.py loading
# --------------------------------------------------------------------------

def test_missing_ports_file_is_not_an_error(tmp_path):
    package = make_package(tmp_path)
    assert load_declared_ports(package) == ({}, [])


def test_ports_file_is_parsed_into_instances(tmp_path):
    package = make_package(tmp_path, ports=SIMPLE_PORTS)
    instances, warnings = load_declared_ports(package)
    assert warnings == []
    assert instances["shaft"][0]["id"] == "seat"


def test_ports_file_without_ports_is_rejected(tmp_path):
    package = make_package(tmp_path, ports="X = 1\n")
    with pytest.raises(MateCheckError, match="没有定义 PORTS"):
        load_declared_ports(package)


def test_ports_must_be_a_mapping(tmp_path):
    package = make_package(tmp_path, ports="PORTS = [1, 2]\n")
    with pytest.raises(MateCheckError, match="映射"):
        load_declared_ports(package)


def test_port_entries_must_carry_id_and_type(tmp_path):
    package = make_package(tmp_path, ports='PORTS = {"shaft": [{"id": "seat"}]}\n')
    with pytest.raises(MateCheckError, match="缺少 id 或 type"):
        load_declared_ports(package)


def test_broken_ports_file_reports_the_author_error(tmp_path):
    package = make_package(tmp_path, ports="raise ValueError('boom')\n")
    with pytest.raises(MateCheckError, match="执行失败"):
        load_declared_ports(package)


def test_building_geometry_in_ports_file_is_warned_about(tmp_path):
    """ports.py is meant to declare, not model.

    Declaring is what keeps the check cheaper than the step it guards; silently
    building solids there would defeat it without anyone noticing.
    """

    package = make_package(tmp_path, ports=(
        "class FakeShape:\n"
        "    solids = (1, 2)\n"
        "    volume = 3.0\n"
        "X = FakeShape()\n"
        + SIMPLE_PORTS
    ))
    instances, warnings = load_declared_ports(package)
    assert "shaft" in instances
    assert any("只做声明" in item for item in warnings)


# --------------------------------------------------------------------------
# Dependency resolution
# --------------------------------------------------------------------------

def test_standard_dependency_resolves_through_the_catalogue(tmp_path):
    package = make_package(tmp_path, ports=SIMPLE_PORTS)
    instances, _ = build_instances(Metadata(deps=BEARING_DEP), package)
    assert "bearing_a" in instances
    bore = next(item for item in instances["bearing_a"] if item["id"] == "shaft_bore")
    assert bore["dimensions_mm"]["diameter"] == pytest.approx(20.0)


def test_duplicate_instance_name_is_rejected(tmp_path):
    package = make_package(tmp_path, ports='PORTS = {"bearing_a": []}\n')
    with pytest.raises(MateCheckError, match="实例名重复"):
        build_instances(Metadata(deps=BEARING_DEP), package)


def test_pkg_dependency_is_skipped_with_a_warning(tmp_path):
    package = make_package(tmp_path)
    deps = [{"name": "frame", "pkg": {"package": "frame.456d", "commit": "abc123"}}]
    instances, warnings = build_instances(Metadata(deps=deps), package)
    assert "frame" not in instances
    assert any("尚未实现" in item for item in warnings)


def test_dependency_without_a_spec_is_rejected(tmp_path):
    package = make_package(tmp_path)
    with pytest.raises(MateCheckError, match="既没有 std 也没有 pkg"):
        build_instances(Metadata(deps=[{"name": "x"}]), package)


def test_bad_standard_spec_reports_a_clear_error(tmp_path):
    package = make_package(tmp_path)
    with pytest.raises(MateCheckError, match="缺少 std 规格"):
        build_instances(Metadata(deps=[{"name": "x", "std": "not-a-mapping"}]), package)


# --------------------------------------------------------------------------
# End-to-end verdicts over a real package tree
# --------------------------------------------------------------------------

def bearing_dep(code: str):
    return [{"name": "bearing_a",
             "std": {"family": "bearing.deep_groove", "params": {"code": code}}}]


def seat_ports(code: str) -> str:
    return (
        "from cadparts import Seat, ShaftSpec, shaft_dimensions\n"
        "from cadparts.interfaces import resolve_interfaces\n"
        f"SPEC = ShaftSpec(stations=(Seat('bearing.deep_groove', {{'code': '{code}'}},"
        " 'shaft_bore', role='support_a'),))\n"
        "PORTS = {'shaft': resolve_interfaces('shaft.stepped', {}, shaft_dimensions(SPEC))}\n"
    )


def test_nominal_match_passes(tmp_path):
    package = make_package(tmp_path, deps=bearing_dep("6204"),
                           mates=[{"a": "shaft.seat_support_a", "b": "bearing_a.shaft_bore"}],
                           ports=seat_ports("6204"))
    result = check_package(package, Metadata(deps=bearing_dep("6204"), mates=[
        {"a": "shaft.seat_support_a", "b": "bearing_a.shaft_bore"}]))
    assert result["overall"] == "PASS"


def test_manifest_and_ports_drift_is_caught(tmp_path):
    """The manifest says 6205, ports.py sized the shaft for 6204.

    This is the drift the check exists to catch: two declarations that were
    supposed to agree no longer do.
    """

    mates = [{"a": "shaft.seat_support_a", "b": "bearing_a.shaft_bore"}]
    package = make_package(tmp_path, deps=bearing_dep("6205"), mates=mates,
                           ports=seat_ports("6204"))
    result = check_package(package, Metadata(deps=bearing_dep("6205"), mates=mates))
    assert result["overall"] == "WARN"
    assert "公称尺寸不符" in result["verdicts"][0]["reason"]


def test_undersized_bore_fails(tmp_path):
    mates = [{"a": "shaft.seat_support_a", "b": "bearing_a.shaft_bore"}]
    package = make_package(tmp_path, deps=bearing_dep("6204"), mates=mates,
                           ports=seat_ports("6205"))
    result = check_package(package, Metadata(deps=bearing_dep("6204"), mates=mates))
    assert result["overall"] == "FAIL"
    assert "装不进去" in result["verdicts"][0]["reason"]


def test_result_carries_coverage_and_boundary(tmp_path):
    mates = [{"a": "shaft.seat_support_a", "b": "bearing_a.shaft_bore"}]
    package = make_package(tmp_path, deps=bearing_dep("6204"), mates=mates,
                           ports=seat_ports("6204"))
    result = check_package(package, Metadata(deps=bearing_dep("6204"), mates=mates))

    assert result["package"] == "demo"
    assert result["instances"]["shaft"]
    assert result["coverage"]["unmated_ports"], "本用例应当有未被引用的接口"
    assert result["boundary"]["not_checked"]
