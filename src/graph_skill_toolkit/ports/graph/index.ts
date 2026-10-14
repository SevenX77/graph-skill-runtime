/** One runtime compile diagnostic (`gskill.compile-diagnostic.v1`), shown verbatim. */
export interface CompileDiagnostic {
  code: string;
  severity: string;
  message: string;
  source_path?: string | null;
  line?: number | null;
  field_path?: string | null;
}

/** Local App data connection, independent of host identity and operations.
 * `receive` gets a drawable graph; `invalid` gets the runtime's diagnostics for
 * a skill that does not compile; `fail` reports read and transport failures. */
export interface GraphConnection {
  connect(callbacks: { receive: (payload: unknown) => void; invalid: (event: { skillRoot: string; diagnostics: unknown }) => void; fail: (error: unknown) => void }): void;
  selectRoot(root: string | null): void;
  dispose(): void;
}
