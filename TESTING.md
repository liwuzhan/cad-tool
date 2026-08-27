# Testing Guide

## Running Tests

### Run All Tests

```bash
pytest
```

### Run with Coverage

```bash
pytest --cov=cad_cli --cov-report=html
```

View coverage report:
```bash
# Windows
start htmlcov/index.html

# Linux/Mac
open htmlcov/index.html
```

### Run Specific Test Modules

```bash
# Runtime tests
pytest test/test_runtime/

# VCS tests
pytest test/test_vcs/

# Feedback tests
pytest test/test_feedback/

# Integration tests
pytest test/test_cli/
```

### Run Specific Test

```bash
pytest test/test_runtime/test_executor.py::test_execute_valid_script
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Print Statements

```bash
pytest -s
```

## Test Structure

```
test/
├── conftest.py                    # Pytest configuration and fixtures
├── fixtures/
│   └── scripts/                   # Test scripts
│       ├── simple_box.py
│       ├── invalid_syntax.py
│       └── runtime_error.py
├── test_runtime/
│   ├── test_executor.py          # Script execution tests
│   └── test_validator.py         # Geometry validation tests
├── test_feedback/
│   ├── test_inspector.py         # Inspection tests
│   ├── test_renderer.py          # Rendering tests
│   └── test_exporter.py          # Export tests
├── test_vcs/
│   └── test_repository.py        # Version control tests
├── test_cli/
│   └── test_integration.py       # End-to-end CLI tests
└── test_utils/
    └── test_jsonl.py             # JSONL output tests
```

## Available Fixtures

### temp_project
Creates a temporary project directory that is cleaned up after the test.

```python
def test_something(temp_project):
    # temp_project is a Path object
    script = temp_project / "test.py"
    script.write_text("from build123d import *\nresult = Box(10, 10, 10)")
```

### initialized_repo
Creates a temporary project with `.cad/` directory initialized.

```python
def test_something(initialized_repo):
    # initialized_repo is a Path object with .cad/ already set up
    assert (initialized_repo / ".cad").exists()
```

### simple_box_script
Creates a valid build123d script that creates a 10x10x10 box.

```python
def test_something(simple_box_script):
    # simple_box_script is a Path to the script file
    executor = ScriptExecutor(simple_box_script.parent)
    shape, error = executor.execute(simple_box_script)
```

### invalid_syntax_script
Creates a script with a syntax error (missing closing parenthesis).

### runtime_error_script
Creates a script with a runtime error (undefined variable).

### missing_result_script
Creates a script that doesn't define the `result` variable.

### cli_runner
Click CLI test runner for testing CLI commands.

```python
def test_command(cli_runner):
    result = cli_runner.invoke(cli, ['init'])
    assert result.exit_code == 0
```

## Writing New Tests

### Test Naming Convention

- Test files: `test_*.py`
- Test functions: `test_*`
- Test classes: `Test*`

### Example Test

```python
import pytest
from cad_cli.runtime.executor import ScriptExecutor

def test_execute_box(initialized_repo, simple_box_script):
    """Test executing a simple box script"""
    executor = ScriptExecutor(initialized_repo)
    shape, error = executor.execute(simple_box_script)

    assert error is None
    assert shape is not None
    assert shape.volume == pytest.approx(1000, abs=1)
```

### Testing Error Conditions

```python
def test_invalid_script(initialized_repo, invalid_syntax_script):
    """Test handling of syntax errors"""
    executor = ScriptExecutor(initialized_repo)
    shape, error = executor.execute(invalid_syntax_script)

    assert shape is None
    assert error is not None
    assert error.code == ErrorCode.E_SYNTAX
```

### Testing CLI Commands

```python
def test_run_command(initialized_repo, simple_box_script, cli_runner):
    """Test run command"""
    result = cli_runner.invoke(cli, ['run', str(simple_box_script)],
                               cwd=str(initialized_repo))

    assert result.exit_code == 0
    assert "run_success" in result.output
```

## Test Coverage Goals

- **Runtime module**: 90%+ coverage
- **VCS module**: 85%+ coverage
- **Feedback module**: 80%+ coverage (rendering may be lower due to pyvista)
- **CLI**: 85%+ coverage
- **Overall**: 85%+ coverage

## Continuous Integration

For CI/CD pipelines, use:

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests with coverage
pytest --cov=cad_cli --cov-report=xml --cov-report=term

# Check coverage threshold
pytest --cov=cad_cli --cov-fail-under=85
```

## Known Test Limitations

### Rendering Tests

Rendering tests may fail in headless environments without proper graphics support. These tests are marked and can be skipped:

```bash
pytest -m "not rendering"
```

### Timeout Tests

Timeout tests may be flaky on slow systems. Adjust timeout values in `constants.py` if needed.

## Debugging Tests

### Run with PDB

```bash
pytest --pdb
```

This will drop into the Python debugger on test failures.

### Run Last Failed Tests

```bash
pytest --lf
```

### Show Local Variables on Failure

```bash
pytest -l
```

## Performance Testing

For performance testing, use:

```bash
pytest --durations=10
```

This shows the 10 slowest tests.

## Test Data

Test scripts are located in `test/fixtures/scripts/`. Add new test scripts there as needed.

## Mocking

For tests that require mocking (e.g., file I/O, external dependencies):

```python
from unittest.mock import patch, MagicMock

def test_with_mock():
    with patch('cad_cli.feedback.renderer.pv.Plotter') as mock_plotter:
        mock_plotter.return_value = MagicMock()
        # Test code here
```
