# CAD CLI Examples

This directory contains example build123d scripts demonstrating various features.

## Running Examples

```bash
# Initialize project
cad init

# Run an example
cad run examples/simple_box.py

# Validate the geometry
cad validate

# Inspect properties
cad inspect --prop=volume
cad inspect --prop=bounds

# Render views
cad render --views="top,front,iso"

# Export
cad export --format=step --output=output/example.step

# Commit
cad commit -m "Example design"
```

## Examples

### simple_box.py
Basic 100x50x20mm box demonstrating the simplest possible script.

### box_with_hole.py
Box with a cylindrical hole, demonstrating boolean operations.

### parametric_bracket.py
Parametric mounting bracket with holes and fillets, demonstrating:
- Parameters
- Multiple boolean operations
- Conditional operations (fillet fallback)

## Creating Your Own Scripts

All scripts must follow this convention:

```python
from build123d import *

# Your modeling code here
shape = Box(10, 10, 10)

# Assign final result (required!)
result = shape
```

The `result` variable must contain the final shape you want to work with.
