"""Tests for model package management"""

import pytest
from pathlib import Path
import tempfile
import shutil

from cad_cli.package import ModelPackage, PackageMetadata, ManifestManager


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    tmpdir = Path(tempfile.mkdtemp())
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_create_model_package(temp_dir):
    """Test creating a new model package"""
    package_path = temp_dir / "test_model.456d"
    package = ModelPackage.create(package_path, name="Test Model")

    assert package.package_path.exists()
    assert package.package_path.is_dir()
    assert str(package.package_path).endswith(".456d")
    assert (package.package_path / "manifest.json").exists()
    assert (package.package_path / "src").exists()
    assert (package.package_path / "vcs").exists()
    assert (package.package_path / "artifacts").exists()
    assert (package.package_path / "runlog").exists()
    assert (package.package_path / "src" / "main.py").exists()


def test_package_manifest(temp_dir):
    """Test manifest management"""
    package_path = temp_dir / "test_model.456d"
    package = ModelPackage.create(package_path, name="Test Model")

    manifest = package.get_manifest()
    assert manifest.name == "Test Model"
    assert manifest.version == "2.0.0"
    assert manifest.unit == "mm"
    assert manifest.timeout_seconds == 60


def test_update_manifest(temp_dir):
    """Test updating manifest"""
    package_path = temp_dir / "test_model.456d"
    package = ModelPackage.create(package_path, name="Test Model")

    package.update_manifest(head="abc123", timeout_seconds=120)
    manifest = package.get_manifest()

    assert manifest.head == "abc123"
    assert manifest.timeout_seconds == 120


def test_open_existing_package(temp_dir):
    """Test opening an existing package"""
    package_path = temp_dir / "test_model.456d"
    package1 = ModelPackage.create(package_path, name="Test Model")

    # Open existing package
    package2 = ModelPackage.open(package_path)
    assert package2.package_path == package1.package_path
    assert package2.get_manifest().name == "Test Model"


def test_find_package(temp_dir):
    """Test finding package from subdirectory"""
    package_path = temp_dir / "test_model.456d"
    package = ModelPackage.create(package_path, name="Test Model")

    # Create a subdirectory inside the package
    subdir = package.src_dir / "submodules"
    subdir.mkdir()

    # Find from subdirectory
    found = ModelPackage.find_package(subdir)
    assert found is not None
    assert found.package_path == package.package_path


def test_package_not_exists():
    """Test opening non-existent package"""
    with pytest.raises(FileNotFoundError):
        ModelPackage.open(Path("/nonexistent/package.456d"))


def test_create_duplicate_package(temp_dir):
    """Test creating duplicate package fails"""
    package_path = temp_dir / "test_model.456d"
    ModelPackage.create(package_path, name="Test Model")

    with pytest.raises(FileExistsError):
        ModelPackage.create(package_path, name="Duplicate")
