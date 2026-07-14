# Embedded Runtime

Baseline example: the shell component runs *in the controller process itself*.
No IPC, no subprocess spawn, no container.

```yaml
component:
  runtime:
    type: embedded
```

## Try it

```bash
model-compose up
model-compose run --input '{"name": "Alice"}'
# -> {"greeting": "hello from Alice\n"}
```

## When to use

- Development / smoke tests.
- Components that are cheap, safe, and don't need dependency isolation.
- The default for `native` controllers when no `runtime:` block is given.

## When NOT to use

- Heavy models (they'll pin the controller thread).
- Anything with fragile native dependencies that could segfault the controller.
- Components with dependency versions that conflict with the controller.

For those cases, see [`../process`](../process), [`../virtualenv-python`](../virtualenv-python), or [`../docker-model`](../docker-model).
