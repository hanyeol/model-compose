# VirtualEnv Runtime (Python `venv`)

Runs the model worker in a **dedicated Python virtualenv** created by `python -m venv`.
The model component declares the packages it needs (e.g. `transformers`, `torch`)
through its driver's setup requirements, and they are installed into that venv
only — the controller's site-packages are never touched.

```yaml
component:
  runtime:
    type: virtualenv
    driver: python
    path: .venv/classifier
```

## Try it

```bash
model-compose up
model-compose run --input '{"text": "You are a wonderful person"}'
```

First `up`:
- creates `.venv/classifier/` next to this file,
- injects the model-compose runtime into the venv's site-packages,
- pip-installs the component driver's setup requirements into that venv,
- spawns the worker on `.venv/classifier/bin/python`.

Subsequent `up`s reuse the venv unless the model-compose runtime version changes.

## What you get

- Everything `process` gives you, plus:
- Independent dependency versions per component.
- No risk of a component pulling in an incompatible `torch` and clobbering the
  controller's install.

## Comparison

| Feature                | `process` | `virtualenv-python` |
|------------------------|:---------:|:-------------------:|
| OS-level isolation     |     ✅    |          ✅         |
| Dependency isolation   |     ❌    |          ✅         |
| Python-version pinning |     ❌    |          ❌         |

For Python-version pinning, see [`../virtualenv-pyenv`](../virtualenv-pyenv).
For system-level isolation, see [`../docker-model`](../docker-model).
