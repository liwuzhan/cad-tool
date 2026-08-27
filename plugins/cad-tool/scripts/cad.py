#!/usr/bin/env python3
"""Install and invoke the CAD CLI shipped inside the Codex plugin.

The installer is intentionally explicit: plugin installation itself performs no
network or package-manager work. The skill asks for approval before calling the
``install`` action, which creates an isolated, persistent virtual environment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Sequence


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = PLUGIN_ROOT / "cad-cli"
STATE_NAME = ".cad-tool-install.json"
SUPPORTED_MIN = (3, 11)
SUPPORTED_MAX = (3, 14)


def emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def default_venv() -> Path:
    override = os.environ.get("CAD_TOOL_VENV")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return (base / "cad-tool" / "venv").resolve()


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def venv_cad(venv: Path) -> Path:
    return venv / ("Scripts/cad.exe" if os.name == "nt" else "bin/cad")


def run(command: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=PLUGIN_ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def supported(command: Sequence[str]) -> tuple[bool, str]:
    try:
        result = run(
            [*command, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"]
        )
        version = result.stdout.strip()
        major, minor = (int(part) for part in version.split(".")[:2])
        return major == 3 and SUPPORTED_MIN[1] <= minor <= SUPPORTED_MAX[1], version
    except (OSError, ValueError, subprocess.CalledProcessError):
        return False, "unknown"


def python_candidates(explicit: str | None) -> list[list[str]]:
    candidates: list[list[str]] = []
    configured = explicit or os.environ.get("CAD_TOOL_PYTHON")
    if configured:
        candidates.append([configured])
    candidates.append([sys.executable])
    if os.name == "nt" and shutil.which("py"):
        candidates.extend([["py", f"-{minor}"] for minor in (12, 13, 11, 14)])
    for name in ("python3.12", "python3.13", "python3.11", "python3.14", "python3"):
        path = shutil.which(name)
        if path:
            candidates.append([path])

    unique: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for candidate in candidates:
        key = tuple(candidate)
        if key not in seen:
            unique.append(candidate)
            seen.add(key)
    return unique


def choose_python(explicit: str | None) -> tuple[list[str], str]:
    for candidate in python_candidates(explicit):
        ok, version = supported(candidate)
        if ok:
            return candidate, version
    raise RuntimeError(
        "Python 3.11-3.14 was not found. Install Python 3.12, or set CAD_TOOL_PYTHON."
    )


def source_digest() -> str:
    digest = hashlib.sha256()
    paths = [SOURCE_ROOT / "pyproject.toml"]
    paths.extend(sorted((SOURCE_ROOT / "src").rglob("*.py")))
    for path in paths:
        digest.update(path.relative_to(SOURCE_ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def probe(venv: Path) -> dict[str, object]:
    python = venv_python(venv)
    cad = venv_cad(venv)
    result: dict[str, object] = {
        "ready": False,
        "venv": str(venv),
        "python": str(python),
        "cad": str(cad),
    }
    if not python.is_file():
        result["reason"] = "virtual environment is not installed"
        return result
    try:
        check = run(
            [
                str(python),
                "-c",
                "import build123d, cad_cli, pyvista; print(cad_cli.__version__)",
            ]
        )
        help_result = run([str(python), "-m", "cad_cli", "--help"])
        result.update(
            ready=True,
            cad_cli_version=check.stdout.strip(),
            help_ok="Commands:" in help_result.stdout,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        result["reason"] = str(exc)
        if isinstance(exc, subprocess.CalledProcessError):
            result["stderr"] = exc.stderr.strip()[-1000:]
    return result


def install(venv: Path, explicit_python: str | None, upgrade: bool) -> dict[str, object]:
    if not (SOURCE_ROOT / "src" / "cad_cli" / "__main__.py").is_file():
        raise RuntimeError(f"Bundled CAD CLI is incomplete: {SOURCE_ROOT}")

    digest = source_digest()
    state_path = venv / STATE_NAME
    current = probe(venv)
    if current.get("ready") and state_path.is_file() and not upgrade:
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if state.get("source_digest") == digest:
                return {**current, "installed": False, "reason": "already current"}
        except (OSError, json.JSONDecodeError):
            pass

    python = venv_python(venv)
    base_version = None
    if not python.is_file():
        base, base_version = choose_python(explicit_python)
        venv.parent.mkdir(parents=True, exist_ok=True)
        created = run([*base, "-m", "venv", str(venv)], check=False)
        if created.returncode != 0:
            raise RuntimeError(created.stderr.strip() or "failed to create virtual environment")

    pip_base = [str(python), "-m", "pip", "--disable-pip-version-check"]
    if upgrade:
        pip_update = run([*pip_base, "install", "--upgrade", "pip"], check=False)
        if pip_update.returncode != 0:
            raise RuntimeError(pip_update.stderr.strip() or "failed to update pip")
    installed = run([*pip_base, "install", "--upgrade", str(SOURCE_ROOT)], check=False)
    if installed.returncode != 0:
        raise RuntimeError(installed.stderr.strip()[-4000:] or "CAD dependency installation failed")

    checked = probe(venv)
    if not checked.get("ready"):
        raise RuntimeError(str(checked.get("reason", "CAD CLI smoke test failed")))
    state_path.write_text(
        json.dumps(
            {
                "plugin": "cad-tool",
                "source_digest": digest,
                "source": str(SOURCE_ROOT),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {**checked, "installed": True, "base_python": base_version}


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="CAD Tool Codex plugin runtime helper")
    sub = root.add_subparsers(dest="action", required=True)

    check_parser = sub.add_parser("check", help="check the isolated CAD environment")
    check_parser.add_argument("--venv", type=Path, default=default_venv())

    install_parser = sub.add_parser("install", help="install the bundled CLI into an isolated venv")
    install_parser.add_argument("--venv", type=Path, default=default_venv())
    install_parser.add_argument("--python", help="base Python executable")
    install_parser.add_argument("--upgrade", action="store_true")

    exec_parser = sub.add_parser("exec", help="execute a CAD CLI command")
    exec_parser.add_argument("--venv", type=Path, default=default_venv())
    exec_parser.add_argument("cad_args", nargs=argparse.REMAINDER)
    return root


def main() -> int:
    args = parser().parse_args()
    venv = args.venv.expanduser().resolve()
    try:
        if args.action == "check":
            result = probe(venv)
            emit(result)
            return 0 if result.get("ready") else 1
        if args.action == "install":
            result = install(venv, args.python, args.upgrade)
            emit(result)
            return 0

        cad_args = list(args.cad_args)
        if cad_args[:1] == ["--"]:
            cad_args = cad_args[1:]
        if not cad_args:
            raise RuntimeError("No CAD command was supplied after 'exec --'.")
        ready = probe(venv)
        if not ready.get("ready"):
            emit({**ready, "hint": "Run 'cad.py install' after obtaining user approval."})
            return 2
        completed = subprocess.run([str(venv_python(venv)), "-m", "cad_cli", *cad_args])
        return completed.returncode
    except (OSError, RuntimeError) as exc:
        emit({"ok": False, "error": str(exc), "venv": str(venv)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
