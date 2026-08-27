"""Repository v2 - Adapted for model packages"""

from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from build123d import Shape

from ..package import ModelPackage
from ..models import ErrorInfo
from ..runtime.workflow import BuildWorkflow
from .commits import CommitHistory, CommitRecord


class Repository:
    """
    Version control repository for CAD model packages

    v2 changes:
    - Works with .456d model packages
    - Uses JSONL-based commit history
    - Artifacts managed by ArtifactManager
    """

    def __init__(self, package: ModelPackage):
        """
        Initialize repository

        Args:
            package: ModelPackage instance
        """
        self.package = package
        self.commit_history = CommitHistory(package.vcs_dir)
        self.build_workflow = BuildWorkflow(package)

    def commit(
        self,
        message: str,
        script_path: Optional[Path] = None,
        render_views: Optional[list[str]] = None,
    ) -> tuple[Optional[CommitRecord], Optional[ErrorInfo]]:
        """
        Create a new commit with full build workflow

        Args:
            message: Commit message
            script_path: Path to script (defaults to src/main.py)
            render_views: Views to render (defaults to manifest settings)

        Returns:
            Tuple of (CommitRecord, ErrorInfo) - one will be None
        """
        # Execute build workflow
        commit_record, error = self.build_workflow.build(
            script_path=script_path,
            commit_message=message,
            render_views=render_views
        )

        if error:
            return None, error

        # Append to history
        self.commit_history.append(commit_record)

        return commit_record, None

    def log(self, limit: Optional[int] = None) -> list[CommitRecord]:
        """
        Get commit history

        Args:
            limit: Maximum number of commits to return (None = all)

        Returns:
            List of CommitRecord objects (newest first)
        """
        if limit is None:
            all_commits = self.commit_history.get_all()
            return list(reversed(all_commits))
        else:
            return self.commit_history.get_recent(limit)

    def get_head(self) -> Optional[CommitRecord]:
        """
        Get the current HEAD commit

        Returns:
            CommitRecord or None if no commits
        """
        return self.commit_history.get_head()

    def find_commit(self, commit_hash: str) -> Optional[CommitRecord]:
        """
        Find a commit by hash (supports prefix matching)

        Args:
            commit_hash: Full or partial commit hash

        Returns:
            CommitRecord or None
        """
        return self.commit_history.find_by_hash(commit_hash)

    def checkout(self, commit_hash: str) -> tuple[Optional[dict], Optional[ErrorInfo]]:
        """
        Checkout a commit (load its STEP artifact and restore script)

        Args:
            commit_hash: Commit hash to checkout

        Returns:
            Tuple of (checkout_info dict, ErrorInfo) - one will be None
        """
        # Find the commit
        commit = self.find_commit(commit_hash)
        if commit is None:
            return None, ErrorInfo(
                file="",
                line=0,
                type="CommitNotFound",
                code="E-IO",
                message=f"Commit not found: {commit_hash}",
                hint="Use 'cad log' to see available commits"
            )

        # Load STEP artifact
        shape = self.package.artifact_manager.load_step(commit.hash)
        if shape is None:
            return None, ErrorInfo(
                file="",
                line=0,
                type="ArtifactNotFound",
                code="E-IO",
                message=f"STEP artifact not found for commit {commit.hash}",
                hint="The artifact may have been cleaned up or never created"
            )

        # Update manifest to point to this commit
        self.package.update_manifest(head=commit.hash)

        # Restore script from artifacts to working directory
        script_restored = False
        script_content = self.package.artifact_manager.load_script(commit.hash)
        if script_content:
            main_script = self.package.get_default_script()
            try:
                with open(main_script, 'w', encoding='utf-8') as f:
                    f.write(script_content)
                script_restored = True
            except Exception:
                pass

        # Restore design doc from artifacts to working directory
        design_restored = False
        design_content = self.package.artifact_manager.load_design_doc(commit.hash)
        if design_content:
            design_doc = self.package.get_design_doc()
            try:
                with open(design_doc, 'w', encoding='utf-8') as f:
                    f.write(design_content)
                design_restored = True
            except Exception:
                pass

        return {
            "commit": commit.hash,
            "shape": shape,
            "script_restored": script_restored,
            "design_restored": design_restored
        }, None

    def status(self) -> dict:
        """
        Get repository status

        Returns:
            Status dictionary with commit info and change detection
        """
        head = self.get_head()
        total_commits = self.commit_history.count()

        # Check if main script has been modified since last commit
        has_changes = False
        main_script = self.package.get_default_script()

        if head and main_script.exists():
            try:
                from datetime import datetime
                script_mtime = main_script.stat().st_mtime
                commit_time = datetime.fromisoformat(head.timestamp).timestamp()
                has_changes = script_mtime > commit_time
            except Exception:
                pass

        return {
            "head": head.hash if head else None,
            "branch": self.package.get_manifest().current_branch,
            "total_commits": total_commits,
            "has_changes": has_changes,
            "script_path": str(main_script.resolve().relative_to(self.package.package_path.resolve())),
        }

    def get_branch_commits(self, branch: Optional[str] = None) -> list[CommitRecord]:
        """
        Get commits on a specific branch

        Args:
            branch: Branch name (None = current branch)

        Returns:
            List of CommitRecord objects
        """
        if branch is None:
            branch = self.package.get_manifest().current_branch

        return self.commit_history.find_by_branch(branch)

    def list_branches(self) -> list[dict]:
        """
        List all branches with their head commits

        Returns:
            List of dicts with branch info: {name, head, is_current, commit_count}
        """
        manifest = self.package.get_manifest()
        current = manifest.current_branch

        branches = []
        for name, head_hash in manifest.branches.items():
            # Get commit count on branch
            branch_commits = self.commit_history.find_by_branch(name)

            branches.append({
                "name": name,
                "head": head_hash,
                "is_current": name == current,
                "commit_count": len(branch_commits)
            })

        return branches

    def create_branch(self, name: str, from_commit: Optional[str] = None) -> tuple[Optional[dict], Optional[ErrorInfo]]:
        """
        Create a new branch

        Args:
            name: Branch name
            from_commit: Commit hash to branch from (None = current HEAD from manifest)

        Returns:
            Tuple of (branch_info, ErrorInfo)
        """
        manifest = self.package.get_manifest()

        # Check if branch already exists
        if name in manifest.branches:
            return None, ErrorInfo(
                file="", line=0, type="BranchExists", code="E-IO",
                message=f"Branch '{name}' already exists",
                hint="Use 'cad branch switch' to switch to it"
            )

        # Determine starting commit
        if from_commit is None:
            # Use manifest HEAD (not commit history HEAD)
            from_commit = manifest.head
            if from_commit is None:
                return None, ErrorInfo(
                    file="", line=0, type="NoCommits", code="E-IO",
                    message="Cannot create branch: no commits yet",
                    hint="Create a commit first with 'cad commit'"
                )
        else:
            # Validate commit exists
            commit = self.find_commit(from_commit)
            if commit is None:
                return None, ErrorInfo(
                    file="", line=0, type="CommitNotFound", code="E-IO",
                    message=f"Commit not found: {from_commit}",
                    hint="Use 'cad log' to see available commits"
                )
            from_commit = commit.hash

        # Create branch using nested update
        self.package.manifest_manager.update_nested(f"branches.{name}", from_commit)

        return {
            "name": name,
            "head": from_commit
        }, None

    def switch_branch(self, name: str) -> tuple[Optional[dict], Optional[ErrorInfo]]:
        """
        Switch to an existing branch

        Args:
            name: Branch name

        Returns:
            Tuple of (branch_info, ErrorInfo)
        """
        manifest = self.package.get_manifest()

        # Check if branch exists
        if name not in manifest.branches:
            return None, ErrorInfo(
                file="", line=0, type="BranchNotFound", code="E-IO",
                message=f"Branch '{name}' does not exist",
                hint=f"Use 'cad branch create {name}' to create it"
            )

        # Switch current_branch and update HEAD to branch head
        branch_head = manifest.branches[name]
        self.package.update_manifest(
            current_branch=name,
            head=branch_head
        )

        # Restore script from artifacts to working directory
        script_restored = False
        if branch_head:
            script_content = self.package.artifact_manager.load_script(branch_head)
            if script_content:
                main_script = self.package.get_default_script()
                try:
                    with open(main_script, 'w', encoding='utf-8') as f:
                        f.write(script_content)
                    script_restored = True
                except Exception:
                    pass

        # Restore design doc from artifacts to working directory
        design_restored = False
        if branch_head:
            design_content = self.package.artifact_manager.load_design_doc(branch_head)
            if design_content:
                design_doc = self.package.get_design_doc()
                try:
                    with open(design_doc, 'w', encoding='utf-8') as f:
                        f.write(design_content)
                    design_restored = True
                except Exception:
                    pass

        return {
            "name": name,
            "head": branch_head,
            "script_restored": script_restored,
            "design_restored": design_restored
        }, None

    def delete_branch(self, name: str, force: bool = False) -> tuple[Optional[dict], Optional[ErrorInfo]]:
        """
        Delete a branch

        Args:
            name: Branch name
            force: Force delete even if current branch

        Returns:
            Tuple of (deleted_info, ErrorInfo)
        """
        manifest = self.package.get_manifest()

        # Check if branch exists
        if name not in manifest.branches:
            return None, ErrorInfo(
                file="", line=0, type="BranchNotFound", code="E-IO",
                message=f"Branch '{name}' does not exist"
            )

        # Cannot delete main branch
        if name == "main":
            return None, ErrorInfo(
                file="", line=0, type="CannotDeleteMain", code="E-IO",
                message="Cannot delete 'main' branch"
            )

        # Cannot delete current branch unless forced
        if name == manifest.current_branch and not force:
            return None, ErrorInfo(
                file="", line=0, type="CannotDeleteCurrent", code="E-IO",
                message=f"Cannot delete current branch '{name}'",
                hint="Switch to another branch first, or use --force"
            )

        # Delete branch
        head = manifest.branches[name]
        del manifest.branches[name]

        # If we force-deleted current branch, switch to main
        if name == manifest.current_branch:
            manifest.current_branch = "main"
            manifest.head = manifest.branches.get("main")

        self.package.manifest_manager.save(manifest)

        return {
            "name": name,
            "deleted_head": head
        }, None
