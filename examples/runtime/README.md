# Runtime Examples

Each example demonstrates a different `runtime.type` supported by model-compose.
The runtime determines *where* and *how* a component's worker actually executes:

| Runtime           | Isolation                  | Use when                                                                 |
|-------------------|----------------------------|--------------------------------------------------------------------------|
| `embedded`        | none (same process)        | Fastest path; component runs in the controller process itself.           |
| `process`         | separate OS process        | Isolate a heavy model / crashing native lib from the controller.         |
| `virtualenv`      | dedicated Python venv      | Pin conflicting dependency versions per component.                       |
| `docker`          | container                  | Bring your own image, or run under a locked runtime + system deps.       |
| `apple-container` | container (macOS-native)   | Same as Docker but via Apple's `container` CLI on macOS.                 |

## Examples

- [`embedded/`](./embedded) — Trivial in-process shell component (baseline).
- [`process/`](./process) — Local model in a subprocess (multiprocessing).
- [`virtualenv-python/`](./virtualenv-python) — venv-isolated worker using the system Python.
- [`virtualenv-pyenv/`](./virtualenv-pyenv) — venv-isolated worker on a pyenv-installed Python version.
- [`docker-shell/`](./docker-shell) — Shell component running inside the standard Docker runtime image.
- [`docker-model/`](./docker-model) — Local model inside the standard Docker runtime image.
- [`docker-custom-image/`](./docker-custom-image) — Bring-your-own Docker image (e.g. `nginx:alpine`) as an HTTP-server component.
- [`apple-container/`](./apple-container) — Same as `docker-shell/`, but launched via Apple's `container` CLI on macOS.

## Running

From any example directory:

```bash
model-compose up          # start the controller (foreground)
# in another shell:
model-compose run --input '{"...": "..."}'
model-compose down        # tear down
```

Container-based examples build/pull their image on first `up`. Subsequent runs
reuse the cached image unless `requirements.txt` or `runtime.image` changes.
