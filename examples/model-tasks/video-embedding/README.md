# Video Embedding Model Task Example

This example demonstrates how to generate a single video-level embedding from an uploaded video using X-CLIP via model-compose's built-in `video-embedding` task. Frames are sampled from the video, fed through X-CLIP's vision encoder + multi-frame integration transformer, and collapsed into one 512-d vector in the same joint video-text space as X-CLIP's text encoder — enabling downstream natural-language search over the vector without re-encoding the video per query.

## Overview

This workflow provides local video embedding that:

1. **Local Video Encoder**: Runs X-CLIP locally via HuggingFace transformers without external APIs
2. **Fixed-Length Vector**: Collapses an arbitrary-length video into one 512-d L2-normalized embedding suitable for cosine similarity search
3. **Joint Video-Text Space**: The vector lives in the same space as X-CLIP's text embeddings, so text queries can retrieve videos directly
4. **Automatic Frame Handling**: The embedder resamples the extracted frames to the count X-CLIP was trained on (32 for `-patch16`, 8 for `-patch32`), so the exact extractor stride doesn't need to match

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- ffmpeg installed and available in your PATH (for frame extraction)
- Sufficient system resources to run X-CLIP (recommended: 8GB+ RAM, GPU optional but accelerates inference)
- Python environment with `transformers`, `torch`, and `accelerate` (installed automatically on first run)

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/video-embedding
   ```

2. No additional environment configuration required — the X-CLIP checkpoint is downloaded from HuggingFace on first run.

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
     -F 'input={"video": "@clip", "frame_interval": 15}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload a `video` file
   - Adjust `frame_interval` / `max_frame_count` if desired
   - Click the "Run Workflow" button

   **Using CLI:**
   ```bash
   model-compose run --input '{"video": "/path/to/video.mp4", "frame_interval": 15}'
   ```

## Component Details

### Frame Extractor Component
- **Type**: `video-frame-extractor`
- **Driver**: `ffmpeg`
- **Purpose**: Sample frames from the input video at a fixed cadence and pass them as a materialized list to the embedder
- **Key knobs**: `frame_interval` (stride; 1 = every frame, 15 = every 15th frame) and `max_frame_count` (cap on the extracted list, useful for long videos)
- **Not streaming**: X-CLIP encodes all frames together in one forward pass, so the embedder needs the full list before it can run.

### Video Embedding Model Component
- **Type**: Model component with `video-embedding` task
- **Driver**: `huggingface`
- **Architecture**: `xclip`
- **Model**: `microsoft/xclip-base-patch16-zero-shot`
- **Features**:
  - Runs X-CLIP's vision encoder + multi-frame integration transformer (MIT) locally
  - Uniformly resamples the extracted frame list to X-CLIP's expected count (32 for `-patch16`, 8 for `-patch32`)
  - Emits a 512-d L2-normalized float vector — cosine similarity against X-CLIP text embeddings is a dot product
  - Serial execution (`max_concurrent_count: 1`) to keep GPU memory bounded

### Model Information: X-CLIP base-patch16 (zero-shot)
- **Developer**: Microsoft
- **Architecture**: CLIP ViT-B/16 vision encoder + multi-frame integration transformer + CLIP text encoder
- **Training Frames**: 32 frames @ 224x224
- **Embedding Dimension**: 512
- **Trained On**: Kinetics-400
- **Zero-Shot Accuracy**: 65.2% on Kinetics-600, 72.0% on UCF-101, 44.6% on HMDB-51
- **License**: MIT
- **Model Card**: [microsoft/xclip-base-patch16-zero-shot](https://huggingface.co/microsoft/xclip-base-patch16-zero-shot)

## Workflow Details

### Default Workflow

**Description**: Sample frames from an uploaded video, run X-CLIP, and return a single video embedding.

#### Job Flow

```mermaid
graph TD
    Input((Input<br/>video)) --> J1

    %% Jobs
    J1((frames<br/>job)) --> C1[Frame Extractor<br/>ffmpeg]
    C1 -.-> |[image, ...]| J1

    J1 --> J2((embed<br/>job))
    J2 -.-> C2[Video Embedder<br/>X-CLIP]
    C2 -.-> |[512-d vector]| J2

    J2 --> Output((Output<br/>embedding))
```

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | video (file) | Yes | - | Input video file |
| `frame_interval` | number | No | 15 | Sample every Nth frame at extraction time. Lower = denser coverage of the source, at higher extraction cost. |
| `max_frame_count` | number | No | 64 | Cap on the extracted frame list. The embedder resamples this down to X-CLIP's training count (32), so anything ≥ that count works — bigger just wastes extraction time. |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `embedding` | number[] | 512 floating-point numbers. L2-normalized, so `dot(a, b)` equals cosine similarity. |

Example:

```json
{
  "embedding": [0.023, -0.451, 0.187, ...]
}
```

## System Requirements

### Minimum Requirements
- **RAM**: 8GB (recommended 16GB+)
- **Disk Space**: ~1GB for the X-CLIP checkpoint
- **CPU**: Any modern x86_64 or ARM64 processor
- **GPU**: Optional (CUDA / MPS) — significantly speeds up inference
- **Internet**: Required for the one-time model download

### Performance Notes
- First run downloads the X-CLIP checkpoint (~400MB) and initializes transformers — subsequent runs are much faster
- Inference cost is dominated by the 32-frame ViT-B/16 forward pass — a few hundred ms on a mid-range GPU, a few seconds on CPU
- Frame extraction cost scales with `frame_interval` — lowering it (denser sampling) is only useful up to `max_frame_count`

## Customization

### Faster Model (Fewer Frames)

Switch to the 8-frame `-patch32` variant for ~4x faster inference at a small accuracy cost:

```yaml
- id: video-embedder
  type: model
  task: video-embedding
  driver: huggingface
  architecture: xclip
  model: microsoft/xclip-base-patch32
```

The embedder reads the model's expected frame count from its config, so no other change is needed.

### Custom X-CLIP Checkpoint

Any X-CLIP-family checkpoint on HuggingFace works — just swap the `model:` field. Set `architecture: auto` if you're loading a non-X-CLIP video encoder that also exposes `get_video_features`.

### Denser Sampling for Short Videos

If your videos are shorter than `frame_interval × 32`, lower `frame_interval` (or drop `max_frame_count`) so ffmpeg produces at least 32 frames — the embedder will then have real frames for every X-CLIP input slot instead of duplicating the last one.

## Integration Examples

### With Vector Stores (Indexing)

Embed each video once, store the vector, and search later:

```yaml
workflows:
  - id: index-video
    jobs:
      - id: frames
        component: frame-extractor
        input:
          video: ${input.video as video}

      - id: embed
        component: video-embedder
        depends_on: [ frames ]
        input:
          frames: ${jobs.frames.output}

      - id: store
        component: vector-store
        depends_on: [ embed ]
        input:
          vector: ${jobs.embed.output}
          metadata:
            video_id: ${input.video_id}
            title: ${input.title}
```

### With Text Search (Retrieval)

Search indexed videos by natural language. Because X-CLIP shares its embedding space with its own text encoder, use the same X-CLIP checkpoint on the text side:

```yaml
workflows:
  - id: search-videos
    jobs:
      - id: embed-query
        component: xclip-text-embedder
        input:
          text: ${input.query}

      - id: search
        component: vector-store
        depends_on: [ embed-query ]
        input:
          action: search
          vector: ${jobs.embed-query.output}
          top_k: 10
```

> **Note**: X-CLIP's text branch is trained jointly with the video branch, so text queries must be embedded with the same X-CLIP model — a generic sentence-transformers embedding will not match the video vector space.

## Troubleshooting

### Common Issues

1. **Out of memory during inference**: Drop to the `-patch32` variant, or move to CPU by setting `device: cpu` on the model component.
2. **Very short video, all-duplicate embedding**: If the source has fewer than 32 frames total, the embedder duplicates the last frame to fill the input tensor. Lower `frame_interval` or accept the degraded fidelity.
3. **Model download fails**: Check internet connectivity and HuggingFace availability; the first run pulls ~400MB.
4. **Text queries don't match**: You're probably using a non-X-CLIP text encoder. Text and video embeddings only align when both come from the same X-CLIP checkpoint.

### Performance Optimization

- **GPU**: Set `device: cuda` (NVIDIA) or `device: mps` (Apple Silicon) on the model component for order-of-magnitude speedup over CPU
- **Smaller model**: `-patch32` (8 frames) is ~4x faster than `-patch16` (32 frames) with modest accuracy loss on general action recognition
- **Batch multiple videos**: Point `frames:` at a list-of-lists to embed several videos in one forward pass (`batch_size` controls how many share a GPU stream)

## Related Examples

- `text-embedding`: Generate embeddings from text (use with a matching X-CLIP checkpoint for cross-modal search)
- `image-embedding`: Single-image variant using CLIP / SigLIP / DINOv2
- `face-tracking`: Per-person time segments in a video — orthogonal signal you can index alongside video embeddings
