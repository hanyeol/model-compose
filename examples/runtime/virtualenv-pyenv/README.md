# VirtualEnv Runtime (`pyenv`)

Same as [`../virtualenv-python`](../virtualenv-python), but the venv is created
against a **specific Python version installed via pyenv**. Use when a component
needs a Python version different from the controller's.

```yaml
component:
  runtime:
    type: virtualenv
    driver: pyenv
    python: "3.11.9"
    path: .venv/py311
```

## Prerequisites

`pyenv` must be installed, and the requested version must already be present:

```bash
pyenv install 3.11.9   # one-time
```

## Try it

```bash
model-compose up
model-compose run --input '{}'
# -> {"python_version": "Python 3.11.9\n"}
```

The worker subprocess runs on `~/.pyenv/versions/3.11.9/bin/python`, regardless
of what the controller is using.

## When to use

- Component needs Python 3.9 but the controller runs Python 3.12 (or vice versa).
- Reproducing a bug against a specific interpreter build.

For pinning system-level dependencies too, containerize instead — see
[`../docker-model`](../docker-model).
