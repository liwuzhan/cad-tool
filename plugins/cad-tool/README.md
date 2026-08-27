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
- Feature-level Checkpoint assertions and BRep validation.
- Geometry inspection, text or rendered review, and design history.
- STEP and STL export.
- A separate path for preview-only failures on headless Windows systems.
