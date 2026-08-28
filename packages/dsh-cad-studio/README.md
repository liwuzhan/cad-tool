# dsh-cad-studio

Self-contained DSH plugin for the CAD Tool workflow. One install supplies:

- 16 Host tools covering environment setup, `.456d` packages, modeling,
  validation, inspection, ordinary multi-view review, optional model-directed
  dimensions/cutaways, versioning, and STEP/STL export;
- the browser-side CAD result cards;
- the complete Python `cad-cli` source used by the environment bootstrapper.

## Install

The plugin is not yet listed in the DSH marketplace. Download the newest
GitHub Release and add the tarball to the target profile:

```bash
# macOS / Linux
curl -fL https://github.com/liwuzhan/cad-tool/releases/latest/download/dsh-cad-studio.tgz \
  -o dsh-cad-studio.tgz
dsh plugin --profile <profile> add ./dsh-cad-studio.tgz
```

```powershell
# Windows PowerShell
Invoke-WebRequest `
  -Uri https://github.com/liwuzhan/cad-tool/releases/latest/download/dsh-cad-studio.tgz `
  -OutFile dsh-cad-studio.tgz
dsh plugin --profile <profile> add ./dsh-cad-studio.tgz
```

The `latest` URL always resolves to the newest published package. After the
marketplace entry is accepted, **CAD Studio** can also be installed there.

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
