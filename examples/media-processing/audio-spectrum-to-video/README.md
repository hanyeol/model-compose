# Audio Spectrum Video Example

Turn an audio file (mp3, wav, ...) into an equalizer-style MP4 video with
the **original audio muxed back in**, by chaining four components:

1. `file-store` (local) writes the uploaded audio to
   `./output/audio/${context.task_id}/audio` so downstream jobs can each
   re-read it independently. The upload arrives as a one-shot stream and
   can't be tee'd; persisting it once and fanning out via URL avoids the
   problem.
2. `audio-feature-extractor` reads that file and produces a per-frame
   frequency spectrum (`frames[frame_count][band_count]`, values in `[0, 1]`).
3. `html-frame-renderer` opens a small HTML page that reads the spectrum
   from `window.__renderer.props.spectrum` and draws the bars for each
   frame on a canvas.
4. `video-encoder` pipes the PNG frames through ffmpeg for H.264 encoding
   and muxes the original audio file as the audio track.

The `${jobs.save-audio.output.url as audio;url}` reference in the extractor
and encoder inputs tells model-compose to treat the file-store's `file://`
URL as an audio resource and load it lazily inside each consumer.

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
   curl -X POST http://localhost:8080/api/render \
     -H 'Content-Type: multipart/form-data' \
     -F 'input.audio=@./song.mp3' \
     -F 'input.fps=30' \
     -F 'input.band_count=48'
   ```

The response contains a path to the produced `.mp4`.
