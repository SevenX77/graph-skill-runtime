# Iteration semantics

Iteration belongs on a graph or phase only when the collection, current item, ordering, and result combination are explicit.

`batch` maps items independently and may declare a positive concurrency limit:

```yaml
iterate:
  mode: batch
  over: records
  item_var: record
  concurrency: 4
```

`loop` processes items in order and requires an accumulator with `var`, `init`, `from`, and `merge`:

```yaml
iterate:
  mode: loop
  over: records
  item_var: record
  accumulate:
    var: accepted
    init: []
    from: result
    merge: append
```

Both modes can declare a two-integer inclusive `range`. `merge` is one of `append`, `extend`, `merge`, or `replace`.

Choose `batch` only when iterations are independent and parallel writes cannot conflict. Choose `loop` when a later item depends on accumulated prior results. Declare item-injected fields in the phase input contract and make the final accumulated value compatible with downstream schemas.

Current host-native and CLI Agent execution rejects graph-level iteration containing an Agent and Agent phase iteration. Those shapes remain Phase 3b work. Do not transform them into silent embedded execution or pretend they are supported because the portable schema can describe them.
