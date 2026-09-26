"""Build a package's interface graph from declarations, without building geometry.

The ordering this preserves is the point of the whole exercise: a compiler checks
its IR *before* codegen, so the assembly's interface graph must be judgeable
before any solid exists. Everything here therefore reads declarations only —
``manifest.json`` for dependencies and mates, ``ports.py`` for the interfaces of
parts the package builds itself, and the catalogue's *derivation* path (which
returns dictionaries, never shapes) for standard parts.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Mapping

PORTS_FILENAME = "ports.py"


class MateCheckError(Exception):
    """Raised when the declarations themselves cannot be read."""


# --------------------------------------------------------------------------
# ports.py — the contract half of a package
# --------------------------------------------------------------------------

def _execute_ports_file(path: Path) -> Mapping[str, Any]:
    """Run ``ports.py`` in its own namespace and return the module object."""

    spec = importlib.util.spec_from_file_location("_cad_ports", path)
    if spec is None or spec.loader is None:
        raise MateCheckError(f"无法加载 {path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # surface the author's error verbatim
        raise MateCheckError(f"{PORTS_FILENAME} 执行失败：{type(exc).__name__}: {exc}") from exc
    return module


def _looks_like_geometry(value: Any) -> bool:
    """Duck-type for a build123d shape without importing the kernel.

    ``ports.py`` is supposed to declare, not model. If it builds solids anyway,
    the check has silently stopped running "before geometry" and the saving that
    justified the split is gone — worth telling the author about.
    """

    for attribute in ("solids", "volume", "bounding_box"):
        if hasattr(value, attribute):
            return True
    return False


def load_declared_ports(package_path: Path) -> tuple[dict[str, list[dict]], list[str]]:
    """Return ``({instance_name: [port, ...]}, warnings)`` from ``ports.py``."""

    path = package_path / PORTS_FILENAME
    if not path.exists():
        return {}, []

    module = _execute_ports_file(path)

    built = [
        name for name, value in vars(module).items()
        if not name.startswith("_") and _looks_like_geometry(value)
    ]
    warnings = []
    if built:
        warnings.append(
            f"{PORTS_FILENAME} 里出现了几何对象（{', '.join(sorted(built)[:3])}）；"
            "该文件应当只做声明，否则类型检查就不再先于几何生成"
        )

    ports = getattr(module, "PORTS", None)
    if ports is None:
        raise MateCheckError(f"{PORTS_FILENAME} 没有定义 PORTS")
    if not isinstance(ports, Mapping):
        raise MateCheckError(f"{PORTS_FILENAME} 的 PORTS 应当是 {{实例名: [接口, ...]}} 映射")

    cleaned: dict[str, list[dict]] = {}
    for instance, items in ports.items():
        if not isinstance(items, (list, tuple)):
            raise MateCheckError(f"{PORTS_FILENAME} 中 {instance!r} 的接口应当是列表")
        normalised = []
        for index, item in enumerate(items):
            if not isinstance(item, Mapping) or "id" not in item or "type" not in item:
                raise MateCheckError(
                    f"{PORTS_FILENAME} 中 {instance}[{index}] 缺少 id 或 type"
                )
            normalised.append(dict(item))
        cleaned[str(instance)] = normalised
    return cleaned, warnings


# --------------------------------------------------------------------------
# Standard parts — derivation only, no shapes
# --------------------------------------------------------------------------

def resolve_standard_ports(dep: Mapping[str, Any]) -> list[dict]:
    """Resolve a ``std:`` dependency's interfaces through the catalogue.

    Uses ``derive`` + ``resolve_interfaces``, both of which return dictionaries.
    Nothing here instantiates a part.
    """

    try:
        from cadparts.catalog import derive
        from cadparts.interfaces import resolve_interfaces
    except ImportError as exc:  # cad-parts is an optional dependency
        raise MateCheckError(
            "解析 std: 依赖需要 cad-parts（pip install cad-parts）；"
            f"未安装：{exc}"
        ) from exc

    spec = dep.get("std")
    if not isinstance(spec, Mapping):
        raise MateCheckError(f"依赖 {dep.get('name')!r} 缺少 std 规格")
    family = spec.get("family")
    if not family:
        raise MateCheckError(f"依赖 {dep.get('name')!r} 的 std 缺少 family")
    params = spec.get("params") or {}
    if not isinstance(params, Mapping):
        raise MateCheckError(f"依赖 {dep.get('name')!r} 的 params 应当是映射")

    derived = derive(str(family), **dict(params))
    return resolve_interfaces(str(family), dict(params), derived)


# --------------------------------------------------------------------------
# Graph assembly
# --------------------------------------------------------------------------

def build_instances(metadata: Any, package_path: Path) -> tuple[dict[str, list[dict]], list[str]]:
    """Collect every declared instance's ports."""

    instances, warnings = load_declared_ports(package_path)

    for dep in getattr(metadata, "deps", []) or []:
        name = dep.get("name")
        if not name:
            raise MateCheckError("deps 中存在没有 name 的条目")
        if name in instances:
            raise MateCheckError(f"实例名重复：{name!r} 同时出现在 deps 与 {PORTS_FILENAME}")
        if "std" in dep:
            instances[str(name)] = resolve_standard_ports(dep)
        elif "pkg" in dep:
            warnings.append(
                f"依赖 {name!r} 使用 pkg:（引用其它包），跨包接口解析尚未实现，已跳过"
            )
        else:
            raise MateCheckError(f"依赖 {name!r} 既没有 std 也没有 pkg 规格")

    return instances, warnings


def check_package(package_path: Path, metadata: Any) -> dict[str, Any]:
    """Evaluate the package's mate graph. Builds no geometry."""

    from cadparts.mates import evaluate_mates

    instances, warnings = build_instances(metadata, package_path)
    result = evaluate_mates(instances, getattr(metadata, "mates", []) or [])
    result["package"] = getattr(metadata, "name", package_path.name)
    result["instances"] = {
        name: sorted(str(port.get("id")) for port in ports)
        for name, ports in sorted(instances.items())
    }
    if warnings:
        result["warnings"] = warnings
    return result


__all__ = [
    "MateCheckError",
    "PORTS_FILENAME",
    "build_instances",
    "check_package",
    "load_declared_ports",
    "resolve_standard_ports",
]
