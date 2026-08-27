---
name: cad-modeling
description: Create, assemble, modify, inspect, render, version, or export parametric CAD models with build123d, optional cad-parts components, and .456d model packages. Use for mechanical geometry, STEP/STL output, CAD source code, or design history.
---

# CAD modeling

Use the bundled CLI as a convenient build123d workspace, not as a prescribed
design process. Choose only the commands and references useful for the task.

## Runtime

`PLUGIN_ROOT` is two levels above this `SKILL.md`. The cross-platform helper is
`PLUGIN_ROOT/scripts/cad.py`:

```bash
python3 <PLUGIN_ROOT>/scripts/cad.py check
python3 <PLUGIN_ROOT>/scripts/cad.py exec -- <cad arguments>
python3 <PLUGIN_ROOT>/scripts/cad.py parts -- <cadparts arguments>
```

On Windows, use an available launcher such as `py -3`. If `check` reports that
the environment is absent, explain that installation creates an isolated cache
venv and downloads roughly 300 MB. Obtain approval before running:

```bash
python3 <PLUGIN_ROOT>/scripts/cad.py install
```

Do not install into global site-packages. `CAD_TOOL_PYTHON`, `CAD_TOOL_VENV`,
and `CAD_PARTS_ROOT` can override interpreter, cache, and optional parts-library
locations.

## Model-package contract

- Editable geometry normally lives in `<name>.456d/src/main.py`; assign the
  final build123d shape to `result`.
- `design.md` is available for intent, named dimensions, coordinates, or other
  context when that helps the task. It need not follow a fixed template.
- A part may be one shape. An assembly normally keeps labeled component shapes
  as children of a `Compound` so their identities survive into STEP.
- `run`, `validate`, `inspect`, `render`, `review`, and `commit` are not a
  mandatory sequence. Select the useful capabilities when their inputs exist.
- Checkpoint assertions are optional probes for uncertain feature operations;
  they are not required after every feature and do not replace model judgment.
- `commit`, `checkout`, and branch operations affect package history or source.
  Preserve unrelated user changes and inspect status when that matters.

If several `.456d` packages are present, identify the intended package rather
than guessing. Read structured JSONL errors and outputs directly; the model may
also inspect source or write temporary diagnostic code whenever useful.

## Optional references

- For a skippable orientation using a wheel hub and a bearing assembly, read
  [references/model_walkthrough.md](references/model_walkthrough.md).
- For assemblies, purchased components, coordinate frames, and `cadparts`, read
  [references/assemblies.md](references/assemblies.md).
- For an unfamiliar build123d operation or selector, read
  [references/build123d.md](references/build123d.md).
- For optional feature probes, read
  [references/checkpoints.md](references/checkpoints.md).
- If ordinary views expose an ambiguity that needs dimensions, callouts, or a
  cutaway, read [references/review_drawing.md](references/review_drawing.md).

These references are aids, not required stages. For fabrication or a
safety-critical design, distinguish tool output from the engineering review,
dimensions, tolerances, material, and load decisions the user actually needs.
