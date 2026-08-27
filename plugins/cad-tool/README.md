# CAD Tool for Codex

This skills-only Codex plugin carries the complete CAD CLI source and a
cross-platform runtime helper. Enabling the plugin does not run installers or
download dependencies.

## Install from the repository marketplace

```bash
codex plugin marketplace add liwuzhan/cad-tool --ref main
codex plugin add cad-tool@cad-tool
```

Start a new Codex session after installation. The first request that actually
needs CAD checks the isolated environment and asks before downloading the
build123d/OCP/PyVista dependency set (about 300 MB).

After the plugin is accepted into the universal plugin directory, the same
package can be installed from the Plugins tab or the Codex `/plugins` browser.

## What the skill covers

- Parametric build123d modeling in `.456d` model packages.
- Multi-solid assembly packages with explicit component placement and labels.
- Optional `cad-parts` search, comparison, interface metadata, and proxies.
- Feature-level Checkpoint assertions and BRep validation.
- Geometry inspection, text or rendered review, and design history.
- STEP and STL export.
- Automatic headless Matplotlib rendering with per-solid assembly colors; VTK remains available where stable.

The runtime helper exposes the optional catalog without requiring shell activation:

```bash
python3 scripts/cad.py parts -- search "20mm 轴承"
python3 scripts/cad.py parts -- describe 6204
```
