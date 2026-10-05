# HTML to Video (Frame Rendering) Example

Render an HTML animation to an MP4 video by chaining the `html-frame-renderer`
and `video-encoder` components.

## Overview

`html-frame-renderer` opens an HTML page in headless Chromium and asks it to
draw one frame at a time via a small page-side contract: a top-level
`window.render(t)` plus a `duration` on `window.__renderer`. The engine
streams PNG bytes to `video-encoder`, which pipes them to ffmpeg for H.264
encoding.

## The page contract

The page defines a top-level `window.render(t)` and flips `ready` when it's
prepared to capture. Total length comes from the action's `duration:` field
(set in `model-compose.yml`) and is injected as `window.__renderer.duration`:

```js
const duration = window.__renderer.duration;   // from action's `duration:`

window.render = (t) => {              // called once per frame, before each screenshot
  // update the DOM / canvas / animation timeline to the state at time t
};
window.__renderer.ready = true;       // declare "ready for capture" — the engine
                                      // only starts rendering after this flips.
                                      // If the page needs async setup first
                                      // (webfonts, images, textures), await
                                      // those and flip the flag afterwards.
```

The engine seeds two fields before any page script runs:

- **`duration`** — number of seconds, parsed from the action's `duration:`
  field. Read-only; useful for `t / duration` progress calculations.
- **`props`** — set from the action input `props:` (optional). Whatever
  shape the workflow passes in is what the page sees on
  `window.__renderer.props`.

This example passes a `title:` in `props` and the page (`animation.html`)
renders it as a large centered heading over a moving progress bar.

## Preparation

### Prerequisites

- model-compose installed
- `ffmpeg` in your `PATH`
- Playwright Chromium browser: `playwright install chromium`

### Environment

```bash
cd examples/media-processing/html-animation-to-video
```

## How to Run

1. **Start the service**
   ```bash
   model-compose up
   ```

2. **Trigger a render**

   Via the Gradio UI at http://localhost:8081, or via HTTP:

   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H 'Content-Type: application/json' \
     -d '{"workflow_id": "render", "input": {"frame_rate": 30}}'
   ```

The response contains a path to the produced `.mp4`.

## Parallel rendering

The renderer action accepts a `worker_count` input (default `1`). Each
worker opens its own Chromium page and pulls frame numbers off a shared
queue; results are reordered and streamed back monotonically to the
encoder. For a lightweight canvas animation like this one the gain is
modest, but for pages that spend real time in `render(t)` (WebGL scenes,
heavy compositing) it scales close to linearly up to a few workers.

```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -H 'Content-Type: application/json' \
  -d '{"workflow_id": "render", "input": {"frame_rate": 30, "worker_count": 4}}'
```
