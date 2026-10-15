import { CONTEXT_TOOL, SELECT_TOOL, CLOSE_TOOL } from "../../host_tools/index.mjs";
import { callNative, nativeData, notSent } from "../tools/index.mjs";

// These handles belong to one authenticated page connection. Native tab IDs
// are never accepted as caller-provided view IDs or moved across sessions.
export async function executeView($, state, owner, request, tools, guard) {
  if (request.action === "views.open") return { status: "unsupported", message: "尚未确认通用宿主视图打开接口。" };
  let store = state.views.get(owner);
  if (!store) { store = { references: new Map(), tabs: new Map() }; state.views.set(owner, store); }
  const readTabs = async () => {
    await guard();
    const result = await callNative($, tools, CONTEXT_TOOL, {});
    if (result.status !== "completed") throw notSent("无法读取宿主视图清单。");
    const data = nativeData(result.data);
    if (!Array.isArray(data?.tabs)) throw notSent("宿主没有返回可识别的标签页清单。");
    // Validate the whole native inventory before assigning page-owned handles.
    // A malformed or repeated host ID cannot become a false completed list.
    const seen = new Set();
    for (const tab of data.tabs) {
      if (!tab || typeof tab.tabId !== "string" || !tab.tabId.trim() || seen.has(tab.tabId)) {
        throw notSent("宿主返回了无效或重复的标签页标识。");
      }
      seen.add(tab.tabId);
    }
    for (const tab of data.tabs) if (!store.tabs.has(tab.tabId)) {
      const id = request.id + "-view-" + (++state.nextViewId);
      store.tabs.set(tab.tabId, id); store.references.set(id, { tabId: tab.tabId, owned: false });
    }
    return data.tabs;
  };
  const tabs = await readTabs();
  if (request.action === "views.list") return { status: "completed", message: "已读取宿主浏览器标签；独立文件面板不在此清单内。", data: { scope: "browser-tabs", views: tabs.map(tab => {
    const id = store.tabs.get(tab.tabId), ref = store.references.get(id);
    return { viewId: id, active: tab.isActive === true, origin: tab.origin ?? null, owned: ref.owned };
  }) } };
  const ref = store.references.get(request.args.viewId);
  if (!ref || !tabs.some(tab => tab.tabId === ref.tabId)) return { status: "rejected", message: "视图标识不属于当前连接或已关闭。" };
  if (request.action === "views.close") {
    if (!ref.owned) return { status: "rejected", message: "本模块未创建该视图，不能关闭用户原有页面。" };
    await guard();
    const result = await callNative($, tools, CLOSE_TOOL, { tabId: ref.tabId });
    if (result.status !== "completed") return result;
    const after = await readTabs();
    if (after.some(tab => tab.tabId === ref.tabId)) return { status: "accepted", message: "关闭请求已返回，视图仍出现在清单中。", data: { viewId: request.args.viewId } };
    store.references.delete(request.args.viewId); store.tabs.delete(ref.tabId);
    return { status: "completed", message: "视图已从宿主清单移除。", data: { viewId: request.args.viewId } };
  }
  await guard();
  const result = await callNative($, tools, SELECT_TOOL, { tabId: ref.tabId });
  if (result.status !== "completed") return result;
  const after = await readTabs(), active = after.some(tab => tab.tabId === ref.tabId && tab.isActive);
  return { status: active ? "completed" : "accepted", message: "视图激活请求已返回；实际活动状态见返回数据。", data: { viewId: request.args.viewId, active } };
}
