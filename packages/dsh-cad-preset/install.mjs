// Copy this package's preset files into ~/.dsh/.agent-presets/cad-studio
// (idempotent; never removes extra user files under the target).
import { cpSync, existsSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const target = join(homedir(), ".dsh", ".agent-presets", "cad-studio");
mkdirSync(target, { recursive: true });
for (const entry of ["preset.yml", "agent.cordis.yml", "tool-bootstrap.mjs", "skills"]) {
  const src = join(root, entry);
  if (!existsSync(src)) throw new Error(`missing ${src}`);
  cpSync(src, join(target, entry), { recursive: true, force: true });
}
console.log(`installed CAD 工场 preset → ${target}`);
