import { readFile } from "node:fs/promises";
import { registerAppResource, registerAppTool, RESOURCE_MIME_TYPE } from "@modelcontextprotocol/ext-apps/server";
import { z } from "zod";
import { labStateDirectory, prepareLab } from "./state.mjs";
import { snapshotHtml, createPreviewConfiguration, pageResourceUri, codexResourceMetadata, createCodexPageSessions, launchHostInfo, requestClientInfo } from "hostpane/server";

// The build places this self-contained page alongside the bundled server.
const html = await readFile(new URL("./interface-lab.html", import.meta.url), "utf8");
const PAGE_KEY = "plugin-interface-lab";
export const ECHO_TOOL = "lab_echo";

/** The Plugin Interface Lab app: a developer page that calls every Plugin Base
 * operation and shows its evidence. It shares no tool or page with the canvas. */
export function interfaceLabApp({ hostBridge, serverInfo }, { stateDirectory = labStateDirectory() } = {}) {
  const previewConfiguration = createPreviewConfiguration({ namePrefix: "interface-lab" });
  const ready = prepareLab(stateDirectory);
  return { register, close: () => previewConfiguration.close() };

  function register(server, { local }) {
    const codexSessions = createCodexPageSessions();
    const granted = ready.then(async lab => { await local.allow(lab.stateDirectory); return lab; });
    const bootstrap = { serverInfo, page: PAGE_KEY, local: { transport: "mcp-tools" } };
    const resourceUri = pageResourceUri("plugin-interface-lab", "lab", snapshotHtml(html, bootstrap));
    const ui = { csp: { connectDomains: [], resourceDomains: [] }, prefersBorder: false };

    registerAppTool(server, "open_interface_lab", {
      title: "Open Plugin Interface Lab",
      description: "Open the Plugin Interface Lab: a developer page that calls each Plugin Base host interface and local capability on this host and shows what was sent, what the host returned, what was observed and which host limits apply. In Codex it is the MCP App view attached to this result. In Claude Code it is an owned loopback HTTP page shown in the Browser pane: HTML presentation requires preview_project_root from the actual Claude session root; record existing tabs, attach the returned preview name, retain the actual HTTP tabId, navigate only that tab to the lab URL, select it and verify it is active with every prior user page preserved. If the Browser pane is hidden, show it once with mcp__ccd_view__show_pane {\"pane\":\"preview\"} and read the tabs again; if it stays hidden, ask the user to open it manually. This tool does not run any interface by itself.",
      inputSchema: z.object({ presentation: z.enum(["mcp-app", "html"]).optional(), preview_project_root: z.string().min(1).optional(),
        native_host: z.object({ name: z.literal("Claude Code"), version: z.string().min(1).max(256), client_type: z.literal("claude_code"),
          sessionId: z.string().min(1).max(256), source: z.literal("claude-mod-session") }).strict().optional().describe("Supplied by the Claude Mod from native session APIs; the Mod overwrites caller values. Omit in ordinary calls.") }).strict(),
      annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: false },
      _meta: { ui: { resourceUri, visibility: ["model"] } },
    }, async ({ presentation, preview_project_root, native_host }, context) => {
      try {
        const hostInfo = launchHostInfo({ clientInfo: requestClientInfo(server.server, context), presentation, nativeHost: native_host });
        if (presentation === "html" && !preview_project_root) throw new Error("HTML preview requires the actual host session's preview_project_root.");
        if (presentation !== "html" && preview_project_root !== undefined) throw new Error("preview_project_root applies only to HTML presentation.");
        const lab = await granted;
        const payload = { lab, hostInfo, serverInfo };
        let httpPresentation;
        if (presentation === "html") {
          const bridge = await hostBridge.createView(PAGE_KEY, hostInfo);
          const document = snapshotHtml(html, { ...bootstrap, ...payload, hostBridge: bridge.browser, local: { transport: "http", ...local.descriptor } });
          const preview = await previewConfiguration.ensure(preview_project_root, bridge.browser.url);
          httpPresentation = { kind: "http", url: hostBridge.publish(PAGE_KEY, document), preview, bridge: bridge.mod };
        }
        return {
          content: [{ type: "text", text: `Plugin Interface Lab is ready. Its sandbox is ${lab.sandbox}; comparison records are written to ${lab.records}.` }],
          structuredContent: { ...payload, ...(httpPresentation ? { presentation: httpPresentation } : {}) },
          ...(presentation !== "html" ? { _meta: codexSessions.metadata(PAGE_KEY) } : {}),
        };
      } catch (error) {
        return { isError: true, content: [{ type: "text", text: `Cannot open the Plugin Interface Lab: ${error.message}` }], ...(presentation !== "html" ? { _meta: codexSessions.existingMetadata(PAGE_KEY) } : {}) };
      }
    });

    registerAppTool(server, ECHO_TOOL, {
      title: "Interface Lab echo",
      description: "Interface Lab test target for tools.call: returns its arguments and the server time. It has no side effect.",
      inputSchema: z.object({ text: z.string().max(2000).optional() }).strict(),
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
      _meta: { ui: { visibility: ["model", "app"] } },
    }, async args => ({
      content: [{ type: "text", text: `lab_echo received: ${JSON.stringify(args)}` }],
      structuredContent: { echo: args, at: new Date().toISOString(), server: serverInfo.name },
    }));

    registerAppResource(server, "Plugin Interface Lab", resourceUri, {
      description: "Developer page that exercises every Plugin Base interface and shows its evidence.",
      _meta: { ui, ...codexResourceMetadata },
    }, async (_uri, context) => {
      const lab = await granted;
      return { contents: [{ uri: resourceUri, mimeType: RESOURCE_MIME_TYPE,
        text: snapshotHtml(html, { ...bootstrap, lab, hostInfo: launchHostInfo({ clientInfo: requestClientInfo(server.server, context) }) }),
        _meta: { ui, ...codexResourceMetadata } }] };
    });
    return [{ name: ECHO_TOOL, description: "Echo the arguments back; the Interface Lab's tools.call target." }];
  }
}
