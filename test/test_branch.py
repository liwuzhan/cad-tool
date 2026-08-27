"""Tests for branch management via Repository"""

import pytest
from pathlib import Path
import tempfile
import shutil

from cad_cli.package import ModelPackage
from cad_cli.vcs.repository_v2 import Repository
from cad_cli.vcs.commits import CommitRecord


@pytest.fixture
def package(tmp_path):
    """Create a test package with one commit"""
    pkg_path = tmp_path / "test.456d"
    pkg = ModelPackage.create(pkg_path, name="Test")

    # Add a commit manually so we have a HEAD
    from cad_cli.vcs.commits import CommitHistory, generate_commit_hash
    from datetime import datetime

    history = CommitHistory(pkg.vcs_dir)
    ts = datetime.now().isoformat()
    h = generate_commit_hash("initial", datetime.now())
    record = CommitRecord(
        hash=h, message="initial", timestamp=ts,
        script_path="src/main.py", branch="main"
    )
    history.append(record)

    # Update manifest to point to this commit
    pkg.update_manifest(head=h)
    pkg.manifest_manager.update_nested("branches.main", h)

    return pkg


def test_list_branches(package):
    """Test listing branches - should have 'main' by default"""
    repo = Repository(package)
    branches = repo.list_branches()

    assert len(branches) >= 1
    main_branch = next(b for b in branches if b["name"] == "main")
    assert main_branch["is_current"] is True


def test_create_branch(package):
    """Test creating a new branch"""
    repo = Repository(package)

    branch_info, error = repo.create_branch("feature")
    assert error is None
    assert branch_info["name"] == "feature"
    assert branch_info["head"] is not None

    # Verify it appears in the branch list
    branches = repo.list_branches()
    names = [b["name"] for b in branches]
    assert "feature" in names


def test_create_branch_duplicate(package):
    """Test creating a branch with duplicate name fails"""
    repo = Repository(package)
    repo.create_branch("feature")

    _, error = repo.create_branch("feature")
    assert error is not None
    assert "already exists" in error.message


def test_switch_branch(package):
    """Test switching to a branch"""
    repo = Repository(package)
    repo.create_branch("feature")

    result, error = repo.switch_branch("feature")
    assert error is None
    assert result["name"] == "feature"

    # Verify current branch changed
    manifest = package.get_manifest()
    assert manifest.current_branch == "feature"


def test_switch_nonexistent_branch(package):
    """Test switching to non-existent branch fails"""
    repo = Repository(package)

    _, error = repo.switch_branch("nonexistent")
    assert error is not None
    assert "does not exist" in error.message


def test_delete_branch(package):
    """Test deleting a branch"""
    repo = Repository(package)
    repo.create_branch("feature")

    result, error = repo.delete_branch("feature")
    assert error is None
    assert result["name"] == "feature"

    # Verify it's gone
    branches = repo.list_branches()
    names = [b["name"] for b in branches]
    assert "feature" not in names


def test_delete_main_branch_fails(package):
    """Test deleting 'main' branch is not allowed"""
    repo = Repository(package)

    _, error = repo.delete_branch("main")
    assert error is not None
    assert "Cannot delete" in error.message


def test_delete_current_branch_fails(package):
    """Test deleting the current branch without force fails"""
    repo = Repository(package)
    repo.create_branch("feature")
    repo.switch_branch("feature")

    _, error = repo.delete_branch("feature")
    assert error is not None
    assert "current" in error.message.lower() or "force" in error.message.lower()


def test_delete_current_branch_with_force(package):
    """Test force-deleting the current branch switches to main"""
    repo = Repository(package)
    repo.create_branch("feature")
    repo.switch_branch("feature")

    result, error = repo.delete_branch("feature", force=True)
    assert error is None

    # Should have switched back to main
    manifest = package.get_manifest()
    assert manifest.current_branch == "main"


def test_create_branch_no_commits(tmp_path):
    """Test creating branch with no commits fails"""
    pkg_path = tmp_path / "empty.456d"
    pkg = ModelPackage.create(pkg_path, name="Empty")

    repo = Repository(pkg)
    _, error = repo.create_branch("feature")
    assert error is not None
    assert "no commits" in error.message.lower()


def test_create_branch_from_specific_commit(package):
    """Test creating a branch from a specific commit"""
    repo = Repository(package)
    head = repo.get_head()

    branch_info, error = repo.create_branch("from_commit", from_commit=head.hash)
    assert error is None
    assert branch_info["head"] == head.hash
