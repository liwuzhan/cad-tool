# dsh-cad-studio

Self-contained DSH plugin for the CAD Tool workflow. One install supplies:

- 16 Host tools covering environment setup, `.456d` packages, modeling,
  validation, inspection, rendering, versioning, and STEP/STL export;
- the browser-side CAD result cards;
- the complete Python `cad-cli` source used by the environment bootstrapper.

## Install

From the DSH plugin marketplace, choose **CAD Studio**. For a local tarball or
registry build, add the single package to the target profile:

```bash
dsh plugin --profile <profile> add -w dsh-cad-studio
```

Start a new session after installation, then call `cad_env_status`. If the
isolated Python environment is not ready, approve `cad_env_bootstrap` once.
The dependency download is about 300 MB and does not modify global Python
packages.

## Headless rendering

Geometry execution, validation, STEP generation, and export work without an
attached display. Some Windows render backends can fail when no interactive
screen is available; that preview-only failure does not invalidate successful
geometry or STEP output.

## Package layout

- `lib/index.js` — DSH Host plugin and 16 `cad_*` tools.
- `lib/client.js` — browser CAD result cards.
- `cad-cli/` — vendored Python CLI and dependency manifest.
- `cordis.patch.yml` — one-row profile bundle patch.
