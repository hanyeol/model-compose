# Docker Runtime (standard image)

Runs the worker inside a Docker container built from the **standard mindor
runtime image**, `mindor/component:<version>`. IPC travels over the docker
daemon's attach stdin/stdout stream, so this works on both Linux native and
macOS Docker Desktop with no extra setup.

```yaml
component:
  runtime:
    type: docker
    # no image / build → the standard image is used
```

## Prerequisites

- Docker daemon running (Docker Desktop on macOS/Windows, dockerd on Linux).

## Try it

```bash
model-compose up
model-compose run --input '{}'
# -> {"uname": "Linux <container-id> ... #1 SMP ... GNU/Linux"}
```

First `up` builds the standard image locally (a few minutes) or pulls it if
already published. Subsequent runs start the container in seconds.

## Image kinds

| Kind      | Trigger                                                     |
|-----------|-------------------------------------------------------------|
| STANDARD  | No `image:` / `build:` / project-level `requirements.txt`.  |
| DERIVED   | Project has a non-empty `requirements.txt` (adds it on top).|
| CUSTOM    | `image:` or `build:` given (see [../docker-custom-image](../docker-custom-image)). |

## When to use

- CI environments where you want the same runtime image everywhere.
- Isolating a component from host system libraries (`libc`, `libstdc++`, ...).
- Running components that require Linux-only libraries on macOS.

## Comparison

| Feature              | `virtualenv` | `docker` |
|----------------------|:-----------:|:--------:|
| System-lib isolation |      ❌     |     ✅   |
| Cross-arch/platform  |      ❌     |     ✅   |
| Startup cost         |    ~5-30s   |  ~5-30s  |
| Cold-start cost      |   1-3 min   | 1-10 min |
