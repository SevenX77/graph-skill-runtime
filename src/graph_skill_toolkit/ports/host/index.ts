/** Shared page contract. Host-specific protocols and side effects belong to adapters. */
export type HostAction =
  | "open-root" | "open-file" | "fill-prompt" | "send-prompt"
  | "update-context" | "list-tools" | "call-tool" | "request-skill";

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

export interface HostAdapter {
  hostName: string;
  rootActionLabel: string;
  connect(callbacks: { receive: (payload: unknown) => void; fail: (error: unknown) => void }): Promise<void>;
  capabilities(): Promise<HostCapabilities>;
  invoke(action: HostAction, args: HostActionArgs): Promise<HostResult>;
  getResult?(requestId: string): Promise<HostResult>;
  openRoot(root: string): Promise<string>;
  dispose(): void | Promise<void>;
}
