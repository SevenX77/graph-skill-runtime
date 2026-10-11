// Test host only. This does not stand in for Codex or Claude Code acceptance.
import { AppBridge, PostMessageTransport } from "@modelcontextprotocol/ext-apps/app-bridge";
import { z } from "zod";

const iframe = document.querySelector("iframe");
const response = await fetch("/tool-result.json");
const result = await response.json();
const native = ["native", "reject"].includes(new URLSearchParams(location.search).get("files"));
const bridge = new AppBridge(null, { name: "graph-canvas-test-host", version: "0.0.2" }, { message: {text:{}}, updateModelContext: {}, serverTools: {}, ...(native ? { experimental: { "openai/files": {} } } : {}) });
bridge.setRequestHandler("openai/files/open", { params: z.object({ path: z.string() }) }, async request => {
  document.documentElement.dataset.openedPath = request.path;
  if (new URLSearchParams(location.search).get("files") === "reject") throw new Error("Test host rejects directories");
  return {};
});
bridge.onmessage = async request => {
  document.documentElement.dataset.agentRequest = JSON.stringify(request);
  // Explicit fault injection for observing unknown-outcome UI recovery.
  if (new URLSearchParams(location.search).get("message") === "timeout") return new Promise(() => {});
  return {};
};
bridge.onupdatemodelcontext = async request => {
  document.documentElement.dataset.modelContext = JSON.stringify(request);
  return {};
};
bridge.oncalltool = async request => {
  if (request.name !== "inspect_graph" || request.arguments?.skill_root !== result.structuredContent.skillRoot) throw new Error("Tool request is outside the displayed Skill.");
  const response = await fetch("/inspect", {method:"POST"});
  if (!response.ok) throw new Error("Graph query failed.");
  return response.json();
};
bridge.oninitialized = async () => {
  await bridge.sendToolInput({ arguments: {} });
  await bridge.sendToolResult(result);
  document.documentElement.dataset.bridge = "initialized";
};
await bridge.connect(new PostMessageTransport(iframe.contentWindow, iframe.contentWindow));
iframe.src = "/canvas.html";
