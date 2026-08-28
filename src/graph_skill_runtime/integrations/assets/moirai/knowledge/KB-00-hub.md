# MoirAI knowledge router

This hub routes a question to one owning knowledge file. It is an index, not a substitute for the subject contract. An installed skill receives only the reference subset declared for that skill, so do not assume every file below is present in every skill directory.

| Question | Owning file |
| --- | --- |
| What belongs in a business gSkill bundle? | `KB-01-skill-anatomy.md` |
| How do typed fields move through a graph? | `KB-02-io-dataflow.md` |
| How should deterministic work be authored? | `KB-03-logic-actions.md` |
| How should an Agent phase be authored? | `KB-04-agent-nodes.md` |
| How are reusable graphs owned and called? | `KB-05-subgraph.md` |
| When and how should work iterate? | `KB-06-iterate.md` |
| How should complete compile diagnostics be repaired? | `KB-07-compile-diagnostics.md` |
| What does prediction prove? | `KB-08-predict.md` |
| How do runs, traces, waits, and checkpoints relate? | `KB-09-run-trace-checkpoint.md` |
| What makes an existing golden baseline pass? | `KB-10-golden.md` |
| Which configuration source owns each value? | `KB-11-runtime-config.md` |
| How is an Agent task executed and submitted? | `KB-12-agent-execution.md` |
| Which public MCP tools and CLI commands exist? | `KB-13-runtime-tools.md` |
| How are declared artifacts selected and persisted? | `KB-14-artifacts-persistence.md` |

Route design work to `moirai-clotho`, repair work to `moirai-lachesis`, and evidence-based evaluation to `moirai-atropos` when the current host exposes those installed specialist profiles. The current host retains final ownership and must give every specialist a self-contained handoff.

The runtime supplies no web/search tool. Current external research belongs to the current host, with source title and URL recorded and fact kept separate from inference.
