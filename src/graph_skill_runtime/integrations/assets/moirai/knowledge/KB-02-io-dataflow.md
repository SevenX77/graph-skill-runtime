# Typed I/O and dataflow

Every graph and phase boundary uses a Draft 2020-12 JSON Schema whose top-level type is `object`. The schema's `properties` names the available fields, and `required` may name only those properties.

Data moves through one explicit blackboard contract:

1. Root graph inputs initialize the root blackboard.
2. A phase receives only the slice declared by its `io.inputs`.
3. A phase may write only keys declared by its `io.outputs`.
4. `graph.yaml.phases[].depends_on` defines which upstream phase results can be available.
5. Root outputs must be available from terminal phases marked `output: true` and must satisfy root `io.outputs`.

Example phase boundary:

```yaml
io:
  inputs:
    type: object
    required: [source]
    properties:
      source: {type: string}
  outputs:
    type: object
    required: [summary]
    properties:
      summary: {type: string}
```

For each required input, identify exactly one guaranteed source: graph input, an upstream phase output, an explicit runtime binding, or iterator injection. A field name appearing in two places is not enough; dependency reachability must make the value available.

Prefer narrow phase contracts. If two independent branches write the same key, redesign the outputs or add an explicit merge owner. `allow_sequential_overwrite` authorizes a named field only along an ancestor path; it does not resolve incomparable parallel writes.

## How the declared slice reaches an Agent phase's model

An Agent phase does not have to ask for its inputs, and its instruction body does not have to carry them. Runtime input middleware does two separate things on every model call of the phase:

1. it delivers the phase's whole declared input slice as a JSON block, on every model call — the block is handed to the model but never written back into the conversation, so each turn is given it again;
2. it renders `{key}` placeholders in the assembled system message against the same blackboard view, because the system prompt is derived at assembly time and would otherwise leave `{key}` literal.

Both mechanisms read the same slice. A `{key}` written into a phase body therefore produces a **second full copy** of a value the model already has, and that copy is paid for on every turn. Declaring two inputs that carry the same content in different shapes — a line array plus the same lines as one numbered string — multiplies the copies again. Name an input and say what it is for; never expand it into the body.

Treat schema changes as contract changes. Update producers, consumers, examples, and acceptance evidence together rather than adding an untyped catch-all object.
