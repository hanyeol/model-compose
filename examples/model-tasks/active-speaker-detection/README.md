# Active Speaker Detection Model Task Example

This example demonstrates how to decide which on-screen person is speaking at each moment using Light-ASD via model-compose's built-in `active-speaker-detection` task. Frames are sampled from an uploaded video at a fixed interval, run through InsightFace face tracking, and then scored against the paired audio by Light-ASD — yielding per-track speaking segments and a flat "who is speaking now" timeline.

## Overview

This workflow provides local active-speaker detection that:

1. **Local Active-Speaker Model**: Runs the Light-ASD model locally without external APIs
2. **Reuses Face Tracks**: Takes the detections produced by the paired `face-tracking` component instead of running its own face detector, so bounding boxes line up frame-for-frame with the shared frame sequence
3. **Audio-Visual Scoring**: Pairs 112x112 grayscale face crops at 25 fps with 100 Hz MFCC features from the 16 kHz mono audio of the input video
4. **Speaking Segments**: Converts the per-frame logit stream into merged `start_time / end_time / duration` segments per face track
5. **Automatic Source Setup**: On first run, clones the upstream Light-ASD repository into the mindor install root (as `lightasd/`) and downloads the Light-ASD checkpoint under `~/.cache/models/light_asd/`

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- ffmpeg installed and available in your PATH (for frame and audio extraction)
- `git` installed and available in your PATH (used on first run to clone the upstream Light-ASD source)
- Sufficient system resources to run a small torch model (recommended: 4GB+ RAM)
- Python environment with `torch`, `torchaudio`, `python_speech_features`, `insightface`, `opencv-python`, and `onnxruntime` (installed automatically on first run)
- The `antelopev2` model pack placed at `./models/antelopev2` (face-tracking uses this; see the face-tracking example for the download layout)

### Model Setup

- The Light-ASD checkpoint is fetched automatically on first run from the upstream GitHub repository and cached under `~/.cache/models/light_asd/`.
- The upstream Light-ASD source is cloned to a temporary cache (keyed by git revision) and installed as the `lightasd` package next to the running `mindor` package on first run. Subsequent runs reuse the installed copy.
- The `antelopev2` face-tracking pack is **not** auto-downloaded — see the face-tracking example README for how to place it under `./models/antelopev2`.

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/active-speaker-detection
   ```

2. Place the `antelopev2` pack under `./models/antelopev2` (same layout as the face-tracking example).

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "clip=@/path/to/video.mp4" \
     -F 'input={"video": "@clip", "frame_interval": 2, "sampled_frame_rate": 25.0}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload a `video` file
   - Adjust `frame_interval` / `sampled_frame_rate` if desired
   - Click the "Run Workflow" button

   **Using CLI:**
   ```bash
   model-compose run --input '{"video": "/path/to/video.mp4", "frame_interval": 2, "sampled_frame_rate": 25.0}'
   ```

## Component Details

### Frame Extractor Component
- **Type**: `video-frame-extractor`
- **Driver**: `ffmpeg`
- **Purpose**: Sample frames at a fixed cadence and materialize them as a list so both the tracker and the speaker detector can consume the same sequence
- **Key knob**: `frame_interval` (1 = every frame, 2 = every other frame, etc.). Pick a value so the sampled fps matches the `sampled_frame_rate` set on the model components (e.g. a 50 fps source + `frame_interval: 2` = 25 fps, which is what Light-ASD trained on)
- **Streaming**: Off. The detector needs the same materialized frame list the tracker saw so bounding boxes line up — streaming the extractor's output would consume it in the tracker before the detector can read it.

### Face Tracking Model Component
- **Type**: Model component with `face-tracking` task
- **Family**: `insightface`
- **Model**: local `./models/antelopev2` pack
- **Role in this workflow**: Produces the per-frame `detections` list that the speaker detector consumes. `return_tracks` is disabled and `return_detections` is enabled because only the frame-level bounding boxes are needed downstream.

### Active-Speaker Detection Model Component
- **Type**: Model component with `active-speaker-detection` task
- **Family**: `light-asd`
- **Preset**: `finetuning-talkset` (default) or `pretrain-ava-cvpr`
- **Features**:
  - Takes the same materialized frames as the tracker, re-crops each face track to 112x112 grayscale, and pairs it with 100 Hz MFCC features from the input video's audio
  - Smooths the per-frame speaking logits over a configurable window before thresholding, so single-frame flickers don't fragment speaking turns
  - Emits per-track speaking segments and an across-tracks `active_timeline`
  - Serial execution (`max_concurrent_count: 1`) to keep GPU memory bounded

### Model Information: Light-ASD
- **Upstream**: [Junhua-Liao/Light-ASD](https://github.com/Junhua-Liao/Light-ASD) (CVPR 2023)
- **Architecture**: Lightweight audio-visual two-stream encoder with a bidirectional GRU backend (~1M parameters)
- **Training**: AVA-ActiveSpeaker (pretrain) and TalkSet (finetune)
- **Expected inputs**: 25 fps grayscale face crops (112x112, mouth-centered) and 16 kHz mono MFCC (100 Hz, 13 coefficients)
- **License**: MIT

## Workflow Details

### Default Workflow

**Description**: Sample frames from an uploaded video, run face tracking, score each track with Light-ASD, and return per-track speaking segments.

#### Job Flow

```mermaid
graph TD
    Input((Input<br/>video)) --> J1

    %% Jobs
    J1((frames<br/>job)) --> C1[Frame Extractor<br/>ffmpeg]
    C1 -.-> |[image, image, ...]| J1

    J1 --> J2((track<br/>job))
    J1 --> J3((detect<br/>job))
    J2 -.-> C2[Face Tracker<br/>insightface]
    C2 -.-> |detections| J2
    J2 --> J3

    Input --> |audio| J3
    J3 -.-> C3[Speaker Detector<br/>light-asd]
    C3 -.-> |speakers, active_timeline| J3

    J3 --> Output((Output<br/>report))
```

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | video (file) | Yes | - | Input video file; also the source of the audio fed to Light-ASD |
| `frame_interval` | number | No | 2 | Sample every Nth frame at extraction time. Choose a value so `source_fps / frame_interval` ≈ 25 (Light-ASD is trained at 25 fps) |
| `sampled_frame_rate` | number | No | 25.0 | Frames-per-second of the *sampled* sequence, used to derive per-frame timestamps. Set to `source_fps / frame_interval` |

#### Output Format

`report` is a JSON object with:

| Field | Type | Description |
|-------|------|-------------|
| `speakers` | array | One entry per detected face track that produced any speaking frames. See below. |
| `active_timeline` | array | Flat time-ordered list of speaking segments across all tracks. Overlapping entries from different tracks are kept distinct. |
| `frame_count` | integer | Total number of sampled frames analyzed |
| `track_count` | integer | Total number of face tracks the detector scored |

Each `speakers[i]` entry:

| Field | Type | Description |
|-------|------|-------------|
| `track_id` | integer | Face-tracking cluster ID; matches the `track_id` returned by the face-tracking component so you can join the two outputs |
| `segments` | array | List of `{start_time, end_time, duration, score}`. See below. |

Each `segments[j]` entry:

| Field | Type | Description |
|-------|------|-------------|
| `start_time` | string | Segment start in `H:MM:SS.mmm` timecode |
| `end_time` | string | Segment end in `H:MM:SS.mmm` timecode |
| `duration` | string | `end_time - start_time` in `H:MM:SS.mmm` timecode |
| `score` | number | Highest smoothed Light-ASD logit across all frames in this segment |

Each `active_timeline[k]` entry:

| Field | Type | Description |
|-------|------|-------------|
| `start_time` | string | Segment start in `H:MM:SS.mmm` timecode |
| `end_time` | string | Segment end in `H:MM:SS.mmm` timecode |
| `track_id` | integer | Which face track is speaking during this entry |
| `score` | number | Smoothed logit for this segment |

Example:

```json
{
  "report": {
    "speakers": [
      {
        "track_id": 1,
        "segments": [
          { "start_time": "0:00:02.000", "end_time": "0:00:08.500", "duration": "0:00:06.500", "score": 1.42 }
        ]
      },
      {
        "track_id": 2,
        "segments": [
          { "start_time": "0:00:09.200", "end_time": "0:00:12.800", "duration": "0:00:03.600", "score": 1.08 }
        ]
      }
    ],
    "active_timeline": [
      { "start_time": "0:00:02.000", "end_time": "0:00:08.500", "track_id": 1, "score": 1.42 },
      { "start_time": "0:00:09.200", "end_time": "0:00:12.800", "track_id": 2, "score": 1.08 }
    ],
    "frame_count": 450,
    "track_count": 2
  }
}
```

## System Requirements

### Minimum Requirements
- **RAM**: 4GB (recommended 8GB+)
- **Disk Space**: ~1GB for the `antelopev2` pack and the Light-ASD source
- **CPU**: Any modern x86_64 or ARM64 processor
- **Internet**: Required for the one-time upstream source clone and the Light-ASD checkpoint download

### Performance Notes
- Light-ASD is a small model (~1M parameters) — CPU is often adequate for short clips. GPU (CUDA / MPS) is still faster on long inputs.
- The dominant cost on long videos is face tracking, not Light-ASD scoring.

## Customization

### Switching to the AVA Checkpoint

The default preset uses the `finetuning-talkset` weights (better on in-the-wild speech). Switch to `pretrain-ava-cvpr` by setting `preset` on the active-speaker-detector component to match the training distribution of your footage:

```yaml
- id: active-speaker-detector
  type: model
  task: active-speaker-detection
  driver: custom
  family: light-asd
  preset: pretrain-ava-cvpr
```

### Trimming or Padding Speaking Segments

The component's `params` block exposes the segment-shaping knobs:

```yaml
params:
  smoothing_window: 0.4s       # longer window suppresses more flicker
  threshold: 0.0               # raise to tighten; lower to catch quieter speech
  min_segment_duration: 0.3s   # drop segments shorter than this after merging
  merge_gap: 0.2s              # merge same-track segments separated by at most this gap
```

### Only the Timeline, No Per-Track Breakdown

Set `return_speakers: false` and `return_timeline: true` to drop the per-track breakdown and return just the flat time-ordered list. The detector still runs per-track scoring internally — this just hides the breakdown.

## Troubleshooting

### Common Issues

1. **No speaking segments returned**: Confirm the `audio` input actually carries speech — Light-ASD scores silence as non-speaking regardless of face motion. Also confirm `sampled_frame_rate` ≈ 25; large deviations push face crops onto frames whose MFCC windows don't align, which flattens the logits.
2. **Speakers merged into one track**: The join is on `track_id` from face-tracking — if two different people share a track, the speaker detector will attribute both of their speech to that single track. Tune `similarity_threshold` on the face-tracker in that case.
3. **Model files not found**: The Light-ASD checkpoint and upstream source are provisioned automatically. If the first run fails, confirm `git` is on `PATH` and the machine can reach `github.com` / `raw.githubusercontent.com`.
4. **`frame_rate` mismatch warning**: Verify `sampled_frame_rate` matches `source_fps / frame_interval`.

### Performance Optimization

- **GPU**: Install a CUDA-enabled `torch` (and optionally `onnxruntime-gpu` for face tracking) for faster inference.
- **Shorter frames**: Lower `sampled_frame_rate` and `frame_interval` proportionally — Light-ASD trained at 25 fps, so staying near that is important for score quality.
