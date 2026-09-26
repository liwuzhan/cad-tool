# Changelog

## 0.1.0-alpha.10 (2026-09-26)

- Report `NOTHING_TO_CHECK` instead of `PASS` when a package declares ports but
  no mates. Found by inspecting a package with six declared ports and zero
  mates: it reported `overall: PASS`, the most misleading thing a checker can
  emit, because a reader sees the word and stops looking.
- Document the new verdict in the `cad-modeling` skill.

## 0.1.0-alpha.9 (2026-09-26)

- Move "which layer surfaces which kind of error" into the `cad-modeling` skill,
  where it belongs, instead of encoding a responsibility map into `cad mates`
  output. Tool output stays factual — what the check does and does not decide —
  and the judgement about where to look next stays with the model. This also
  keeps the skill consistent with its own stated principle that these are
  capabilities rather than a mandatory pipeline.

## 0.1.0-alpha.8 (2026-09-26)

- Document the declarative shaft generator in the `cad-modeling` skill. The
  generator is not a catalogue family (a shaft is a design artefact derived from
  what mounts on it, not a catalogue part), so `cadparts search` cannot surface
  it; without this the capability is unreachable for a model that only knows the
  discovery path.

## 0.1.0-alpha.7 (2026-09-26)

- Fix every `cad_*` tool failing with "subprocess 服务不可用" on DSH 0.1.7. The
  plugin only injected `tools`, so cordis could instantiate it before
  `dsh-subprocess-local` had registered the `subprocess` service; `ctx.get()`
  returned undefined and the value was frozen into the closure for the plugin's
  whole lifetime. It now injects `["tools", "subprocess"]`.
- Resolve `sandboxPolicy` lazily per call instead of at `apply()`. It is not
  registered yet when the plugin instantiates (verified: available ~2.5 s later,
  and injecting it blocks the plugin from loading at all). Capturing the
  `undefined` silently downgraded every write command to `unconfined`, dropping
  the session sandbox policy without any diagnostic.
- Warn through `ctx.logger` when a captured service is missing, instead of
  leaving a silent `undefined`.

## 0.1.0-alpha.6 (2026-09-26)

- Support DSH 0.1.7-rc.2. Its plugin compatibility gate compares only
  `@deepseek-ai/dsh*` peer ranges with `includePrerelease` semantics, which the
  existing ranges already satisfy; no range change was required.
- Ship the CAD skills inside this package and register them through a
  `@deepseek-ai/dsh-skill-filesystem` provider. DSH 0.1.7 removed directory-based
  agent presets, so the skills previously installed to `~/.dsh/.agent-presets/`
  no longer loaded for any session.
- Declare `@deepseek-ai/dsh-skill-filesystem` as an optional peer.

## 0.1.0-alpha.5 (2026-09-01)

- Confirm compatibility with DSH 0.1.2 after its breaking runtime changes.
- Refresh the installable DSH package from the current main branch.
- Keep the existing CAD tool registration and packaged CLI workflow working on the current DSH contract.

## 0.1.0-alpha.4 (2026-08-28)

- Fix the macOS Bash 3.2 variable-boundary failure when optional `cad-parts` is detected.
- Ship the corrected installer in the self-contained DSH release tarball.

## 0.1.0-alpha.3 (2026-08-28)

- Add the model-first assembly workflow and optional `cad-parts` integration.
- Add model-directed review drawings with dimensions, labels, sections, and probes.
- Discover `.456d` packages both at the workspace root and one directory below it.
- Ship the simplified, model-directed CAD guidance and worked examples.

## 0.1.0-alpha.2

- Add the single-package DSH distribution.
- Bundle the Host tools, browser client, and complete Python CAD CLI.
- Add release-store metadata and screenshots.
