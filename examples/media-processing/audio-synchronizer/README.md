# Audio Synchronizer Example

This example demonstrates the `audio-synchronizer` component, which computes the time offset between multiple recordings that share the same underlying audio (multi-camera shoots, mirrored streams, or the same event captured on different devices).

The component decodes each source to mono PCM through ffmpeg and runs an FFT-based cross-correlation against the first source. It returns one `{offset, confidence}` entry per input, anchored on the latest-starting source so every reported offset is the amount to trim from the head of that source to reach the common start.

## Overview

A single workflow is exposed, backed by the `audio-synchronizer` component:

- **Align Recordings**: Compute per-recording offsets for a list of recordings, anchored on the latest-starting recording.

The component accepts video or audio sources interchangeably; any video track is dropped during decoding.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- [ffmpeg](https://ffmpeg.org/) installed and available in your PATH
- `numpy` installed (`pip install numpy`)

### Setup

Navigate to this example directory:
```bash
cd examples/media-processing/audio-synchronizer
```

Verify ffmpeg is installed:
```bash
ffmpeg -version
```

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

   The service will start:
   - API endpoint: http://localhost:8080/api
   - Web UI: http://localhost:8081

2. **Run the workflow:**

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload the recordings (audio or video)
   - Click "Run Workflow"

   **Using CLI:**
   ```bash
   model-compose run --input '{
     "sources": [
       "/path/to/camera-a.mp4",
       "/path/to/camera-b.mp4",
       "/path/to/camera-c.mp4"
     ]
   }'
   ```

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "sources=@/path/to/camera-a.mp4" \
     -F "sources=@/path/to/camera-b.mp4" \
     -F "sources=@/path/to/camera-c.mp4"
   ```

## Component Details

### Audio Synchronizer Component

- **Type**: `audio-synchronizer`
- **Driver**: `ffmpeg`
- **Purpose**: Estimate time offsets between recordings that share the same audio, using FFT cross-correlation on ffmpeg-decoded PCM.

Each source is decoded to 8 kHz mono PCM before correlation — this keeps enough bandwidth for typical speech and music transients while keeping FFT cost low. Sub-sample precision is recovered by parabolic interpolation around the correlation peak, so the reported offset is not limited to 1/8000 s.

Video and audio sources are both accepted. The decoder drops any video track, so an `.mp4` and an `.wav` recording of the same event can be aligned against each other with no pre-processing.

#### Key Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `sources` | list of media sources | Yes | - | Recordings to align; the first entry is the reference |
| `batch_size` | integer | No | all sources | Number of sources decoded in parallel |

#### Output

The action returns a list of `{offset, confidence}` entries in the same order as `sources`. Offsets are anchored on the latest-starting source: that source reports `offset = 0.0`, and every other source reports how many seconds to trim from its head to reach the common start. All offsets are therefore `>= 0` and can be applied directly by a downstream clipper.

| Field | Type | Description |
|-------|------|-------------|
| `offset` | float (seconds) | Amount to trim from the start of this source to align it with the latest-starting source. `0.0` for the anchor itself. |
| `confidence` | float 0..1 | Normalized peak correlation against the first source (used as the correlation reference). Values near 1.0 indicate a clean match; values near 0 mean the recordings likely do not share the same audio. |

Example output for three cameras (camera A is the correlation reference, but camera B turns out to start last and becomes the anchor):

```json
[
  { "offset": 1.2345, "confidence": 1.000 },
  { "offset": 0.0000, "confidence": 0.987 },
  { "offset": 1.7345, "confidence": 0.972 }
]
```

Interpretation: camera B started last, so it is used as the shared origin. Camera A must drop its first 1.2345 s and camera C must drop its first 1.7345 s to line up with camera B.

## Workflow Details

### Align Recordings

**Description**: Compute offsets for an arbitrary number of recordings, anchored on the latest-starting one.

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `sources` | list of files | Yes | Recordings to align. Order is preserved in the output; the anchor is chosen automatically |

#### Output

| Field | Type | Description |
|-------|------|-------------|
| `offsets` | list | One `{offset, confidence}` entry per source, in input order. `offset` is the seconds to trim from that source's head to reach the common start |

## Tips

- **Anchor is picked automatically**: The recording that started last becomes the shared origin (`offset = 0`); every other recording reports a non-negative head-trim amount. Input order only controls the layout of the returned list.
- **Applying offsets**: A downstream `audio-clipper` or `video-clipper` can trim `offset` seconds off the start of each source to align them on a common timeline — no sign check or padding needed.
- **First source drives correlation, not the anchor**: The first source is used as the correlation reference for the FFT step, so its confidence is always `1.0`. That does not mean it is the timeline anchor.
- **Confidence threshold**: Real-world matches usually land above ~0.5. Values below ~0.2 typically mean the two recordings do not actually share the same audio — treat those offsets as unreliable.
- **Mixed audio and video**: Video containers are decoded to audio automatically, so `.mp4`, `.mov`, `.wav`, `.mp3` files can be mixed freely in one `sources` list.
- **Length differences**: Recordings do not need to be the same length. Cross-correlation scans every lag between the two, so a 30-minute recording can be aligned against a 5-minute one from the middle of the event.
- **Clock drift**: The component reports a single offset per source and assumes the recording clocks run at the same rate. Long recordings from cheap hardware may drift by tens of milliseconds per hour — split them into shorter segments and align each segment if drift matters.
- **Silence and repetition**: If a section of the reference has no distinctive content (long silence, a repeating beat), the correlation peak can land on the wrong copy of the pattern. Prefer aligning recordings that span a moment with a sharp transient (a clap, a door slam, a spoken word).

## Troubleshooting

### Common Issues

1. **ffmpeg not found**: Ensure ffmpeg is installed and available in your `PATH`.
2. **`numpy` missing**: The synchronizer uses numpy for the FFT correlation. Install it with `pip install numpy`.
3. **All confidences are low (< 0.2)**: The recordings likely do not share the same audio, or one of them is silent. Confirm the sources by ear before trusting the offsets.
4. **One source unexpectedly reports offset = 0**: That source is the one that started last — the common-start anchor. If a different source should be the anchor, either reorder the input so it appears first (it still needs to actually start last for the numbers to make sense) or align externally.
5. **Offset is off by seconds even at high confidence**: Repeated patterns (a metronome, a looping jingle) can produce a strong secondary peak at the wrong lag. Feed a segment that contains a unique transient, or crop the sources to a stretch with more variety.
6. **Very long recordings feel slow**: Each source is decoded end-to-end before correlation. For hours-long files, pre-clip them to the region you actually need to align — a minute of shared audio is usually more than enough.
