/** Shared page contract. Host-specific protocols and side effects belong to adapters. */
import { HOST_ACTIONS } from "./contract.mjs";
export type HostAction = typeof HOST_ACTIONS[number];
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

export interface HostContext {
  skillRoot: string;
  graphId: string;
  nodeId?: string;
}

export interface HostActionArgs {
  skillRoot: string;
  text?: string;
  context?: HostContext;
}

export interface HostCapability {
  available: boolean;
  detail: string;
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

/** One page-scoped entry for graph delivery and every host operation. */
export interface HostAdapter extends HostDriver {
  readonly hostInfo: HostInfo;
  readonly hostId: HostId;
  readonly hostName: string;
  readonly state: HostState;
  connect(callbacks: { receive: (payload: unknown) => void; fail: (error: unknown) => void }): Promise<void>;
  capabilities(): Promise<HostCapabilities>;
  dispose(): void | Promise<void>;
}
