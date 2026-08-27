// Pack the four @deepseek-ai/dsh-cad-* packages, install the tarballs into a
// clean temp project, and verify bare-specifier resolution + manifest shape.
// Usage: node packages/test-tarballs.mjs [--keep]
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const keep = process.argv.includes("--keep");
const packDir = mkdtempSync(join(tmpdir(), "cad-packs-"));
const projDir = mkdtempSync(join(tmpdir(), "cad-pkg-test-"));
const tarballs = [];

function run(cmd, args, cwd) {
  return execFileSync(cmd, args, { cwd, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
}

try {
  for (const name of ["dsh-cad-tools", "dsh-cad-client", "dsh-cad-bundle", "dsh-cad-preset"]) {
    const out = run("npm", ["pack", "--pack-destination", packDir, join(root, "packages", name)], root);
    const file = out.trim().split("\n").at(-1);
    tarballs.push(join(packDir, file));
  }
  run("npm", ["init", "-y"], projDir);
  run("npm", ["install", "--no-audit", "--no-fund", ...tarballs], projDir);

  const test = `
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import tools from "@deepseek-ai/dsh-cad-tools";
const require = createRequire(import.meta.url);
if (typeof tools.apply !== "function" || !Array.isArray(tools.inject)) throw new Error("tools export broken");
const defs = [];
tools.apply({ tools: { register(d) { defs.push(d); } }, get() { return null; } }, {});
if (defs.length !== 16) throw new Error("expected 16 tools, got " + defs.length);
const clientPkg = require("@deepseek-ai/dsh-cad-client/package.json");
if (!clientPkg.dsh?.client || clientPkg.dsh.client.platform !== "web" || !Array.isArray(clientPkg.dsh.client.inject)) throw new Error("client manifest broken");
const clientUrl = import.meta.resolve("@deepseek-ai/dsh-cad-client/client");
if (!clientUrl.endsWith("lib/client.js")) throw new Error("client subpath broken: " + clientUrl);
const bundlePkg = require("@deepseek-ai/dsh-cad-bundle/package.json");
if (bundlePkg.dsh?.bundle?.patch !== "./cordis.patch.yml") throw new Error("bundle manifest broken");
const patch = readFileSync(new URL("./" + bundlePkg.dsh.bundle.patch, import.meta.resolve("@deepseek-ai/dsh-cad-bundle/package.json")), "utf8");
if (!patch.includes("@deepseek-ai/dsh-cad-tools") || !patch.includes("@deepseek-ai/dsh-cad-client")) throw new Error("bundle patch rows missing");
const presetPkg = require("@deepseek-ai/dsh-cad-preset/package.json");
if (!presetPkg.scripts?.install) throw new Error("preset install script missing");
console.log("NPM-PACKAGES-OK tools=" + defs.length + " client=" + clientUrl);
`;
  const testPath = join(projDir, "test.mjs");
  writeFileSync(testPath, test);
  const result = run("node", [testPath], projDir);
  console.log(result.trim());
  console.log(`TARBALLS-OK ${tarballs.length} packages (${packDir})`);
} finally {
  if (!keep) {
    rmSync(packDir, { recursive: true, force: true });
    rmSync(projDir, { recursive: true, force: true });
  }
}
