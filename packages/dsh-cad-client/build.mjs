// Derive lib/client.js (web __ModuleLoader__ bundle) from the single-source
// client module in plugin/cad-studio/cad-studio-client.mjs.
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const src = join(root, "plugin", "cad-studio", "cad-studio-client.mjs");
const out = join(root, "packages", "dsh-cad-client", "lib", "client.js");
const text = readFileSync(src, "utf8");
const marker = "export default cadClientPlugin;";
if (!text.includes(marker)) throw new Error("source marker not found: " + marker);
const body = text.replace(marker, "").trim();

const bundle = `window.__ModuleLoader__.load({
\tid: "@deepseek-ai/dsh-cad-client",
\tfactory: (require) => {
\t\tvar module = { exports: {} };
\t\tvar exports = module.exports;
\t\tObject.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
\t\tlet react = require("react");
\t\tconst React = react;
\t\t${body.replace(/\n/g, "\n\t\t")}
\t\texports.apply = cadClientPlugin.apply;
\t\texports.inject = cadClientPlugin.inject;
\t\treturn module.exports;
\t}
});
`;
writeFileSync(out, bundle);
console.log("built", out, bundle.length, "bytes");
