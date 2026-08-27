# Installation Guide

## Prerequisites

- Python 3.11 or higher
- Conda (recommended) or pip

## Installation Steps

### Option 1: Using Conda (Recommended)

Conda is recommended because build123d and its dependencies (especially OCP) are easier to install via conda-forge.

```bash
# 1. Create a new conda environment
conda create -n cad-cli python=3.11
conda activate cad-cli

# 2. Install build123d and pyvista from conda-forge
conda install -c conda-forge build123d pyvista

# 3. Navigate to the project directory
cd "C:\Users\liwuz\Desktop\test\cad tools"

# 4. Install CAD CLI in development mode
pip install -e .

# 5. Verify installation
cad --help
```

### Option 2: Using pip

```bash
# 1. Create a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# 2. Install dependencies
pip install build123d pyvista click numpy

# 3. Install CAD CLI
pip install -e .

# 4. Verify installation
cad --help
```

## Development Installation

For development with testing and code quality tools:

```bash
# Install with development dependencies
pip install -e ".[dev]"

# Verify pytest is installed
pytest --version
```

## Troubleshooting

### Issue: build123d installation fails with pip

**Solution**: Use conda instead:
```bash
conda install -c conda-forge build123d
```

### Issue: OCP module not found

**Solution**: Install cadquery-ocp:
```bash
conda install -c conda-forge cadquery-ocp
# or
pip install cadquery-ocp
```

### Issue: pyvista rendering errors

**Solution**: For headless environments, pyvista will automatically use software rendering. Ensure you have:
```bash
pip install pyvista[all]
```

### Issue: Command not found after installation

**Solution**: Ensure the Python Scripts directory is in your PATH, or use:
```bash
python -m cad_cli --help
```

## Verifying Installation

Run these commands to verify everything is working:

```bash
# 1. Check CLI is accessible
cad --help

# 2. Initialize a test project
mkdir test_project
cd test_project
cad init

# 3. Create a simple script
echo "from build123d import *" > test.py
echo "result = Box(10, 10, 10)" >> test.py

# 4. Run the script
cad run test.py

# 5. Validate
cad validate

# 6. Inspect
cad inspect --prop=volume
```

If all commands complete without errors, the installation is successful!

## Next Steps

- Read the [README.md](README.md) for usage instructions
- Try the examples in the `examples/` directory
- Run the test suite: `pytest`
