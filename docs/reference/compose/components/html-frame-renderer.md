# HTML Frame Renderer Component

The HTML frame renderer component drives an HTML/CSS/JavaScript page as a time-based animation and captures each frame as a PIL image. The page implements a small `window.__renderer` contract that exposes the animation's `duration` and a `seek(t)` function; the engine steps time from 0 to `duration` at the configured `fps`, calling `seek(t)` and screenshotting after each step. Frames stream out one at a time (or collected into a list), ready to feed into `video-encoder` or any other frame-consuming component.

## Basic Configuration

```yaml
component:
  type: html-frame-renderer
  driver: playwright
  headless: true
  action:
    html: ./animation.html
    fps: 30
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
| `props` | object \| array \| string | `null` | Data injected into `window.__renderer.props` before the page loads |
| `fps` | integer \| float | `30` | Output frame rate in frames per second |
| `width` | integer | `1920` | Rendering viewport width in CSS pixels |
| `height` | integer | `1080` | Rendering viewport height in CSS pixels |
| `ready_timeout` | string | `30s` | Maximum time to wait for `window.__renderer.seek` to appear on the page |
| `filename_format` | string | `null` | Per-frame filename pattern (e.g. `frame-%04d.png`); when set, each frame includes a `filename` key |
| `batch_size` | integer | `null` | Number of input HTMLs processed per batch when `html` is a list or stream |
| `streaming` | boolean | `false` | Emit frames incrementally as they are rendered instead of collecting them into a list |
| `output` | string | `null` | Output template applied to the collected/streamed result |

## Page Contract

The rendered page must expose a `window.__renderer` object with:

| Property | Type | Description |
|----------|------|-------------|
| `duration` | number | Total animation length in seconds. The engine reads this to compute frame count as `int(duration * fps)` |
| `seek(t)` | function | Advance the page to time `t` (seconds from 0). Must render synchronously, or call `window.__renderer.ready(t)` when the frame is painted |
| `ready(t)` *(injected)* | function | Signal that the frame for time `t` is fully painted. Provided by the engine; call this from `seek()` to enable the pipelined capture path |
| `props` *(injected)* | any | Read-only value of the action's `props` field, populated before any page script runs |

Minimal example:

```html
<canvas id="viz" width="1280" height="720"></canvas>
<script>
  const ctx = document.getElementById("viz").getContext("2d");

  function drawFrame(t) {
    // paint frame for time t...
  }

  window.__renderer = window.__renderer || {};
  Object.assign(window.__renderer, {
    duration: 5.0,
    seek(t) {
      drawFrame(t);
      window.__renderer.ready(t);  // enables pipelined capture; safe to omit
    },
  });
</script>
```

If `seek()` does not call `ready()`, the engine automatically falls back after `ready_timeout` to a sequential path that awaits each `seek()` before screenshotting. The output is identical; only throughput differs.

## Supported Drivers

### Playwright

Chromium-backed rendering through Playwright's async API. One browser process is shared across all render actions of the component; each action opens a fresh page and closes it when done. `seek` and `screenshot` are pipelined using Playwright's `expose_binding` — the page pushes a "frame painted" signal that the engine uses to trigger the CDP screenshot, overlapping seek RPC with capture.

```yaml
component:
  type: html-frame-renderer
  driver: playwright
  headless: true
  action:
    html: ./animation.html
    fps: 30
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
| `timestamp` | float | Time in seconds passed to `seek(t)` for this frame |
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
          fps: ${input.fps}
        output:
          frames: ${output}

      - id: encode
        component: encoder
        input:
          frames: ${jobs.render.output.frames}
          fps: ${input.fps}
        depends_on: [render]

components:
  - id: renderer
    type: html-frame-renderer
    driver: playwright
    action:
      html: ./animation.html
      fps: ${input.fps}
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
      fps: ${input.fps}
      output: ./out.mp4
```

### Audio-Driven Visualization

Extract per-frame audio features, feed them to an HTML visualizer, and encode the result. Because `props` accepts arbitrary JSON, precomputed feature arrays can be handed straight to the page.

```yaml
components:
  - id: features
    type: audio-feature-extractor
    action:
      audio: ${input.audio}
      feature: spectrum
      fps: ${input.fps}

  - id: renderer
    type: html-frame-renderer
    driver: playwright
    action:
      html: ./animation.html
      fps: ${input.fps}
      width: 1280
      height: 720
      props:
        spectrum: ${input.spectrum}
      streaming: true
      output: ${result[].image}
```

## Best Practices

1. **Set `duration` on the page, not in the workflow**: the engine reads `window.__renderer.duration` to determine frame count. Keeping the length inside the page keeps the animation self-describing.
2. **Call `window.__renderer.ready(t)` after each render**: this unlocks the pipelined capture path. If your rendering is synchronous, add the call at the end of `seek()`. If you use `requestAnimationFrame`, call it inside the rAF callback.
3. **Prefer `streaming: true` for long animations**: the encoder can consume frames as they are produced without holding the entire animation in memory.
4. **Use `props` to pass precomputed data**: heavy per-frame data (spectrum bins, motion paths, subtitles) should be computed once and injected via `props` rather than fetched from within the page.
5. **Match viewport to output resolution**: `width` × `height` is what gets screenshotted. Set both to the target video resolution to avoid downstream rescaling.
6. **Keep `seek(t)` deterministic**: given the same `t`, the frame must look the same. Do not rely on wall-clock time, `Math.random()` without a seed, or animation state that carries across frames.
