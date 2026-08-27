# Plugin distribution

## DSH

The storefront target is the self-contained package at
`packages/dsh-cad-studio`. Its `dsh.bundle` patch inserts one profile row, and
the same package declares the browser client and includes the Python CLI.

Tagging a version such as `v0.1.0-alpha.2` runs the release workflow and
attaches `dsh-cad-studio.tgz` to the GitHub Release. The ready-to-copy
awesome-dsh-plugin entry is under `release/awesome-dsh-plugin/`.

Before opening the upstream pull request:

1. Confirm the repository is at least one day old and has at least ten commits.
2. Add the `dsh-plugin` GitHub repository topic.
3. Push a version tag and verify the release tarball.
4. Copy the prepared YAML file to the same path under
   `awesome-dsh-plugin/awesome-dsh-plugin/data/plugins/`.
5. Run `npm ci` and `node scripts/generate-readme.mjs` in that repository, then
   open a pull request containing the entry and regenerated READMEs.

## Codex and ChatGPT

The installable plugin is `plugins/cad-tool`; the repository marketplace is
`.agents/plugins/marketplace.json`.

```bash
codex plugin marketplace add liwuzhan/cad-tool --ref main
codex plugin add cad-tool@cad-tool
```

The plugin is skills-only and has no remote service or authentication. Public
listing in the universal plugin directory is a separate reviewed submission
through the OpenAI Platform. The package includes listing metadata, policy
URLs, three starter prompts, screenshots, and five positive plus three negative
evaluation prompts. The submitter must still use a verified publisher identity
and complete the portal attestations.
