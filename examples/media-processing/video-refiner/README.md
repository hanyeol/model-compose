# Video Refiner Example

This example demonstrates a workflow that detects speech regions in a video's audio track with Silero VAD, cuts only those regions out of the original video, and concatenates them into a single "speech-only" mp4. Silero VAD runs in streaming mode so each confirmed speech segment reaches the clipper without waiting for the full audio to be analysed.

## Overview

Given an input video, the workflow returns a refined version of the same video containing only the parts where somebody is talking.

The strategy is:

1. **Fan the upload stream out** with a `fan-out` job in `spool: true` mode. The upload is single-use, and the clipper starts consuming only after VAD has produced at least one segment — a plain in-memory fan-out queue would need to buffer the whole upload while VAD walks the audio. Spool mode lands the upload on a tempfile once and hands both branches a file-backed StreamResource that they can seek/read at independent paces without queue backpressure. The tempfile is deleted after both branches close.
2. **Split the audio track** out of the video with `audio-extractor` (`format: wav` — uncompressed, Silero downmixes/resamples to 16 kHz mono internally).
3. **Detect speech regions** with Silero VAD in `streaming: true` mode. Each confirmed segment is emitted as `{start_time, end_time, confidence}` the moment it is confirmed, so the clipper can start work without waiting for the full audio to be analysed.
4. **Cut and concatenate** the speech regions with `video-clipper` (`merge: true`). The clipper consumes the VAD segment stream, extracts each `[start_time, end_time]` slice from the spooled video with `ffmpeg -c copy` (no re-encoding), and concatenates every clip into a single mp4 via ffmpeg's `concat` demuxer.

### Why spooled fan-out

The upload stream is single-use — `audio-extractor` and `video-clipper` each need to read the same source bytes. Ordinary fan-out tees the upload into two in-memory branches at bounded cost, but that only works when both branches drain at roughly the same pace. Here the clipper is gated behind VAD (which walks the whole audio track before the last segment lands, and continues throughout playback), so its branch would fall arbitrarily far behind the audio branch and the fan-out queue would have to buffer the entire upload. `spool: true` swaps the in-memory queue for a tempfile: the upload is written to disk once as it arrives, both branches open the file independently, and the file is deleted after the last branch closes. The workflow stays end-to-end streaming without a separate `file-store` component and without unbounded memory growth.

### Why streaming VAD

Silero's non-streaming mode returns the full segment list only after processing the whole audio track, so the clipper couldn't start until VAD had finished. With `streaming: true` the clipper begins cutting as soon as the first segment is confirmed, and the ffmpeg concat step joins clips as they arrive — the pipeline overlaps VAD and clipping instead of running them in series.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- FFmpeg (and `ffprobe`) installed and available in your PATH — used by both `audio-extractor` and `video-clipper`
- Python dependencies for Silero VAD (installed automatically on first run):
  - `silero-vad`, `torch`, `torchaudio`, `numpy`

### Setup

1. Navigate to this example directory:
   ```bash
   cd examples/media-processing/video-refiner
   ```

2. Prepare a video file to refine. The spool tempfile is written under the OS's default temporary directory and cleaned up automatically after the workflow finishes — no example-local storage directory is used.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload the video and optionally override `threshold` / `min_speech_duration` / `min_silence_duration` / `speech_padding_time`
   - Click "Run Workflow" and download the refined video

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'input={"threshold": 0.5, "min_speech_duration": "250ms"};type=application/json' \
     -F 'video=@./recording.mp4'
   ```

   **Using CLI:**
   ```bash
   model-compose run --input '{
     "video": "./recording.mp4",
     "threshold": 0.5,
     "min_speech_duration": "250ms",
     "min_silence_duration": "500ms",
     "speech_padding_time": "100ms"
   }'
   ```

## Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | video (file) | Yes | - | Input video to refine |
| `threshold` | number | No | `0.5` | Silero speech-probability threshold (0.0 – 1.0). Higher is stricter — raise it to drop marginal speech, lower it to catch more borderline moments |
| `min_speech_duration` | duration | No | `250ms` | Discard confirmed speech chunks shorter than this |
| `min_silence_duration` | duration | No | `500ms` | Silence required between adjacent speech chunks before they are treated as separate segments |
| `speech_padding_time` | duration | No | `100ms` | Padding added to both sides of each detected segment. Prevents word-onset clipping caused by Silero's frame-level threshold |

Duration fields accept values like `"250ms"`, `"0.5s"`, or bare numeric seconds.

## Job Details

### Fan-Out (`fanout-video`)
- **Type**: `fan-out` (`spool: true`)
- **Function**: Tees the single-use upload stream into two independent branches — `for-audio` (feeds `extract` → VAD) and `for-clip` (feeds the clipper). With `spool: true` the upload is written to a tempfile once, and each branch opens the file independently; when both branches close, the tempfile is deleted. Spool avoids the queue backpressure the ordinary fan-out path would otherwise hit because the clipper branch only starts consuming after VAD has processed most of the audio.

## Component Details

### Audio Extractor (`extractor`)
- **Type**: `audio-extractor`
- **Driver**: `ffmpeg`
- **Function**: Reads its input as uncompressed WAV. Fed by the `for-audio` branch of the upstream spooled fan-out, so it consumes the upload in parallel with the clipper without landing the video on shared storage. WAV is the natural choice because Silero downmixes/resamples the input to 16 kHz mono internally.

### VAD (`vad`)
- **Type**: `model` — `voice-activity-detection` task
- **Driver**: `custom` (Silero family)
- **Function**: Runs Silero VAD on the extracted audio in `streaming: true` mode, emitting each confirmed speech segment as `{start_time, end_time, confidence}` the moment it is confirmed. The model is bundled inside the `silero-vad` pip package, so no separate download is required. `max_concurrent_count: 1` serialises access to the model instance.

### Clipper (`clipper`)
- **Type**: `video-clipper`
- **Driver**: `ffmpeg`
- **Function**: Consumes the VAD segment stream and cuts each `[start_time, end_time]` slice out of the spooled video with `ffmpeg -c copy` (no re-encoding). With `merge: true` the clipper concatenates every clip into a single mp4 via ffmpeg's `concat` demuxer, so the workflow's output is one ready-to-play refined video rather than a stream of separate clips. VAD's extra `confidence` field passes through harmlessly — the clipper only reads `start_time` / `end_time`.

## Notes and Tuning

- **Threshold**: If no clips are produced, `threshold` is likely too strict — lower it (e.g. `0.3`) or reduce `min_speech_duration`. If false positives dominate, raise `threshold` (e.g. `0.6`).
- **Padding**: A `speech_padding_time` of 100–200 ms usually prevents word-onset clipping caused by Silero's frame-level threshold. Bump it further if opening consonants are still cut.
- **Lossless clipping**: The clipper uses `-c copy`, so cut points snap to the nearest preceding keyframe. For h.264 / hevc content, individual cuts may be off by a few tens of milliseconds. Chain a `video-encoder` component after the clipper if frame-accurate cuts are required — you lose the "no re-encoding" property but gain exact boundaries.
- **Streaming VAD, concatenated output**: VAD runs in streaming mode so segment detection overlaps with clipping, but `merge: true` on the clipper forces it to wait for the full segment stream before concatenating. To yield one clip at a time as they finish instead, set `merge: false` and change the workflow output to a stream shape.
- **Spool tempfile location**: The spool writes to the OS temp directory returned by `tempfile.NamedTemporaryFile`. On systems where `TMPDIR` points at a small partition, override it (e.g. `TMPDIR=/data/tmp model-compose up`) or your uploads may exceed the partition.
- **When spool is the right choice**: `spool: true` is the right knob whenever one fan-out branch consumes far more slowly than the others (or starts consuming only after a downstream signal). If every branch drains at similar pace, the default in-memory fan-out is cheaper. Spool trades RAM for disk and adds one tempfile write per run.

## Troubleshooting

### Common Issues

1. **No clips are produced / output is empty**: `threshold` is too strict. Lower it (e.g. `0.3`) or reduce `min_speech_duration`.
2. **Words clipped at segment boundaries**: Increase `speech_padding_time` (e.g. `200ms`).
3. **`ffmpeg` not found**: Install FFmpeg and `ffprobe` and ensure both are on `PATH`.
4. **Spool tempfile write fails / "No space left on device"**: The OS temp directory is out of space. Set `TMPDIR` to a partition with room for the upload, or use `file-store` on a large disk instead of `spool: true`.
5. **"Upload stream already consumed" error**: The upload stream is single-use. This workflow uses `spool: true` on the fan-out for exactly that reason — if you customize the workflow to skip the `fanout-video` job, the second reader of `${input.video}` will fail. Either keep the spooled fan-out or route the upload through a `file-store` (or another mechanism that gives you a re-readable path) before splitting to multiple consumers.
