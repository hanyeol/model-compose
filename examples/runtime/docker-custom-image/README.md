# Docker Runtime (custom image)

Runs an off-the-shelf Docker image (`nginx:alpine`) as the container behind an
`http-server` component. Setting `image:` marks this as a **CUSTOM image** —
model-compose does no build, no derived-image layering, and no IPC handshake
(the component talks plain HTTP inside the container).

```yaml
component:
  type: http-server
  runtime:
    type: docker
    image: nginx:alpine
    ports:
      - "8090:80"
    volumes:
      - ./html:/usr/share/nginx/html:ro
```

## Try it

```bash
model-compose up
model-compose run --input '{"path": "index.html"}'
# -> {"body": "<h1>Hello from nginx</h1>\n"}

model-compose run --input '{"path": "data.json"}'
# -> {"body": "{\"message\": \"hi from JSON\"}\n"}
```

## When to use

- The component is really a plain HTTP service you're wrapping (nginx, vLLM,
  llama-server, gradio, ...).
- You have a curated image and want to skip mindor's image layering entirely.

## What's different from `docker-shell` / `docker-model`

- No `mindor/component-*` image ever gets built.
- No IPC over docker attach — the controller reaches the component over
  regular HTTP via the `port:` field.
- `container_name:` and `ports:` are the important knobs here; everything else
  is passed through to `docker create`.
