# Quick Start Guide

Get started with CAD CLI in 5 minutes!

## 1. Installation

```bash
# Create conda environment
conda create -n cad-cli python=3.11
conda activate cad-cli

# Install dependencies
conda install -c conda-forge build123d pyvista

# Install CAD CLI
cd "C:\Users\liwuz\Desktop\test\cad tools"
pip install -e .
```

## 2. Initialize Your First Project

```bash
# Create project directory
mkdir my_cad_project
cd my_cad_project

# Initialize CAD CLI
cad init
```

You should see:
```json
{"event": "init_success", "ts": "2026-01-29T...", "payload": {"cad_dir": ".cad"}}
```

## 3. Create Your First Model

Create a file called `main.py`:

```python
from build123d import *

# Create a simple box
box = Box(100, 50, 20)

# IMPORTANT: Assign to 'result'
result = box
```

## 4. Run and Validate

```bash
# Execute the script
cad run main.py

# Validate the geometry
cad validate
```

Expected output:
```json
{"event": "run_start", ...}
{"event": "run_success", "payload": {"metrics": {"volume": 100000, ...}}}
{"event": "validate_start", ...}
{"event": "validate_success", ...}
```

## 5. Inspect Properties

```bash
# Get volume
cad inspect --prop=volume

# Get bounding box
cad inspect --prop=bounds

# Get surface area
cad inspect --prop=area

# List all faces, edges, vertices
cad inspect --list-targets
```

## 6. Generate Renderings

```bash
# Render default views
cad render --views="top,front,right,iso"
```

Images are saved to `.cad/thumbs/`:
- `top.png`
- `front.png`
- `right.png`
- `iso.png`

## 7. Export Your Model

```bash
# Export to STEP (for CAD software)
cad export --format=step --output=output/my_box.step

# Export to STL (for 3D printing)
cad export --format=stl --output=output/my_box.stl
```

## 8. Version Control

```bash
# Commit your design
cad commit -m "Initial box design"

# View commit history
cad log

# Check status
cad status
```

## Next Steps

### Try More Complex Models

Edit `main.py`:

```python
from build123d import *

# Create a box with a hole
box = Box(100, 50, 20)
cylinder = Cylinder(15, 30, align=(Align.CENTER, Align.CENTER, Align.CENTER))
result = box - cylinder
```

Run the workflow again:
```bash
cad run main.py
cad validate
cad render --views="iso"
cad commit -m "Added hole to box"
```

### Explore Examples

```bash
# Run an example
cad run examples/box_with_hole.py
cad render --views="iso"
```

### Query Specific Topology

```bash
# List all faces
cad inspect --list-targets

# Query a specific face
cad inspect --target=face[0] --target-prop=center
cad inspect --target=face[0] --target-prop=area

# Query an edge
cad inspect --target=edge[0] --target-prop=length
```

## Common Workflows

### Design Iteration

```bash
# 1. Edit main.py
# 2. Run and validate
cad run main.py && cad validate

# 3. Check changes
cad inspect --prop=volume

# 4. Render
cad render --views="iso"

# 5. Commit if satisfied
cad commit -m "Updated design"
```

### Export for Manufacturing

```bash
# Run and validate
cad run main.py
cad validate

# Export STEP for CNC
cad export --format=step --output=manufacturing/part.step

# Export STL for 3D printing
cad export --format=stl --output=manufacturing/part.stl
```

### Review History

```bash
# View all commits
cad log

# Check current status
cad status
```

## Tips

1. **Always assign to `result`**: Your script must end with `result = <your_shape>`

2. **Use JSONL output**: All commands output JSONL for easy parsing by AI tools

3. **Check validation**: Always run `cad validate` before exporting

4. **Commit often**: Use version control to track design iterations

5. **Use parameters**: Make your designs parametric for easy modification

## Troubleshooting

### Script doesn't run
- Check syntax: `python main.py` (should show error)
- Ensure `result` variable is defined
- Check imports: `from build123d import *`

### Validation fails
- Check geometry is valid (no self-intersections)
- Ensure shape has positive volume
- Review error messages in JSONL output

### Rendering fails
- Ensure pyvista is installed: `pip install pyvista`
- Check `.cad/thumbs/` directory exists
- Try a simpler shape first

## Getting Help

- Read the full [README.md](README.md)
- Check [INSTALL.md](INSTALL.md) for installation issues
- Review [examples/](examples/) for more complex models
- See [TESTING.md](TESTING.md) for development

## Example Session

Here's a complete example session:

```bash
# Setup
mkdir bracket_project
cd bracket_project
cad init

# Create design
cat > main.py << 'EOF'
from build123d import *

# Parametric bracket
width = 80
height = 60
thickness = 10

base = Box(width, height, thickness)
hole = Cylinder(4, thickness*2, align=(Align.CENTER, Align.CENTER, Align.CENTER))
hole = hole.translate((width/3, height/3, 0))

result = base - hole
EOF

# Execute workflow
cad run main.py
cad validate
cad inspect --prop=volume
cad render --views="top,front,iso"
cad export --format=step --output=bracket.step
cad commit -m "Initial bracket design"

# Review
cad log
cad status
```

Congratulations! You've created, validated, rendered, exported, and version-controlled your first CAD model with CAD CLI!
