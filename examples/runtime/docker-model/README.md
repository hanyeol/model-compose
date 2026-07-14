# Docker Runtime (derived image with model)

Same Docker backend as [`../docker-shell`](../docker-shell), but this directory
has a `requirements.txt` — so model-compose builds a **DERIVED image**
(`mindor/component-<project>:<version>`) on top of the standard runtime image,
with `transformers` + `torch` installed.

```yaml
component:
  runtime:
    type: docker
    volumes:
      - ./.hf-cache:/root/.cache/huggingface
```

## Try it

```bash
model-compose up
model-compose run --input '{"text": "the weather is lovely"}'
```

First `up` is slow (image build + model download). Subsequent runs are fast:
- image is cached under its `mindor.requirements-sha256` label,
- the HuggingFace cache is bind-mounted, so the model file survives container
  restarts.

## When to use

- Local models where you want dependency + system isolation *and* a stable
  runtime environment across dev machines.
- Any component that needs Linux system libs the host doesn't have.

## Notes

- Rebuilds happen automatically when `requirements.txt` changes.
- Delete `.hf-cache/` to force re-download the model.
