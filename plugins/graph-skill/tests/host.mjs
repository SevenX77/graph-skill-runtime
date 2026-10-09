// Test host only. This does not stand in for Codex or Claude Code acceptance.
import { AppBridge, PostMessageTransport } from "@modelcontextprotocol/ext-apps/app-bridge";
import { z } from "zod";

const iframe = document.querySelector("iframe");
const response = await fetch("/tool-result.json");
const result = await response.json();
const native = ["native", "reject"].includes(new URLSearchParams(location.search).get("files"));
const bridge = new AppBridge(null, { name: "graph-canvas-test-host", version: "0.0.2" }, native ? { experimental: { "openai/files": {} } } : {});
bridge.setRequestHandler(z.object({ method: z.literal("openai/files/open"), params: z.object({ path: z.string() }) }), async request => {
  document.documentElement.dataset.openedPath = request.params.path;
  if (new URLSearchParams(location.search).get("files") === "reject") throw new Error("Test host rejects directories");
  return {};
});
bridge.onmessage = async request => {
  document.documentElement.dataset.agentRequest = JSON.stringify(request);
  return {};
};
bridge.oninitialized = async () => {
  await bridge.sendToolInput({ arguments: {} });
  await bridge.sendToolResult(result);
  document.documentElement.dataset.bridge = "initialized";
};
await bridge.connect(new PostMessageTransport(iframe.contentWindow, iframe.contentWindow));
iframe.src = "/canvas.html";
