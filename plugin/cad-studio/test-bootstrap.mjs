// Standalone cad_env_bootstrap verification (real pip install into
// ~/.cache/dsh-cad/venv through the plugin's own runner).
import { spawn } from "node:child_process";
import plugin from "./cad-studio-plugin.mjs";

const fakeSession = { header: { cwd: process.cwd() }, id: "bootstrap-test" };
const fakeAgent = { session: fakeSession };
const tools = new Map();

function collector(stream, maxBytes) {
  const chunks = [];
  let total = 0;
  stream.on("data", (c) => {
    chunks.push(c);
    total += c.length;
    let excess = total - maxBytes;
    while (excess > 0 && chunks.length) {
      const first = chunks[0];
      if (first.length <= excess) { excess -= first.length; total -= first.length; chunks.shift(); }
      else { chunks[0] = first.subarray(first.length - (first.length - excess)); total = maxBytes; excess = 0; }
    }
  });
  return {
    reader() {
      const self = this;
      return { readFrom: () => ({ text: Buffer.concat(chunks).toString("utf8"), nextOffset: total, lossy: false, spillPath: undefined }) };
    },
  };
}

const subprocess = {
  spawn(spec) {
    const child = spawn(spec.argv[0], spec.argv.slice(1), {
      cwd: spec.cwd,
      env: { ...process.env, PYTHONUTF8: "1" },
      stdio: ["ignore", "pipe", "pipe"],
    });
    const so = collector(child.stdout, spec.stdio.stdout.maxBytes);
    const se = collector(child.stderr, spec.stdio.stderr.maxBytes);
    const done = new Promise((resolve, reject) => {
      child.on("error", reject);
      child.on("close", (code, signal) => resolve({ exitCode: code, signal }));
    });
    if (spec.signal) spec.signal.addEventListener("abort", () => { try { child.kill("SIGTERM"); } catch {} }, { once: true });
    return {
      pid: child.pid || -1, stdin: undefined, stdout: child.stdout, stderr: child.stderr,
      collected: { stdout: so.reader(), stderr: se.reader() },
      done, terminate() { try { child.kill("SIGTERM"); } catch {} },
      async waitForExit() { await done; return true; },
    };
  },
};

const ctx = {
  tools: { register(d) { tools.set(d.name, d); } },
  get(name) { return name === "subprocess" ? subprocess : name === "jobs" ? null : undefined; },
};
plugin.apply(ctx, { cliRoot: process.cwd() });

const bootstrap = tools.get("cad_env_bootstrap");
if (!bootstrap) throw new Error("cad_env_bootstrap not registered");
const value = await bootstrap.execute(
  { channel: "pip", run_in_background: false },
  { agent: fakeAgent, signal: new AbortController().signal },
);
console.log(JSON.stringify(value, null, 2));
if (!value.ok || value.background || value.smoke.cli_ok !== true || value.smoke.import_ok !== true) process.exit(1);
console.log("BOOTSTRAP-OK");
process.exit(0);
