# Video Playback Component

The video playback component opens an OS-native window on the host machine and plays a video source through the bundled `ffplay` binary. Video renders in the window and, if present, the audio track plays through the system default output — no separate audio pipeline is needed.

Unlike media components that produce a file or stream, this one is a **sink**: it consumes a video input and returns no value. Typical uses include local preview of a generated clip, sequential playback of a queue of clips, and kiosk-style always-on video display.

## Basic Configuration

```yaml
component:
  id: player
  type: video-playback
  driver: ffplay
  action:
    video: ${input.source as video}
    window_title: My Player
    wait_for_finish: true
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `video-playback` |
| `driver` | string | `ffplay` | Playback backend; currently only `ffplay` |
| `actions` | array | `[]` | List of playback actions |

### Action Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `video` | string \| string[] | **required** | Input to play — file path, URL, bytes, stream, or variable reference. Accepts a single value, a list, or an async stream. |
| `window_title` | string | `null` | Title shown on the playback window. When unset, ffplay uses the input filename/URL. |
| `window_size` | string | `null` | Window size as `WIDTHxHEIGHT` (e.g. `1280x720`). When unset, the video's native resolution is used. |
| `fullscreen` | boolean \| string | `false` | Open the window in fullscreen mode. |
| `always_on_top` | boolean \| string | `false` | Keep the window above other windows. |
| `borderless` | boolean \| string | `false` | Draw the window without OS chrome. |
| `mute` | boolean \| string | `false` | Disable the audio track. Video continues to play. |
| `volume` | integer \| string | `100` | Startup audio volume from `0` (mute) to `100` (unchanged). Clamped to the valid range. |
| `duration` | string \| number | `null` | Maximum playback duration (e.g. `10s`, `1m30s`). When unset, plays to the end of the input. |
| `wait_for_finish` | boolean \| string | `true` | Whether the action waits for playback to finish before returning. See [Wait For Finish](#wait-for-finish). |
| `batch_size` | integer \| string | `null` | Number of inputs consumed per batch when `video` is a list or stream. Defaults to `1`, i.e. one at a time. |

## Input Cardinality

`video` decides how playback is driven:

- **Single value** — one file/URL/bytes source; plays once and returns.
- **List** — plays each entry in order. With `wait_for_finish: true` clips are sequential; with `false` they may overlap.
- **AsyncIterator / stream** — consumes items as they arrive (e.g. from `data-queue.dequeue`). Playback follows the stream and finishes when the stream is exhausted or the consumer is cancelled.

The component normalizes all three via `BatchSourceIterator`; `batch_size` controls how many items a single iteration groups together (defaults to 1 so clips remain sequential unless you opt into overlap).

## Wait For Finish

- `wait_for_finish: true` (default) — the action awaits the `ffplay` process. Cancelling the action (via `CancellationToken`) kills the process cleanly. For list/stream inputs this is what keeps clips from overlapping.
- `wait_for_finish: false` — fire-and-forget. `ffplay` is spawned in a detached task and the action returns immediately. Useful for background playback triggered from another workflow; the caller doesn't see a non-zero ffplay exit as an error.

## Input Handling

The driver inspects each `MediaSource` and picks the cheapest way to feed ffplay:

| Source shape | How ffplay reads it |
|--------------|---------------------|
| `FileStreamResource` | Path passed directly to `-i` — no spooling. |
| Streamable format (`mpegts`, `flv`, `mp3`, `wav`, …) | Streamed via `pipe:0` — no temp file. |
| Anything else (`mp4`, `mov`, unknown) | Spooled to a temp file so ffplay can seek, then cleaned up when playback ends. |

The `-autoexit` flag is always set so ffplay terminates when the input ends instead of holding the last frame open.

## Supported Drivers

### ffplay

Uses the `ffplay` binary that ships with most `ffmpeg` distributions. Video is displayed via SDL2; audio is routed to the OS default output (Core Audio on macOS, WASAPI on Windows, PulseAudio/ALSA on Linux) through ffplay's built-in audio backend.

**Requires:** `ffplay` binary on the system path. On macOS/Homebrew, `brew install ffmpeg` includes it.

**Notes:**
- ffplay always opens its own window — the OS window handle is owned by the `ffplay` process. Embedding into another application's window is not supported.
- On macOS, the window inherits normal Cocoa focus/mission-control behavior.
- On Linux, an X11 or Wayland session is required; headless environments fail with `Unable to open display`.

## Output Format

Playback is a side effect (window + speakers). The action returns `null`.

## Multiple Actions Configuration

Define multiple playback modes on the same component:

```yaml
component:
  id: player
  type: video-playback
  driver: ffplay
  actions:
    - id: windowed
      video: ${input.video}
      window_title: Preview
      window_size: "1280x720"
      wait_for_finish: true

    - id: fullscreen
      video: ${input.video}
      fullscreen: true
      always_on_top: true
      wait_for_finish: true

    - id: silent-bg
      video: ${input.video}
      mute: true
      wait_for_finish: false
```

## Integration with Workflows

### Preview a Generated Clip

```yaml
workflows:
  - id: preview
    jobs:
      - id: play
        component: player
        input:
          video: ${input.source as video}

components:
  - id: player
    type: video-playback
    action:
      video: ${input.video}
      window_title: Preview
      wait_for_finish: true
```

### Sequential Playback From a Queue

```yaml
workflows:
  - id: play-queue
    jobs:
      - id: subscribe
        component: video-queue
        action: dequeue

      - id: play
        component: player
        input:
          video: ${jobs.subscribe.output as video}
        depends_on: [ subscribe ]

components:
  - id: video-queue
    type: data-queue
    driver: memory
    max_size: 100
    actions:
      - id: enqueue
        method: enqueue
        item: ${input}
      - id: dequeue
        method: dequeue

  - id: player
    type: video-playback
    action:
      video: ${input.video}
      wait_for_finish: true
```

`wait_for_finish: true` on the player is what keeps clips from overlapping — the dequeue stream feeds one clip at a time and the next clip only starts when the previous one exits.

### Fullscreen Kiosk Loop

```yaml
components:
  - id: kiosk
    type: video-playback
    action:
      video: ${input.playlist as video}
      fullscreen: true
      always_on_top: true
      borderless: true
      mute: true
      wait_for_finish: true
```

Pair with a workflow that keeps handing a fresh list/stream of clips to the action to build a rolling display.

## Best Practices

1. **Leave `wait_for_finish: true` for anything sequential.** It's the only thing preventing overlap when the input is a list or stream. Flip it off only when you actually want fire-and-forget background playback.
2. **Don't set `window_size` unless you need a specific layout.** ffplay picks the video's native size by default, which avoids blurry scaling.
3. **Use `mute: true` instead of `volume: 0` when you never want audio.** `-an` skips the audio decoder entirely; `-volume 0` still decodes and mixes silently.
4. **Prefer file paths or streamable formats.** Non-seekable non-streamable formats (mp4/mov delivered as raw bytes) are spooled to a temp file before playback, which delays first frame. If the upstream can hand over a path (`FileStreamResource`) or MPEG-TS, use that.
5. **Cancel to stop cleanly.** Cancelling the workflow terminates the ffplay process via `CancellationToken`. Closing the window works too, but cancellation is what you want for programmatic control.
6. **Not for embedded/headless use.** ffplay always draws its own OS window and needs a graphical session. For headless preview, transcode with `video-encoder` and inspect frames with `video-frame-extractor` instead.
