import { identifyHost, readLaunchHostInfo, unknownHost } from "../detection/index.mjs";

// The SDK owns protocol-era translation. A modern request that omits identity
// cannot inherit a prior request's cached identity from the legacy accessor.
export function requestClientInfo(server, context) {
  const envelope = context?.mcpReq?.envelope;
  return envelope !== undefined ? envelope["io.modelcontextprotocol/clientInfo"] : server.getClientVersion();
}

/** Capture launch facts before business work. MCP client versions describe the
 * calling engine, not the UI shell; only UI initialization grants UI capabilities. */
export function launchHostInfo({ clientInfo, presentation, nativeHost }) {
  const transport = presentation === "html" ? "http-bridge" : "mcp-app";
  const reported = clientInfo && typeof clientInfo === "object" ? clientInfo : {};
  let id = "unknown";
  if (["codex-mcp-client", "chatgpt"].includes(reported.name) &&
      (reported.client_type === undefined || reported.client_type === "codex_desktop")) id = "codex";
  if (reported.name === "claude-code") id = "claude";
  if (nativeHost !== undefined) {
    const native = identifyHost({transport,connected:true,identity:nativeHost,capabilities:{}});
    if (id !== "claude" || native.id !== "claude" || transport !== "http-bridge") {
      throw new Error("Native launch identity requires the actual Claude MCP connection and HTML presentation.");
    }
    return readLaunchHostInfo(native);
  }
  return readLaunchHostInfo({ ...unknownHost("启动调用尚未提供可确认的宿主身份。"),
    id, status: id === "unknown" ? "unknown" : "confirmed", transport, identitySource: "mcp-client",
    name: reported.name ?? null, version: reported.version === "unknown" ? null : reported.version ?? null,
    clientType: reported.client_type ?? null, sessionId: null });
}

/** Cross-check facts that describe the same thing. MCP engine and UI-shell
 * names/versions may differ, so they are not compared across evidence sources. */
export function launchMatchesConnection(launch, current) {
  if (launch.transport !== current.transport) return false;
  if (launch.id === "unknown" || current.status !== "confirmed") return true;
  if (launch.id !== current.id) return false;
  if (launch.sessionId && launch.sessionId !== current.sessionId) return false;
  return launch.identitySource !== current.identitySource ||
    ["name", "version", "clientType"].every(key => !launch[key] || launch[key] === current[key]);
}
