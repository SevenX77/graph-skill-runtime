import { CONTEXT_TOOL, SELECT_TOOL } from "../../../adapters/claude/mod/host_tools/index.mjs";
import { has, present } from "../../../adapters/claude/mod/operations/shared.mjs";
import { nativeData } from "../../../adapters/claude/mod/operations/tools/index.mjs";
import { executeView } from "../../../adapters/claude/mod/operations/views/index.mjs";

export const capability = tools => present(has(tools, CONTEXT_TOOL) && has(tools, SELECT_TOOL), "激活当前连接已观察到的浏览器标签", { scope: "browser-tabs" });

// The shared view dispatcher reads tabs both before and after selection. A
// failure in the second read cannot prove the selection was never delivered.
export function invoke($, { state, owner, request, tools, guard }) {
  let selectionAttempted = false;
  const observer = { tool: { call: async input => {
    if (input.tool === SELECT_TOOL) selectionAttempted = true;
    const response = await $.tool.call(input);
    if (selectionAttempted && input.tool === CONTEXT_TOOL && !response?.deny && !response?.denied && !response?.isError) {
      const tabs = nativeData(response)?.tabs;
      if (Array.isArray(tabs) && tabs.some(tab => typeof tab?.tabId !== "string" || typeof tab.isActive !== "boolean")) {
        throw Object.assign(new Error("宿主激活后的标签状态格式不明确。"), { outcome: "unknown" });
      }
    }
    return response;
  } } };
  return executeView(observer, state, owner, request, tools, guard).catch(error => {
    if (selectionAttempted && error?.outcome === "not-sent") error.outcome = "unknown";
    throw error;
  });
}
