# Audio Spectrum Video Example

Turn an audio file (mp3, wav, ...) into an equalizer-style MP4 video with
the **original audio muxed back in**, by chaining four jobs:

1. `fan-out` (`spool: true`) tees the one-shot audio upload into two
   independent branches — one for the spectrum extractor, one for the
   final encoder. The upload is landed on a tempfile once so both
   branches can open the file at their own pace: the encoder branch
   sits idle until the spectrum → frame render pipeline finishes, which
   an ordinary in-memory fan-out queue couldn't hold. The tempfile is
   deleted after both branches close.
2. `audio-feature-extractor` reads the `for-spectrum` branch and produces
   a per-frame frequency spectrum
   (`frames[frame_count][band_count]`, values in `[0, 1]`).
3. `html-frame-renderer` opens a small HTML page that reads the spectrum
   from `window.__renderer.props.spectrum` and draws the bars for each
   frame on a canvas.
4. `video-encoder` pipes the rendered frames through ffmpeg for H.264
   encoding and muxes the `for-encode` audio branch back in as the audio
   track.

## The `window.__renderer` contract

The page exposes `duration` and `seek(t)` on `window.__renderer`. The engine
reads `duration` to decide how many frames to capture, then calls `seek(t)`
once per frame and takes a screenshot after each call.

```js
window.__renderer = window.__renderer || {};
Object.assign(window.__renderer, {
  duration: totalSeconds,
  seek(t) {
    // draw the frame at time t on the page's canvas
  },
});
```

The engine seeds `window.__renderer.props` before any page script runs from
the action's `props:` input. In this example the workflow passes the full
spectrum result:

```js
window.__renderer.props.spectrum = {
  frames: [[...], [...], ...],  // per-frame band amplitudes in [0, 1]
  fps: 30,
  band_count: 48,
  frame_count: N,
  duration: seconds,
  sample_rate: 22050,
};
```

`animation.html` picks the closest source frame for the render time `t` and
draws one hue-shifted vertical bar per band.

## Preparation

### Prerequisites

- model-compose installed
- `ffmpeg` in your `PATH`
- Playwright Chromium browser: `playwright install chromium`

### Environment

```bash
cd examples/media-processing/audio-spectrum-to-video
```

Have an audio file ready (mp3, wav, flac, ogg, opus, or aac).

## How to Run

1. **Start the service**
   ```bash
   model-compose up
   ```

2. **Trigger a render**

   Via the Gradio UI at http://localhost:8081, or via HTTP:

   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'workflow_id=render' \
     -F 'input.audio=@./song.mp3' \
     -F 'input.fps=30' \
     -F 'input.band_count=48'
   ```

The response contains a path to the produced `.mp4`.
