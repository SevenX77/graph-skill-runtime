import { SHOW_PANE_TOOL, SIDEBAR_TOOL, WINDOW_LAYOUT_TOOL, LAYOUT_TOOL } from "../../../adapters/claude/mod/host_tools/index.mjs";
import { callNative, nativeData, noWindowMessage } from "../../../adapters/claude/mod/operations/tools/index.mjs";
import { has, present } from "../../../adapters/claude/mod/operations/shared.mjs";
// The page's Claude container is the Browser pane beside the conversation. A
// display mode names how much of the host window that container gets:
//   inline      the pane is shown and the sidebar is expanded (the normal layout);
//   fullscreen  the pane is shown and the sidebar is collapsed (the widest the host offers).
// The host sets each part with its own tools and the result is read back from
// the host's layout reports, never assumed from the request.
export const MODES = Object.freeze(["inline", "fullscreen"]);
export const LAYOUT_TOOLS = Object.freeze([WINDOW_LAYOUT_TOOL, LAYOUT_TOOL]);
const PIP_LIMIT = "画中画（pip）：Browser 面板可以弹出成独立窗口，但只能由用户拖出；宿主没有给插件的接口。";
const SCREEN_LIMIT = "只在本会话显示于主窗口时生效：会话不在屏幕上、在分栏或弹出窗口里时宿主拒绝改布局，读回的模式为空。";
export const capability = tools => present([SHOW_PANE_TOOL, SIDEBAR_TOOL, ...LAYOUT_TOOLS].every(name => has(tools, name)),
  "改变页面容器（Browser 面板）在宿主窗口里的面积档位：inline 为面板显示、侧边栏展开；fullscreen 为面板显示、侧边栏折叠。设置后从宿主布局读回实际模式",
  { scope: "current-app-container", constraints: { modes: [...MODES] }, limits: [PIP_LIMIT, SCREEN_LIMIT] });

/** The container's current mode as the host's layout reports it: null when the pane is not shown on screen. */
export async function readDisplayMode($, tools, guard) {
  await guard();
  const window = await callNative($, tools, WINDOW_LAYOUT_TOOL, {});
  await guard();
  const view = await callNative($, tools, LAYOUT_TOOL, {});
  const main = nativeData(window.data), panes = nativeData(view.data);
  const sidebarCollapsed = typeof main?.main_window?.sidebar_collapsed === "boolean" ? main.main_window.sidebar_collapsed : null;
  const onScreen = typeof main?.this_session?.on_screen === "boolean" ? main.this_session.on_screen : null;
  const paneOpen = Array.isArray(panes?.open_panes) && panes.open_panes.includes("preview");
  const mode = !paneOpen || onScreen === false || sidebarCollapsed === null ? null : sidebarCollapsed ? "fullscreen" : "inline";
  return { mode, layout: { onScreen, sidebarCollapsed, paneOpen }, receipt: { window: window.data, view: view.data } };
}

export async function invoke($, { tools, args, guard }) {
  if (!MODES.includes(args.mode)) return { status: "unsupported", message: PIP_LIMIT, data: { mode: args.mode }, evidence: { sent: null, limits: [PIP_LIMIT] } };
  await guard();
  const shown = await callNative($, tools, SHOW_PANE_TOOL, { pane: "preview" });
  if (shown.status !== "completed") return { ...shown, evidence: { receipt: shown.data } };
  const noWindow = noWindowMessage(shown.data);
  if (noWindow) return { status: "rejected", message: noWindow, data: { mode: null }, evidence: { receipt: shown.data, limits: [SCREEN_LIMIT] } };
  await guard();
  const sidebar = await callNative($, tools, SIDEBAR_TOOL, { collapsed: args.mode === "fullscreen" });
  if (sidebar.status !== "completed") return { ...sidebar, evidence: { receipt: { pane: shown.data, sidebar: sidebar.data } } };
  const actual = await readDisplayMode($, tools, guard);
  const evidence = { sent: { pane: "preview", sidebarCollapsed: args.mode === "fullscreen" }, receipt: { pane: shown.data, sidebar: sidebar.data, ...actual.receipt }, limits: [PIP_LIMIT, SCREEN_LIMIT] };
  return actual.mode === args.mode
    ? { status: "completed", message: "宿主布局读回为请求的显示模式；页面容器的宽度变化在窗口中观察。", data: { mode: actual.mode, layout: actual.layout }, evidence }
    : { status: "rejected", message: "宿主布局读回的显示模式与请求不同；请求的模式未设定。", data: { mode: actual.mode, layout: actual.layout }, evidence };
}
