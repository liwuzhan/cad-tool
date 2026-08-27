// cad-studio —— CAD 工场：面向 agent 的 DSH 插件（vendored preset 形态，阶段 A）
//
// P1（dsh-cad-core）+ P2（dsh-cad-tools）的原型合并在本文件内：
//   - CadRuntime：Python 环境解析、venv 引导、CLI runner（ctx.subprocess +
//     ctx.sandbox + 超时/取消）、JSONL 事件流规范化、.456d 模型包索引、runlog 落盘；
//   - cad_* 工具：env_status / env_bootstrap / init / run / validate / inspect /
//     commit / pkg_list，全部返回 canonical JSON，模型可见文本走 output.render。
//
// 设计原则：
//   - CAD CLI（Python，build123d）是唯一几何真源；本插件只做编排与展示；
//   - 所有子进程 argv 数组化，不拼 shell；写入类命令经 ctx.sandbox 按会话策略约束；
//   - CLI 非零退出不抛异常：返回 {ok:false, error:{code,message,hint}}；
//     只有基础设施错误（subprocess 服务缺失、spawn 失败）才 throw 进入 isError 通道。
//
// 用法：作为 agent preset 的一行插件（name: './cad-studio-plugin.mjs'）。
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { basename, dirname, extname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const PLUGIN_DIR = dirname(fileURLToPath(import.meta.url));
const STDOUT_CAP = 4 * 1024 * 1024;   // 单次命令 stdout 内存保留上限（尾部）
const STDERR_CAP = 64 * 1024;         // stderr 保留上限（尾部）
const SPILL_CAP = 32 * 1024 * 1024;   // 溢出时完整流落盘上限
const GRACE_MS = 10000;               // SIGTERM → SIGKILL 升级窗口

const text = (v, fb = "") => (typeof v === "string" ? v.trim() : fb);
const num = (v, fb = 0) => { const n = Number(v); return Number.isFinite(n) ? n : fb; };
const list = (v) => (Array.isArray(v) ? v : []);
const nowIso = () => new Date().toISOString();
const tsTag = () => nowIso().replace(/[-:]/g, "").replace(/\..*$/, "").replace("T", "_");
const short = (s, n = 240) => { s = String(s ?? ""); return s.length > n ? s.slice(-n) : s; };

/** ≤200KB 的 PNG 内联为 dataUrl；大图只给路径（Client 端降级为路径文本）。 */
function imagePreview(path, label) {
  try {
    if (!path || !existsSync(path)) return null;
    const size = statSync(path).size;
    const entry = { path, label: label || basename(path), sizeBytes: size, inline: size <= 200 * 1024 };
    if (entry.inline) entry.dataUrl = `data:image/png;base64,${readFileSync(path, "base64")}`;
    return entry;
  } catch { return null; }
}

// ─────────────────────────────────────────────────────────────────────
// 模型包写锁：mkdir 原子性实现，防多会话并发写同一 .456d 包。
// 锁目录 <package>/.cad-lock，owner.json 记录持有者；等待超时返回 E-LOCK，
// 超过 staleMs 的孤儿锁自动回收。
// ─────────────────────────────────────────────────────────────────────
const sleepMs = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function acquirePackageLock(packageDir, label, lockTimeoutMs, lockStaleMs) {
  const lockDir = join(packageDir, ".cad-lock");
  const deadline = Date.now() + lockTimeoutMs;
  for (;;) {
    try {
      mkdirSync(lockDir);
      try {
        writeFileSync(join(lockDir, "owner.json"), JSON.stringify({ label, pid: process.pid, ts: nowIso() }), "utf8");
      } catch { /* owner metadata is advisory; the directory is the lock */ }
      return lockDir;
    } catch (e) {
      if (e && e.code !== "EEXIST") {
        throw new CadError("E-LOCK", `无法创建模型包锁: ${String(e && e.message || e)}`, `检查 ${lockDir} 的目录权限`);
      }
      let stale = false;
      try {
        const owner = JSON.parse(readFileSync(join(lockDir, "owner.json"), "utf8"));
        const age = Date.now() - new Date(owner.ts).getTime();
        stale = Number.isFinite(age) && age > lockStaleMs;
      } catch { /* unreadable owner.json; treat as live */ }
      if (stale) {
        rmSync(lockDir, { recursive: true, force: true });
        continue;
      }
      if (Date.now() > deadline) {
        throw new CadError(
          "E-LOCK",
          `模型包被另一会话锁定（${lockDir}），等待 ${Math.round(lockTimeoutMs / 1000)}s 未释放`,
          "等待其他 cad_* 写操作结束后重试；确认无并发任务后可手动删除 .cad-lock",
        );
      }
      await sleepMs(200);
    }
  }
}

function releasePackageLock(lockDir) {
  try { rmSync(lockDir, { recursive: true, force: true }); } catch { /* release is best-effort */ }
}

function resolvePath(base, p) {
  const raw = text(p);
  if (!raw) return resolve(base);
  return isAbsolute(raw) ? resolve(raw) : resolve(base, raw);
}

function isWithin(parent, child) {
  const p = resolve(parent);
  const c = resolve(child);
  return c === p || c.startsWith(p.endsWith(sep) ? p : p + sep);
}

function isFile(path) {
  try { return statSync(path).isFile(); } catch { return false; }
}

function isDir(path) {
  try { return statSync(path).isDirectory(); } catch { return false; }
}

/** 领域错误：进入 canonical {ok:false,error} 通道而不是 isError 通道。 */
class CadError extends Error {
  constructor(code, message, hint) {
    super(message);
    this.name = "CadError";
    this.code = code;
    this.hint = hint || null;
  }
}

function errorOf(e, fbCode = "E-INTERNAL") {
  if (e instanceof CadError) return { code: e.code, message: e.message, hint: e.hint };
  return { code: fbCode, message: String(e && e.message || e) };
}

const errorSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    code: { type: "string" },
    message: { type: "string" },
    hint: { type: "string" },
  },
};
const eventSchema = {
  type: "object",
  additionalProperties: false,
  properties: { event: { type: "string" }, payload: { type: "object" } },
};
const checkpointSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    name: { type: "string" },
    event: { type: "string" },
    passed: { type: "integer" },
    total: { type: "integer" },
    image: { type: "string" },
    state: { type: "object" },
    checks: { type: "array", items: { type: "object" } },
  },
};
const metricsSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    volume: { type: "number" },
    area: { type: "number" },
    bbox: { type: "array", items: { type: "number" } },
    face_count: { type: "integer" },
    edge_count: { type: "integer" },
    vertex_count: { type: "integer" },
  },
};
const freeObject = { type: "object" };

export const name = "cad-studio";
export const inject = ["tools"];

export default {
  inject,
  apply(ctx, config) {
    const tools = ctx.tools;
    const subprocess = ctx.get("subprocess");
    const sandbox = ctx.get("sandbox");
    const sandboxPolicy = ctx.get("sandboxPolicy");
    const jobs = ctx.get("jobs");
    config = config || {};
    const LOCK_TIMEOUT_MS = Math.max(num(config.lockTimeoutMs, 30000), 100);
    const LOCK_STALE_MS = Math.max(num(config.lockStaleMs, 300000), LOCK_TIMEOUT_MS);

    // ─────────────────────────────────────────────────────────────────────
    // P1 · CadRuntime
    // ─────────────────────────────────────────────────────────────────────

    const workspaceOf = (exec) => {
      try {
        const cwd = exec && exec.agent && exec.agent.session && exec.agent.session.header && exec.agent.session.header.cwd;
        if (cwd) return resolve(String(cwd));
      } catch { /* fall through */ }
      try { return resolve(process.cwd()); } catch { return resolve("."); }
    };
    const sessionOf = (exec) => {
      try { return exec && exec.agent ? exec.agent.session : undefined; } catch { return undefined; }
    };

    /** 从工作区向上寻找 cad-cli 源码根（含 src/cad_cli/__main__.py）。 */
    function locateCliRoot(workspace) {
      const candidates = [];
      if (config.cliRoot) candidates.push(resolve(PLUGIN_DIR, String(config.cliRoot)));
      candidates.push(join(PLUGIN_DIR, "cad-cli"));
      let cur = workspace;
      while (true) {
        candidates.push(cur);
        const parent = dirname(cur);
        if (parent === cur) break;
        cur = parent;
      }
      for (const c of candidates) {
        if (existsSync(join(c, "src", "cad_cli", "__main__.py"))) return c;
      }
      return null;
    }

    /** Python 解释器候选：显式参数 → CAD_PYTHON → 工作区向上 .cad-venv/.venv → 用户缓存 venv → python3。 */
    function resolvePython(workspace, explicit) {
      const explicitPath = text(explicit) || text(process.env && process.env.CAD_PYTHON);
      if (explicitPath) return explicitPath;
      const exe = process.platform === "win32" ? "python.exe" : "bin/python";
      const candidates = [];
      let cur = workspace;
      while (true) {
        candidates.push(join(cur, ".cad-venv", exe));
        candidates.push(join(cur, ".venv", exe));
        const parent = dirname(cur);
        if (parent === cur) break;
        cur = parent;
      }
      candidates.push(join(homedir(), ".cache", "dsh-cad", "venv", exe));
      for (const c of candidates) if (existsSync(c)) return c;
      return "python3";
    }

    /** ctx.sandbox 包装 argv；服务缺失时原样通过（subprocess 服务仍是执行边界）。 */
    function confineArgv(argv, session) {
      if (!sandbox || !sandboxPolicy) return { argv: [...argv], mode: "unconfined" };
      let policy;
      try { policy = session ? sandboxPolicy.resolve({ session }) : sandboxPolicy.resolve(); } catch { policy = null; }
      if (!policy || policy.mode === "danger-full-access") return { argv: [...argv], mode: policy ? policy.mode : "unconfined" };
      try {
        const wrapped = sandbox.confine(argv, policy);
        return { argv: wrapped.argv, mode: policy.mode, enforcement: wrapped.enforcement };
      } catch (e) {
        throw new CadError(
          "E-SANDBOX",
          `无法按 ${policy.mode} 策略约束子进程: ${String(e && e.message || e)}`,
          "当前会话的沙箱后端不可用；请切换沙箱模式或检查 dsh-sandbox 后端",
        );
      }
    }

    /** exec.signal 与显式超时合并。 */
    function combinedSignal(exec, timeoutMs) {
      const caller = exec && exec.signal;
      const bound = timeoutMs > 0 ? timeoutMs : 0;
      if (!caller && !bound) return undefined;
      if (caller && !bound) return caller;
      const controller = new AbortController();
      if (caller) {
        if (caller.aborted) { controller.abort(); return controller.signal; }
        caller.addEventListener("abort", () => controller.abort(), { once: true });
      }
      const timer = bound ? setTimeout(() => controller.abort(), bound) : null;
      if (timer) {
        if (typeof timer.unref === "function") timer.unref();
        controller.signal.addEventListener("abort", () => clearTimeout(timer), { once: true });
      }
      return controller.signal;
    }

    /**
     * 执行一个 CAD CLI 子进程并收集输出。
     * 返回 {exitCode, signal, stdout, stdoutTruncated, stdoutSpill, stderr, stderrTruncated, stderrSpill, mode}
     */
    async function spawnCollect(argv, opts) {
      opts = opts || {};
      if (!subprocess) {
        throw new CadError("E-INFRA", "subprocess 服务不可用", "本插件依赖 DSH Host 的 subprocess capability seam");
      }
      const session = opts.session;
      const { argv: finalArgv, mode, enforcement } = confineArgv(argv, session);
      const signal = opts.signal;
      const handle = subprocess.spawn({
        argv: finalArgv,
        cwd: opts.cwd,
        stdio: {
          stdin: "ignore",
          stdout: { maxBytes: opts.stdoutCap ?? STDOUT_CAP, spill: { maxBytes: SPILL_CAP } },
          stderr: { maxBytes: STDERR_CAP, spill: { maxBytes: SPILL_CAP } },
        },
        graceMs: GRACE_MS,
        ...(signal ? { signal } : {}),
      });
      const outcome = await handle.done;
      const so = handle.collected.stdout ? handle.collected.stdout.readFrom(0) : { text: "", truncated: false, spillPath: undefined };
      const se = handle.collected.stderr ? handle.collected.stderr.readFrom(0) : { text: "", truncated: false, spillPath: undefined };
      return {
        exitCode: outcome.exitCode,
        signal: outcome.signal,
        stdout: so.text || "",
        stdoutTruncated: !!so.truncated,
        stdoutSpill: so.spillPath || null,
        stderr: se.text || "",
        stderrTruncated: !!se.truncated,
        stderrSpill: se.spillPath || null,
        mode,
        enforcement: enforcement || null,
      };
    }

    /** CLI 错误对象清洗：只保留 schema 允许的 code/message/hint，
     *  null/缺省字段省略（canonical 输出禁 null、禁附加键）。 */
    function sanitizeError(e, fallbackMsg) {
      const src = e && typeof e === "object" ? e : {};
      const out = {
        code: text(src.code, "E-CLI"),
        message: text(src.message, fallbackMsg || "CAD CLI 命令失败"),
      };
      const hint = text(src.hint);
      if (hint) out.hint = hint;
      return out;
    }

    /** JSONL 解析 + 规范化：事件去 ts、Checkpoint 摘取、metrics/error 定位。 */
    function normalizeCli(raw) {
      const events = [];
      const rawEvents = [];
      const checkpoints = [];
      let metrics = null;
      let error = null;
      for (const line of String(raw.stdout || "").split(/\r?\n/)) {
        const s = line.trim();
        if (!s) continue;
        let evt = null;
        try { evt = JSON.parse(s); } catch { continue; }
        if (!evt || typeof evt.event !== "string") continue;
        rawEvents.push(evt);
        events.push({ event: evt.event, payload: evt.payload ?? {} });
        if (evt.event === "checkpoint_passed" || evt.event === "checkpoint_failed") {
          const p = evt.payload || {};
          const img = text(p.image);
          checkpoints.push({
            name: String(p.name || `checkpoint-${checkpoints.length + 1}`),
            event: evt.event,
            passed: num(p.passed),
            total: num(p.total),
            // verify(render=False) 的 Checkpoint 没有渲染图：键必须缺省而不是 null，
            // 否则过不了 output schema 的 {type:"string"} 校验（canonical 输出禁 null）。
            ...(img ? { image: img } : {}),
            state: p.state ?? {},
            checks: list(p.checks),
          });
        }
        const m = evt.payload && evt.payload.metrics;
        if (m && typeof m === "object") metrics = m;
        if (evt.event.endsWith("_error")) {
          const p = evt.payload || {};
          error = sanitizeError(p.error, text(p.message) || undefined);
        }
      }
      if (!error && raw.exitCode !== 0) {
        error = sanitizeError({ code: "E-EXIT", message: short(raw.stderr, 400) || `CLI exited ${raw.exitCode}` });
      }
      const ok = raw.exitCode === 0 && !error;
      return { ok, exitCode: raw.exitCode, signal: raw.signal, events, rawEvents, checkpoints, metrics, error };
    }

    /** 把原始 JSONL 事件落到 <package>/runlog/<tag>_<ts>.jsonl。 */
    function writeRunlog(packageDir, tag, rawEvents, extra) {
      try {
        if (!isDir(packageDir)) return null;
        const runlogDir = join(packageDir, "runlog");
        mkdirSync(runlogDir, { recursive: true });
        const path = join(runlogDir, `${tag}_${tsTag()}.jsonl`);
        const lines = [];
        for (const evt of rawEvents) lines.push(JSON.stringify(evt));
        if (extra) lines.push(JSON.stringify(extra));
        writeFileSync(path, lines.join("\n") + (lines.length ? "\n" : ""), "utf8");
        return path;
      } catch { return null; }
    }

    /** 定位 .456d 模型包：显式路径 → 沿目录向上 → 工作区内唯一包。 */
    function findPackageDir(workspace, explicit) {
      let start = workspace;
      if (text(explicit)) {
        const given = resolvePath(workspace, explicit);
        if (!isWithin(workspace, given)) {
          throw new CadError("E-PATH", `package 路径越界: ${given}`, "模型包必须位于会话工作区内");
        }
        start = isFile(given) ? dirname(given) : given;
      }
      let cur = start;
      while (isWithin(workspace, cur)) {
        if (cur.endsWith(".456d") && existsSync(join(cur, "manifest.json"))) return cur;
        const parent = dirname(cur);
        if (parent === cur) break;
        cur = parent;
      }
      if (workspace.endsWith(".456d") && existsSync(join(workspace, "manifest.json"))) return workspace;
      let hits = [];
      try {
        hits = readdirSync(workspace)
          .filter((d) => d.endsWith(".456d") && existsSync(join(workspace, d, "manifest.json")))
          .map((d) => join(workspace, d));
      } catch { hits = []; }
      if (hits.length === 1) return hits[0];
      if (hits.length > 1) {
        throw new CadError(
          "E-AMBIGUOUS",
          `工作区内有 ${hits.length} 个 .456d 模型包，无法自动选定`,
          `通过 package 参数指定其一: ${hits.map((p) => basename(p)).join(", ")}`,
        );
      }
      throw new CadError("E-NO-PACKAGE", "工作区内没有 .456d 模型包", "先调用 cad_init 创建模型包");
    }

    /** 脚本路径解析 + 工作区边界校验。 */
    function resolveScript(workspace, packageDir, script) {
      if (text(script)) {
        const p = resolvePath(workspace, script);
        if (!isWithin(workspace, p)) {
          throw new CadError("E-PATH", `script 路径越界: ${p}`, "脚本必须位于会话工作区内");
        }
        return p;
      }
      return join(packageDir, "src", "main.py");
    }

    function requireCli(workspace) {
      const root = locateCliRoot(workspace);
      if (!root) throw new CadError("E-CLI-ROOT", "找不到 cad-cli 源码根（src/cad_cli/__main__.py）", "在插件 config.cliRoot 或工作区树内提供 cad-cli");
      return root;
    }

    function requirePython(workspace, explicit) {
      const p = resolvePython(workspace, explicit);
      if (p === "python3" || isAbsolute(p)) return p;
      return p;
    }

    /** 同步 CLI 执行：spawn → normalize → runlog。 */
    async function runCli(tool, workspace, argv, opts) {
      const result = await spawnCollect(argv, {
        cwd: opts.cwd || workspace,
        session: opts.session,
        signal: opts.signal,
      });
      const normalized = normalizeCli(result);
      return { ...normalized, stdout: result.stdout, stderr: result.stderr, mode: result.mode };
    }

    // ─────────────────────────────────────────────────────────────────────
    // 工具定义辅助
    // ─────────────────────────────────────────────────────────────────────

    function define(name, description, parameters, output, execute, presenters) {
      tools.register({
        name,
        description,
        parameters,
        output,
        execute: async (args, exec) => {
          try {
            return await execute(args || {}, exec);
          } catch (e) {
            if (e instanceof CadError) return { ok: false, error: errorOf(e) };
            throw e;
          }
        },
        ...(presenters || {}),
      });
    }

    const block = (t) => [{ type: "text", text: t }];
    const runSummary = (v) => {
      if (!v.ok) return `✗ ${text(v.error && v.error.code, "FAILED")}: ${text(v.error && v.error.message)}${v.error && v.error.hint ? `\n提示: ${v.error.hint}` : ""}`;
      const cp = list(v.checkpoints);
      const m = v.metrics || {};
      const bits = ["✓"];
      if (m.volume !== undefined) bits.push(`volume=${Number(m.volume).toFixed(2)}`);
      if (m.face_count !== undefined) bits.push(`faces=${m.face_count}`);
      if (cp.length) bits.push(`checkpoints ${cp.filter((c) => c.event === "checkpoint_passed").length}/${cp.length} passed`);
      return bits.join(" ");
    };

    const pythonArgs = (py) => [py, "-m", "cad_cli"];

    // ─────────────────────────────────────────────────────────────────────
    // cad_env_status
    // ─────────────────────────────────────────────────────────────────────
    const ENV_PROBE = [
      "import importlib, json, platform, sys",
      "out = {'version': f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}',",
      "       'arch': platform.machine(), 'platform': sys.platform}",
      "mods = [('build123d', '>=0.5.0'), ('cad_cli', '>=2.0.0'), ('pyvista', '>=0.43.0')]",
      "packages, missing = [], []",
      "for mod, req in mods:",
      "    try:",
      "        m = importlib.import_module(mod)",
      "        packages.append({'name': mod, 'version': str(getattr(m, '__version__', 'unknown')), 'required': req})",
      "    except Exception:",
      "        missing.append(mod)",
      "print(json.dumps({'detected': out, 'packages': packages, 'missing': missing}))",
    ].join("\n");

    define(
      "cad_env_status",
      "检查 CAD Python 环境：解释器、build123d/cad_cli/pyvista 依赖、venv 与 CLI 源码定位。纯读取。",
      {
        type: "object",
        properties: {
          python: { type: "string", description: "显式 Python 解释器路径；缺省按 .cad-venv/.venv/缓存 venv/python3 顺序探测" },
          cwd: { type: "string", description: "查找基准目录；缺省为会话工作区" },
        },
        required: [],
      },
      {
        schema: {
          type: "object",
          additionalProperties: false,
          properties: {
            ok: { type: "boolean" },
            ready: { type: "boolean" },
            python: freeObject,
            venv: freeObject,
            cli: freeObject,
            packages: { type: "array", items: freeObject },
            missing: { type: "array", items: { type: "string" } },
            hint: { type: "string" },
            error: errorSchema,
          },
        },
        render: (_a, v) => block(
          v.ok
            ? `CAD 环境${v.ready ? "就绪" : "未就绪"} | python ${v.python && v.python.version || "?"} | ${(v.packages || []).map((p) => p.name).join(", ") || "无依赖"}${v.missing && v.missing.length ? `\n缺失: ${v.missing.join(", ")}` : ""}`
            : `✗ ${v.error && v.error.message || "环境检查失败"}${v.error && v.error.hint ? `\n提示: ${v.error.hint}` : ""}`,
        ),
      },
      async (args, exec) => {
        const ws = resolvePath(workspaceOf(exec), args.cwd);
        const cliRoot = locateCliRoot(ws);
        const py = resolvePython(ws, args.python);
        const venvPath = existsSync(py) && basename(dirname(dirname(py))) !== ".cache"
          ? dirname(dirname(py))
          : null;
        const probe = await spawnCollect([py, "-c", ENV_PROBE], { cwd: ws, session: sessionOf(exec), signal: combinedSignal(exec, 30000) });
        let detected = {};
        let packages = [];
        let missing = [];
        if (probe.exitCode === 0) {
          try {
            const parsed = JSON.parse(probe.stdout.split("\n").find((l) => l.trim().startsWith("{")) || "{}");
            detected = parsed.detected || {};
            packages = parsed.packages || [];
            missing = parsed.missing || [];
          } catch { missing = ["unknown"]; }
        } else {
          missing = ["python"];
        }
        const ready = probe.exitCode === 0 && missing.length === 0 && !!cliRoot;
        const hint = ready
          ? "环境就绪，可直接 cad_init → cad_run → cad_commit"
          : cliRoot
            ? "调用 cad_env_bootstrap 创建 venv 并安装依赖"
            : "先提供 cad-cli 源码根（plugin config.cliRoot 或工作区树内）";
        return {
          ok: probe.exitCode === 0 || missing.length === 0,
          ready,
          python: { path: py, ...detected },
          venv: { path: venvPath, exists: !!venvPath && existsSync(venvPath) },
          cli: { root: cliRoot, found: !!cliRoot },
          packages,
          missing,
          hint,
          ...(probe.exitCode !== 0 && missing.includes("python") ? { error: { code: "E-ENV", message: short(probe.stderr, 400) || "Python 不可用", hint } } : {}),
        };
      },
    );

    // ─────────────────────────────────────────────────────────────────────
    // cad_env_bootstrap
    // ─────────────────────────────────────────────────────────────────────
    define(
      "cad_env_bootstrap",
      "一键安装 CAD 运行环境：channel=pip 创建私有 venv（默认 ~/.cache/dsh-cad/venv）+ pip install -e cad-cli；channel=conda 用 conda-forge 创建 ~/.cache/dsh-cad/conda-env（python 3.12 + build123d + pyvista）。两者都做 --help 与 build123d 导入冒烟。",
      {
        type: "object",
        properties: {
          python: { type: "string", description: "基础解释器路径；缺省自动探测 python3" },
          channel: { type: "string", enum: ["pip", "conda"], description: "安装渠道；当前版本实现 pip，conda 仅作为提示保留" },
          upgrade: { type: "boolean", description: "即使依赖已存在也重新安装（默认 false）" },
          run_in_background: { type: "boolean", description: "通过 DSH jobs 后台执行（默认 true 且 jobs 可用时）" },
        },
        required: [],
      },
      {
        schema: {
          type: "object",
          additionalProperties: false,
          properties: {
            ok: { type: "boolean" },
            background: { type: "boolean" },
            jobId: { type: "string" },
            venv: freeObject,
            steps: { type: "array", items: freeObject },
            smoke: freeObject,
            hint: { type: "string" },
            error: errorSchema,
          },
        },
        render: (_a, v) => {
          if (!v.ok) return block(`✗ ${v.error && v.error.message || "bootstrap 失败"}${v.error && v.error.hint ? `\n提示: ${v.error.hint}` : ""}`);
          if (v.background) return block(`已启动后台安装（job ${v.jobId}），用 job_output 读取进度；完成后调用 cad_env_status 确认`);
          const steps = list(v.steps);
          return block(`bootstrap 完成 | ${steps.filter((s) => s.status === "ok").length}/${steps.length} 步成功\n` + steps.map((s) => `${s.status === "ok" ? "✓" : "✗"} ${s.phase}`).join("\n"));
        },
      },
      async (args, exec) => {
        const ws = workspaceOf(exec);
        const cliRoot = requireCli(ws);
        const channel = text(args.channel, "pip");
        if (channel !== "pip" && channel !== "conda") {
          return { ok: false, error: { code: "E-ARGS", message: `未知 channel: ${channel}`, hint: "可选 pip / conda" } };
        }
        const basePython = text(args.python) || "python3";
        let condaBin = null;
        if (channel === "conda") {
          const candidates = [
            text(args.python),
            "/opt/homebrew/bin/conda",
            "/usr/local/bin/conda",
            join(homedir(), "miniforge3", "bin", "conda"),
            join(homedir(), "anaconda3", "bin", "conda"),
          ].filter(Boolean);
          const pathDirs = String(process.env && process.env.PATH || "").split(process.platform === "win32" ? ";" : ":");
          for (const dir of pathDirs) {
            for (const name of ["conda", "mamba", "micromamba"]) candidates.push(join(dir, name));
          }
          condaBin = candidates.find((c) => existsSync(c)) || null;
          if (!condaBin) {
            return { ok: false, error: { code: "E-CHANNEL", message: "未找到 conda/mamba 可执行文件", hint: "安装 miniforge 后重试，或改用 channel='pip'" } };
          }
        }
        const venvDir = channel === "conda"
          ? resolvePath(join(homedir(), ".cache", "dsh-cad"), "conda-env")
          : resolvePath(join(homedir(), ".cache", "dsh-cad"), "venv");
        const exe = process.platform === "win32" ? "python.exe" : "bin/python";
        const venvPython = join(venvDir, exe);

        const work = async ({ signal, log }) => {
          const steps = [];
          const step = async (phase, argv, cwd) => {
            const t0 = Date.now();
            const r = await spawnCollect(argv, { cwd, session: sessionOf(exec), signal });
            steps.push({
              phase,
              status: r.exitCode === 0 ? "ok" : "failed",
              detail: r.exitCode === 0 ? undefined : short(r.stderr, 300),
              durationMs: Date.now() - t0,
            });
            if (r.exitCode !== 0) {
              throw new CadError("E-BOOTSTRAP", `${phase} 失败: ${short(r.stderr, 300)}`, `日志尾部见 ${join(homedir(), ".cache", "dsh-cad", "bootstrap.log")}`);
            }
            return r;
          };
          const exists = existsSync(venvPython);
          if (channel === "conda") {
            await step("conda-detect", [condaBin, "--version"], ws);
            if (!exists || args.upgrade) {
              await step("conda-create", [condaBin, "create", "-y", "-p", venvDir, "-c", "conda-forge", "python=3.12", "build123d", "pyvista"], ws);
            }
            await step("pip-install-cli", [venvPython, "-m", "pip", "install", "-e", cliRoot], cliRoot);
          } else {
            await step("detect", [basePython, "--version"], ws);
            if (!exists || args.upgrade) await step("venv", [basePython, "-m", "venv", venvDir], ws);
            await step("pip-upgrade", [venvPython, "-m", "pip", "install", "--upgrade", "pip"], ws);
            const needInstall = args.upgrade || !exists;
            if (needInstall) await step("pip-install", [venvPython, "-m", "pip", "install", "-e", cliRoot], cliRoot);
          }
          await step("smoke-cli", [venvPython, "-m", "cad_cli", "--help"], ws);
          await step("smoke-import", [venvPython, "-c", ENV_PROBE], ws);
          return { ok: true, venv: { path: venvDir, exists: true }, steps, smoke: { cli_ok: true, import_ok: true } };
        };

        // 后台分支：ctx.jobs 可用且 agent 存在时启动 <kind>-N 任务。
        if (args.run_in_background !== false && jobs && exec.agent) {
          try {
            let controller = null;
            let cancelled = false;
            const logLines = [];
            const jobId = jobs.start({
              kind: "cad",
              label: `cad_env_bootstrap (${channel})`,
              owner: exec.agent,
              outputLimitBytes: 1 << 20,
              run: () => {
                controller = new AbortController();
                const done = work({ signal: controller.signal, log: (l) => logLines.push(String(l)) }).then(
                  (v) => ({ status: cancelled ? "killed" : "completed", detail: cancelled ? "cancelled" : "ok" }),
                  (e) => ({ status: cancelled ? "killed" : "failed", detail: String(e && e.message || e) }),
                );
                return {
                  cancel(reason) { cancelled = true; if (controller) controller.abort(String(reason || "cancelled")); },
                  done,
                  readOutput() {
                    const chunk = logLines.splice(0).join("\n");
                    return chunk ? chunk + "\n" : "";
                  },
                };
              },
            });
            return { ok: true, background: true, jobId: String(jobId), steps: [], venv: { path: venvDir, exists: existsSync(venvPython) } };
          } catch { /* 落回同步 */ }
        }

        const result = await work({ signal: combinedSignal(exec, 600000) });
        return { ok: true, background: false, venv: result.venv, steps: result.steps, smoke: result.smoke };
      },
    );

    // ─────────────────────────────────────────────────────────────────────
    // cad_pkg_list
    // ─────────────────────────────────────────────────────────────────────
    define(
      "cad_pkg_list",
      "列出会话工作区内的 .456d 模型包（含 manifest、当前分支、HEAD、src/main.py 状态）。纯读取。",
      { type: "object", properties: { cwd: { type: "string" } }, required: [] },
      {
        schema: {
          type: "object",
          additionalProperties: false,
          properties: {
            ok: { type: "boolean" },
            packages: { type: "array", items: freeObject },
            error: errorSchema,
          },
        },
        render: (_a, v) => block(v.ok ? `${(v.packages || []).length} 个模型包\n` + (v.packages || []).map((p) => `${p.name} (${p.path}) head=${p.head || "none"}`).join("\n") : `✗ ${v.error && v.error.message}`),
      },
      async (args, exec) => {
        const ws = resolvePath(workspaceOf(exec), args.cwd);
        let dirs = [];
        try { dirs = readdirSync(ws).filter((d) => d.endsWith(".456d") && existsSync(join(ws, d, "manifest.json"))); } catch { /* empty */ }
        if (ws.endsWith(".456d") && existsSync(join(ws, "manifest.json"))) dirs = [basename(ws)];
        const packages = dirs.map((d) => {
          const dir = ws.endsWith(".456d") && d === basename(ws) ? ws : join(ws, d);
          let manifest = {};
          try { manifest = JSON.parse(readFileSync(join(dir, "manifest.json"), "utf8")); } catch { /* keep */ }
          return {
            name: manifest.name || basename(dir),
            path: dir,
            head: manifest.head || null,
            branch: manifest.current_branch || null,
            hasMain: existsSync(join(dir, "src", "main.py")),
          };
        });
        return { ok: true, packages };
      },
    );

    // ─────────────────────────────────────────────────────────────────────
    // cad_init
    // ─────────────────────────────────────────────────────────────────────
    define(
      "cad_init",
      "在会话工作区内创建新的 .456d 模型包（含 manifest 与 src/main.py 模板）。",
      {
        type: "object",
        properties: {
          path: { type: "string", description: "模型包名或相对路径；实际目录为 <path>.456d" },
          name: { type: "string", description: "模型显示名" },
        },
        required: ["path", "name"],
      },
      {
        schema: {
          type: "object",
          additionalProperties: false,
          properties: {
            ok: { type: "boolean" },
            package: freeObject,
            events: { type: "array", items: eventSchema },
            error: errorSchema,
          },
        },
        render: (_a, v) => block(v.ok ? `已创建模型包 ${v.package && v.package.path}` : `✗ ${v.error && v.error.message}${v.error && v.error.hint ? `\n提示: ${v.error.hint}` : ""}`),
      },
      async (args, exec) => {
        const ws = workspaceOf(exec);
        const target = resolvePath(ws, args.path);
        if (!isWithin(ws, target)) {
          return { ok: false, error: { code: "E-PATH", message: `init 目标越界: ${target}`, hint: "模型包必须创建在会话工作区内" } };
        }
        const py = resolvePython(ws);
        const cliRoot = requireCli(ws);
        void cliRoot;
        const r = await runCli("init", ws, [...pythonArgs(py), "init", target, "--name", text(args.name)], {
          session: sessionOf(exec), signal: combinedSignal(exec, 60000), cwd: ws,
        });
        const pkgDir = `${target}.456d`;
        let manifest = {};
        try { manifest = JSON.parse(readFileSync(join(pkgDir, "manifest.json"), "utf8")); } catch { /* keep */ }
        return {
          ok: r.ok,
          // 失败路径 package 键缺省而非 null（schema 为 object 型）
          ...(r.ok ? { package: { path: pkgDir, name: manifest.name || text(args.name), defaultScript: join(pkgDir, "src", "main.py") } } : {}),
          events: r.events,
          ...(r.ok ? {} : { error: r.error }),
        };
      },
      { presentCall: (args) => ({ card: "generic", title: `cad_init ${args.path}`, kind: "other", rawInput: { name: args.name }, locations: [{ path: `${args.path}.456d` }] }) },
    );

    // ─────────────────────────────────────────────────────────────────────
    // cad_run
    // ─────────────────────────────────────────────────────────────────────
    define(
      "cad_run",
      "执行模型包内的 build123d 脚本（内存运行，不保存工件）。输出规范化 JSONL 事件、metrics、Checkpoint 结果与 runlog 路径；失败时返回 hint。",
      {
        type: "object",
        properties: {
          script: { type: "string", description: "脚本路径（相对工作区或绝对）；缺省用当前包的 src/main.py" },
          package: { type: "string", description: ".456d 模型包路径；缺省自动定位（多个包时必须指定）" },
          timeout_seconds: { type: "number", description: "超时秒数，缺省 120，上限 300" },
          run_in_background: { type: "boolean", description: "通过 DSH jobs 后台执行" },
        },
        required: [],
      },
      {
        schema: {
          type: "object",
          additionalProperties: false,
          properties: {
            ok: { type: "boolean" },
            background: { type: "boolean" },
            jobId: { type: "string" },
            package: { type: "string" },
            script: { type: "string" },
            events: { type: "array", items: eventSchema },
            checkpoints: { type: "array", items: checkpointSchema },
            metrics: metricsSchema,
            preview: { type: "array", items: freeObject },
            runlog: { type: "string" },
            exitCode: { type: "integer" },
            error: errorSchema,
          },
        },
        render: (_a, v) => block(v.background ? `已启动后台运行（job ${v.jobId}）` : runSummary(v)),
        presentationMeta: (_a, v) => ({
          kind: "cad-run",
          ok: !!v.ok,
          package: v.package || null,
          script: v.script || null,
          metrics: v.metrics || null,
          checkpoints: v.checkpoints || [],
          preview: v.preview || [],
          error: v.error || null,
        }),
      },
      async (args, exec) => {
        const ws = workspaceOf(exec);
        const session = sessionOf(exec);
        const pkgDir = findPackageDir(ws, args.package);
        const script = resolveScript(ws, pkgDir, args.script);
        if (!existsSync(script)) return { ok: false, error: { code: "E-SCRIPT", message: `脚本不存在: ${script}`, hint: "先创建 src/main.py 再运行" } };
        const py = resolvePython(ws);
        const timeoutMs = Math.min(Math.max(num(args.timeout_seconds, 120), 1), 300) * 1000;

        const work = async ({ signal }) => {
          const lockDir = await acquirePackageLock(pkgDir, "cad_run", LOCK_TIMEOUT_MS, LOCK_STALE_MS);
          try {
            const r = await runCli("run", ws, [...pythonArgs(py), "run", script], { session, signal, cwd: pkgDir });
            const runlog = writeRunlog(pkgDir, "run", r.rawEvents, { event: "plugin_meta", payload: { exitCode: r.exitCode, mode: r.mode, ts: nowIso() } });
            const preview = (r.checkpoints || [])
              .map((c) => imagePreview(c.image, `checkpoint:${c.name}`))
              .filter(Boolean);
            return {
              ok: r.ok,
              package: pkgDir,
              script,
              events: r.events,
              checkpoints: r.checkpoints,
              // 失败路径 metrics 为 null：键缺省而非 null（schema 为 object 型）
              ...(r.metrics ? { metrics: r.metrics } : {}),
              preview,
              runlog,
              exitCode: r.exitCode,
              ...(r.ok ? {} : { error: r.error }),
            };
          } finally {
            releasePackageLock(lockDir);
          }
        };

        if (args.run_in_background && jobs && exec.agent) {
          const jobId = startJob(exec, `cad run ${relative(ws, script)}`, async () => {
            const value = await work({ signal: undefined });
            return value;
          });
          if (jobId) return { ok: true, background: true, jobId, package: pkgDir, script };
        }
        return await work({ signal: combinedSignal(exec, timeoutMs) });
      },
      {
        presentCall: (args) => ({ card: "terminal", title: args.script ? `cad run ${args.script}` : "cad run", description: "执行 build123d 建模脚本（内存）", cwd: args.package || undefined }),
        presentResult: (_a, result) => ({
          card: "terminal",
          title: result.isError ? "cad run (failed)" : "cad run",
          output: result.content.map((c) => c.text || "").join("\n"),
          ...(result.meta && result.meta.exitCode !== undefined ? { exitCode: result.meta.exitCode } : {}),
        }),
      },
    );

    // ─────────────────────────────────────────────────────────────────────
    // cad_validate
    // ─────────────────────────────────────────────────────────────────────
    define(
      "cad_validate",
      "验证几何有效性（BRep）。缺省验证 HEAD 工件；给 script 则先执行脚本再验证。",
      {
        type: "object",
        properties: {
          script: { type: "string", description: "要执行验证的脚本；缺省验证 HEAD" },
          package: { type: "string" },
        },
        required: [],
      },
      {
        schema: {
          type: "object",
          additionalProperties: false,
          properties: {
            ok: { type: "boolean" },
            package: { type: "string" },
            events: { type: "array", items: eventSchema },
            error: errorSchema,
          },
        },
        render: (_a, v) => block(v.ok ? "✓ 几何有效" : `✗ ${v.error && v.error.message}${v.error && v.error.hint ? `\n提示: ${v.error.hint}` : ""}`),
      },
      async (args, exec) => {
        const ws = workspaceOf(exec);
        const pkgDir = findPackageDir(ws, args.package);
        const py = resolvePython(ws);
        const argv = [...pythonArgs(py), "validate"];
        if (text(args.script)) argv.push(resolveScript(ws, pkgDir, args.script));
        const r = await runCli("validate", ws, argv, { session: sessionOf(exec), signal: combinedSignal(exec, 120000), cwd: pkgDir });
        return { ok: r.ok, package: pkgDir, events: r.events, ...(r.ok ? {} : { error: r.error }) };
      },
    );

    // ─────────────────────────────────────────────────────────────────────
    // cad_inspect
    // ─────────────────────────────────────────────────────────────────────
    define(
      "cad_inspect",
      "查询模型几何属性：volume / area / bounds / faces / edges / vertices / face_types / geometry_summary（读取 HEAD 或指定 commit）。",
      {
        type: "object",
        properties: {
          prop: { type: "string", enum: ["volume", "area", "bounds", "faces", "edges", "vertices", "face_types", "geometry_summary"], description: "要查询的属性" },
          package: { type: "string" },
          commit: { type: "string", description: "commit hash；缺省 HEAD" },
        },
        required: ["prop"],
      },
      {
        schema: {
          type: "object",
          additionalProperties: false,
          properties: {
            ok: { type: "boolean" },
            property: { type: "string" },
            value: {},
            events: { type: "array", items: eventSchema },
            error: errorSchema,
          },
        },
        render: (_a, v) => block(v.ok ? `${v.property} = ${typeof v.value === "object" ? JSON.stringify(v.value) : v.value}` : `✗ ${v.error && v.error.message}${v.error && v.error.hint ? `\n提示: ${v.error.hint}` : ""}`),
      },
      async (args, exec) => {
        const ws = workspaceOf(exec);
        const pkgDir = findPackageDir(ws, args.package);
        const py = resolvePython(ws);
        const argv = [...pythonArgs(py), "inspect", "--prop", text(args.prop)];
        if (text(args.commit)) argv.push(text(args.commit));
        const r = await runCli("inspect", ws, argv, { session: sessionOf(exec), signal: combinedSignal(exec, 60000), cwd: pkgDir });
        const payload = r.events.find((e) => e.event === "inspect_result");
        return {
          ok: r.ok && !!payload,
          property: text(args.prop),
          value: payload ? payload.payload.value : null,
          events: r.events,
          ...(r.ok && payload ? {} : { error: r.error || { code: "E-INSPECT", message: "未获得 inspect_result" } }),
        };
      },
    );

    // ─────────────────────────────────────────────────────────────────────
    // cad_commit
    // ─────────────────────────────────────────────────────────────────────
    define(
      "cad_commit",
      "提交当前模型：执行脚本 → 验证 → 保存 STEP + 4 视图缩略图 + metrics → 记录版本历史。",
      {
        type: "object",
        properties: {
          message: { type: "string", description: "提交信息" },
          script: { type: "string", description: "要提交的脚本；缺省 src/main.py" },
          package: { type: "string" },
          views: { type: "array", items: { type: "string" }, description: "缩略图视图（top/front/right/iso），缺省全部" },
          run_in_background: { type: "boolean" },
        },
        required: ["message"],
      },
      {
        schema: {
          type: "object",
          additionalProperties: false,
          properties: {
            ok: { type: "boolean" },
            background: { type: "boolean" },
            jobId: { type: "string" },
            package: { type: "string" },
            commit: freeObject,
            artifacts: { type: "array", items: freeObject },
            metrics: metricsSchema,
            events: { type: "array", items: eventSchema },
            checkpoints: { type: "array", items: checkpointSchema },
            preview: { type: "array", items: freeObject },
            error: errorSchema,
          },
        },
        render: (_a, v) => {
          if (v.background) return block(`已启动后台提交（job ${v.jobId}）`);
          if (!v.ok) return block(`✗ ${v.error && v.error.message}${v.error && v.error.hint ? `\n提示: ${v.error.hint}` : ""}`);
          const c = v.commit || {};
          return block(`✓ commit ${c.hash || ""} | ${c.message || ""} | artifacts: ${(v.artifacts || []).map((a) => a.name).join(", ")}`);
        },
        presentationMeta: (_a, v) => ({
          kind: "cad-commit",
          ok: !!v.ok,
          package: v.package || null,
          commit: v.commit || null,
          artifacts: v.artifacts || [],
          metrics: v.metrics || null,
          checkpoints: v.checkpoints || [],
          preview: v.preview || [],
          error: v.error || null,
        }),
      },
      async (args, exec) => {
        const ws = workspaceOf(exec);
        const session = sessionOf(exec);
        const pkgDir = findPackageDir(ws, args.package);
        const py = resolvePython(ws);
        const argv = [...pythonArgs(py), "commit", "-m", text(args.message)];
        if (text(args.script)) argv.push(resolveScript(ws, pkgDir, args.script));
        const views = list(args.views).filter((v) => ["top", "front", "right", "iso"].includes(String(v)));
        if (views.length) argv.push("--views", views.join(","));

        const work = async ({ signal }) => {
          const lockDir = await acquirePackageLock(pkgDir, "cad_commit", LOCK_TIMEOUT_MS, LOCK_STALE_MS);
          try {
            const r = await runCli("commit", ws, argv, { session, signal, cwd: pkgDir });
            const commitEvt = r.events.find((e) => e.event === "commit_success");
            const hash = commitEvt ? text(commitEvt.payload.hash) : null;
            let artifacts = [];
            let metrics = r.metrics || null;
            let preview = [];
            if (hash) {
              const artDir = join(pkgDir, "artifacts", hash);
              try {
                artifacts = readdirSync(artDir).map((f) => ({ name: f, size: statSync(join(artDir, f)).size }));
              } catch { artifacts = []; }
              try { metrics = JSON.parse(readFileSync(join(artDir, "metrics.json"), "utf8")); } catch { /* keep run metrics */ }
              preview = ["iso", "top", "front", "right"]
                .map((view) => imagePreview(join(artDir, `thumb_${view}.png`), view))
                .filter(Boolean);
            }
            writeRunlog(pkgDir, "commit", r.rawEvents, { event: "plugin_meta", payload: { hash, ts: nowIso() } });
            return {
              ok: r.ok && !!hash,
              package: pkgDir,
              // 失败路径 commit/metrics 键缺省而非 null（schema 为 object 型）
              ...(hash ? { commit: { hash, message: text(args.message), timestamp: commitEvt ? commitEvt.payload.timestamp : null, branch: null } } : {}),
              artifacts,
              ...(metrics ? { metrics } : {}),
              preview,
              events: r.events,
              checkpoints: r.checkpoints,
              ...(r.ok && hash ? {} : { error: r.error || { code: "E-COMMIT", message: "commit_success 缺失" } }),
            };
          } finally {
            releasePackageLock(lockDir);
          }
        };

        if (args.run_in_background && jobs && exec.agent) {
          const jobId = startJob(exec, `cad commit -m ${short(text(args.message), 40)}`, () => work({ signal: undefined }));
          if (jobId) return { ok: true, background: true, jobId, package: pkgDir };
        }
        return await work({ signal: combinedSignal(exec, 300000) });
      },
      {
        presentCall: (args) => ({ card: "terminal", title: `cad commit ${args.message}`, description: "执行 + 验证 + 保存 STEP/缩略图 + 记录历史", cwd: args.package || undefined }),
        presentResult: (_a, result) => ({
          card: "terminal",
          title: result.isError ? "cad commit (failed)" : "cad commit",
          output: result.content.map((c) => c.text || "").join("\n"),
        }),
      },
    );

    // ─────────────────────────────────────────────────────────────────────
    // cad_log
    // ─────────────────────────────────────────────────────────────────────
    define(
      "cad_log",
      "查看模型包提交历史（版本时间线）。",
      {
        type: "object",
        properties: {
          limit: { type: "integer", description: "返回条数，默认 10，上限 50" },
          package: { type: "string" },
        },
        required: [],
      },
      {
        schema: {
          type: "object",
          additionalProperties: false,
          properties: {
            ok: { type: "boolean" },
            total: { type: "integer" },
            commits: { type: "array", items: freeObject },
            events: { type: "array", items: eventSchema },
            error: errorSchema,
          },
        },
        render: (_a, v) => block(
          v.ok
            ? `${v.total} 个提交\n` + (v.commits || []).map((c) => `${c.hash || c.commit || "?"} ${c.message || ""} ${c.timestamp || ""}`).join("\n")
            : `✗ ${v.error && v.error.message}`,
        ),
      },
      async (args, exec) => {
        const ws = workspaceOf(exec);
        const pkgDir = findPackageDir(ws, args.package);
        const py = resolvePython(ws);
        const limit = Math.min(Math.max(num(args.limit, 10), 1), 50);
        const argv = [...pythonArgs(py), "log", "--limit", String(limit)];
        const r = await runCli("log", ws, argv, { session: sessionOf(exec), signal: combinedSignal(exec, 30000), cwd: pkgDir });
        const payload = r.events.find((e) => e.event === "log_result");
        return {
          ok: r.ok && !!payload,
          total: payload ? num(payload.payload.total) : 0,
          commits: payload ? list(payload.payload.commits) : [],
          events: r.events,
          ...(r.ok && payload ? {} : { error: r.error || { code: "E-LOG", message: "log_result 缺失" } }),
        };
      },
    );

    // ─────────────────────────────────────────────────────────────────────
    // cad_status
    // ─────────────────────────────────────────────────────────────────────
    define(
      "cad_status",
      "查看模型包当前状态：HEAD、分支、提交数、main.py 是否有未提交修改。",
      { type: "object", properties: { package: { type: "string" } }, required: [] },
      {
        schema: {
          type: "object",
          additionalProperties: false,
          properties: {
            ok: { type: "boolean" },
            status: freeObject,
            events: { type: "array", items: eventSchema },
            error: errorSchema,
          },
        },
        render: (_a, v) => block(
          v.ok
            ? `head=${v.status && v.status.head || "none"} branch=${v.status && v.status.branch || "?"} commits=${(v.status && v.status.total_commits) ?? "?"} hasChanges=${v.status && v.status.has_changes}`
            : `✗ ${v.error && v.error.message}`,
        ),
      },
      async (args, exec) => {
        const ws = workspaceOf(exec);
        const pkgDir = findPackageDir(ws, args.package);
        const py = resolvePython(ws);
        const r = await runCli("status", ws, [...pythonArgs(py), "status"], { session: sessionOf(exec), signal: combinedSignal(exec, 30000), cwd: pkgDir });
        const payload = r.events.find((e) => e.event === "status_result");
        return {
          ok: r.ok && !!payload,
          status: payload ? payload.payload : {},
          events: r.events,
          ...(r.ok && payload ? {} : { error: r.error || { code: "E-STATUS", message: "status_result 缺失" } }),
        };
      },
    );

    // ─────────────────────────────────────────────────────────────────────
    // cad_render
    // ─────────────────────────────────────────────────────────────────────
    define(
      "cad_render",
      "离屏渲染模型为 PNG（iso/top/front/right），写入 <package>/runlog/render_<view>.png；≤200KB 的图内联为 dataUrl 预览。",
      {
        type: "object",
        properties: {
          views: { type: "array", items: { type: "string" }, description: "视图列表，缺省 top,front,right,iso" },
          commit: { type: "string", description: "commit hash；缺省 HEAD" },
          package: { type: "string" },
        },
        required: [],
      },
      {
        schema: {
          type: "object",
          additionalProperties: false,
          properties: {
            ok: { type: "boolean" },
            images: { type: "array", items: freeObject },
            preview: { type: "array", items: freeObject },
            events: { type: "array", items: eventSchema },
            error: errorSchema,
          },
        },
        render: (_a, v) => block(
          v.ok
            ? `渲染完成: ${(v.images || []).map((i) => `${i.view}(${i.path})`).join(", ")}`
            : `✗ ${v.error && v.error.message}${v.error && v.error.hint ? `\n提示: ${v.error.hint}` : ""}`,
        ),
        presentationMeta: (_a, v) => ({
          kind: "cad-render",
          ok: !!v.ok,
          images: v.images || [],
          preview: v.preview || [],
          error: v.error || null,
        }),
      },
      async (args, exec) => {
        const ws = workspaceOf(exec);
        const pkgDir = findPackageDir(ws, args.package);
        const py = resolvePython(ws);
        const views = list(args.views).filter((v) => ["top", "front", "right", "iso"].includes(String(v)));
        const argv = [...pythonArgs(py), "render", "--views", views.join(",") || "top,front,right,iso"];
        if (text(args.commit)) argv.push(text(args.commit));
        const lockDir = await acquirePackageLock(pkgDir, "cad_render", LOCK_TIMEOUT_MS, LOCK_STALE_MS);
        try {
          const r = await runCli("render", ws, argv, { session: sessionOf(exec), signal: combinedSignal(exec, 180000), cwd: pkgDir });
          const viewList = views.length ? views : ["top", "front", "right", "iso"];
          const out = viewList.map((view) => {
            const p = join(pkgDir, "runlog", `render_${view}.png`);
            if (!existsSync(p)) return { view, path: p, exists: false };
            let size = 0;
            try { size = statSync(p).size; } catch { /* keep 0 */ }
            return { view, path: p, exists: true, sizeBytes: size };
          });
          const preview = out.map((img) => imagePreview(img.path, img.view)).filter(Boolean);
          return {
            ok: r.ok && out.some((i) => i.exists),
            images: out,
            preview,
            events: r.events,
            ...(r.ok && out.some((i) => i.exists) ? {} : { error: r.error || { code: "E-RENDER", message: "没有生成任何渲染图" } }),
          };
        } finally {
          releasePackageLock(lockDir);
        }
      },
      { presentCall: (args) => ({ card: "generic", title: `cad_render ${(args.views || []).join(",") || "top,front,right,iso"}`, kind: "execute", rawInput: { commit: args.commit } }) },
    );

    // ─────────────────────────────────────────────────────────────────────
    // cad_review
    // ─────────────────────────────────────────────────────────────────────
    define(
      "cad_review",
      "执行脚本并生成视觉审查：渲染多视图 PNG + 生成 review.md 模板 + 返回 metrics/Checkpoint/面类型摘要。",
      {
        type: "object",
        properties: {
          script: { type: "string" },
          package: { type: "string" },
          views: { type: "array", items: { type: "string" } },
          text_only: { type: "boolean", description: "跳过渲染，仅生成文本审查（非多模态模型用）" },
        },
        required: [],
      },
      {
        schema: {
          type: "object",
          additionalProperties: false,
          properties: {
            ok: { type: "boolean" },
            metrics: metricsSchema,
            images: { type: "array", items: freeObject },
            features: { type: "array", items: { type: "string" } },
            checkpoints: { type: "array", items: freeObject },
            faceTypes: freeObject,
            preview: { type: "array", items: freeObject },
            reviewTemplate: { type: "string" },
            textOnly: { type: "boolean" },
            events: { type: "array", items: eventSchema },
            error: errorSchema,
          },
        },
        render: (_a, v) => block(
          v.ok
            ? `review 就绪 | ${(v.images || []).length} 张视图 | ${(v.features || []).length} 个特征 | 模板: ${v.reviewTemplate}`
            : `✗ ${v.error && v.error.message}${v.error && v.error.hint ? `\n提示: ${v.error.hint}` : ""}`,
        ),
        presentationMeta: (_a, v) => ({
          kind: "cad-review",
          ok: !!v.ok,
          metrics: v.metrics || null,
          images: v.images || [],
          preview: v.preview || [],
          features: v.features || [],
          checkpoints: v.checkpoints || [],
          reviewTemplate: v.reviewTemplate || null,
          textOnly: !!v.textOnly,
          error: v.error || null,
        }),
      },
      async (args, exec) => {
        const ws = workspaceOf(exec);
        const pkgDir = findPackageDir(ws, args.package);
        const script = resolveScript(ws, pkgDir, args.script);
        const py = resolvePython(ws);
        const views = list(args.views).filter((v) => ["top", "front", "right", "iso"].includes(String(v)));
        const argv = [...pythonArgs(py), "review"];
        if (existsSync(script)) argv.push(script);
        if (views.length) argv.push("--views", views.join(","));
        if (args.text_only) argv.push("--text-only");
        const lockDir = await acquirePackageLock(pkgDir, "cad_review", LOCK_TIMEOUT_MS, LOCK_STALE_MS);
        try {
          const r = await runCli("review", ws, argv, { session: sessionOf(exec), signal: combinedSignal(exec, 240000), cwd: pkgDir });
          const payload = r.events.find((e) => e.event === "review_ready");
          const p = payload ? payload.payload : {};
          const images = list(p.images);
          const preview = images
            .map((img) => imagePreview(text(img && img.path), text(img && img.view)))
            .filter(Boolean);
          return {
            ok: r.ok && !!payload,
            // metrics 缺失时键缺省而非 null（schema 为 object 型）
            ...(p.metrics ? { metrics: p.metrics } : {}),
            images,
            features: list(p.features),
            checkpoints: list(p.checkpoint_results),
            faceTypes: p.face_types || {},
            preview,
            reviewTemplate: text(p.review_template),
            textOnly: !!p.text_only,
            events: r.events,
            ...(r.ok && payload ? {} : { error: r.error || { code: "E-REVIEW", message: "review_ready 缺失" } }),
          };
        } finally {
          releasePackageLock(lockDir);
        }
      },
    );

    // ─────────────────────────────────────────────────────────────────────
    // cad_checkout
    // ─────────────────────────────────────────────────────────────────────
    define(
      "cad_checkout",
      "切换到指定版本：加载该 commit 的 STEP 工件并恢复当时的 main.py 脚本。",
      {
        type: "object",
        properties: {
          commit: { type: "string", description: "目标 commit hash（用 cad_log 查询）" },
          package: { type: "string" },
        },
        required: ["commit"],
      },
      {
        schema: {
          type: "object",
          additionalProperties: false,
          properties: {
            ok: { type: "boolean" },
            commit: { type: "string" },
            metrics: metricsSchema,
            scriptRestored: { type: "boolean" },
            events: { type: "array", items: eventSchema },
            error: errorSchema,
          },
        },
        render: (_a, v) => block(v.ok ? `✓ 已切换到 ${v.commit}（scriptRestored=${v.scriptRestored}）` : `✗ ${v.error && v.error.message}${v.error && v.error.hint ? `\n提示: ${v.error.hint}` : ""}`),
      },
      async (args, exec) => {
        const ws = workspaceOf(exec);
        const pkgDir = findPackageDir(ws, args.package);
        const py = resolvePython(ws);
        const lockDir = await acquirePackageLock(pkgDir, "cad_checkout", LOCK_TIMEOUT_MS, LOCK_STALE_MS);
        try {
          const r = await runCli("checkout", ws, [...pythonArgs(py), "checkout", text(args.commit)], { session: sessionOf(exec), signal: combinedSignal(exec, 120000), cwd: pkgDir });
          const payload = r.events.find((e) => e.event === "checkout_success");
          return {
            ok: r.ok && !!payload,
            commit: text(args.commit),
            // metrics 缺失时键缺省而非 null（schema 为 object 型）
            ...(payload && payload.payload.metrics ? { metrics: payload.payload.metrics } : {}),
            scriptRestored: payload ? !!payload.payload.script_restored : false,
            events: r.events,
            ...(r.ok && payload ? {} : { error: r.error || { code: "E-CHECKOUT", message: "checkout_success 缺失" } }),
          };
        } finally {
          releasePackageLock(lockDir);
        }
      },
    );

    // ─────────────────────────────────────────────────────────────────────
    // cad_branch
    // ─────────────────────────────────────────────────────────────────────
    define(
      "cad_branch",
      "管理模型包分支：list / create / switch / delete。",
      {
        type: "object",
        properties: {
          op: { type: "string", enum: ["list", "create", "switch", "delete"] },
          name: { type: "string", description: "分支名（create/switch/delete 必填）" },
          from_commit: { type: "string", description: "create 时从指定 commit 建分支" },
          force: { type: "boolean", description: "delete 时强制删除当前分支" },
          package: { type: "string" },
        },
        required: ["op"],
      },
      {
        schema: {
          type: "object",
          additionalProperties: false,
          properties: {
            ok: { type: "boolean" },
            op: { type: "string" },
            result: { type: "array", items: freeObject },
            events: { type: "array", items: eventSchema },
            error: errorSchema,
          },
        },
        render: (_a, v) => block(
          v.ok
            ? `branch ${v.op} ok` + (v.result && v.result.length ? `\n${JSON.stringify(v.result, null, 2)}` : "")
            : `✗ ${v.error && v.error.message}${v.error && v.error.hint ? `\n提示: ${v.error.hint}` : ""}`,
        ),
      },
      async (args, exec) => {
        const ws = workspaceOf(exec);
        const pkgDir = findPackageDir(ws, args.package);
        const py = resolvePython(ws);
        const op = text(args.op, "list");
        const argv = [...pythonArgs(py), "branch"];
        if (op === "list") argv.push("list");
        else if (op === "create") { argv.push("create", text(args.name)); if (text(args.from_commit)) argv.push("--from", text(args.from_commit)); }
        else if (op === "switch") argv.push("switch", text(args.name));
        else if (op === "delete") { argv.push("delete", text(args.name)); if (args.force) argv.push("--force"); }
        else return { ok: false, error: { code: "E-ARGS", message: `未知 op: ${op}`, hint: "可选 list/create/switch/delete" } };
        if (!text(args.name) && op !== "list") return { ok: false, error: { code: "E-ARGS", message: `${op} 需要 name 参数` } };
        const lockDir = op === "list" ? null : await acquirePackageLock(pkgDir, `cad_branch:${op}`, LOCK_TIMEOUT_MS, LOCK_STALE_MS);
        try {
          const r = await runCli("branch", ws, argv, { session: sessionOf(exec), signal: combinedSignal(exec, 60000), cwd: pkgDir });
          const successEvents = ["branch_list", "branch_create_success", "branch_switch_success", "branch_delete_success"];
          const payload = r.events.find((e) => successEvents.includes(e.event));
          return {
            ok: r.ok && !!payload,
            op,
            result: payload ? (Array.isArray(payload.payload.branches) ? payload.payload.branches : [payload.payload]) : [],
            events: r.events,
            ...(r.ok && payload ? {} : { error: r.error || { code: "E-BRANCH", message: `branch ${op} 失败` } }),
          };
        } finally {
          if (lockDir) releasePackageLock(lockDir);
        }
      },
    );

    // ─────────────────────────────────────────────────────────────────────
    // cad_export
    // ─────────────────────────────────────────────────────────────────────
    define(
      "cad_export",
      "导出当前版本（或指定 commit）为 STEP / STL 文件。输出必须位于会话工作区内。",
      {
        type: "object",
        properties: {
          format: { type: "string", enum: ["step", "stl"] },
          output: { type: "string", description: "输出文件路径（相对工作区或绝对）" },
          commit: { type: "string" },
          package: { type: "string" },
        },
        required: ["format", "output"],
      },
      {
        schema: {
          type: "object",
          additionalProperties: false,
          properties: {
            ok: { type: "boolean" },
            format: { type: "string" },
            path: { type: "string" },
            events: { type: "array", items: eventSchema },
            error: errorSchema,
          },
        },
        render: (_a, v) => block(v.ok ? `已导出 ${v.format} → ${v.path}` : `✗ ${v.error && v.error.message}${v.error && v.error.hint ? `\n提示: ${v.error.hint}` : ""}`),
      },
      async (args, exec) => {
        const ws = workspaceOf(exec);
        const pkgDir = findPackageDir(ws, args.package);
        const py = resolvePython(ws);
        const out = resolvePath(ws, args.output);
        if (!isWithin(ws, out)) return { ok: false, error: { code: "E-PATH", message: `输出路径越界: ${out}`, hint: "导出文件必须位于会话工作区内" } };
        const argv = [...pythonArgs(py), "export", "--format", text(args.format), "--output", out];
        if (text(args.commit)) argv.push(text(args.commit));
        const r = await runCli("export", ws, argv, { session: sessionOf(exec), signal: combinedSignal(exec, 120000), cwd: pkgDir });
        const payload = r.events.find((e) => e.event === "export_success");
        return {
          ok: r.ok && !!payload,
          format: text(args.format),
          path: payload ? text(payload.payload.path) : out,
          events: r.events,
          ...(r.ok && payload ? {} : { error: r.error || { code: "E-EXPORT", message: "export_success 缺失" } }),
        };
      },
    );

    // ─────────────────────────────────────────────────────────────────────
    // cad_artifact
    // ─────────────────────────────────────────────────────────────────────
    define(
      "cad_artifact",
      "管理模型包工件：list 列出各提交的工件与大小；clean 按策略清理旧工件。",
      {
        type: "object",
        properties: {
          op: { type: "string", enum: ["list", "clean"] },
          policy: { type: "string", enum: ["all_commits", "latest_per_branch", "releases_only"], description: "clean 策略；缺省用 manifest.artifact_policy" },
          package: { type: "string" },
        },
        required: ["op"],
      },
      {
        schema: {
          type: "object",
          additionalProperties: false,
          properties: {
            ok: { type: "boolean" },
            op: { type: "string" },
            artifacts: { type: "array", items: freeObject },
            totalSizeBytes: { type: "integer" },
            totalSizeMb: { type: "number" },
            policy: { type: "string" },
            deleted: { type: "array", items: { type: "string" } },
            events: { type: "array", items: eventSchema },
            error: errorSchema,
          },
        },
        render: (_a, v) => block(
          v.ok
            ? v.op === "list"
              ? `${(v.artifacts || []).length} 个提交工件，合计 ${v.totalSizeMb} MB`
              : `清理完成：删除 ${(v.deleted || []).length} 个提交工件（policy=${v.policy}）`
            : `✗ ${v.error && v.error.message}${v.error && v.error.hint ? `\n提示: ${v.error.hint}` : ""}`,
        ),
      },
      async (args, exec) => {
        const ws = workspaceOf(exec);
        const pkgDir = findPackageDir(ws, args.package);
        const py = resolvePython(ws);
        const op = text(args.op, "list");
        const argv = [...pythonArgs(py), "artifacts"];
        if (op === "list") argv.push("list");
        else if (op === "clean") { argv.push("clean"); if (text(args.policy)) argv.push("--policy", text(args.policy)); }
        else return { ok: false, error: { code: "E-ARGS", message: `未知 op: ${op}`, hint: "可选 list/clean" } };
        const lockDir = op === "list" ? null : await acquirePackageLock(pkgDir, `cad_artifact:${op}`, LOCK_TIMEOUT_MS, LOCK_STALE_MS);
        try {
          const r = await runCli("artifacts", ws, argv, { session: sessionOf(exec), signal: combinedSignal(exec, 60000), cwd: pkgDir });
          const listEvt = r.events.find((e) => e.event === "artifacts_list");
          const cleanEvt = r.events.find((e) => e.event === "artifacts_clean_success");
          const okPayload = listEvt || cleanEvt;
          return {
            ok: r.ok && !!okPayload,
            op,
            artifacts: listEvt ? list(listEvt.payload.artifacts) : [],
            totalSizeBytes: listEvt ? num(listEvt.payload.total_size_bytes) : 0,
            totalSizeMb: listEvt ? num(listEvt.payload.total_size_mb) : 0,
            // list 操作时 policy 键缺省而非 null（schema 为 string 型）
            ...(cleanEvt ? { policy: text(cleanEvt.payload.policy) } : {}),
            deleted: cleanEvt ? list(cleanEvt.payload.deleted_commits) : [],
            events: r.events,
            ...(r.ok && okPayload ? {} : { error: r.error || { code: "E-ARTIFACT", message: `artifacts ${op} 失败` } }),
          };
        } finally {
          if (lockDir) releasePackageLock(lockDir);
        }
      },
    );

    // ─────────────────────────────────────────────────────────────────────
    // 后台任务辅助（tool-jobs 的 ctx.jobs）
    // ─────────────────────────────────────────────────────────────────────
    function startJob(exec, label, work) {
      if (!jobs || !exec.agent) return null;
      try {
        let controller = null;
        let cancelled = false;
        const chunks = [];
        const id = jobs.start({
          kind: "cad",
          label,
          owner: exec.agent,
          outputLimitBytes: 1 << 20,
          run: () => {
            controller = new AbortController();
            const done = Promise.resolve()
              .then(() => work({ signal: controller.signal }))
              .then(() => ({ status: cancelled ? "killed" : "completed", detail: cancelled ? "cancelled" : "ok" }))
              .catch((e) => ({ status: cancelled ? "killed" : "failed", detail: String(e && e.message || e) }));
            return {
              cancel(reason) {
                cancelled = true;
                if (controller) controller.abort(String(reason || "cancelled"));
              },
              done,
              readOutput() {
                const chunk = chunks.splice(0).join("\n");
                return chunk ? chunk + "\n" : "";
              },
            };
          },
        });
        return String(id);
      } catch { return null; }
    }

    console.log("[cad-studio] plugin loaded (16 tools: env_status/env_bootstrap/pkg_list/init/run/validate/inspect/commit/log/status/render/review/checkout/branch/export/artifact)");
  },
};
