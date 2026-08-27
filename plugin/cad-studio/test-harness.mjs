// Standalone harness for cad-studio-plugin.mjs — simulates the DSH Host
// contract (ctx.tools / ctx.subprocess) with real node child processes so the
// plugin's runner path is tested end-to-end against the real CAD CLI.
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync, existsSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import plugin from "./cad-studio-plugin.mjs";

const ws = mkdtempSync(join(process.cwd(), ".cad-smoke-"));
const toolDefs = new Map();
const fakeSession = { header: { cwd: ws }, id: "test-session" };
const fakeAgent = { session: fakeSession };

function tailCollect(stream, maxBytes) {
  let chunks = [];
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
    text() { return Buffer.concat(chunks).toString("utf8"); },
    truncated: false,
    reader() {
      return { readFrom: () => ({ text: this.text(), nextOffset: total, lossy: false, spillPath: undefined }) };
    },
  };
}

const mockSubprocess = {
  spawn(spec) {
    const child = spawn(spec.argv[0], spec.argv.slice(1), {
      cwd: spec.cwd,
      env: { ...process.env, PYTHONUTF8: "1", CAD_CLI_NO_TELEMETRY: "1" },
      stdio: ["ignore", "pipe", "pipe"],
    });
    const so = tailCollect(child.stdout, spec.stdio.stdout.maxBytes);
    const se = tailCollect(child.stderr, spec.stdio.stderr.maxBytes);
    const done = new Promise((resolve, reject) => {
      child.on("error", (e) => { try { child.kill(); } catch {} reject(e); });
      child.on("close", (code, signal) => resolve({ exitCode: code, signal }));
    });
    if (spec.signal) {
      spec.signal.addEventListener("abort", () => {
        try { child.kill("SIGTERM"); } catch {}
        setTimeout(() => { try { child.kill("SIGKILL"); } catch {} }, 3000).unref();
      }, { once: true });
    }
    return {
      pid: child.pid || -1,
      stdin: undefined, stdout: child.stdout, stderr: child.stderr,
      collected: { stdout: so.reader(), stderr: se.reader() },
      done,
      terminate() { try { child.kill("SIGTERM"); } catch {} },
      async waitForExit() { await done; return true; },
    };
  },
};

const ctx = {
  tools: { register(def) { toolDefs.set(def.name, def); } },
  get(name) {
    if (name === "subprocess") return mockSubprocess;
    if (name === "jobs") return null;
    return undefined;
  },
};

plugin.apply(ctx, { cliRoot: process.cwd() });

function find(name) {
  const t = toolDefs.get(name);
  if (!t) throw new Error(`tool ${name} not registered`);
  return t;
}
const execCtx = { agent: fakeAgent, signal: new AbortController().signal };

// 最小 JSON-Schema 校验器：覆盖插件 output.schema 用到的子集
// （type/properties/required/additionalProperties/items/enum）。
// 回归目标：canonical 输出里 null 不得泄漏进 string/object 类型键。
function validateSchema(schema, value, path) {
  if (!schema || typeof schema !== "object") return [];
  const errs = [];
  const typeOf = (v) => (v === null ? "null" : Array.isArray(v) ? "array" : typeof v);
  const t = schema.type;
  if (t) {
    const actual = typeOf(value);
    const match =
      (t === "integer" && actual === "number" && Number.isInteger(value)) ||
      (t === "number" && actual === "number") ||
      (t !== "integer" && t !== "number" && actual === t);
    if (!match) {
      errs.push(`${path}: expected ${t}, got ${actual} (${JSON.stringify(value)?.slice(0, 60)})`);
      return errs;
    }
  }
  if (schema.enum && !schema.enum.includes(value)) errs.push(`${path}: ${JSON.stringify(value)} not in enum`);
  if (t === "object" && schema.properties) {
    for (const [k, sub] of Object.entries(schema.properties)) {
      if (value[k] !== undefined) errs.push(...validateSchema(sub, value[k], `${path}.${k}`));
    }
    if (schema.additionalProperties === false) {
      for (const k of Object.keys(value)) {
        if (!(k in schema.properties)) errs.push(`${path}.${k}: additional property`);
      }
    }
    for (const k of schema.required || []) {
      if (value[k] === undefined) errs.push(`${path}.${k}: required but missing`);
    }
  }
  if (t === "array" && schema.items) {
    value.forEach((item, i) => errs.push(...validateSchema(schema.items, item, `${path}[${i}]`)));
  }
  return errs;
}

async function call(name, args) {
  const t = find(name);
  const value = await t.execute(args, execCtx);
  if (t.output && t.output.schema) {
    const errs = validateSchema(t.output.schema, value, "value");
    if (errs.length) throw new Error(`${name} output schema violations:\n  ${errs.join("\n  ")}`);
  }
  const rendered = t.output.render(args, value);
  console.log(`\n=== ${name}(${JSON.stringify(args)}) ===`);
  console.log(rendered.map((b) => b.text).join("\n"));
  return value;
}

async function main() {
  // 1. env status (no CAD_PYTHON override → should find workspace .venv up-tree)
  const status = await call("cad_env_status", {});
  if (!status.ok) throw new Error("env status failed: " + JSON.stringify(status.error));

  // 2. package list (empty)
  await call("cad_pkg_list", {});

  // 3. init
  const init = await call("cad_init", { path: "demo", name: "Demo Box" });
  if (!init.ok) throw new Error("init failed: " + JSON.stringify(init.error));

  // 4. write main.py with checkpoints（第三个用 render=False：回归 render=False 时
  //    checkpoint.image 不得为 null，否则 output schema 校验失败）
  const mainPy = join(init.package.path, "src", "main.py");
  writeFileSync(mainPy, `from build123d import *
from cad_cli.feedback import Checkpoint
Checkpoint.reset()
with BuildPart() as part:
    Box(100, 60, 30)
    Checkpoint(part, "base").expect_solids(1).expect_bbox_size(100, 60, 30).verify()
    Cylinder(10, 30, mode=Mode.SUBTRACT)
    Checkpoint(part, "hole").expect_volume_decreased().expect_solids(1).verify()
    Box(5, 5, 5, mode=Mode.SUBTRACT)
    Checkpoint(part, "norender").expect_solids(1).verify(render=False)
result = part.part
`);

  // 5. run
  const run = await call("cad_run", { package: init.package.path });
  if (!run.ok) throw new Error("run failed: " + JSON.stringify(run.error));
  if (!run.metrics || run.metrics.volume <= 0) throw new Error("run metrics missing");
  if (run.checkpoints.length !== 3) throw new Error(`expected 3 checkpoints, got ${run.checkpoints.length}`);
  if (!run.preview || run.preview.length !== 2 || !run.preview.every((p) => p.dataUrl)) throw new Error("run checkpoint preview missing");
  if (!existsSync(run.runlog)) throw new Error("runlog not written");

  // 5b. 失败路径回归：脚本语法错误 → ok:false + error，metrics 键必须缺省而非 null
  const badPy = join(init.package.path, "src", "bad.py");
  writeFileSync(badPy, "this is not python\n");
  const badRun = await call("cad_run", { package: init.package.path, script: badPy });
  if (badRun.ok !== false || !badRun.error) throw new Error("bad script should fail with error");
  if ("metrics" in badRun) throw new Error("failed run must omit metrics key (null leaks into schema)");

  // 6. validate (script path: no HEAD yet) + commit
  const val = await call("cad_validate", { package: init.package.path, script: mainPy });
  if (!val.ok) throw new Error("validate failed: " + JSON.stringify(val.error));

  // 7. commit
  const commit = await call("cad_commit", { package: init.package.path, message: "plugin harness smoke" });
  if (!commit.ok) throw new Error("commit failed: " + JSON.stringify(commit.error));
  if (!commit.artifacts.some((a) => a.name === "model.step")) throw new Error("model.step missing");
  if (commit.artifacts.filter((a) => a.name.endsWith(".png")).length !== 4) throw new Error("expected 4 thumbnails");
  if (!commit.preview || commit.preview.length !== 4 || !commit.preview.every((p) => p.dataUrl)) throw new Error("commit preview missing");

  // 8. inspect (HEAD now exists)
  const insp = await call("cad_inspect", { package: init.package.path, prop: "volume" });
  if (!insp.ok) throw new Error("inspect failed: " + JSON.stringify(insp.error));

  // 8. pkg list should show head
  const pkgs = await call("cad_pkg_list", {});
  if (pkgs.packages[0].head !== commit.commit.hash) throw new Error("manifest head not updated");

  // 9. status / log
  const repoStatus = await call("cad_status", { package: init.package.path });
  if (!repoStatus.ok || repoStatus.status.head !== commit.commit.hash) throw new Error("status head mismatch");
  const history = await call("cad_log", { package: init.package.path, limit: 5 });
  if (!history.ok || history.total < 1) throw new Error("log failed");

  // 10. render (iso+top) — verifies image output + preview dataUrl
  const rendered = await call("cad_render", { package: init.package.path, views: ["iso", "top"] });
  if (!rendered.ok || rendered.images.length !== 2 || !rendered.preview.some((p) => p.dataUrl.startsWith("data:image/png;base64,"))) throw new Error("render failed");

  // 11. review (rendered iso+front) — exercises image preview meta path
  const review = await call("cad_review", { package: init.package.path, views: ["iso", "front"] });
  if (!review.ok || review.features.length !== 3) throw new Error("review failed: " + JSON.stringify(review.error));
  if (!review.preview || review.preview.length !== 2 || !review.preview.every((p) => p.dataUrl)) throw new Error("review preview missing");

  // 12. export step + stl
  const exp = await call("cad_export", { package: init.package.path, format: "step", output: join(ws, "out.step") });
  if (!exp.ok || !existsSync(exp.path)) throw new Error("export step failed");
  const expStl = await call("cad_export", { package: init.package.path, format: "stl", output: join(ws, "out.stl") });
  if (!expStl.ok || !existsSync(expStl.path)) throw new Error("export stl failed");

  // 13. artifacts list
  const arts = await call("cad_artifact", { package: init.package.path, op: "list" });
  if (!arts.ok || arts.artifacts.length < 1) throw new Error("artifacts list failed");

  // 14. branch lifecycle
  const bl0 = await call("cad_branch", { package: init.package.path, op: "list" });
  if (!bl0.ok || bl0.result.length < 1) throw new Error("branch list failed");
  await call("cad_branch", { package: init.package.path, op: "create", name: "dev" });
  await call("cad_branch", { package: init.package.path, op: "switch", name: "main" });
  const bl1 = await call("cad_branch", { package: init.package.path, op: "list" });
  if (!bl1.ok || !bl1.result.some((b) => b.name === "dev" || b.branch === "dev")) throw new Error("branch create failed");
  await call("cad_branch", { package: init.package.path, op: "delete", name: "dev", force: true });

  // 15. checkout back to the commit we made
  const co = await call("cad_checkout", { package: init.package.path, commit: commit.commit.hash });
  if (!co.ok) throw new Error("checkout failed: " + JSON.stringify(co.error));

  console.log(`\nALL-OK workspace=${ws} commit=${commit.commit.hash} tools=${toolDefs.size}`);
  process.exit(0);
}

main().catch((e) => { console.error("HARNESS-FAIL", e); process.exit(1); });
