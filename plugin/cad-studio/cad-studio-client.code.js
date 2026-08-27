// cad-studio Client 半件（P3 · L2 CADPreviewNode 原型）
//
// 挂载点：`tool.call.toolview`（keyed by tool name，来自 client-ui-tool 的
// `conversation.chat.node → tool-call` 声明树，owner props:
//   { callId, toolName, block, openFile, cwd, inspect }）。
// 数据来源：Host 插件 output.presentationMeta 投影进 `tool/result` 事件的
// meta 字段，Client 侧 ToolResultNode.meta 原样携带，因此 block.meta 里有
// { kind, ok, metrics, checkpoints, preview:[{path,label,dataUrl?,inline}] }。
//
// 本文件为 ESM 形态（供 bundler / 静态装配使用）；`cad-studio-client.code.js`
// 由本文件派生，是 cordis_define 的 `code.client` 函数体（React 为注入参数）。
// 仅用 React.createElement，无 JSX / import / TS。
const el = React.createElement;

function parseArgs(raw) {
  try { return JSON.parse(raw || "{}"); } catch { return {}; }
}

function numberFmt(n) {
  const v = Number(n);
  return Number.isFinite(v) ? (Math.abs(v) >= 100 ? v.toFixed(1) : v.toFixed(3)) : String(n ?? "-");
}

function MetricLine({ m }) {
  if (!m || typeof m !== "object") return null;
  const bits = [];
  if (m.volume !== undefined) bits.push(`体积 ${numberFmt(m.volume)} mm³`);
  if (m.area !== undefined) bits.push(`面积 ${numberFmt(m.area)} mm²`);
  if (m.face_count !== undefined) bits.push(`${m.face_count} 面`);
  if (m.edge_count !== undefined) bits.push(`${m.edge_count} 边`);
  if (Array.isArray(m.bbox) && m.bbox.length === 6) bits.push(`边界 ${m.bbox.map((x) => numberFmt(x)).join(", ")}`);
  if (bits.length === 0) return null;
  return el("div", { style: { font: "var(--dsw-font-xs-13)", color: "var(--dsw-alias-label-secondary)", lineHeight: "18px" } }, bits.join(" · "));
}

function CheckpointChips({ checkpoints }) {
  const list = Array.isArray(checkpoints) ? checkpoints : [];
  if (list.length === 0) return null;
  return el(
    "div",
    { style: { display: "flex", flexWrap: "wrap", gap: "4px", marginTop: "4px" } },
    list.map((cp) => {
      const passed = cp.event === "checkpoint_passed";
      return el(
        "span",
        {
          key: cp.name,
          style: {
            font: "var(--dsw-font-xs-13)",
            lineHeight: "20px",
            padding: "0 8px",
            borderRadius: "999px",
            border: "1px solid " + (passed ? "var(--dsw-alias-state-success-border, rgba(34,197,94,.5))" : "var(--dsw-alias-state-error-primary)"),
            color: passed ? "var(--dsw-alias-state-success-primary, #22c55e)" : "var(--dsw-alias-state-error-primary)",
            background: "var(--dsw-alias-bg-base)",
          },
        },
        (passed ? "✓ " : "✗ ") + cp.name + " " + (cp.passed ?? 0) + "/" + (cp.total ?? 0),
      );
    }),
  );
}

function PreviewGrid({ preview }) {
  const imgs = (Array.isArray(preview) ? preview : []).filter((p) => p && p.dataUrl);
  if (imgs.length === 0) return null;
  return el(
    "div",
    {
      style: {
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
        gap: "6px",
        marginTop: "6px",
      },
    },
    imgs.map((p) =>
      el("figure", { key: p.path, style: { margin: 0 } },
        el("img", {
          src: p.dataUrl,
          alt: p.label || p.path || "",
          style: {
            width: "100%",
            maxHeight: "200px",
            objectFit: "contain",
            borderRadius: "6px",
            border: "1px solid var(--dsw-alias-border-l1)",
            background: "var(--dsw-alias-bg-base)",
          },
        }),
        el("figcaption", { style: { font: "var(--dsw-font-xs-13)", color: "var(--dsw-alias-label-caption)", textAlign: "center", marginTop: "2px" } }, p.label || ""),
      ),
    ),
  );
}

function PathList({ images }) {
  const paths = (Array.isArray(images) ? images : []).filter((i) => i && i.path && !i.dataUrl);
  if (paths.length === 0) return null;
  return el(
    "div",
    { style: { font: "var(--dsw-font-xs-13)", color: "var(--dsw-alias-label-tertiary)", marginTop: "4px", wordBreak: "break-all" } },
    paths.map((p) => el("div", { key: p.path }, String(p.view || p.label || "") + " → " + String(p.path))),
  );
}

function ErrorBox({ error, isError, content }) {
  if (!isError && (!error || !error.message)) return null;
  const message = (error && error.message) || "";
  const code = error && error.code ? " [" + error.code + "]" : "";
  const hint = error && error.hint ? "\n提示: " + error.hint : "";
  return el(
    "div",
    {
      style: {
        marginTop: "6px",
        padding: "6px 8px",
        borderRadius: "6px",
        border: "1px solid var(--dsw-alias-state-error-primary)",
        color: "var(--dsw-alias-state-error-primary)",
        font: "var(--dsw-font-xs-13)",
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
      },
    },
    message + code + hint,
  );
}

function StateDot({ state }) {
  const color = state === "ok" ? "var(--dsw-alias-state-success-primary, #22c55e)"
    : state === "error" ? "var(--dsw-alias-state-error-primary)"
    : state === "running" ? "var(--dsw-static-deepseek-500, #4d6bfe)"
    : "var(--dsw-alias-label-tertiary)";
  return el("span", {
    style: { display: "inline-block", width: "8px", height: "8px", borderRadius: "999px", background: color, flex: "none", marginRight: "6px", marginTop: "7px" },
  });
}

function CadRow({ toolName, block, cwd, openFile, inspect, callId }) {
  const [open, setOpen] = React.useState(false);
  const done = block !== null && typeof block === "object" && ("kind" in block);
  const meta = done && block.meta && typeof block.meta === "object" ? block.meta : null;
  const state = !done ? "running" : done && block.isError ? "error" : "ok";
  const argsRaw = done ? (block.call && block.call.argsRaw) || "" : block.argsRaw || "";
  const args = parseArgs(argsRaw);
  const pkg = (meta && meta.package) || args.package || null;
  const commit = meta && meta.commit ? meta.commit.hash : null;
  const script = (meta && meta.script) || args.script || null;
  const message = args.message || null;

  let summary = pkg ? String(pkg) : callId || "";
  if (done && meta) {
    if (meta.kind === "cad-commit" && commit) summary += " · " + String(commit);
    if (meta.ok === false && meta.error) summary += " · 失败";
  } else if (script) summary = String(script);

  const head = el(
    "div",
    {
      role: "button",
      tabIndex: 0,
      onClick: () => setOpen(!open),
      onKeyDown: (e) => { if (e.key === "Enter" || e.key === " ") { setOpen(!open); } },
      style: { display: "flex", alignItems: "flex-start", minWidth: 0, cursor: "pointer", padding: "2px 0" },
    },
    el(StateDot, { state }),
    el("span", { style: { font: "var(--dsw-font-s-14, 14px)", color: "var(--dsw-alias-label-secondary)", flex: "none", lineHeight: "22px" } }, toolName || "cad"),
    el("span", { style: { margin: "0 8px", flex: "none", color: "var(--dsw-alias-label-caption)", lineHeight: "22px" } }, "·"),
    el("span", { style: { font: "var(--dsw-font-s-14, 14px)", color: state === "error" ? "var(--dsw-alias-state-error-primary)" : "var(--dsw-alias-label-tertiary)", textOverflow: "ellipsis", whiteSpace: "nowrap", overflow: "hidden", minWidth: 0, flex: "auto", lineHeight: "22px" } }, summary || " "),
  );

  let body = null;
  if (open || state === "error") {
    body = el(
      "div",
      { style: { display: "flex", flexDirection: "column", gap: "4px", margin: "2px 0 4px 14px" } },
      message !== null ? el("div", { style: { font: "var(--dsw-font-xs-13)", color: "var(--dsw-alias-label-secondary)" } }, "message: " + String(message)) : null,
      script && openFile ? el("button", { type: "button", onClick: () => openFile(String(script)), style: { alignSelf: "flex-start", background: "transparent", border: "none", color: "var(--dsw-static-deepseek-500)", cursor: "pointer", padding: 0, font: "var(--dsw-font-xs-13)" } }, "open script") : null,
      done && meta ? el(MetricLine, { m: meta.metrics }) : null,
      done && meta ? el(CheckpointChips, { checkpoints: meta.checkpoints }) : null,
      done && meta ? el(PreviewGrid, { preview: meta.preview || meta.images }) : null,
      done && meta ? el(PathList, { images: (meta.images || meta.preview || []).concat(meta.preview || []) }) : null,
      done ? el(ErrorBox, { error: meta && meta.error, isError: !!block.isError, content: block.content }) : null,
    );
  }

  return el(
    "div",
    {
      style: {
        border: "1px solid " + (state === "error" ? "var(--dsw-alias-state-error-primary)" : "var(--dsw-alias-border-l1)"),
        background: "var(--dsw-alias-bg-base)",
        borderRadius: "8px",
        padding: "4px 10px",
        minWidth: 0,
      },
      "data-cad-toolview": toolName,
    },
    head,
    body,
    inspect ? el("button", { type: "button", onClick: () => inspect(), style: { position: "absolute", opacity: 0, pointerEvents: "none", width: 0, height: 0 } }) : null,
  );
}

const cadClientPlugin = {
  name: "cad-studio-client",
  inject: ["slots"],
  apply(ctx) {
    const slots = ctx.get("slots");
    if (slots === undefined) return;
    const keys = [
      "cad_env_status", "cad_env_bootstrap", "cad_pkg_list", "cad_init",
      "cad_run", "cad_validate", "cad_inspect", "cad_commit",
      "cad_log", "cad_status", "cad_render", "cad_review",
      "cad_checkout", "cad_branch", "cad_export", "cad_artifact",
    ];
    slots.inject("tool.call.toolview", function* () {
      for (const key of keys) {
        yield slots.register({ name: "tool.call.toolview", key }, CadRow);
      }
    });
    console.log("[cad-studio-client] registered", keys.length, "toolviews");
  },
};

return cadClientPlugin;
