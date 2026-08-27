// Client-half harness: parse cad-studio-client.code.js with the exact wrapper
// shape used by dsh-cordis-client-runner (`new Function("React", ..., body)`),
// then mount it against a mock slots service and render CadRow with fake
// running/done blocks to catch runtime errors without a browser.
import { readFileSync } from "node:fs";

const code = readFileSync(new URL("./cad-studio-client.code.js", import.meta.url), "utf8");

const registrations = [];
const fakeSlots = {
  inject(name, callback) {
    const out = callback();
    if (out && typeof out.next === "function") {
      for (let step = out.next(); !step.done; step = out.next()) registrations.push(step.value);
    } else if (out) registrations.push(out);
  },
  register(options, renderer) {
    const reg = { ...options, renderer };
    registrations.push(reg);
    return () => {};
  },
};

const plugin = await (async () => {
  const React = {
    createElement(type, props, ...children) {
      return { type, props: props || {}, children };
    },
    useState(initial) { return [initial, () => {}]; },
  };
  const host = { call: async () => null };
  const harness = {};
  const styles = { insert: () => () => {} };
  const fn = new Function(
    "React", "console", "styles", "host", "harness", "process", "Buffer",
    `return (async () => {\n${code}\n})()`,
  );
  return fn(React, console, styles, host, harness, process, Buffer);
})();

if (!plugin || typeof plugin.apply !== "function") throw new Error("client code did not return a plugin");
plugin.apply({ get: (name) => (name === "slots" ? fakeSlots : undefined) });
console.log(`registered keys: ${registrations.map((r) => r.key).join(",")}`);

const runningBlock = { callId: "call-1", name: "cad_run", argsRaw: JSON.stringify({ package: "/ws/demo.456d" }) };
const doneBlock = {
  kind: "tool-result",
  call: { name: "cad_run", argsRaw: JSON.stringify({ package: "/ws/demo.456d" }) },
  content: [{ type: "text", text: "ok" }],
  isError: false,
  meta: {
    kind: "cad-run",
    ok: true,
    package: "/ws/demo.456d",
    metrics: { volume: 170575.22, area: 22856.64, face_count: 7, bbox: [-50, -30, -15, 50, 30, 15] },
    checkpoints: [
      { name: "base", event: "checkpoint_passed", passed: 2, total: 2 },
      { name: "hole", event: "checkpoint_passed", passed: 2, total: 2 },
    ],
    preview: [{ path: "/tmp/x.png", label: "checkpoint:base", sizeBytes: 12, inline: true, dataUrl: "data:image/png;base64,AA==" }],
  },
};

const runRow = registrations.find((r) => r.key === "cad_run");
if (!runRow) throw new Error("cad_run toolview not registered");
const Component = runRow.renderer;
if (typeof Component !== "function") throw new Error("cad_run registration has no renderer");

// render running + done variants
for (const block of [runningBlock, doneBlock]) {
  const tree = Component({ toolName: "cad_run", block, cwd: "/ws", openFile: () => {}, inspect: () => {}, callId: block.callId });
  if (!tree || tree.type !== "div") throw new Error("CadRow root is not a div");
}
console.log("CLIENT-RENDER-OK (running + done blocks)");
process.exit(0);
