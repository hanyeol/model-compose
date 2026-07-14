# VirtualEnv Runtime (Python `venv`)

Runs the model worker in a **dedicated Python virtualenv** created by `python -m venv`.
The `requirements.txt` in this directory installs `transformers` + `torch` into
that venv only — the controller's site-packages are never touched.

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
- pip-installs `requirements.txt` into that venv,
- injects mindor into the venv's site-packages,
- spawns the worker on `.venv/classifier/bin/python`.

Subsequent `up`s reuse the venv unless mindor's version or `requirements.txt`
changes.

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
