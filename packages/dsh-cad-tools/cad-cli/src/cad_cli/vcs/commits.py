"""JSONL-based commit history management"""

import json
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass
class CommitRecord:
    """A single commit record in the history"""
    hash: str
    message: str
    timestamp: str  # ISO 8601
    script_path: str
    parent_hash: Optional[str] = None
    branch: str = "main"
    metrics_hash: Optional[str] = None
    has_step: bool = False
    has_thumbnails: bool = False

    REQUIRED_FIELDS = {"hash", "message", "timestamp", "script_path"}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CommitRecord":
        missing = cls.REQUIRED_FIELDS - set(data.keys())
        if missing:
            raise ValueError(f"Missing required fields: {missing}")
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_jsonl(self) -> str:
        """Convert to JSONL line (no newline at end)"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_jsonl(cls, line: str) -> "CommitRecord":
        """Parse from JSONL line"""
        data = json.loads(line.strip())
        return cls.from_dict(data)


class CommitHistory:
    """Manages commit history in JSONL format"""

    COMMITS_FILENAME = "commits.jsonl"

    def __init__(self, vcs_dir: Path):
        """
        Initialize commit history

        Args:
            vcs_dir: Path to the vcs/ directory
        """
        self.vcs_dir = vcs_dir
        self.commits_path = vcs_dir / self.COMMITS_FILENAME

    def append(self, commit: CommitRecord) -> None:
        """
        Append a commit to history

        Args:
            commit: CommitRecord to append
        """
        self.vcs_dir.mkdir(parents=True, exist_ok=True)

        with open(self.commits_path, 'a', encoding='utf-8') as f:
            f.write(commit.to_jsonl() + '\n')

    def get_all(self) -> list[CommitRecord]:
        """
        Get all commits in chronological order

        Returns:
            List of CommitRecord objects (oldest first)
        """
        if not self.commits_path.exists():
            return []

        commits = []
        with open(self.commits_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        commits.append(CommitRecord.from_jsonl(line))
                    except (json.JSONDecodeError, TypeError):
                        # Skip invalid lines
                        continue

        return commits

    def get_recent(self, limit: int = 10) -> list[CommitRecord]:
        """
        Get recent commits (newest first)

        Args:
            limit: Maximum number of commits to return

        Returns:
            List of CommitRecord objects (newest first)
        """
        all_commits = self.get_all()
        return list(reversed(all_commits[-limit:]))

    def get_head(self) -> Optional[CommitRecord]:
        """
        Get the most recent commit

        Returns:
            CommitRecord or None if no commits
        """
        if not self.commits_path.exists():
            return None
        try:
            with open(self.commits_path, 'r', encoding='utf-8') as f:
                last_lines = deque(f, maxlen=1)
                if last_lines:
                    return CommitRecord.from_jsonl(last_lines[0])
        except (json.JSONDecodeError, TypeError, IndexError):
            pass

        # Fallback: read all and return last
        all_commits = self.get_all()
        return all_commits[-1] if all_commits else None

    def find_by_hash(self, commit_hash: str) -> Optional[CommitRecord]:
        """
        Find a commit by its hash (supports prefix matching)

        Args:
            commit_hash: Full or partial commit hash

        Returns:
            CommitRecord or None if not found
        """
        for commit in self.get_all():
            if commit.hash.startswith(commit_hash):
                return commit
        return None

    def find_by_branch(self, branch: str) -> list[CommitRecord]:
        """
        Find all commits on a branch

        Args:
            branch: Branch name

        Returns:
            List of CommitRecord objects on the branch
        """
        return [c for c in self.get_all() if c.branch == branch]

    def get_branch_head(self, branch: str) -> Optional[CommitRecord]:
        """
        Get the head commit of a branch

        Args:
            branch: Branch name

        Returns:
            CommitRecord or None
        """
        branch_commits = self.find_by_branch(branch)
        return branch_commits[-1] if branch_commits else None

    def count(self) -> int:
        """
        Count total commits

        Returns:
            Number of commits
        """
        if not self.commits_path.exists():
            return 0

        count = 0
        with open(self.commits_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    count += 1
        return count

    def is_empty(self) -> bool:
        """
        Check if history is empty

        Returns:
            True if no commits
        """
        return not self.commits_path.exists() or self.commits_path.stat().st_size == 0


def generate_commit_hash(message: str, timestamp: datetime, parent_hash: Optional[str] = None) -> str:
    """
    Generate a commit hash

    Args:
        message: Commit message
        timestamp: Commit timestamp
        parent_hash: Parent commit hash

    Returns:
        12-character hash string
    """
    import hashlib

    content = f"{timestamp.isoformat()}{message}{parent_hash or ''}"
    return hashlib.sha256(content.encode()).hexdigest()[:12]
