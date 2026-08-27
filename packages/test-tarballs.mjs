// Pack the legacy @deepseek-ai/dsh-cad-* packages plus the unified storefront
// package, install the tarballs into a
// clean temp project, and verify bare-specifier resolution + manifest shape.
// Usage: node packages/test-tarballs.mjs [--keep]
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
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
  for (const name of ["dsh-cad-tools", "dsh-cad-client", "dsh-cad-bundle", "dsh-cad-preset", "dsh-cad-studio"]) {
    const out = run("npm", ["pack", "--offline", "--ignore-scripts", "--pack-destination", packDir, join(root, "packages", name)], root);
    const file = out.trim().split("\n").at(-1);
    tarballs.push(join(packDir, file));
  }
  run("npm", ["init", "-y"], projDir);
  run("npm", ["install", "--offline", "--ignore-scripts", "--legacy-peer-deps", "--no-audit", "--no-fund", ...tarballs], projDir);

  const test = `
import { createRequire } from "node:module";
import { existsSync, readFileSync } from "node:fs";
import tools from "@deepseek-ai/dsh-cad-tools";
import studio from "dsh-cad-studio";
const require = createRequire(import.meta.url);
if (typeof tools.apply !== "function" || !Array.isArray(tools.inject)) throw new Error("tools export broken");
const defs = [];
tools.apply({ tools: { register(d) { defs.push(d); } }, get() { return null; } }, {});
if (defs.length !== 16) throw new Error("expected 16 tools, got " + defs.length);
const studioDefs = [];
studio.apply({ tools: { register(d) { studioDefs.push(d); } }, get() { return null; } }, {});
if (studioDefs.length !== 16) throw new Error("expected 16 unified tools, got " + studioDefs.length);
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
const studioPkgUrl = import.meta.resolve("dsh-cad-studio/package.json");
const studioPkg = require("dsh-cad-studio/package.json");
if (studioPkg.dsh?.bundle?.patch !== "./cordis.patch.yml" || studioPkg.dsh?.client?.platform !== "web") throw new Error("unified manifest broken");
const studioPatch = readFileSync(new URL("./" + studioPkg.dsh.bundle.patch, studioPkgUrl), "utf8");
if (!studioPatch.includes("name: dsh-cad-studio") || studioPatch.match(/- id:/g)?.length !== 1) throw new Error("unified bundle must insert one package row");
const studioClientUrl = import.meta.resolve("dsh-cad-studio/client");
if (!studioClientUrl.endsWith("lib/client.js")) throw new Error("unified client subpath broken");
if (!readFileSync(new URL(studioClientUrl), "utf8").includes('id: "dsh-cad-studio"')) throw new Error("unified client module id broken");
if (!existsSync(new URL("./cad-cli/src/cad_cli/__main__.py", studioPkgUrl))) throw new Error("unified vendored CLI missing");
console.log("NPM-PACKAGES-OK tools=" + defs.length + " unified=" + studioDefs.length + " client=" + clientUrl);
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
