// Package-lock harness: E-LOCK timeout, stale-lock reclaim, and clean release.
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import plugin from "./cad-studio-plugin.mjs";

const ws = mkdtempSync(join(process.cwd(), ".cad-smoke-lock-"));
const fakeSession = { header: { cwd: ws }, id: "lock-test" };
const fakeAgent = { session: fakeSession };
const tools = new Map();

function collector(stream, maxBytes) {
  const chunks = []; let total = 0;
  stream.on("data", (c) => { chunks.push(c); total += c.length; let excess = total - maxBytes;
    while (excess > 0 && chunks.length) { const first = chunks[0];
      if (first.length <= excess) { excess -= first.length; total -= first.length; chunks.shift(); }
      else { chunks[0] = first.subarray(first.length - (first.length - excess)); total = maxBytes; excess = 0; } } });
  return { reader() { return { readFrom: () => ({ text: Buffer.concat(chunks).toString("utf8"), nextOffset: total, lossy: false }) }; } };
}
const subprocess = {
  spawn(spec) {
    const child = spawn(spec.argv[0], spec.argv.slice(1), { cwd: spec.cwd, env: { ...process.env, PYTHONUTF8: "1" }, stdio: ["ignore", "pipe", "pipe"] });
    const so = collector(child.stdout, spec.stdio.stdout.maxBytes); const se = collector(child.stderr, spec.stdio.stderr.maxBytes);
    const done = new Promise((resolve, reject) => { child.on("error", reject); child.on("close", (code, signal) => resolve({ exitCode: code, signal })); });
    if (spec.signal) spec.signal.addEventListener("abort", () => { try { child.kill("SIGTERM"); } catch {} }, { once: true });
    return { pid: child.pid || -1, stdin: undefined, stdout: child.stdout, stderr: child.stderr,
      collected: { stdout: so.reader(), stderr: se.reader() }, done, terminate() { try { child.kill("SIGTERM"); } catch {} }, async waitForExit() { await done; return true; } };
  },
};
const ctx = { tools: { register(d) { tools.set(d.name, d); } }, get(n) { return n === "subprocess" ? subprocess : n === "jobs" ? null : undefined; } };
plugin.apply(ctx, { cliRoot: process.cwd(), lockTimeoutMs: 400, lockStaleMs: 800 });

const exec = { agent: fakeAgent, signal: new AbortController().signal };
await tools.get("cad_init").execute({ path: "demo", name: "Lock Test" }, exec);
const pkg = join(ws, "demo.456d");
writeFileSync(join(pkg, "src", "main.py"), "from build123d import *\nresult = Box(10, 10, 10)\n");

// 1) live lock → E-LOCK after timeout
const lockDir = join(pkg, ".cad-lock");
mkdirSync(lockDir);
writeFileSync(join(lockDir, "owner.json"), JSON.stringify({ label: "other", pid: 99999, ts: new Date().toISOString() }));
const blocked = await tools.get("cad_run").execute({ package: pkg }, exec);
if (blocked.ok || blocked.error.code !== "E-LOCK") throw new Error("live lock did not block: " + JSON.stringify(blocked));
console.log("LOCK-BLOCKS-OK", blocked.error.code, blocked.error.hint);

// 2) stale lock → reclaimed and run succeeds
writeFileSync(join(lockDir, "owner.json"), JSON.stringify({ label: "other", pid: 99999, ts: new Date(Date.now() - 60_000).toISOString() }));
const reclaimed = await tools.get("cad_run").execute({ package: pkg }, exec);
if (!reclaimed.ok) throw new Error("stale lock not reclaimed: " + JSON.stringify(reclaimed));
if (existsSync(lockDir)) throw new Error("lock dir left after release");
console.log("LOCK-STALE-RECLAIM-OK");

rmSync(ws, { recursive: true, force: true });
console.log("LOCK-HARNESS-OK");
process.exit(0);
