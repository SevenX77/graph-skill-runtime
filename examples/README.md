# Repository examples

These business gSkills demonstrate the portable source format without becoming
part of the `graph-skill-runtime` wheel. Installing the runtime never registers,
copies, or globally discovers these examples.

Compile the deterministic hello-world example from the repository root:

```console
gskill compile examples/hello-world
```

Run it through the embedded executor when the optional embedded dependencies
are installed:

```console
gskill run examples/hello-world --executor embedded --inputs-json '{"name":"Developer"}'
```

An Agent Skills host can discover [`hello-world/SKILL.md`](./hello-world/SKILL.md)
as the single instruction entry. The runtime reads the adjacent
[`graph.yaml`](./hello-world/graph.yaml) as machine topology.
