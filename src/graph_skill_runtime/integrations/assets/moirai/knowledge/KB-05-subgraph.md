# Reusable subgraphs

Reusable graphs are independent graph units stored in one flat registry:

```text
<skill-root>/graphs/<graph_id>/
├── graph.yaml
└── phases/
```

Each registry graph uses the same graph schema as the root, except artifact declarations are root-only. Its `graph_id` must equal its directory name and be unique across the whole bundle.

A `SUBGRAPH.md` phase names the called graph through `graph` and declares an explicit input/output boundary. `AGENT.md.subgraphs[].graph` can also declare graph call edges. These declarations, not filesystem nesting, are the topology truth.

Use a subgraph when the unit has a coherent contract and may be reused or tested independently. Keep a phase inline when extraction would merely rename one small operation without establishing a stable boundary.

The compiler resolves every call, rejects unknown ids and call cycles, and derives callers from edges. `python -m graph_skill_runtime inspect SKILL_ROOT --call-graph` projects the compiled edge set. Do not store a separate `parent` or callers list.

Current host-native and CLI Agent handoff does not support an Agent phase inside a registry graph. Such a shape fails before execution rather than falling back to a model path.
