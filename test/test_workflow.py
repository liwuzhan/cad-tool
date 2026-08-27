"""Tests for BuildWorkflow"""

import pytest
from pathlib import Path
import json

from cad_cli.package import ModelPackage
from cad_cli.runtime.workflow import BuildWorkflow


@pytest.fixture
def package(tmp_path):
    """Create a test package with a valid script"""
    pkg_path = tmp_path / "test.456d"
    pkg = ModelPackage.create(pkg_path, name="Test")

    # Write a valid script
    script = pkg.get_default_script()
    script.write_text(
        "from build123d import *\n"
        "result = Box(10, 10, 10)\n"
    )

    return pkg


def test_build_with_commit(package):
    """Test full build workflow creates commit with artifacts"""
    workflow = BuildWorkflow(package)

    commit_record, error = workflow.build(
        commit_message="Test commit"
    )

    assert error is None, f"Unexpected error: {error}"
    assert commit_record is not None
    assert commit_record.hash
    assert commit_record.message == "Test commit"
    assert commit_record.has_step is True

    # Verify STEP artifact exists
    assert package.artifact_manager.step_exists(commit_record.hash)

    # Verify metrics were saved
    metrics = package.artifact_manager.load_metrics(commit_record.hash)
    assert metrics is not None
    assert abs(metrics["volume"] - 1000) < 1.0


def test_build_without_commit(package):
    """Test build without commit message returns no commit"""
    workflow = BuildWorkflow(package)

    commit_record, error = workflow.build(commit_message=None)

    assert error is None
    assert commit_record is None  # No commit created


def test_build_script_not_found(package):
    """Test build with missing script returns error"""
    workflow = BuildWorkflow(package)

    missing_script = package.src_dir / "nonexistent.py"
    commit_record, error = workflow.build(
        script_path=missing_script,
        commit_message="Should fail"
    )

    assert commit_record is None
    assert error is not None
    assert "not found" in error.message.lower()


def test_build_syntax_error(package):
    """Test build with syntax error in script"""
    script = package.get_default_script()
    script.write_text("from build123d import *\nresult = Box(10, 10, 10\n")  # missing )

    workflow = BuildWorkflow(package)
    commit_record, error = workflow.build(commit_message="Bad syntax")

    assert commit_record is None
    assert error is not None
    assert error.code == "E-SYNTAX"


def test_build_validation_saved(package):
    """Test that validation results are saved"""
    workflow = BuildWorkflow(package)

    commit_record, error = workflow.build(commit_message="Test")
    assert commit_record is not None

    # Load validation results from artifacts
    artifact_dir = package.artifact_manager.get_artifact_dir(commit_record.hash)
    validate_path = artifact_dir / "validate.json"
    assert validate_path.exists()

    with open(validate_path, 'r') as f:
        validation = json.load(f)
    assert "valid" in validation
    assert "errors" in validation


def test_build_updates_manifest(package):
    """Test that build updates manifest HEAD"""
    workflow = BuildWorkflow(package)

    commit_record, _ = workflow.build(commit_message="First")
    manifest = package.get_manifest()
    assert manifest.head == commit_record.hash

    # Second commit
    commit_record2, _ = workflow.build(commit_message="Second")
    manifest = package.get_manifest()
    assert manifest.head == commit_record2.hash


def test_build_script_snapshot_saved(package):
    """Test that script snapshot is saved in artifacts"""
    workflow = BuildWorkflow(package)

    commit_record, _ = workflow.build(commit_message="With script")
    assert commit_record is not None

    script_content = package.artifact_manager.load_script(commit_record.hash)
    assert script_content is not None
    assert "Box(10, 10, 10)" in script_content


def test_build_multiple_commits(package):
    """Test multiple sequential commits"""
    workflow = BuildWorkflow(package)

    hashes = []
    for i in range(3):
        cr, err = workflow.build(commit_message=f"Commit {i}")
        assert err is None
        hashes.append(cr.hash)

    # All hashes should be unique
    assert len(set(hashes)) == 3

    # Manifest HEAD should be the last one
    assert package.get_manifest().head == hashes[-1]
