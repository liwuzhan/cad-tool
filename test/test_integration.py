"""Integration tests for the full CLI workflow"""

import pytest
import os
import subprocess
import sys
import json
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def test_dir():
    """Create a temporary directory"""
    tmpdir = Path(tempfile.mkdtemp())
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


def run_cad(args, cwd=None):
    """Run cad CLI command and return parsed output"""
    cmd = [sys.executable, "-m", "cad_cli"] + args
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True
    )
    return result


def parse_jsonl(text):
    """Parse JSONL output, return last event"""
    events = []
    for line in text.strip().split('\n'):
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events


def test_init_creates_package(test_dir):
    """Test cad init creates a valid package"""
    result = run_cad(["init", "my_model", "--name=My Model"], cwd=test_dir)
    assert result.returncode == 0

    events = parse_jsonl(result.stdout)
    assert any(e["event"] == "init_success" for e in events)

    # Verify package structure
    package = test_dir / "my_model.456d"
    assert package.exists()
    assert (package / "manifest.json").exists()
    assert (package / "src" / "main.py").exists()


def test_run_executes_script(test_dir):
    """Test cad run executes script correctly"""
    # Create package
    run_cad(["init", "test", "--name=Test"], cwd=test_dir)
    package = test_dir / "test.456d"

    # Run default script
    result = run_cad(["run"], cwd=package)
    assert result.returncode == 0

    events = parse_jsonl(result.stdout)
    success_events = [e for e in events if e["event"] == "run_success"]
    assert len(success_events) == 1

    # Check metrics
    metrics = success_events[0]["payload"]["metrics"]
    assert "volume" in metrics
    assert "area" in metrics
    assert "face_count" in metrics


def test_commit_creates_artifacts(test_dir):
    """Test cad commit creates all artifacts"""
    # Create package
    run_cad(["init", "test", "--name=Test"], cwd=test_dir)
    package = test_dir / "test.456d"

    # Commit
    result = run_cad(["commit", "-m", "Initial commit"], cwd=package)
    assert result.returncode == 0

    events = parse_jsonl(result.stdout)
    success_events = [e for e in events if e["event"] == "commit_success"]
    assert len(success_events) == 1

    commit_hash = success_events[0]["payload"]["hash"]

    # Verify artifacts
    artifacts = package / "artifacts" / commit_hash
    assert (artifacts / "model.step").exists()
    assert (artifacts / "metrics.json").exists()
    # Headless CI can explicitly skip the optional PNG preview layer while
    # still testing geometry, STEP, metrics, validation, and version history.
    if os.environ.get("CAD_SKIP_RENDER", "").strip().lower() not in {"1", "true", "yes", "on"}:
        thumbnails = list(artifacts.glob("thumb_*.png"))
        assert len(thumbnails) > 0


def test_log_shows_history(test_dir):
    """Test cad log shows commit history"""
    # Create package and commit
    run_cad(["init", "test", "--name=Test"], cwd=test_dir)
    package = test_dir / "test.456d"
    run_cad(["commit", "-m", "First commit"], cwd=package)
    run_cad(["commit", "-m", "Second commit"], cwd=package)

    # Check log
    result = run_cad(["log"], cwd=package)
    assert result.returncode == 0

    events = parse_jsonl(result.stdout)
    log_events = [e for e in events if e["event"] == "log_result"]
    assert len(log_events) == 1

    commits = log_events[0]["payload"]["commits"]
    assert len(commits) == 2
    assert commits[0]["message"] == "Second commit"
    assert commits[1]["message"] == "First commit"


def test_status_shows_info(test_dir):
    """Test cad status shows repository info"""
    # Create package
    run_cad(["init", "test", "--name=Test"], cwd=test_dir)
    package = test_dir / "test.456d"

    # Status before commit
    result = run_cad(["status"], cwd=package)
    assert result.returncode == 0

    events = parse_jsonl(result.stdout)
    status_events = [e for e in events if e["event"] == "status_result"]
    status = status_events[0]["payload"]
    assert status["head"] is None
    assert status["total_commits"] == 0

    # Commit and check again
    run_cad(["commit", "-m", "First"], cwd=package)
    result = run_cad(["status"], cwd=package)
    events = parse_jsonl(result.stdout)
    status_events = [e for e in events if e["event"] == "status_result"]
    status = status_events[0]["payload"]
    assert status["head"] is not None
    assert status["total_commits"] == 1


def test_checkout_loads_step(test_dir):
    """Test cad checkout loads STEP artifact"""
    # Create package and commit
    run_cad(["init", "test", "--name=Test"], cwd=test_dir)
    package = test_dir / "test.456d"
    commit_result = run_cad(["commit", "-m", "Initial"], cwd=package)
    events = parse_jsonl(commit_result.stdout)
    commit_hash = [e for e in events if e["event"] == "commit_success"][0]["payload"]["hash"]

    # Checkout
    result = run_cad(["checkout", commit_hash], cwd=package)
    assert result.returncode == 0

    events = parse_jsonl(result.stdout)
    success_events = [e for e in events if e["event"] == "checkout_success"]
    assert len(success_events) == 1
    assert "metrics" in success_events[0]["payload"]


def test_artifacts_list(test_dir):
    """Test cad artifacts list shows artifacts"""
    # Create package and commit
    run_cad(["init", "test", "--name=Test"], cwd=test_dir)
    package = test_dir / "test.456d"
    run_cad(["commit", "-m", "Initial"], cwd=package)

    # List artifacts
    result = run_cad(["artifacts", "list"], cwd=package)
    assert result.returncode == 0

    events = parse_jsonl(result.stdout)
    list_events = [e for e in events if e["event"] == "artifacts_list"]
    assert len(list_events) == 1
    assert "total_size_bytes" in list_events[0]["payload"]
