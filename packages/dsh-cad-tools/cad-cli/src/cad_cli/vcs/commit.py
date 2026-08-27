"""Commit data structure and utilities"""

import hashlib
from datetime import datetime
from typing import Optional, Dict, Any

from ..models import CommitData, GeometryMetrics


def create_commit_hash(message: str, timestamp: datetime) -> str:
    """
    Create a commit hash from message and timestamp

    Args:
        message: Commit message
        timestamp: Commit timestamp

    Returns:
        8-character hash string
    """
    content = f"{timestamp.isoformat()}{message}"
    return hashlib.sha256(content.encode()).hexdigest()[:8]


def commit_to_dict(commit: CommitData) -> Dict[str, Any]:
    """
    Convert CommitData to dictionary for serialization

    Args:
        commit: CommitData object

    Returns:
        Dictionary representation
    """
    return commit.to_dict()


def dict_to_commit(data: Dict[str, Any]) -> CommitData:
    """
    Convert dictionary to CommitData

    Args:
        data: Dictionary representation

    Returns:
        CommitData object
    """
    return CommitData(
        hash=data['hash'],
        message=data['message'],
        timestamp=data['timestamp'],
        script_path=data['script_path'],
        metrics=data.get('metrics'),
        thumbnail_path=data.get('thumbnail_path')
    )
