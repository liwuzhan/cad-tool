"""Record what happens to a script's assertions between commits.

This **records; it does not block.** The assertions belong to whoever wrote the
model, and refusing to let them be revised would be both paternalistic and a
dead end the moment a constraint turns out to be wrong.

What must not happen is the revision going unnoticed. The dangerous change is not
deletion but quiet loosening — ``tolerance=1.0`` becoming ``tolerance=1000.0``,
``expect_solids(1)`` becoming "at least one" — because that turns a red build
green without anyone deciding it should. Recording the *diff* rather than a bare
"assertions changed" flag is what makes that visible.

The extraction is AST-based rather than textual so it survives formatting and
line rewrapping, and so a Checkpoint mentioned in a comment or a string never
counts as an assertion.
"""

from __future__ import annotations

import ast
from typing import Any, Iterable

CHECKPOINT_FACTORY = "Checkpoint"
_CHECK_PREFIX = "expect_"
_TERMINALS = {"verify"}


class AssertionSyntaxError(ValueError):
    """Raised when the source cannot be parsed at all."""


def _render_call(node: ast.Call) -> str:
    """Render one ``expect_*(...)`` call as just that call.

    Rendering the whole fluent prefix instead would make every later check's
    identity depend on every earlier one, so editing the first check would look
    like a rewrite of the entire chain.
    """

    parts = [ast.unparse(argument) for argument in node.args]
    parts += [
        f"{keyword.arg}={ast.unparse(keyword.value)}"
        for keyword in node.keywords
        if keyword.arg is not None
    ]
    return f"{node.func.attr}({', '.join(parts)})"


def _collect_constants(tree: ast.Module) -> dict[str, str]:
    """Top-level literal assignments, rendered as source text.

    Projects conventionally put tunables at the top of the file and forbid magic
    numbers in the body, so an assertion literally reads ``tolerance=TOL``. Left
    alone, changing ``TOL`` from 1.0 to 1000.0 would leave the assertion text
    identical and the loosening invisible — which is precisely the change this
    module exists to surface.
    """

    constants: dict[str, str] = {}
    for node in tree.body:
        target = value = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        if not isinstance(target, ast.Name) or value is None:
            continue
        if not isinstance(value, (ast.Constant, ast.UnaryOp, ast.Tuple, ast.List)):
            continue
        try:
            constants[target.id] = ast.unparse(value)
        except Exception:  # unparse should not fail on these, but never break a commit
            continue
    return constants


class _ConstantFolder(ast.NodeTransformer):
    """Replace module-level names with their literal values, recursively."""

    def __init__(self, constants: dict[str, str]):
        self.constants = constants

    def visit_Name(self, node: ast.Name) -> ast.AST:
        replacement = self.constants.get(node.id)
        if replacement is None:
            return node
        try:
            folded = ast.parse(replacement, mode="eval").body
        except SyntaxError:
            return node
        return ast.copy_location(folded, node)


def _checkpoint_name(node: ast.Call) -> str:
    """Read the checkpoint's label from ``Checkpoint(part, "name")`` or ``name=``."""

    for keyword in node.keywords:
        if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
            return str(keyword.value.value)
    for argument in node.args[1:]:
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            return argument.value
    return "-"


def _walk_chain(node: ast.AST, constants: dict[str, str] | None = None) -> dict[str, Any] | None:
    """Unwind a ``Checkpoint(...).expect_*().verify()`` chain, outermost first."""

    constants = constants or {}
    checks: list[str] = []
    current: ast.AST = node
    while isinstance(current, ast.Call) and isinstance(current.func, ast.Attribute):
        attribute = current.func.attr
        if attribute.startswith(_CHECK_PREFIX):
            folded = _ConstantFolder(constants).visit(
                ast.copy_location(
                    ast.Call(func=current.func, args=list(current.args),
                             keywords=list(current.keywords)),
                    current,
                )
            )
            checks.append(_render_call(folded))
        elif attribute not in _TERMINALS:
            return None  # some other fluent API; not a Checkpoint chain
        current = current.func.value

    if (
        isinstance(current, ast.Call)
        and isinstance(current.func, ast.Name)
        and current.func.id == CHECKPOINT_FACTORY
    ):
        return {
            "checkpoint": _checkpoint_name(current),
            "checks": list(reversed(checks)),
        }
    return None


def extract_assertions(source: str) -> list[dict[str, Any]]:
    """Return ``[{"checkpoint": name, "checks": [...]}, ...]`` for a model script.

    Only the chained form is recognised — ``Checkpoint(x, "n").expect_a().verify()``
    as a statement. Assigning a Checkpoint to a variable and calling checks later
    is not tracked; that is a documented limitation, not an accident.
    """

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise AssertionSyntaxError(f"脚本无法解析：{exc}") from exc

    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    constants = _collect_constants(tree)
    for node in ast.walk(tree):
        # Only expression statements. Iterating every node and reading `.value`
        # would also match each ast.Attribute in the middle of a chain, yielding
        # the same assertion once per fluent link.
        if not isinstance(node, ast.Expr):
            continue
        chain = _walk_chain(node.value, constants)
        if chain is None or not chain["checks"]:
            continue
        identity = f"{chain['checkpoint']}\u0000{'|'.join(chain['checks'])}"
        if identity in seen:
            continue
        seen.add(identity)
        found.append(chain)
    return found


def assertion_keys(items: Iterable[dict[str, Any]]) -> set[str]:
    """Flatten to identity strings ``<checkpoint>:<check>`` for set comparison."""

    keys: set[str] = set()
    for item in items:
        name = item.get("checkpoint", "-")
        for check in item.get("checks", []):
            keys.add(f"{name}:{check}")
    return keys


def diff_assertions(previous_source: str | None, current_source: str) -> dict[str, Any]:
    """Compare the assertion sets of two revisions of a script.

    Returns counts plus the fully rendered added/removed entries, so a loosened
    tolerance shows up as a removed/added pair with both values legible rather
    than as an opaque "changed" flag.
    """

    try:
        current_items = extract_assertions(current_source)
    except AssertionSyntaxError:
        return {"available": False, "reason": "当前脚本无法解析，未记录断言差量"}

    current_keys = assertion_keys(current_items)
    if previous_source is None:
        return {
            "available": True,
            "first_commit": True,
            "previous_total": 0,
            "current_total": len(current_keys),
            "added": sorted(current_keys),
            "removed": [],
            "items": current_items,
        }

    try:
        previous_keys = assertion_keys(extract_assertions(previous_source))
    except AssertionSyntaxError:
        return {
            "available": False,
            "reason": "上一版脚本无法解析，未记录断言差量",
        }

    return {
        "available": True,
        "first_commit": False,
        "previous_total": len(previous_keys),
        "current_total": len(current_keys),
        "added": sorted(current_keys - previous_keys),
        "removed": sorted(previous_keys - current_keys),
        "items": current_items,
    }


def summarize(delta: dict[str, Any]) -> str:
    """One line suitable for a commit event, or "" when nothing changed."""

    if not delta.get("available"):
        return delta.get("reason", "")
    if delta.get("first_commit"):
        return f"断言集合首次记录，共 {delta['current_total']} 条"
    added, removed = delta.get("added", []), delta.get("removed", [])
    if not added and not removed:
        return ""
    parts = []
    if added:
        parts.append(f"新增 {len(added)} 条")
    if removed:
        parts.append(f"移除 {len(removed)} 条")
    return f"断言集合变更：{'、'.join(parts)}（{delta['previous_total']} → {delta['current_total']}）"


__all__ = [
    "AssertionSyntaxError",
    "assertion_keys",
    "diff_assertions",
    "extract_assertions",
    "summarize",
]
