"""Tests for artifact management"""

import pytest
from pathlib import Path
import tempfile
import shutil

from cad_cli.package import ModelPackage, ArtifactManager


@pytest.fixture
def package(tmp_path):
    """Create a test package"""
    package_path = tmp_path / "test.456d"
    pkg = ModelPackage.create(package_path, name="Test")
    return pkg


def test_artifact_manager_init(package):
    """Test artifact manager initialization"""
    manager = ArtifactManager(package.package_path)
    assert manager.artifacts_dir == package.package_path / "artifacts"


def test_save_and_load_step(package):
    """Test saving and loading STEP files"""
    from build123d import Box

    box = Box(10, 10, 10)
    commit_hash = "abc123"

    # Save STEP
    step_path = package.artifact_manager.save_step(box, commit_hash)
    assert step_path.exists()
    assert step_path.name == "model.step"

    # Load STEP
    loaded_shape = package.artifact_manager.load_step(commit_hash)
    assert loaded_shape is not None
    assert abs(loaded_shape.volume - 1000) < 0.1  # 10^3


def test_save_metrics(package):
    """Test saving metrics"""
    commit_hash = "abc123"
    metrics = {
        "volume": 1000,
        "area": 600,
        "face_count": 6
    }

    metrics_path = package.artifact_manager.save_metrics(commit_hash, metrics)
    assert metrics_path.exists()

    # Load and verify
    loaded = package.artifact_manager.load_metrics(commit_hash)
    assert loaded == metrics


def test_list_artifacts(package):
    """Test listing artifacts"""
    from build123d import Box

    # Create some artifacts
    box = Box(10, 10, 10)
    package.artifact_manager.save_step(box, "commit1")
    package.artifact_manager.save_step(box, "commit2")

    artifacts = package.artifact_manager.list_artifacts()
    commit_hashes = [a["commit"] for a in artifacts]

    assert "commit1" in commit_hashes
    assert "commit2" in commit_hashes


def test_get_total_size(package):
    """Test getting total artifact size"""
    from build123d import Box

    initial_size = package.artifact_manager.get_total_size()

    box = Box(10, 10, 10)
    package.artifact_manager.save_step(box, "commit1")

    after_size = package.artifact_manager.get_total_size()
    assert after_size > initial_size


def test_delete_artifacts(package):
    """Test deleting artifacts"""
    from build123d import Box

    box = Box(10, 10, 10)
    commit_hash = "commit1"
    package.artifact_manager.save_step(box, commit_hash)

    assert package.artifact_manager.step_exists(commit_hash)

    deleted = package.artifact_manager.delete_artifacts(commit_hash)
    assert deleted is True
    assert not package.artifact_manager.step_exists(commit_hash)
