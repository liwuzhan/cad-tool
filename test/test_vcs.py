"""Tests for version control (commits)"""

import pytest
from pathlib import Path
import tempfile
import shutil
from datetime import datetime

from cad_cli.vcs.commits import CommitHistory, CommitRecord, generate_commit_hash


@pytest.fixture
def vcs_dir(tmp_path):
    """Create a temporary VCS directory"""
    vcs = tmp_path / "vcs"
    vcs.mkdir()
    return vcs


def test_generate_commit_hash():
    """Test commit hash generation"""
    timestamp = datetime(2024, 1, 1, 12, 0, 0)
    hash1 = generate_commit_hash("message", timestamp)
    hash2 = generate_commit_hash("message", timestamp)

    assert len(hash1) == 12
    assert hash1 == hash2  # Same input = same hash

    # Different message = different hash
    hash3 = generate_commit_hash("different", timestamp)
    assert hash1 != hash3


def test_commit_record():
    """Test CommitRecord creation"""
    record = CommitRecord(
        hash="abc123",
        message="Test commit",
        timestamp="2024-01-01T12:00:00",
        script_path="src/main.py"
    )

    assert record.hash == "abc123"
    assert record.message == "Test commit"
    assert record.branch == "main"
    assert record.has_step is False


def test_commit_record_to_jsonl():
    """Test JSONL serialization"""
    record = CommitRecord(
        hash="abc123",
        message="Test commit",
        timestamp="2024-01-01T12:00:00",
        script_path="src/main.py",
        has_step=True
    )

    jsonl = record.to_jsonl()
    assert "abc123" in jsonl
    assert "Test commit" in jsonl
    assert "\n" not in jsonl

    # Roundtrip
    parsed = CommitRecord.from_jsonl(jsonl)
    assert parsed.hash == record.hash
    assert parsed.message == record.message


def test_commit_history_append(vcs_dir):
    """Test appending commits"""
    history = CommitHistory(vcs_dir)

    record = CommitRecord(
        hash="abc123",
        message="First commit",
        timestamp="2024-01-01T12:00:00",
        script_path="src/main.py"
    )

    history.append(record)
    commits = history.get_all()

    assert len(commits) == 1
    assert commits[0].hash == "abc123"


def test_commit_history_get_head(vcs_dir):
    """Test getting HEAD commit"""
    history = CommitHistory(vcs_dir)

    # Empty history
    assert history.get_head() is None

    # Add commits
    history.append(CommitRecord(
        hash="first",
        message="First",
        timestamp="2024-01-01T12:00:00",
        script_path="src/main.py"
    ))
    history.append(CommitRecord(
        hash="second",
        message="Second",
        timestamp="2024-01-01T12:01:00",
        script_path="src/main.py"
    ))

    head = history.get_head()
    assert head.hash == "second"


def test_commit_history_find_by_hash(vcs_dir):
    """Test finding commit by hash"""
    history = CommitHistory(vcs_dir)

    history.append(CommitRecord(
        hash="abc123de",
        message="Test",
        timestamp="2024-01-01T12:00:00",
        script_path="src/main.py"
    ))

    # Full hash
    found = history.find_by_hash("abc123de")
    assert found is not None
    assert found.hash == "abc123de"

    # Prefix
    found = history.find_by_hash("abc123")
    assert found is not None

    # Not found
    found = history.find_by_hash("xyz")
    assert found is None


def test_commit_history_get_recent(vcs_dir):
    """Test getting recent commits"""
    history = CommitHistory(vcs_dir)

    for i in range(5):
        history.append(CommitRecord(
            hash=f"hash{i}",
            message=f"Commit {i}",
            timestamp=f"2024-01-01T12:0{i}:00",
            script_path="src/main.py"
        ))

    recent = history.get_recent(3)
    assert len(recent) == 3
    assert recent[0].hash == "hash4"  # Most recent first
    assert recent[2].hash == "hash2"


def test_commit_history_count(vcs_dir):
    """Test counting commits"""
    history = CommitHistory(vcs_dir)

    assert history.count() == 0

    for i in range(3):
        history.append(CommitRecord(
            hash=f"hash{i}",
            message=f"Commit {i}",
            timestamp=f"2024-01-01T12:0{i}:00",
            script_path="src/main.py"
        ))

    assert history.count() == 3
