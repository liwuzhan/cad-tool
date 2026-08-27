# CAD CLI v2.0 - Model Package Architecture

AI-Native CAD Command Line Tool with Model Packages (.456d)

## What's New in v2.0

### Key Improvements

1. **Model Packages (.456d)** - Self-contained package structure replacing `.cad` directories
2. **STEP Artifacts** - Reliable STEP files instead of unstable pickle caching
3. **JSON Metadata** - Render outputs include camera parameters and timestamps
4. **JSONL History** - Efficient commit history in JSONL format
5. **Artifact Management** - Configurable cleanup policies for managing storage
6. **Assembly Packages** - `kind=assembly`, multi-solid validation, aggregate metrics, and component-aware headless PNGs
7. **Optional Standard Parts** - Progressive `cadparts` catalog queries and reusable assembly proxies

### Migration from v1.0

v1.0 has been archived to `src/cad_cli/v1/`. No automatic migration is provided - start fresh with v2.0.

## Installation

### Codex plugin

```bash
codex plugin marketplace add liwuzhan/cad-tool --ref main
codex plugin add cad-tool@cad-tool
```

Start a new Codex session after installation. The plugin itself has no install
hook; on the first real CAD request it checks the local runtime and asks before
creating the isolated dependency environment.

### DSH plugin package

The self-contained storefront package is `packages/dsh-cad-studio`. It carries
the 16 Host tools, browser result cards, and the complete Python CLI in one
tarball. Until the marketplace entry is merged, install a release tarball or a
local pack with:

```bash
dsh plugin --profile <profile> add -w dsh-cad-studio
```

Headless Linux automatically uses a process-safe Matplotlib renderer and colors
assembly solids separately. On unstable Windows remote/screen-off sessions, set
`CAD_RENDER_BACKEND=matplotlib`. Use `CAD_SKIP_RENDER=1` only when automation
should omit PNGs completely; geometry checks, STEP, metrics, and history remain active.

### One-line install

```bash
git clone https://github.com/liwuzhan/cad-tool
cd cad-tool
bash install.sh          # macOS / Linux
# Windows: powershell -ExecutionPolicy Bypass -File install.ps1
```

The script needs **Python 3.11–3.14**, creates an isolated `.venv` inside the repo
(~300 MB download: build123d + OCP + pyvista), verifies the install with a smoke
test, and never touches your global site-packages.

**Optional:** clone the [cad-parts](https://github.com/liwuzhan/cad-parts)
parametric standard-parts library next to this repo — `install.sh` (and the DSH
plugin's `cad_env_bootstrap`) auto-detects and installs it as a soft dependency
(`CAD_PARTS_ROOT=/path` to override). Everything works without it; with it,
model scripts can directly `from cadparts import gear, deep_groove_bearing, ...`
and query the catalog via the `cadparts` CLI.

### AI-assisted install

Paste this prompt to any coding agent (Claude Code, DSH, Cursor, ...) — it can
finish the install on its own by reading this README:

```text
Install the CAD CLI tool:
1. git clone https://github.com/liwuzhan/cad-tool && cd cad-tool
2. macOS/Linux: run  bash install.sh
   Windows:      run  powershell -ExecutionPolicy Bypass -File install.ps1
   (Requires Python 3.11-3.14. The script builds an isolated .venv; do NOT
   pip-install into the global environment.)
3. Verify: .venv/bin/cad --help  (Windows: .venv\Scripts\cad.exe --help)
   then smoke-test the CLI by creating and running a throwaway package:
   cad init /tmp/smoke.456d --name=smoke && cd /tmp/smoke.456d && cad run
4. Report the installed versions and the smoke-test result.
If install.sh fails, follow its printed hints (Python version, pip mirror)
and retry; do not give up after one attempt.
```

### Manual install

```bash
# Using conda
conda create -n cad-cli python=3.12
conda activate cad-cli
conda install -c conda-forge build123d pyvista
pip install -e .

# Or plain pip inside a venv
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Quick Start

### 1. Create a Model Package

```bash
cad init my_gear --name="Spur Gear"
cd my_gear.456d
```

For an assembly, choose the assembly template explicitly:

```bash
cad init bearing_block --name="Bearing block assembly" --kind assembly
```

The assembly workflow keeps components as labeled `Compound` children and allows
multiple valid solids. See [`docs/assembly_workflow.md`](docs/assembly_workflow.md)
for coordinate, interface, standard-parts, validation, and review conventions.

This creates:
```
my_gear.456d/
├── manifest.json              # Package metadata
├── src/
│   └── main.py                # Your CAD script
├── vcs/
│   └── commits.jsonl          # Commit history
├── artifacts/                 # Build artifacts
└── runlog/                    # Execution logs
```

### 2. Write Your Model

Edit `src/main.py`:

```python
from build123d import *

# Create your model
result = Box(100, 50, 20)
```

### 3. Run and Test

```bash
# Execute script (in-memory, no artifacts)
cad run

# Validate geometry
cad validate

# Inspect properties
cad inspect --prop=volume
cad inspect --prop=bounds
```

### 4. Commit Your Work

```bash
# Full build workflow: execute + validate + STEP + thumbnails + metrics
cad commit -m "Initial gear design"
```

This creates artifacts at `artifacts/<hash>/`:
- `model.step` - STEP file (persistent)
- `thumb_*.png` - Thumbnail renders
- `thumb_*.json` - Render metadata
- `metrics.json` - Geometry metrics
- `validate.json` - Validation results

### 5. Version Control

```bash
# Show commit history
cad log

# Check current status
cad status

# Checkout previous version (loads STEP)
cad checkout abc123

# Export to file
cad export --format=step --output=gear_v1.step
```

### 6. Manage Artifacts

```bash
# List all artifacts and sizes
cad artifacts list

# Clean up old artifacts (uses manifest policy)
cad artifacts clean
```

## Command Reference

### Project Management

- `cad init <path> --name=<name>` - Create new model package
- `cad status` - Show repository status
- `cad log [--limit=N]` - Show commit history

### Modeling Workflow

- `cad run [script]` - Execute script (in-memory only)
- `cad build [script]` - Build workflow without commit
- `cad commit -m "msg" [script]` - Full build + commit
- `cad validate [script]` - Validate geometry
- `cad checkout <hash>` - Load commit's STEP artifact

### Inspection

- `cad inspect --prop=<property>` - Query geometry property
  - Properties: `volume`, `area`, `bounds`, `faces`, `edges`, `vertices`
- `cad inspect --list-targets` - List all topology targets
- `cad inspect --target=face[0] --target-prop=center` - Query specific target

### Output

- `cad render [--views=top,front,iso]` - Generate renders
- `cad export --format=<step|stl> --output=<path>` - Export model

### Artifact Management

- `cad artifacts list` - List artifacts and sizes
- `cad artifacts clean [--policy=<policy>]` - Clean up artifacts
  - Policies: `all_commits`, `latest_per_branch`, `releases_only`

### Branch Management

- `cad branch list` - List all branches
- `cad branch create <name>` - Create a new branch
- `cad branch switch <name>` - Switch to a branch (restores STEP + script)
- `cad branch delete <name>` - Delete a branch

## Model Package Structure

```
<model_name>.456d/
├── manifest.json              # Package metadata
│   ├── name, version
│   ├── head (current commit)
│   ├── branches
│   ├── artifact_policy
│   └── render settings
│
├── src/
│   └── main.py                # Main script
│
├── vcs/
│   └── commits.jsonl          # Linear commit history
│
├── artifacts/
│   └── <commit_hash>/
│       ├── model.step         # STEP artifact
│       ├── thumb_*.png        # Thumbnails
│       ├── thumb_*.json       # Render metadata
│       ├── metrics.json       # Geometry metrics
│       └── validate.json      # Validation results
│
└── runlog/
    └── <run_id>.jsonl         # Execution logs
```

## Configuration

Edit `manifest.json` to configure:

```json
{
  "name": "My Model",
  "unit": "mm",
  "timeout_seconds": 60,
  "artifact_policy": "latest_per_branch",
  "render": {
    "default_views": ["top", "front", "right", "iso"],
    "resolution": [800, 600],
    "image_format": "png"
  }
}
```

## Output Format

All commands output JSONL (JSON Lines):

```json
{"event": "run_start", "ts": "2026-01-31T10:30:00", "payload": {"script": "src/main.py"}}
{"event": "run_success", "ts": "2026-01-31T10:30:01", "payload": {"metrics": {...}}}
```

## Script Convention

Scripts must assign the final shape to a `result` variable:

```python
from build123d import *

# Create geometry
box = Box(100, 50, 20)
cylinder = Cylinder(30, 100)

# Assign to result
result = box - cylinder
```

## Feature-Level Checkpoints

Checkpoints are the reliable way to detect boolean operation failures. Add checkpoints after each feature operation:

```python
from build123d import *
from cad_cli.feedback import Checkpoint

Checkpoint.reset()

with BuildPart() as part:
    Cylinder(30, 10)
    Checkpoint(part, "base").expect_volume(28274, tolerance=100).expect_solids(1).verify()

    Cylinder(10, 10, mode=Mode.SUBTRACT)
    Checkpoint(part, "hole").expect_volume_decreased().expect_solids(1).verify()

result = part.part
```

### Checkpoint Methods

| Method | Description |
|--------|-------------|
| `.expect_volume(value, tolerance=1.0)` | Assert specific volume |
| `.expect_volume_decreased()` | Assert volume decreased from previous checkpoint |
| `.expect_volume_increased()` | Assert volume increased from previous checkpoint |
| `.expect_solids(count)` | Assert number of solids (always verify = 1) |
| `.expect_faces(count)` | Assert face count |
| `.expect_bbox_size(x, y, z, tolerance=1.0)` | Assert bounding box dimensions |
| `.verify()` | Execute all checks, raise exception on failure |

Checkpoint results appear in JSONL output as `checkpoint_passed` or `checkpoint_failed` events.

## Testing

Run the test suite:

```bash
pytest                           # All tests
pytest --cov=cad_cli             # With coverage
pytest test/test_package.py -v   # Specific test
```

## Architecture Highlights

### v2.0 vs v1.0

| Feature | v1.0 | v2.0 |
|---------|------|------|
| Project structure | `.cad/` directory | `.456d` package |
| Shape caching | Pickle (unreliable) | STEP artifacts |
| Commit storage | Individual JSON files | Single JSONL file |
| Render metadata | None | JSON with camera params |
| Artifact cleanup | Manual | Policy-based |
| Complex models | Fails >150 faces | Reliable with STEP |

## Error Codes

- `E-SYNTAX` - Python syntax error
- `E-RUNTIME` - Runtime error
- `E-CONSTRAINT` - Constraint violation
- `E-BREP` - BRep validation failure
- `E-RENDER` - Rendering error
- `E-IO` - File I/O error

## Development

```bash
pip install -e ".[dev]"   # Install dev dependencies
pytest                     # Run tests
black src/ test/           # Format code
mypy src/                  # Type check
```

## Requirements

- Python 3.11+
- build123d 0.5.0+
- cadquery-ocp 7.7.0+
- pyvista 0.43.0+
- click 8.1.0+
- numpy 1.24.0+

## License

MIT

## Troubleshooting

### "No model package found"
Make sure you're inside a `.456d` directory or run `cad init` first.

### "STEP artifact not found"
The commit may have been cleaned up. Check `cad artifacts list`.

### Render failures
Ensure pyvista is installed: `pip install pyvista`

### Import errors
Make sure build123d is installed: `conda install -c conda-forge build123d`
