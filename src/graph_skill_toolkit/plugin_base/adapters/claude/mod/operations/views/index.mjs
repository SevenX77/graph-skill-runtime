import { PREVIEW_TOOL, NAVIGATE_TOOL, CONTEXT_TOOL, SELECT_TOOL, CLOSE_TOOL } from "../../host_tools/index.mjs";
import { callNative, nativeData, noWindowMessage, notSent } from "../tools/index.mjs";

export const HIDDEN_PANE_LIMIT = "Claude 的 Browser 面板隐藏时，宿主没有可调用的显示方法：标签会打开并激活，但面板保持隐藏，需要用户点击预览卡片的 Open 或 Browser 开关。";

// Own views only: a viewId names a Browser tab this page connection opened.
// User tabs never receive a handle and cannot be listed, selected or closed.
function store(state, owner) {
  let views = state.views.get(owner);
  if (!views) { views = { byId: new Map(), byKey: new Map() }; state.views.set(owner, views); }
  return views;
}

/** Read the Browser inventory, including whether the pane itself is displayed. */
async function readTabs($, tools, guard) {
  await guard();
  const result = await callNative($, tools, CONTEXT_TOOL, {});
  const noWindow = noWindowMessage(result.data);
  if (noWindow) throw Object.assign(new Error(noWindow), { outcome: "rejected", data: result.data });
  if (result.status !== "completed") throw notSent("无法读取宿主浏览器标签。", result.data);
  const data = nativeData(result.data);
  if (!Array.isArray(data?.tabs) || data.tabs.some(tab => typeof tab?.tabId !== "string" || !tab.tabId)) throw notSent("宿主没有返回可识别的标签页清单。", result.data);
  const text = JSON.stringify(result.data);
  const paneDisplayed = /pane is (currently )?displayed/i.test(text) ? true : /pane is (currently )?hidden/i.test(text) ? false : null;
  return { tabs: data.tabs, paneDisplayed, receipt: result.data };
}

function describe(view, inventory) {
  const tab = inventory.tabs.find(item => item.tabId === view.tabId);
  return { viewId: view.viewId, reuseKey: view.reuseKey, url: view.url, present: Boolean(tab), active: tab?.isActive === true, paneDisplayed: inventory.paneDisplayed };
}

async function select($, tools, guard, tabId) {
  await guard();
  const result = await callNative($, tools, SELECT_TOOL, { tabId });
  if (result.status !== "completed") throw Object.assign(new Error("宿主没有完成标签选择。"), { outcome: "unknown" });
  return result.data;
}

export async function openView($, { state, owner, request, tools, guard, args }) {
  if (args.resource.kind !== "web") return { status: "unsupported", message: "Claude 文件面板不返回视图句柄；文件请用 files.openFile。" };
  const views = store(state, owner), url = args.resource.url;
  let inventory = await readTabs($, tools, guard);
  const existing = views.byId.get(views.byKey.get(args.reuseKey));
  const receipts = [];
  let view;
  if (existing && inventory.tabs.some(tab => tab.tabId === existing.tabId)) {
    view = existing;
    if (view.url !== url) {
      await guard();
      const navigated = await callNative($, tools, NAVIGATE_TOOL, { tabId: view.tabId, url });
      receipts.push({ navigate: navigated.data });
      if (navigated.status !== "completed") return { ...navigated, evidence: { receipt: receipts } };
      view.url = url;
    }
  } else {
    await guard();
    const opened = await callNative($, tools, PREVIEW_TOOL, { url });
    receipts.push({ open: opened.data });
    if (opened.status !== "completed") return { ...opened, evidence: { receipt: receipts } };
    const tabId = nativeData(opened.data)?.tabId;
    if (typeof tabId !== "string" || !tabId) return { status: "pending", message: "宿主打开了请求，但没有返回可归属的标签标识；不要重复打开。", evidence: { receipt: receipts } };
    view = { viewId: request.id + "-view-" + (++state.nextViewId), tabId, url, reuseKey: args.reuseKey };
    views.byId.set(view.viewId, view); views.byKey.set(args.reuseKey, view.viewId);
  }
  if (args.activate) receipts.push({ select: await select($, tools, guard, view.tabId) });
  inventory = await readTabs($, tools, guard);
  const observed = describe(view, inventory);
  const visible = observed.active && observed.paneDisplayed === true;
  const limits = args.activate && observed.paneDisplayed !== true ? [HIDDEN_PANE_LIMIT] : [];
  return {
    status: !args.activate || visible ? "completed" : "accepted",
    message: !args.activate ? "视图已在后台打开。" : visible ? "视图已打开并显示在前台。" : "视图已打开并激活，但 Browser 面板没有确认显示。",
    data: { viewId: view.viewId }, evidence: { receipt: receipts, observed, limits },
  };
}

export async function listViews($, { state, owner, tools, guard }) {
  const views = store(state, owner), inventory = await readTabs($, tools, guard);
  for (const view of [...views.byId.values()]) if (!inventory.tabs.some(tab => tab.tabId === view.tabId)) { views.byId.delete(view.viewId); views.byKey.delete(view.reuseKey); }
  const listed = [...views.byId.values()].map(view => describe(view, inventory));
  return { status: "completed", message: `本页面拥有 ${listed.length} 个视图；用户自己的标签不在清单中。`, data: { scope: "own-views", views: listed },
    evidence: { receipt: inventory.receipt, observed: { paneDisplayed: inventory.paneDisplayed } } };
}

export async function closeView($, { state, owner, tools, guard, args }) {
  const views = store(state, owner), view = views.byId.get(args.viewId);
  if (!view) return { status: "rejected", message: "视图标识不属于本页面，或已关闭。" };
  await guard();
  const closed = await callNative($, tools, CLOSE_TOOL, { tabId: view.tabId });
  if (closed.status !== "completed") return { ...closed, evidence: { receipt: closed.data } };
  const inventory = await readTabs($, tools, guard);
  if (inventory.tabs.some(tab => tab.tabId === view.tabId)) return { status: "accepted", message: "关闭请求已返回，视图仍在清单中。", data: { viewId: view.viewId }, evidence: { receipt: closed.data, observed: describe(view, inventory) } };
  views.byId.delete(view.viewId); views.byKey.delete(view.reuseKey);
  return { status: "completed", message: "视图已关闭。", data: { viewId: view.viewId }, evidence: { receipt: closed.data, observed: { present: false } } };
}
