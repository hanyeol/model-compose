# Apple Container Runtime

macOS-only backend. Uses Apple's native [`container`](https://github.com/apple/container)
CLI instead of Docker Desktop. IPC bootstraps the same way as the Docker
backend, but over `container start -a -i <name>` subprocess stdin/stdout.

```yaml
component:
  runtime:
    type: apple-container
```

## Prerequisites

- macOS with Apple's `container` CLI installed and configured.
- Apple Silicon (M-series) recommended.

Verify:

```bash
container --version
```

## Try it

```bash
model-compose up
model-compose run --input '{}'
# -> {"uname": "Linux <container-id> ... aarch64 GNU/Linux"}
```

## When to use

- macOS environments where you want native containerization without running
  Docker Desktop.
- Everything you'd use `../docker-shell` for, but on Apple Silicon without
  Docker Desktop overhead.

## Notes

- The DSL for `apple-container` mirrors `docker` closely (image, volumes,
  ports, environment, etc.), so migrating between the two is mostly a matter
  of changing `runtime.type`.
- `image:` may point to any OCI image the `container` CLI can pull.
