"""Pytest configuration and fixtures"""

import pytest
import tempfile
import shutil
from pathlib import Path


@pytest.fixture
def tmp_path():
    """Create a temporary directory that is cleaned up after test"""
    tmpdir = Path(tempfile.mkdtemp())
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)
