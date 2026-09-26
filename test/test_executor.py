"""Tests for script executor v2"""

import pytest
from pathlib import Path
import tempfile

from cad_cli.package import ModelPackage
from cad_cli.runtime.executor_v2 import ScriptExecutorV2


@pytest.fixture
def package(tmp_path):
    """Create a test package"""
    package_path = tmp_path / "test.456d"
    pkg = ModelPackage.create(package_path, name="Test")
    return pkg


def test_execute_simple_script(package):
    """Test executing a simple valid script"""
    script = package.src_dir / "test_box.py"
    script.write_text(
        "from build123d import *\n"
        "result = Box(10, 10, 10)\n"
    )

    executor = ScriptExecutorV2(package)
    shape, error = executor.execute(script)

    assert error is None
    assert shape is not None
    assert abs(shape.volume - 1000) < 0.1


def test_execute_missing_result(package):
    """Test script without result variable"""
    script = package.src_dir / "no_result.py"
    script.write_text(
        "from build123d import *\n"
        "box = Box(10, 10, 10)\n"
    )

    executor = ScriptExecutorV2(package)
    shape, error = executor.execute(script)

    assert shape is None
    assert error is not None
    assert error.code == "E-RUNTIME"
    assert "result" in error.message.lower()


def test_execute_syntax_error(package):
    """Test script with syntax error"""
    script = package.src_dir / "syntax_error.py"
    script.write_text(
        "from build123d import *\n"
        "result = Box(10, 10, 10\n"  # Missing closing paren
    )

    executor = ScriptExecutorV2(package)
    shape, error = executor.execute(script)

    assert shape is None
    assert error is not None
    assert error.code == "E-SYNTAX"


def test_execute_runtime_error(package):
    """Test script with runtime error"""
    script = package.src_dir / "runtime_error.py"
    script.write_text(
        "from build123d import *\n"
        "result = 1 / 0\n"
    )

    executor = ScriptExecutorV2(package)
    shape, error = executor.execute(script)

    assert shape is None
    assert error is not None
    assert error.code == "E-RUNTIME"


def test_execute_invalid_result_type(package):
    """Test script that sets result to non-Shape"""
    script = package.src_dir / "invalid_result.py"
    script.write_text(
        "result = 42\n"
    )

    executor = ScriptExecutorV2(package)
    shape, error = executor.execute(script)

    assert shape is None
    assert error is not None
    assert "Shape object" in error.message


def test_no_pickle_caching(package):
    """Test that v2 doesn't create pickle files"""
    script = package.src_dir / "box.py"
    script.write_text(
        "from build123d import *\n"
        "result = Box(10, 10, 10)\n"
    )

    executor = ScriptExecutorV2(package)
    shape, error = executor.execute(script)

    assert error is None

    # Check no pickle file was created
    pickle_path = package.runlog_dir / "current_shape.pkl"
    assert not pickle_path.exists()


def test_execute_resolves_relative_script_before_changing_subprocess_cwd(package, monkeypatch):
    script = package.src_dir / "relative.py"
    script.write_text("from build123d import Box\nresult = Box(2, 3, 4)\n")
    monkeypatch.chdir(package.package_path)

    shape, error = ScriptExecutorV2(package).execute(Path("src/relative.py"))

    assert error is None
    assert shape.volume == pytest.approx(24)


def test_executed_script_can_locate_itself_via_dunder_file(package):
    """Scripts must be able to locate their own package without guessing cwd.

    The runner exec()s the source, so __file__ has to be seeded explicitly.
    Without it a script that needs a sibling file (ports.py, a data table) can
    only rely on the process cwd, which is an implicit contract that breaks as
    soon as the execution context changes.
    """

    script = package.src_dir / "locate.py"
    script.write_text(
        "from pathlib import Path\n"
        "from build123d import *\n"
        "assert Path(__file__).name == 'locate.py', __file__\n"
        "assert Path(__file__).resolve().parent.name == 'src'\n"
        "result = Box(1, 1, 1)\n"
    )

    executor = ScriptExecutorV2(package)
    shape, error = executor.execute(script)

    assert error is None, error
    assert shape is not None


def test_script_can_read_a_sibling_contract_file(package):
    """The reason __file__ matters: reading the package's own declarations."""

    (package.package_path / "ports.py").write_text("PORTS = {'p': []}\n", encoding="utf-8")
    script = package.src_dir / "reads_contract.py"
    script.write_text(
        "import importlib.util\n"
        "from pathlib import Path\n"
        "from build123d import *\n"
        "_p = Path(__file__).resolve().parents[1] / 'ports.py'\n"
        "_s = importlib.util.spec_from_file_location('_c', _p)\n"
        "_m = importlib.util.module_from_spec(_s)\n"
        "_s.loader.exec_module(_m)\n"
        "assert _m.PORTS == {'p': []}\n"
        "result = Box(1, 1, 1)\n"
    )

    executor = ScriptExecutorV2(package)
    shape, error = executor.execute(script)

    assert error is None, error
    assert shape is not None
