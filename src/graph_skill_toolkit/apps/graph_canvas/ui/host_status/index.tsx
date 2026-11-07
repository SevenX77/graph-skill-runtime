import packageInfo from "../../../../package.json" with { type: "json" };
import type { HostInfo } from "hostpane/page/types";

export function HostStatus({ info, connection }: { info: HostInfo | null; connection: string }) {
  const name = info?.status === "confirmed" ? info.id === "codex" ? "ChatGPT(Codex)" : info.name : "未知宿主";
  const label = connection === "connected" ? info?.status === "confirmed" ? "已连接" : "身份未确认" : connection === "connecting" ? "连接中" : connection === "failed" ? "连接失败" : "未连接宿主";
  return <span className={`connection ${connection}`} data-host={info?.id ?? "unknown"} title={label}>
    {name} {info?.version ?? "软件版本未知"} · 插件 {packageInfo.version}{connection !== "connected" ? ` · ${label}` : null}
  </span>;
}
