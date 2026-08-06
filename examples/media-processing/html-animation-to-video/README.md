# HTML to Video (Frame Rendering) Example

Render an HTML animation to an MP4 video by chaining the `html-frame-renderer`
and `video-encoder` components.

## Overview

`html-frame-renderer` opens an HTML page in headless Chromium and asks it to
draw one frame at a time via a small page-side contract on
`window.__renderer`. The engine streams PNG bytes to `video-encoder`,
which pipes them to ffmpeg for H.264 encoding.

## The `window.__renderer` contract

The page exposes `duration` and a `seek(t)` function on `window.__renderer`:

```js
window.__renderer = window.__renderer || {};
Object.assign(window.__renderer, {
  duration: 5.0,        // total composition length in seconds — the engine
                        // reads this to decide how many frames to capture.
  seek(t) {             // called once per frame, before each screenshot
    // update the DOM / canvas / animation timeline to the state at time t
  },
});
```

The engine seeds one field before any page script runs:

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
     -d '{"workflow_id": "render", "input": {"fps": 30}}'
   ```

The response contains a path to the produced `.mp4`.
