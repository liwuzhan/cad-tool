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
