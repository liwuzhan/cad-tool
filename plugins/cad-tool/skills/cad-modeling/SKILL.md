---
name: cad-modeling
description: Create, assemble, modify, validate, review, version, or export parametric CAD models with build123d, optional cad-parts standard components, and .456d model packages. Use for CAD parts or assemblies, mechanical geometry, STEP/STL files, build123d scripts, dimensional changes, geometry inspection, or CAD design history.
---

# CAD modeling with the bundled CLI

Use the CLI vendored inside this plugin as the geometry source of truth. Do not
replace it with ad-hoc mesh scripts when the request needs editable parametric
geometry, validation, version history, or STEP output.

## Runtime helper

Resolve `PLUGIN_ROOT` as the directory two levels above this `SKILL.md`. Use the
cross-platform helper at `PLUGIN_ROOT/scripts/cad.py`; it invokes the same CLI
on macOS, Linux, and Windows without relying on an activated shell.

Check the environment before the first CAD command:

```bash
python3 <PLUGIN_ROOT>/scripts/cad.py check
```

On Windows, use the available Python launcher, for example:

```powershell
py -3 <PLUGIN_ROOT>\scripts\cad.py check
```

If the check says the environment is not installed, tell the user that setup
creates an isolated cache venv and downloads about 300 MB of build123d/OCP and
PyVista dependencies. Obtain approval before running:

```bash
python3 <PLUGIN_ROOT>/scripts/cad.py install
```

Never install into global site-packages. Do not run setup merely because the
plugin was enabled; run it only for a CAD task after approval. The user can set
`CAD_TOOL_PYTHON` to a Python 3.11-3.14 executable and `CAD_TOOL_VENV` to choose
another cache location.

The environment check also reports the optional `cadparts` library. For a
standard component, query the fixed catalog instead of browsing source files or
remodeling it:

```bash
python3 <PLUGIN_ROOT>/scripts/cad.py parts -- search "20mm 轴承"
python3 <PLUGIN_ROOT>/scripts/cad.py parts -- compare 6204 6304
python3 <PLUGIN_ROOT>/scripts/cad.py parts -- describe 6204
```

If `cadparts` is absent, ordinary CAD remains available. Place the `cad-parts`
repository beside the workspace or set `CAD_PARTS_ROOT`, then rerun the explicit
install action after approval.

Invoke every CAD command through the helper:

```bash
python3 <PLUGIN_ROOT>/scripts/cad.py exec -- <cad arguments>
```

## Standard workflow

1. Inspect the workspace for an existing `.456d` model package. If more than
   one exists, identify the intended package instead of guessing.
2. For a new design, create `design.md` with named dimensions, units,
   tolerances, feature order, and validation targets.
3. Create the package, then work inside it:

   ```bash
   python3 <PLUGIN_ROOT>/scripts/cad.py exec -- init bracket --name "Bracket"
   cd bracket.456d
   ```

4. Edit `src/main.py`. Keep all dimensions as named parameters and assign the
   final `build123d` shape to `result`.
5. Add `cad_cli.feedback.Checkpoint` assertions after important features.
   Always check one solid for a single part; check the base bounding box and
   expected volume changes after additive or subtractive features.
6. Iterate with `run`, then use `validate` and `inspect` to confirm BRep health,
   bounds, volume, and topology:

   ```bash
   python3 <PLUGIN_ROOT>/scripts/cad.py exec -- run
   python3 <PLUGIN_ROOT>/scripts/cad.py exec -- validate
   python3 <PLUGIN_ROOT>/scripts/cad.py exec -- inspect --prop bounds
   python3 <PLUGIN_ROOT>/scripts/cad.py exec -- inspect --prop volume
   ```

7. Use `review` before committing. On a machine without a usable display,
   prefer `review --text-only`; successful validation and STEP output remain
   authoritative even if a Windows preview renderer cannot create PNGs.
8. Commit only after checkpoints and validation pass, then export as requested:

   ```bash
   python3 <PLUGIN_ROOT>/scripts/cad.py exec -- commit -m "Add mounting holes"
   python3 <PLUGIN_ROOT>/scripts/cad.py exec -- export --format step --output ../bracket.step
   ```

For a request containing multiple components, an assembly, a mechanism, or
standard purchased parts, read [references/assemblies.md](references/assemblies.md)
before creating the package. Keep the main skill lightweight; the assembly
reference contains the coordinate, interface, labeling, catalog, and validation
conventions.

Ordinary orthographic and isometric views are normally sufficient. If they
reveal a concern that is still hard to localize, optionally read
[references/review_drawing.md](references/review_drawing.md) and give `review`
a model-chosen drawing specification for selected dimensions, callouts, or a
cutaway. Do not make annotated drawings a mandatory step for simple work.

## Editing and recovery rules

- Read JSONL events and act on `error.code`, `error.message`, and `error.hint`.
- A failed Checkpoint identifies the first broken feature; fix that feature
  before adding later geometry.
- Use `cad status`, `cad log`, and `cad branch` before version operations.
- Treat `cad checkout` and branch switching like source-control operations:
  inspect current status first and do not discard unrelated user edits.
- Do not equate a headless PNG-render failure with invalid geometry. Report the
  preview limitation separately and continue validation/export when those
  operations succeed.
- Headless Linux automatically uses the process-safe Matplotlib backend. If VTK
  is unstable in a Windows remote or screen-off session, set
  `CAD_RENDER_BACKEND=matplotlib` and retry the review before skipping PNGs.
- Before fabrication or safety-critical use, clearly require human engineering
  review of dimensions, tolerances, materials, loads, and manufacturing rules.

## References

- Read [references/build123d.md](references/build123d.md) before writing an
  unfamiliar build123d feature or selector.
- Read [references/checkpoints.md](references/checkpoints.md) when defining or
  debugging feature-level assertions.
- Read [references/assemblies.md](references/assemblies.md) only for assemblies,
  standard purchased parts, or multi-body layout work.
- Read [references/review_drawing.md](references/review_drawing.md) only when
  ordinary views have exposed an ambiguity that needs localized visual evidence.
