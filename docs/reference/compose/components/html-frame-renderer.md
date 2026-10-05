# HTML Frame Renderer Component

The HTML frame renderer component drives an HTML/CSS/JavaScript page as a time-based animation and captures each frame as a PIL image. The animation length is specified by the action's `duration` field; the page implements a small contract — a top-level `window.render(t)` function and a `window.__renderer.ready` signal. The engine samples `round(duration * frame_rate)` evenly spaced timestamps from `0` to `(frame_count - 1) / frame_rate`, calling `render(t)` and screenshotting after each step. The sampled range sits one frame short of `duration` so the encoded video's length matches `duration` exactly. Frames stream out one at a time (or collected into a list), ready to feed into `video-encoder` or any other frame-consuming component.

## Basic Configuration

```yaml
component:
  type: html-frame-renderer
  driver: playwright
  headless: true
  action:
    html: ./animation.html
    duration: 5s
    frame_rate: 30
    width: 1280
    height: 720
    props:
      title: ${input.title}
    streaming: true
    output: ${result[].image}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `html-frame-renderer` |
| `driver` | string | `playwright` | Rendering backend. Currently: `playwright` |
| `headless` | boolean | `true` | Run the browser without a visible window |
| `actions` | array | `[]` | List of render actions |

### Action Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `html` | string \| array | **required** | HTML source: http(s) URL, file path, directory containing `index.html`, or inline HTML |
| `duration` | string | **required** | Animation length (e.g. `5s`, `1m30s`). Exposed to the page as `window.__renderer.duration` |
| `props` | object \| array \| string | `null` | Data injected into `window.__renderer.props` before the page loads |
| `frame_rate` | integer \| float | `30` | Output frame rate in frames per second |
| `width` | integer | `1920` | Rendering viewport width in CSS pixels |
| `height` | integer | `1080` | Rendering viewport height in CSS pixels |
| `format` | string | `jpeg` | Image format of the captured frames (`jpeg` or `png`) |
| `quality` | integer | `null` | JPEG quality from 0 to 100; applies only when `format` is `jpeg` |
| `transparent` | boolean | `false` | Capture the viewport with a transparent background. Requires `format: png`; the page must leave `html` and `body` backgrounds unset (default stylesheets paint white) |
| `ready_timeout` | string | `60s` | Maximum time to wait for the page to set `window.__renderer.ready = true` after it loads |
| `render_timeout` | string | `10s` | Maximum time to wait for each frame's `rendered()` call |
| `worker_count` | integer | `1` | Number of pages that render frames in parallel. Each worker owns one page; frames are pulled off a shared queue and yielded back in monotonic order |
| `filename_format` | string | `null` | Per-frame filename pattern (e.g. `frame-%04d.png`); when set, each frame includes a `filename` key |
| `batch_size` | integer | `null` | Number of input HTMLs processed per batch when `html` is a list or stream |
| `streaming` | boolean | `false` | Emit frames incrementally as they are rendered instead of collecting them into a list |
| `output` | string | `null` | Output template applied to the collected/streamed result |

## Page Contract

The rendered page must define a top-level `window.render(t)` and set `window.__renderer.ready` to `true` when it's prepared to capture:

| Property | Type | Description |
|----------|------|-------------|
| `window.render(t)` | function | Advance the page to time `t` (seconds from 0). Must render synchronously, or call `window.__renderer.rendered(t)` when the frame is painted |
| `window.__renderer.ready` | boolean | Flip to `true` once the page is fully prepared to render frames. The driver blocks on this before the first `render(t)` call. Owning this signal lets the page gate on its own async setup — webfonts, images, textures, WebGL scene load — without the driver having to guess |
| `window.__renderer.duration` *(injected)* | number | Total animation length in seconds, from the action's `duration` field. Read-only — set by the driver before any page script runs. Useful for `t / duration` progress calculations |
| `window.__renderer.rendered(t)` *(injected)* | function | Signal that the frame for time `t` is fully painted. Provided by the engine; call this from `render()` to enable the pipelined capture path |
| `window.__renderer.props` *(injected)* | any | Read-only value of the action's `props` field, populated before any page script runs |

Minimal example:

```html
<canvas id="viz" width="1280" height="720"></canvas>
<script>
  const ctx = document.getElementById("viz").getContext("2d");
  const duration = window.__renderer.duration;  // from the action's `duration:` field

  function drawFrame(t) {
    // paint frame for time t; e.g. use t / duration for progress...
  }

  window.render = (t) => {
    drawFrame(t);
    window.__renderer.rendered(t);  // enables pipelined capture; safe to omit
  };
  window.__renderer.ready = true;    // declare "ready for capture"
</script>
```

If the page needs to await async setup first:

```html
<script>
  // ...define render, duration as above...

  (async () => {
    await document.fonts.ready;      // webfonts
    await loadTextures();             // images / three.js assets
    window.__renderer.ready = true;
  })();
</script>
```

If `render()` does not call `rendered()`, the engine automatically falls back after `render_timeout` to a sequential path that awaits each `render()` before screenshotting. The output is identical; only throughput differs.

## Supported Drivers

### Playwright

Chromium-backed rendering through Playwright's async API. One browser process is shared across all render actions of the component; each action opens `worker_count` fresh pages and closes them when done. `render` and `screenshot` are pipelined using Playwright's `expose_binding` — each page pushes a "frame painted" signal that the engine uses to trigger the CDP screenshot, overlapping render RPC with capture.

```yaml
component:
  type: html-frame-renderer
  driver: playwright
  headless: true
  action:
    html: ./animation.html
    frame_rate: 30
    width: 1280
    height: 720
```

**Auto-installed dependency:** `playwright` (plus a browser install via `playwright install chromium`)

## HTML Source Resolution

The `html` field accepts several forms, resolved in this order:

1. `http(s)://` URL — used as-is.
2. Existing directory path — resolved to `<dir>/index.html`.
3. Existing file path — served via a `file://` URL.
4. Anything else — written to a temporary file and served via `file://`. Use this for inline HTML.

Resolved sources are cached per action, so the same `html` value is not re-read across render calls.

## Output Format

Each rendered frame is a dictionary:

```python
{
  "number":    1,               # 1-based frame index
  "image":     <PIL.Image>,     # RGB screenshot of the viewport
  "timestamp": 0.0,             # seconds from 0
  "filename":  "frame-0001.png" # only present when filename_format is set
}
```

### Streaming vs Collecting

- `streaming: false` (default) — the action returns a list of frame dicts once the full animation is rendered.
- `streaming: true` — the action returns an async iterator of frame dicts. Downstream components can consume frames as they are produced, avoiding buffering the entire animation in memory.

### Output Fields

| Field | Type | Description |
|-------|------|-------------|
| `number` | integer | 1-based frame index within this render call |
| `image` | PIL.Image | RGB screenshot of the viewport at the given `timestamp` |
| `timestamp` | float | Time in seconds passed to `render(t)` for this frame |
| `filename` | string | Frame filename produced by `filename_format`; omitted when `filename_format` is unset |

## Integration with Workflows

### HTML Animation to Video

Render a self-contained HTML animation and encode the frames into a video file.

```yaml
workflows:
  - id: html-to-video
    jobs:
      - id: render
        component: renderer
        input:
          title: ${input.title}
          frame_rate: ${input.frame_rate}
        output:
          frames: ${output}

      - id: encode
        component: encoder
        input:
          frames: ${jobs.render.output.frames}
          frame_rate: ${input.frame_rate}
        depends_on: [render]

components:
  - id: renderer
    type: html-frame-renderer
    driver: playwright
    action:
      html: ./animation.html
      duration: 5s
      frame_rate: ${input.frame_rate}
      width: 1280
      height: 720
      props:
        title: ${input.title}
      streaming: true
      output: ${result[].image}

  - id: encoder
    type: video-encoder
    action:
      frames: ${input.frames}
      frame_rate: ${input.frame_rate}
      output: ./out.mp4
```

### Audio-Driven Visualization

Extract per-frame audio features, feed them to an HTML visualizer, and encode the result. Because `props` accepts arbitrary JSON, precomputed feature arrays can be handed straight to the page. The visualizer's `duration` can be fed from the extractor's output so the render length automatically matches the audio.

```yaml
components:
  - id: features
    type: audio-feature-extractor
    action:
      audio: ${input.audio}
      feature: spectrum
      frame_rate: ${input.frame_rate}

  - id: renderer
    type: html-frame-renderer
    driver: playwright
    action:
      html: ./animation.html
      duration: ${input.duration}
      frame_rate: ${input.frame_rate}
      width: 1280
      height: 720
      props:
        spectrum: ${input.spectrum}
      streaming: true
      output: ${result[].image}
```

## Best Practices

1. **Drive `duration` from the workflow, not hard-coded in the page**: the action's `duration` field is the single source of truth, and the engine exposes it to the page as `window.__renderer.duration`. This lets other jobs feed the length in (e.g. `duration: ${jobs.features.output.duration}s` from an audio extractor) without the page having to agree on the number.
2. **Call `window.__renderer.rendered(t)` after each render**: this unlocks the pipelined capture path. If your rendering is synchronous, add the call at the end of `render()`. If you use `requestAnimationFrame`, call it inside the rAF callback.
3. **Prefer `streaming: true` for long animations**: the encoder can consume frames as they are produced without holding the entire animation in memory.
4. **Use `props` to pass precomputed data**: heavy per-frame data (spectrum bins, motion paths, subtitles) should be computed once and injected via `props` rather than fetched from within the page.
5. **Match viewport to output resolution**: `width` × `height` is what gets screenshotted. Set both to the target video resolution to avoid downstream rescaling.
6. **Keep `render(t)` deterministic**: given the same `t`, the frame must look the same. Do not rely on wall-clock time, `Math.random()` without a seed, or animation state that carries across frames.
7. **For transparent output, leave `html` and `body` backgrounds unset**: `transparent: true` passes `omit_background` to the browser, but it only takes effect when the page itself does not paint a background. Encode the result with an alpha-capable codec (e.g. VP9 in webm) to preserve the alpha channel.
8. **Gate async setup on `window.__renderer.ready`**: the driver blocks on the ready flag before the first `render(t)`, so the page is the right place to await webfonts (`document.fonts.ready`), images, textures, WebGL scene load, or any other prerequisite. Keeping ownership on the page means the driver never has to guess what "ready" means for a given animation. If the page never flips the flag, the render fails after `ready_timeout`.
9. **Scale with `worker_count` when `render(t)` is heavy**: each worker is a separate page, so `worker_count: 4` runs four `render(t)` calls in parallel against the same Chromium process. Pays off most for scenes that spend milliseconds per frame on compositing or WebGL work; adds little for lightweight canvas animations where the bottleneck is already the screenshot/encoder pipeline. Each worker repeats the page's setup (fonts, textures, scene load), so very expensive setups amortize worse with more workers.
