// A fake Claude Browser: preview_start opens tabs, tabs_context reports them in
// the host's text shape (JSON then a pane-visibility line), select/close mutate.
import { PREVIEW_TOOL, NAVIGATE_TOOL, CONTEXT_TOOL, SELECT_TOOL, CLOSE_TOOL } from "../../plugin_base/adapters/claude/mod/host_tools/index.mjs";

export const BROWSER_TOOLS = [PREVIEW_TOOL, NAVIGATE_TOOL, CONTEXT_TOOL, SELECT_TOOL, CLOSE_TOOL].map(name => ({ name }));

export function fakeBrowser({ tabs = [], paneDisplayed = false, tools = BROWSER_TOOLS } = {}) {
  const calls = [];
  let next = 0;
  const text = data => ({ content: [{ type: "text", text: JSON.stringify(data) }] });
  const api = {
    session: { id: async () => "session-a" },
    tool: {
      list: async () => tools,
      call: async input => {
        calls.push(input);
        if (input.tool === CONTEXT_TOOL) return { content: [{ type: "text", text: JSON.stringify({ browserOpen: true, tabs }) + `\nThe Browser pane is currently ${browser.paneDisplayed ? "displayed" : "hidden"}.` }] };
        if (input.tool === PREVIEW_TOOL) { const tab = { tabId: "tab-new-" + (++next), origin: new URL(input.url).origin, isActive: false }; tabs.push(tab); return text({ tabId: tab.tabId }); }
        if (input.tool === NAVIGATE_TOOL) { const tab = tabs.find(item => item.tabId === input.tabId); tab.origin = new URL(input.url).origin; return text({ ok: true }); }
        if (input.tool === SELECT_TOOL) { for (const tab of tabs) tab.isActive = tab.tabId === input.tabId; return text({ ok: true }); }
        if (input.tool === CLOSE_TOOL) { tabs.splice(tabs.findIndex(tab => tab.tabId === input.tabId), 1); return text({ ok: true }); }
        return text({});
      },
    },
  };
  const browser = { api, calls, tabs, paneDisplayed };
  return browser;
}
