# Artifact declaration, request, and persistence

An artifact declaration answers what the business gSkill can materialize. Its only owner is root `graph.yaml.artifacts[]`, where a stable `artifact_id` names the declaration and `stem`, `fields`, `mode`, and `format` define materialization.

An artifact request answers what one run selects. `RunPreset`, `RunInvocation`, and resolved `RunRequest` may select a declaration by `artifact_id` and optionally supply a destination. A request cannot redefine the declaration's fields, mode, format, or stem.

Before execution:

1. ensure every requested id exists in the root declarations;
2. reject duplicate requested ids;
3. confirm each declared field belongs to the root graph outputs;
4. resolve the destination under the applicable runtime and host path policy.

`run` may materialize selected artifacts after the required outputs exist. `predict` does not persist declared artifact outputs. A completed run without an artifact request is not evidence that an artifact should exist.

Treat the immutable request snapshot, checkpoint database, trace, handoff record, and artifact files as separate owned records. Relate them by run and artifact identity; do not use an artifact file as a substitute for terminal run status or golden evidence.
