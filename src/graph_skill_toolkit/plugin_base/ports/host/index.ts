/** Shared page contract. Host-specific protocols and side effects belong to adapters. */
export type HostAction = "host.getInfo" | "host.getCapabilities" | "host.getContext" | "events.subscribe" | "files.openFile" | "files.revealDirectory" | "composer.writeDraft" | "conversation.submitMessage" | "context.update" | "tools.list" | "tools.call" | "skills.list" | "skills.invoke" | "views.open" | "views.list" | "views.close" | "views.requestDisplayMode";
export type HostEventType = "tool.completed" | "turn.completed" | "session.ended" | "page.teardown" | "host.contextChanged" | "context.attached";
export interface HostEvent { type: HostEventType; at: string; data?: unknown }
export type Selection = { source: "current" } | { source: "default" } | { source: "specified"; value: string };
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
  /** The session's permission mode as the host names it (`default`, `auto`, `bypassPermissions`, ...); null when unreadable. */
  readonly permissionMode: string | null;
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
  connect(callbacks: { receive: (payload: unknown) => void; fail: (error: unknown) => void; event?: (event: HostEvent) => void }): Promise<void>;
  /** Pull-based connections start relaying events on the first subscriber. */
  subscribeEvents?(event: (event: HostEvent) => void): void;
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
  /** Host limits a caller must know before relying on the effect, in plain text. */
  limits?: string[];
  /** What the session's current permission mode takes away from this operation; the operation still runs when called. */
  modeLimit?: { mode: string; effect: "blocked" | "partial"; detail: string };
}

export type HostCapabilities = Record<string, HostCapability>;

export type HostResultStatus = "completed" | "accepted" | "pending" | "unsupported" | "rejected" | "error";

/** What every call reports besides its status. */
export interface CallEvidence {
  /** The exact payload delivered to the host or operating system. */
  sent?: unknown;
  /** The raw host response. */
  receipt?: unknown;
  /** Data read back about the actual effect. */
  observed?: unknown;
  /** Host limits that applied, in plain text. */
  limits?: string[];
}

export interface HostResult {
  status: HostResultStatus;
  message: string;
  data?: unknown;
  requestId?: string;
  /** The bridge has finished this receipt, even when the effect remains unknown. */
  settled?: boolean;
  evidence?: CallEvidence;
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
  readonly host: { getInfo(): Promise<HostInfo>; getCapabilities(): Promise<HostCapabilities>; getContext(): Promise<HostResult> };
  /** Receive host notifications; returns the unsubscribe function. */
  readonly events: { subscribe(listener: (event: HostEvent) => void, types?: HostEventType[]): () => void };
  readonly files: { revealDirectory(args: { path: string }): Promise<HostResult>; openFile(args: { path: string; line?: number }): Promise<HostResult> };
  readonly composer: { writeDraft(args: { text: string; mode: "append" | "replace" }): Promise<HostResult> };
  readonly conversation: { submitMessage(args: { text: string; model?: Selection; effort?: Selection }): Promise<HostResult> };
  readonly context: { update(args: { snapshot: Record<string, unknown> }): Promise<HostResult> };
  readonly tools: { list(args?: { scope?: "session" | "originating-server" }): Promise<HostResult>; call(args: { tool: ToolReference; arguments: Record<string, unknown> }): Promise<HostResult> };
  readonly views: { open(args: { resource: ViewResource; reuseKey: string; activate: boolean }): Promise<HostResult>; list(): Promise<HostResult>; close(args: { viewId: string }): Promise<HostResult>; requestDisplayMode(args: { mode: "inline" | "fullscreen" | "pip" }): Promise<HostResult> };
  readonly skills: { list(): Promise<HostResult>; invoke(args: { skill: string; input?: unknown }): Promise<HostResult> };
  /** The plugin process's local capabilities; they never pass through the host. */
  readonly local: LocalClient;
  dispose(): void | Promise<void>;
}

export type LocalAction = "local.files.read" | "local.files.write" | "local.files.watch" | "local.system.openExternal" | "local.system.revealInFileManager";
export interface LocalFileChange { type: "local.files.changed"; at: string; data: { watchId: string; path: string; change: "created" | "modified" | "deleted"; size: number | null; mtimeMs: number | null } }
export type LocalWatchResult = HostResult & { stop(): Promise<HostResult> };

/** Operations the plugin's own Node process performs on the local machine. */
export interface LocalClient {
  readonly available: boolean;
  readonly operations: readonly LocalAction[];
  call(operation: LocalAction, args: Record<string, unknown>): Promise<HostResult>;
  readonly files: {
    read(args: { path: string; encoding?: "utf8" | "base64"; maxBytes?: number }): Promise<HostResult>;
    write(args: { path: string; content: string; encoding?: "utf8" | "base64" }): Promise<HostResult>;
    watch(args: { paths: string[] }, listener: (event: LocalFileChange) => void): Promise<LocalWatchResult>;
  };
  readonly system: { openExternal(args: { url: string }): Promise<HostResult>; revealInFileManager(args: { path: string }): Promise<HostResult> };
  dispose(): void;
}
