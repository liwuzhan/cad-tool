"""Main CLI entry point"""

import sys
from pathlib import Path

import click

from .config import Config
from .utils.jsonl import emit_event


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """CAD CLI - AI-Native CAD Command Line Tool"""
    pass


@cli.command()
def init():
    """Initialize a new CAD project"""
    from .vcs.repository import Repository

    repo = Repository(Path.cwd())
    repo.init()
    emit_event("init_success", {"cad_dir": ".cad"})


@cli.command()
@click.argument('script_path', type=click.Path(exists=True))
def run(script_path):
    """Execute a build123d script"""
    from .runtime.executor import ScriptExecutor
    from .utils.geometry import compute_metrics

    emit_event("run_start", {"script": script_path})

    executor = ScriptExecutor(Path.cwd())
    shape, error = executor.execute(Path(script_path))

    if error:
        emit_event("run_error", {"error": error.to_dict()})
        sys.exit(1)
    else:
        metrics = compute_metrics(shape)
        emit_event("run_success", {"metrics": metrics.to_dict()})


@cli.command()
def validate():
    """Validate the current geometry"""
    from .runtime.executor import ScriptExecutor
    from .runtime.validator import GeometryValidator

    emit_event("validate_start", {})

    # Load the last executed shape
    executor = ScriptExecutor(Path.cwd())
    shape = executor.load_current_shape()

    if shape is None:
        emit_event("validate_error", {"message": "No shape to validate. Run a script first."})
        sys.exit(1)

    validator = GeometryValidator()
    errors = validator.validate(shape)

    if errors:
        emit_event("validate_failed", {"errors": [e.to_dict() for e in errors]})
        sys.exit(1)
    else:
        emit_event("validate_success", {})


@cli.command()
@click.option('--prop', type=click.Choice(['bounds', 'volume', 'area', 'faces', 'edges', 'vertices']))
@click.option('--list-targets', is_flag=True, help='List all topology targets')
@click.option('--target', help='Query specific target (e.g., face[0])')
@click.option('--target-prop', help='Property to query for target')
def inspect(prop, list_targets, target, target_prop):
    """Inspect geometry properties"""
    from .runtime.executor import ScriptExecutor
    from .feedback.inspector import GeometryInspector

    executor = ScriptExecutor(Path.cwd())
    shape = executor.load_current_shape()

    if shape is None:
        emit_event("inspect_error", {"message": "No shape to inspect. Run a script first."})
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
        emit_event("inspect_error", {"message": "Must specify --prop, --list-targets, or --target with --target-prop"})
        sys.exit(1)


@cli.command()
@click.option('--views', default='top,front,right,iso', help='Comma-separated list of views')
def render(views):
    """Render geometry to images"""
    from .runtime.executor import ScriptExecutor
    from .feedback.renderer import OffscreenRenderer
    from .feedback.camera import STANDARD_VIEWS

    executor = ScriptExecutor(Path.cwd())
    shape = executor.load_current_shape()

    if shape is None:
        emit_event("render_error", {"message": "No shape to render. Run a script first."})
        sys.exit(1)

    emit_event("render_start", {"views": views.split(',')})

    renderer = OffscreenRenderer(Path.cwd())
    view_list = views.split(',')
    output_paths = []

    try:
        for view_name in view_list:
            if view_name not in STANDARD_VIEWS:
                emit_event("render_error", {"message": f"Unknown view: {view_name}"})
                sys.exit(1)

            output_path = Path.cwd() / ".cad" / "thumbs" / f"{view_name}.png"
            renderer.render(shape, STANDARD_VIEWS[view_name], output_path)
            output_paths.append(str(output_path))

        emit_event("render_success", {"views": view_list, "paths": output_paths})
    except Exception as e:
        emit_event("render_error", {"message": str(e)})
        sys.exit(1)


@cli.command()
@click.option('--format', type=click.Choice(['step', 'stl']), required=True, help='Export format')
@click.option('--output', type=click.Path(), required=True, help='Output file path')
def export(format, output):
    """Export geometry to file"""
    from .runtime.executor import ScriptExecutor
    from .feedback.exporter import ModelExporter

    executor = ScriptExecutor(Path.cwd())
    shape = executor.load_current_shape()

    if shape is None:
        emit_event("export_error", {"message": "No shape to export. Run a script first."})
        sys.exit(1)

    emit_event("export_start", {"format": format, "output": output})

    try:
        exporter = ModelExporter()
        exporter.export(shape, format, Path(output))
        emit_event("export_success", {"format": format, "path": output})
    except Exception as e:
        emit_event("export_error", {"message": str(e)})
        sys.exit(1)


@cli.command()
@click.option('-m', '--message', required=True, help='Commit message')
def commit(message):
    """Commit current design version"""
    from .runtime.executor import ScriptExecutor
    from .vcs.repository import Repository

    executor = ScriptExecutor(Path.cwd())
    shape = executor.load_current_shape()

    if shape is None:
        emit_event("commit_error", {"message": "No shape to commit. Run a script first."})
        sys.exit(1)

    emit_event("commit_start", {"message": message})

    try:
        repo = Repository(Path.cwd())
        commit_data = repo.commit(message, shape)
        emit_event("commit_success", {"hash": commit_data.hash, "message": message})
    except Exception as e:
        emit_event("commit_error", {"message": str(e)})
        sys.exit(1)


@cli.command()
def log():
    """Show commit history"""
    from .vcs.repository import Repository

    try:
        repo = Repository(Path.cwd())
        commits = repo.log()
        emit_event("log_result", {"commits": [c.to_dict() for c in commits]})
    except Exception as e:
        emit_event("log_error", {"message": str(e)})
        sys.exit(1)


@cli.command()
def status():
    """Show current project status"""
    from .vcs.repository import Repository

    try:
        repo = Repository(Path.cwd())
        status_info = repo.status()
        emit_event("status_result", status_info)
    except Exception as e:
        emit_event("status_error", {"message": str(e)})
        sys.exit(1)


def main():
    """Main entry point"""
    cli()


if __name__ == '__main__':
    main()
