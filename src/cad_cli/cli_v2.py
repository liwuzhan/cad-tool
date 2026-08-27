"""CAD CLI v2.0 - Main CLI entry point"""

import sys
from pathlib import Path
from typing import Optional

import click

from build123d import Shape

from .package import ModelPackage
from .vcs.repository_v2 import Repository
from .vcs.commits import CommitHistory
from .runtime.executor_v2 import ScriptExecutorV2
from .runtime.validator import GeometryValidator
from .runtime.workflow import BuildWorkflow
from .feedback.inspector import GeometryInspector
from .feedback.exporter import ModelExporter
from .feedback.renderer_v2 import OffscreenRendererV2
from .feedback.camera import STANDARD_VIEWS
from .utils.jsonl import emit_event
from .utils.geometry import compute_metrics


def _load_shape(package: ModelPackage, commit_hash: Optional[str] = None) -> tuple[Optional["Shape"], Optional[str]]:
    """Load shape from commit hash or HEAD.
    
    Returns (shape, error_message). One will be None.
    """
    if commit_hash:
        shape = package.artifact_manager.load_step(commit_hash)
        if shape is None:
            return None, f"STEP not found for commit {commit_hash}"
        return shape, None
    
    repo = Repository(package)
    head = repo.get_head()
    if head is None:
        return None, "No commits yet"
    shape = package.artifact_manager.load_step(head.hash)
    if shape is None:
        return None, "STEP artifact not found for HEAD"
    return shape, None


@click.group()
@click.version_option(version="2.0.0")
def cli():
    """CAD CLI v2.0 - AI-Native CAD with Model Packages"""
    pass


def find_or_error() -> ModelPackage:
    """Find model package or exit with error"""
    package = ModelPackage.find_package()
    if package is None:
        emit_event("error", {
            "message": "Not in a model package. Run 'cad init <name>' to create one."
        })
        sys.exit(1)
    return package


@cli.command()
@click.argument('path', type=click.Path())
@click.option('--name', required=True, help='Package name')
@click.option('--kind', type=click.Choice(['part', 'assembly']), default='part', show_default=True)
def init(path, name, kind):
    """Initialize a new model package (.456d)"""
    try:
        package_path = Path(path)
        package = ModelPackage.create(
            package_path,
            name=name,
            kind=kind,
            create_default_script=True,
        )
        emit_event("init_success", {
            "package_path": str(package.package_path),
            "name": name,
            "kind": kind,
            "default_script": str(package.get_default_script())
        })
    except FileExistsError as e:
        emit_event("init_error", {"message": str(e)})
        sys.exit(1)
    except Exception as e:
        emit_event("init_error", {"message": f"Failed to create package: {e}"})
        sys.exit(1)


@cli.command()
@click.argument('script_path', type=click.Path(exists=True), required=False)
def run(script_path):
    """Execute a build123d script (in-memory, no artifacts)"""
    package = find_or_error()

    if script_path:
        script = Path(script_path)
    else:
        script = package.get_default_script()

    emit_event("run_start", {"script": str(script)})

    executor = ScriptExecutorV2(package)
    shape, error = executor.execute(script)

    if error:
        emit_event("run_error", {"error": error.to_dict()})
        sys.exit(1)
    else:
        metrics = compute_metrics(shape)
        emit_event("run_success", {"metrics": metrics.to_dict()})


@cli.command()
@click.argument('script_path', type=click.Path(exists=True), required=False)
@click.option('--views', default=None, help='Comma-separated views to render')
def build(script_path, views):
    """
    Execute full build workflow (execute + validate + artifacts)
    Does NOT create a commit. Use 'cad commit' for that.
    """
    package = find_or_error()

    if script_path:
        script = Path(script_path)
    else:
        script = package.get_default_script()

    render_views = views.split(',') if views else None

    emit_event("build_start", {"script": str(script)})

    workflow = BuildWorkflow(package)
    commit_record, error = workflow.build(
        script_path=script,
        commit_message=None,  # No commit, just build
        render_views=render_views
    )

    if error:
        emit_event("build_error", {"error": error.to_dict()})
        sys.exit(1)
    else:
        emit_event("build_success", {"script": str(script)})


@cli.command()
@click.option('-m', '--message', required=True, help='Commit message')
@click.argument('script_path', type=click.Path(exists=True), required=False)
@click.option('--views', default=None, help='Comma-separated views to render')
def commit(message, script_path, views):
    """Create a commit with full build workflow"""
    package = find_or_error()

    if script_path:
        script = Path(script_path)
    else:
        script = None  # Will default to src/main.py

    render_views = views.split(',') if views else None

    emit_event("commit_start", {"message": message})

    repo = Repository(package)
    commit_record, error = repo.commit(
        message=message,
        script_path=script,
        render_views=render_views
    )

    if error:
        emit_event("commit_error", {"error": error.to_dict()})
        sys.exit(1)
    else:
        emit_event("commit_success", {
            "hash": commit_record.hash,
            "message": commit_record.message,
            "timestamp": commit_record.timestamp
        })


@cli.command()
@click.option('--limit', type=int, default=10, help='Number of commits to show')
def log(limit):
    """Show commit history"""
    package = find_or_error()
    repo = Repository(package)

    commits = repo.log(limit=limit)

    emit_event("log_result", {
        "commits": [c.to_dict() for c in commits],
        "total": len(commits)
    })


@cli.command()
def status():
    """Show current repository status"""
    package = find_or_error()
    repo = Repository(package)

    status_info = repo.status()
    emit_event("status_result", status_info)


@cli.command()
@click.argument('commit_hash')
def checkout(commit_hash):
    """Checkout a commit (load STEP artifact and restore script)"""
    package = find_or_error()
    repo = Repository(package)

    emit_event("checkout_start", {"commit": commit_hash})

    checkout_info, error = repo.checkout(commit_hash)

    if error:
        emit_event("checkout_error", {"error": error.to_dict()})
        sys.exit(1)
    else:
        shape = checkout_info["shape"]
        metrics = compute_metrics(shape)
        emit_event("checkout_success", {
            "commit": checkout_info["commit"],
            "metrics": metrics.to_dict(),
            "script_restored": checkout_info["script_restored"]
        })


@cli.command()
@click.argument('script_path', type=click.Path(exists=True), required=False)
def validate(script_path):
    """Validate geometry from script or current HEAD"""
    package = find_or_error()

    if script_path:
        # Validate from script execution
        script = Path(script_path)
        executor = ScriptExecutorV2(package)
        shape, error = executor.execute(script)

        if error:
            emit_event("validate_error", {"error": error.to_dict()})
            sys.exit(1)
    else:
        # Validate from HEAD STEP artifact
        shape, err_msg = _load_shape(package)
        if shape is None:
            emit_event("validate_error", {"message": err_msg})
            sys.exit(1)

    emit_event("validate_start", {})

    validator = GeometryValidator()
    errors = validator.validate(
        shape,
        allow_multiple_solids=package.get_manifest().kind == "assembly",
    )

    if errors:
        emit_event("validate_failed", {"errors": [e.to_dict() for e in errors]})
        sys.exit(1)
    else:
        emit_event("validate_success", {})


@cli.command()
@click.option('--prop', type=click.Choice(['bounds', 'volume', 'area', 'faces', 'edges', 'vertices', 'face_types', 'geometry_summary']))
@click.option('--list-targets', is_flag=True, help='List all topology targets')
@click.option('--target', help='Query specific target (e.g., face[0])')
@click.option('--target-prop', help='Property to query for target')
@click.argument('commit_hash', required=False)
def inspect(prop, list_targets, target, target_prop, commit_hash):
    """Inspect geometry properties (from HEAD or specific commit)"""
    package = find_or_error()

    # Load shape
    shape, err_msg = _load_shape(package, commit_hash)
    if shape is None:
        emit_event("inspect_error", {"message": err_msg})
        sys.exit(1)

    inspector = GeometryInspector()

    if list_targets:
        targets = inspector.list_targets(shape)
        emit_event("inspect_targets", {"targets": targets})
    elif target and target_prop:
        try:
            value = inspector.query_target(shape, target, target_prop)
            emit_event("inspect_result", {"target": target, "property": target_prop, "value": value})
        except Exception as e:
            emit_event("inspect_error", {"message": str(e)})
            sys.exit(1)
    elif prop:
        value = getattr(inspector, f"get_{prop}")(shape)
        emit_event("inspect_result", {"property": prop, "value": value})
    else:
        emit_event("inspect_error", {
            "message": "Specify --prop, --list-targets, or --target with --target-prop"
        })
        sys.exit(1)


@cli.command()
@click.option('--views', default='top,front,right,iso', help='Comma-separated list of views')
@click.argument('commit_hash', required=False)
def render(views, commit_hash):
    """Render geometry (from HEAD or specific commit)"""
    package = find_or_error()

    # Load shape
    shape, err_msg = _load_shape(package, commit_hash)
    if shape is None:
        emit_event("render_error", {"message": err_msg})
        sys.exit(1)

    emit_event("render_start", {"views": views.split(',')})

    renderer = OffscreenRendererV2(package)
    view_list = views.split(',')
    rendered = []

    try:
        for view_name in view_list:
            if view_name not in STANDARD_VIEWS:
                emit_event("render_error", {"message": f"Unknown view: {view_name}"})
                sys.exit(1)

            output_png = package.runlog_dir / f"render_{view_name}.png"
            output_json = package.runlog_dir / f"render_{view_name}.json"

            metadata = renderer.render(shape, STANDARD_VIEWS[view_name], output_png, output_json)
            rendered.append(metadata)

        emit_event("render_success", {"rendered": rendered})
    except Exception as e:
        emit_event("render_error", {"message": str(e)})
        sys.exit(1)


def _generate_review_template(
    review_path: Path,
    images: list[dict],
    metrics,
    features: list[str],
    checkpoint_results: list[dict] | None = None,
    geometry_summary: str = "",
    face_types: dict | None = None,
    text_only: bool = False,
) -> None:
    """Generate review.md template with rich text data for both multimodal and text-only models.

    When text_only=True (or when the model cannot view images), the template
    includes detailed topology data and checkpoint measurements so a text-only
    AI can still perform meaningful review.
    """
    lines = []
    lines.append("# 设计审查\n")

    # --- 1. Render images (optional, for multimodal models) ---
    if not text_only and images:
        lines.append("\n## 渲染图\n\n")
        for img in images:
            lines.append(f"- {img['view']}: `{img['path']}`\n")
    elif text_only:
        lines.append("\n> 文本模式：跳过渲染，基于数值数据进行审查\n")

    # --- 2. Geometry metrics ---
    lines.append(f"\n## 几何指标\n\n")
    lines.append(f"- 体积: {metrics.volume:.2f} mm³\n")
    lines.append(f"- 表面积: {metrics.area:.2f} mm²\n")
    lines.append(f"- 面数: {metrics.face_count}\n")
    lines.append(f"- 边数: {metrics.edge_count}\n")
    lines.append(f"- 顶点数: {metrics.vertex_count}\n")
    lines.append(f"- 实体数: {metrics.solid_count}\n")
    bbox = metrics.bbox
    x_size = bbox[3] - bbox[0]
    y_size = bbox[4] - bbox[1]
    z_size = bbox[5] - bbox[2]
    lines.append(f"- 边界框: X[{bbox[0]:.1f}, {bbox[3]:.1f}] "
                 f"Y[{bbox[1]:.1f}, {bbox[4]:.1f}] "
                 f"Z[{bbox[2]:.1f}, {bbox[5]:.1f}]\n")
    lines.append(f"- 外形尺寸: {x_size:.1f} x {y_size:.1f} x {z_size:.1f} mm\n")

    # --- 3. Face type breakdown (critical for text-only models) ---
    if face_types:
        lines.append("\n## 面类型分布\n\n")
        lines.append("| 类型 | 数量 | 占比 | 总面积 |\n")
        lines.append("|------|------|------|--------|\n")
        total_faces = face_types.get("total", metrics.face_count)
        for ftype, info in sorted(face_types.get("faces_by_type", {}).items(),
                                   key=lambda x: -x[1]["count"]):
            pct = info["count"] / total_faces * 100 if total_faces else 0
            lines.append(f"| {ftype} | {info['count']} | {pct:.0f}% | {info['total_area']:.2f} mm² |\n")

        # Detailed planar face directions
        planar = face_types.get("faces_by_type", {}).get("planar", {})
        if planar and "directions" in planar:
            dirs = ", ".join(f"{d}: {c}面" for d, c in sorted(planar["directions"].items()))
            lines.append(f"\n平面方向分布: {dirs}\n")

        # Cylindrical features (holes and bosses)
        cylindrical = face_types.get("faces_by_type", {}).get("cylindrical", {})
        if cylindrical:
            lines.append(f"\n圆柱面: {cylindrical['count']} 个")
            if "face_indices" in cylindrical:
                lines.append(f" (索引: {cylindrical['face_indices']})")
            lines.append("\n")

    # --- 4. Geometry text description (for text-only models) ---
    if geometry_summary:
        lines.append("\n## 几何结构文本描述\n\n")
        lines.append("```\n")
        lines.append(geometry_summary)
        lines.append("\n```\n")

    # --- 5. Per-feature review with checkpoint data ---
    lines.append("\n## 逐特征审查\n")

    if checkpoint_results:
        for i, cp in enumerate(checkpoint_results):
            name = cp.get("name", f"checkpoint_{i}")
            state = cp.get("state", {})
            checks = cp.get("checks", [])
            all_passed = cp.get("passed", 0) == cp.get("total", 0)
            status_icon = "PASS" if all_passed else "FAIL"

            lines.append(f"\n### 特征: {name}  [{status_icon}]\n")

            # Checkpoint state
            if state:
                lines.append(f"- **体积**: {state.get('volume', '?'):.2f}" if isinstance(state.get('volume'), (int, float)) else f"- **体积**: {state.get('volume', '?')}")
                lines.append(" mm³\n")
                lines.append(f"- **面数**: {state.get('face_count', '?')}\n")
                lines.append(f"- **实体数**: {state.get('solid_count', '?')}\n")

                # Face type breakdown at this checkpoint
                ft = state.get("face_types", {})
                if ft:
                    ft_str = ", ".join(f"{t}:{c}" for t, c in sorted(ft.items(), key=lambda x: -x[1]))
                    lines.append(f"- **面类型**: {ft_str}\n")

                b = state.get("bbox", [])
                if b and len(b) == 6:
                    lines.append(f"- **边界框**: X[{b[0]:.1f}..{b[3]:.1f}] Y[{b[1]:.1f}..{b[4]:.1f}] Z[{b[2]:.1f}..{b[5]:.1f}]\n")

            # Previous state diff (for non-first checkpoints)
            if i > 0 and checkpoint_results[i - 1].get("state"):
                prev = checkpoint_results[i - 1].get("state", {})
                curr = state
                lines.append(f"\n**相比上一步的变化:**\n")
                if isinstance(curr.get('volume'), (int, float)) and isinstance(prev.get('volume'), (int, float)):
                    delta_v = curr['volume'] - prev['volume']
                    lines.append(f"- 体积变化: {delta_v:+.2f} mm³\n")
                if isinstance(curr.get('face_count'), int) and isinstance(prev.get('face_count'), int):
                    delta_f = curr['face_count'] - prev['face_count']
                    lines.append(f"- 面数变化: {delta_f:+d}\n")

            # Individual check results
            if checks:
                lines.append(f"\n**断言结果:**\n")
                for c in checks:
                    icon = "✓" if c.get("passed") else "✗"
                    lines.append(f"- {icon} {c.get('message', c.get('type', ''))}\n")

            # Review prompts
            lines.append(f"\n- **意图**: \n")
            lines.append(f"- **分析**: (基于数值数据) 这一步的物理目的是什么？尺寸合理吗？\n")
            lines.append(f"- **判定**: ✓ / ✗\n")
    else:
        # Fallback: no checkpoint data available
        for feat in features:
            lines.append(f"\n### 特征: {feat}\n")
            lines.append("- **意图**: \n")
            lines.append("- **观察**: \n")
            lines.append("- **物理**: 力从哪来？传到哪？能工作吗？\n")
            lines.append("- **判定**: ✓ / ✗\n")

        if not features:
            lines.append("\n### 特征: [名称]\n")
            lines.append("- **意图**: \n")
            lines.append("- **观察**: \n")
            lines.append("- **物理**: \n")
            lines.append("- **判定**: ✓ / ✗\n")

    # --- 6. Overall verdict ---
    lines.append("\n## 总体判定\n\n")
    if checkpoint_results:
        total_checks = sum(cp.get("total", 0) for cp in checkpoint_results)
        passed_checks = sum(cp.get("passed", 0) for cp in checkpoint_results)
        lines.append(f"- **断言通过率**: {passed_checks}/{total_checks}\n")
    lines.append("- [ ] 所有特征物理上可行\n")
    if not text_only:
        lines.append("- [ ] 渲染结果与 design.md 一致\n")
    else:
        lines.append("- [ ] 数值指标与 design.md 一致\n")
    lines.append("- [ ] 可以 commit\n")

    review_path.write_text("".join(lines), encoding='utf-8')


@cli.command()
@click.argument('script_path', type=click.Path(exists=True), required=False)
@click.option('--views', default='iso,front,top,right')
@click.option('--text-only', is_flag=True, help='Skip rendering, generate text-only review for non-multimodal models')
def review(script_path, views, text_only):
    """Execute script, render views, generate review template"""
    package = find_or_error()

    if script_path:
        script = Path(script_path)
    else:
        script = package.get_default_script()

    emit_event("review_start", {"script": str(script), "text_only": text_only})

    # 1. Execute script
    executor = ScriptExecutorV2(package)
    shape, error = executor.execute(script)
    if error:
        emit_event("review_error", {"error": error.to_dict()})
        sys.exit(1)

    # 2. Checkpoint results (full payloads with state + checks)
    features = executor.checkpoint_names
    checkpoint_results = executor.checkpoint_results

    # 3. Metrics
    metrics = compute_metrics(shape)

    # 4. Geometry text analysis (always available, essential for text-only models)
    inspector = GeometryInspector()
    geometry_summary = inspector.get_geometry_summary(shape)
    face_types = inspector.get_face_types(shape)

    # 5. Render views (skip in text-only mode)
    rendered = []
    if not text_only:
        renderer = OffscreenRendererV2(package)
        for view_name in [v.strip() for v in views.split(',')]:
            if view_name not in STANDARD_VIEWS:
                continue
            png = package.runlog_dir / f"review_{view_name}.png"
            json_path = package.runlog_dir / f"review_{view_name}.json"
            try:
                renderer.render(shape, STANDARD_VIEWS[view_name], png, json_path)
                rendered.append({"view": view_name, "path": str(png)})
            except Exception:
                pass

    # 6. Generate review.md
    review_path = package.package_path / "review.md"
    _generate_review_template(
        review_path,
        rendered,
        metrics,
        features,
        checkpoint_results=checkpoint_results,
        geometry_summary=geometry_summary,
        face_types=face_types,
        text_only=text_only,
    )

    # 7. Output
    emit_event("review_ready", {
        "metrics": metrics.to_dict(),
        "images": rendered,
        "features": features,
        "checkpoint_results": checkpoint_results,
        "face_types": {k: v for k, v in face_types.items() if k != "all_faces"},
        "review_template": str(review_path),
        "text_only": text_only,
    })


@cli.command()
@click.option('--format', type=click.Choice(['step', 'stl']), required=True, help='Export format')
@click.option('--output', type=click.Path(), required=True, help='Output file path')
@click.argument('commit_hash', required=False)
def export(format, output, commit_hash):
    """Export geometry to file (from HEAD or specific commit)"""
    package = find_or_error()

    # Load shape
    shape, err_msg = _load_shape(package, commit_hash)
    if shape is None:
        emit_event("export_error", {"message": err_msg})
        sys.exit(1)

    emit_event("export_start", {"format": format, "output": output})

    try:
        exporter = ModelExporter()
        exporter.export(shape, format, Path(output))
        emit_event("export_success", {"format": format, "path": output})
    except Exception as e:
        emit_event("export_error", {"message": str(e)})
        sys.exit(1)


@cli.group()
def artifacts():
    """Manage artifacts in the package"""
    pass


@artifacts.command('list')
def artifacts_list():
    """List all artifacts and their sizes"""
    package = find_or_error()
    artifact_list = package.artifact_manager.list_artifacts()
    total_size = package.artifact_manager.get_total_size()

    emit_event("artifacts_list", {
        "artifacts": artifact_list,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / 1024 / 1024, 2)
    })


@artifacts.command('clean')
@click.option('--policy', type=click.Choice(['all_commits', 'latest_per_branch', 'releases_only']),
              default=None, help='Cleanup policy (default: use manifest setting)')
def artifacts_clean(policy):
    """Clean up artifacts based on policy"""
    package = find_or_error()

    if policy is None:
        policy = package.get_manifest().artifact_policy

    emit_event("artifacts_clean_start", {"policy": policy})

    # Get commits to keep based on policy
    keep_commits = []

    if policy == "all_commits":
        # Keep all
        history = CommitHistory(package.vcs_dir)
        keep_commits = [c.hash for c in history.get_all()]

    elif policy == "latest_per_branch":
        # Keep branch heads
        manifest = package.get_manifest()
        for branch, commit_hash in manifest.branches.items():
            if commit_hash:
                keep_commits.append(commit_hash)

    # elif policy == "releases_only":
    # Would need to track releases separately

    deleted = package.artifact_manager.cleanup_by_policy(policy, keep_commits)

    emit_event("artifacts_clean_success", {
        "policy": policy,
        "deleted_count": len(deleted),
        "deleted_commits": deleted
    })


@cli.group()
def branch():
    """Manage branches in the repository"""
    pass


@branch.command('list')
def branch_list():
    """List all branches"""
    package = find_or_error()
    repo = Repository(package)

    branches = repo.list_branches()
    emit_event("branch_list", {"branches": branches})


@branch.command('create')
@click.argument('name')
@click.option('--from', 'from_commit', default=None, help='Create branch from specific commit')
def branch_create(name, from_commit):
    """Create a new branch"""
    package = find_or_error()
    repo = Repository(package)

    emit_event("branch_create_start", {"name": name, "from": from_commit})

    branch_info, error = repo.create_branch(name, from_commit)

    if error:
        emit_event("branch_create_error", {"error": error.to_dict()})
        sys.exit(1)
    else:
        emit_event("branch_create_success", branch_info)


@branch.command('switch')
@click.argument('name')
def branch_switch(name):
    """Switch to an existing branch"""
    package = find_or_error()
    repo = Repository(package)

    emit_event("branch_switch_start", {"name": name})

    branch_info, error = repo.switch_branch(name)

    if error:
        emit_event("branch_switch_error", {"error": error.to_dict()})
        sys.exit(1)
    else:
        emit_event("branch_switch_success", branch_info)


@branch.command('delete')
@click.argument('name')
@click.option('--force', is_flag=True, help='Force delete even if current branch')
def branch_delete(name, force):
    """Delete a branch"""
    package = find_or_error()
    repo = Repository(package)

    emit_event("branch_delete_start", {"name": name, "force": force})

    deleted_info, error = repo.delete_branch(name, force)

    if error:
        emit_event("branch_delete_error", {"error": error.to_dict()})
        sys.exit(1)
    else:
        emit_event("branch_delete_success", deleted_info)


def main():
    """Main entry point"""
    cli()


if __name__ == '__main__':
    main()
