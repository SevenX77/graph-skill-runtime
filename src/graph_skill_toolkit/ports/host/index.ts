/** Shared page contract. Host-specific protocols and side effects belong to adapters. */
export type HostAction = "files.revealDirectory" | "files.openFile" | "composer.writeDraft" | "conversation.submitMessage" | "context.set" | "context.remove" | "tools.list" | "tools.call" | "views.open" | "views.list" | "views.activate" | "views.close" | "views.requestDisplayMode" | "skills.list" | "skills.invoke";
export type HostId = "codex" | "claude" | "unknown";
export type HostState = "new" | "connecting" | "connected" | "failed" | "disposed";
export type HostTransport = "mcp-app" | "http-bridge" | "none";

/** Connection-reported identity; confirmation is not cryptographic attestation. */
export interface HostInfo {
  readonly id: HostId;
  readonly status: "confirmed" | "unknown";
  readonly name: string | null;
  readonly version: string | null;
  readonly clientType: string | null;
  readonly sessionId: string | null;
  readonly transport: HostTransport;
  readonly identitySource: "mcp-client" | "mcp-initialize" | "claude-mod-session" | "none";
  readonly reason: string;
  readonly capabilities: HostCapabilities;
}

export interface HostEvidence {
  transport: HostTransport;
  connected: boolean;
  identity: unknown;
  capabilities: unknown;
}

/** Establishing a channel does not select an execution adapter. */
export interface HostConnection {
  connect(callbacks: { receive: (payload: unknown) => void; fail: (error: unknown) => void }): Promise<void>;
  inspect(): Promise<HostEvidence>;
  dispose(): void | Promise<void>;
}

export type HostActionArgs = Record<string, unknown>;
export interface ToolReference { name: string; server?: string; scope?: "session" | "originating-server" }
export type ViewResource = { kind: "file"; path: string; line?: number } | { kind: "web"; url: string };

export interface HostCapability {
  state: "available" | "unavailable" | "unknown";
  detail: string;
  scope?: string;
  constraints?: Record<string, unknown>;
}

export type HostCapabilities = Record<string, HostCapability>;

export type HostResultStatus = "completed" | "accepted" | "pending" | "unsupported" | "rejected" | "error";

export interface HostResult {
  status: HostResultStatus;
  message: string;
  data?: unknown;
  requestId?: string;
}

/** Internal host execution contract; consumers use the adapter factory. */
export interface HostDriver {
  invoke(action: HostAction, args: HostActionArgs): Promise<HostResult>;
  getResult?(requestId: string): Promise<HostResult>;
}

/** One page-scoped entry for host startup evidence and every host operation. */
export interface HostAdapter extends HostDriver {
  readonly hostInfo: HostInfo;
  readonly hostId: HostId;
  readonly hostName: string;
  readonly state: HostState;
  connect(callbacks: { receive: (payload: unknown) => void; fail: (error: unknown) => void }): Promise<void>;
  capabilities(): Promise<HostCapabilities>;
  readonly host: { getInfo(): Promise<HostInfo>; getCapabilities(): Promise<HostCapabilities> };
  readonly files: { revealDirectory(args: { path: string }): Promise<HostResult>; openFile(args: { path: string; line?: number }): Promise<HostResult> };
  readonly composer: { writeDraft(args: { text: string; mode: "append" | "replace" }): Promise<HostResult> };
  readonly conversation: { submitMessage(args: { text: string }): Promise<HostResult> };
  readonly context: { set(args: { key: string; content: unknown }): Promise<HostResult>; remove(args: { key: string }): Promise<HostResult> };
  readonly tools: { list(args?: { scope?: "session" | "originating-server" }): Promise<HostResult>; call(args: { tool: ToolReference; arguments: Record<string, unknown> }): Promise<HostResult> };
  readonly views: { open(args: { resource: ViewResource; reuseKey: string; activate: boolean }): Promise<HostResult>; list(): Promise<HostResult>; activate(args: { viewId: string }): Promise<HostResult>; close(args: { viewId: string }): Promise<HostResult>; requestDisplayMode(args: { mode: "inline" | "fullscreen" | "pip" }): Promise<HostResult> };
  readonly skills: { list(): Promise<HostResult>; invoke(args: { skill: string; input?: unknown }): Promise<HostResult> };
  dispose(): void | Promise<void>;
}
