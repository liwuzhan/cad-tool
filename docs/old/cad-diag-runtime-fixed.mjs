// cad-diag-runtime 诊断插件 — 修正版（pkg-2 的 schema 修复）
//
// 修复点：DSH 要求 JSON Schema 中每个 object 节点显式声明
// `additionalProperties: true | false`。旧版漏写，导致：
//   unsupported JSON schema: schema.properties.providers.items.additionalProperties
//   must be explicitly true or false (host-half-failed)
//
// 用法：在定义该插件的 DSH web 会话里，让模型读取本文件，然后用
// `cordis_define` 重新定义（kind: existing, pluginId: cdiag-1 会生成新 pkg），
// 再 `cordis_run` 运行新 pkg。不要直接重试旧 pkg-2 —— 旧代码没有变。

export const hostCode = `return {
  apply(ctx) {
    const tool = harness.defineTool({
      name: 'diag_runtime',
      description: '诊断：列出 LLM providers/models、clientModules 图与 cad-client 接线、默认模型选择。纯读取。',
      parameters: { type: 'object', properties: {}, required: [], additionalProperties: false },
      output: {
        schema: {
          type: 'object',
          additionalProperties: false,
          properties: {
            providers: { type: 'array', items: { type: 'object', additionalProperties: true } },
            models: { type: 'object', additionalProperties: true },
            defaultModel: { type: 'object', additionalProperties: true },
            clientGraph: { type: 'object', additionalProperties: true },
          },
        },
        render: (_a, v) => [{ type: 'text', text: JSON.stringify(v, null, 2) }],
      },
      async execute() {
        const out = { providers: [], models: {}, defaultModel: {}, clientGraph: {} };
        const llm = ctx.get('llm');
        if (llm) {
          try { out.providers = llm.listProviders().map((p) => ({ id: p.id || p.provider || p.name, label: p.label || p.name })); } catch (e) { out.providers = [{ error: String(e && e.message || e) }]; }
          for (const p of out.providers) {
            const id = p.id;
            if (!id) continue;
            try {
              const ms = await llm.listModels(id);
              out.models[id] = ms.map((m) => (typeof m === 'string' ? m : (m.id || m.model || m.name))).slice(0, 40);
            } catch (e) { out.models[id] = 'ERROR: ' + String(e && e.message || e); }
          }
        }
        const adm = ctx.get('agentDefaultModel');
        if (adm) {
          try { const sel = adm.currentSelection(); out.defaultModel = { provider: sel && sel.provider, model: sel && sel.model, reasoningEffort: sel && sel.reasoningEffort }; } catch (e) { out.defaultModel = { error: String(e && e.message || e) }; }
        }
        const cm = ctx.get('clientModules');
        if (cm) {
          try {
            const g = cm.graph();
            const ids = g && g.modules ? Object.keys(g.modules) : (g && g.entries ? Object.keys(g.entries) : Object.keys(g || {}));
            out.clientGraph = {
              ids: ids.filter((i) => i.includes('cad') || i.includes('client')).slice(0, 30),
              cadClientPath: cm.clientPath('@deepseek-ai/dsh-cad-client') || null,
              cadClientRebuilt: cm.rebuilt('@deepseek-ai/dsh-cad-client') || null,
            };
          } catch (e) { out.clientGraph = { error: String(e && e.message || e) }; }
        }
        return out;
      },
    });
    harness.registerTool(ctx, tool);
    console.log('[diag] diag_runtime registered');
  },
};`;

// 建议的 cordis_define 参数（在 DSH web 会话里由模型调用；kind: new 也可以）：
export const cordisDefineArguments = {
  code: { host: hostCode },
  name: 'cad-diag-runtime',
  plugin: { kind: 'existing', pluginId: 'cdiag-1' },
  purpose: '临时诊断插件（schema 修正版）：注册 diag_runtime 工具，读取 LLM providers/models、clientModules 启动图与 cad-client 接线状态。',
};
