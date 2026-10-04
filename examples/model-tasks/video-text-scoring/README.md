# Video-Text Scoring Model Task Example

This example shows how to score the semantic alignment between a video and one or more captions with a local X-CLIP model via model-compose's built-in `video-text-scoring` task. Two workflows cover the common pair: a scalar CLIPScore-style gate for text-to-video output and a zero-shot video classifier that ranks candidate captions.

## Overview

X-CLIP's forward conditions its text embeddings on the video it is scoring, so the scores are **not reproducible** by embedding the two sides separately through `video-embedding` + `text-embedding`. The `video-text-scoring` task calls the full X-CLIP forward and returns dense scores — cosine similarity, optional pre-softmax logits, and optional softmax probabilities.

Scoring modes are picked automatically from the input shapes:

- `pairwise` — N videos × N captions. One cosine per pair.
- `texts_to_video` — one video × K captions. Cosines across the text axis; softmax ranks the captions.
- `videos_to_text` — N videos × one caption. Cosines across the video axis; softmax ranks the videos.

Mismatched lengths raise an error.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- `ffmpeg` on your PATH (used by the frame extractor)
- Sufficient system resources for X-CLIP (recommended: 12GB+ RAM, GPU recommended for latency-sensitive gates)
- Python environment with `transformers` and `torch` (managed automatically)

### Why Score (Instead of Embed)

With CLIP (image-text), embedding both sides and taking cosine reproduces CLIPScore exactly. With X-CLIP it does **not** — the text embedding depends on which video it is scored against. So `video-text-scoring` is the only path that returns the true X-CLIP score:

- **Text-to-video quality gates** — accept or reject a generated clip based on how well it matches its prompt.
- **Zero-shot video classification** — treat labels as captions, score the video against all of them, and read the softmax as class probabilities. No training required.
- **Video retrieval ranking** — rank N candidate clips against one text query.

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/video-text-scoring
   ```

2. No additional environment configuration required — the model is downloaded and cached automatically on first run.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run workflow 1 — score video × prompt (pairwise):**

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/score-video/runs \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "video": "https://example.com/clip.mp4",
         "text": "a chef chopping vegetables in a kitchen"
       }
     }'
   ```

   **Using CLI:**
   ```bash
   model-compose run score-video --input '{
     "video": "https://example.com/clip.mp4",
     "text": "a chef chopping vegetables in a kitchen"
   }'
   ```

   Returns a single scalar cosine such as `{"cosine": 0.26}`.

3. **Run workflow 2 — zero-shot video classification:**

   ```bash
   model-compose run classify-video --input '{
     "video": "https://example.com/clip.mp4",
     "text": [
       "a cooking video",
       "a sports highlight",
       "an animated short",
       "a dance performance"
     ]
   }'
   ```

   Returns per-caption cosines plus softmax probabilities across the captions, so the highest-softmax caption is the model's zero-shot label.

   **Using Web UI:** open http://localhost:8081, pick the workflow, and enter the inputs.

## Component Details

### Video-Text Scoring Model Component

- **Type**: Model component with `video-text-scoring` task
- **Driver**: `huggingface`
- **Architecture**: `xclip` (per-video-conditioned text embeddings)
- **Model**: `microsoft/xclip-base-patch32`
- **Shared model, two actions**:
  - `score` — pairwise shape; returns scalar `cosine`
  - `rank` — texts_to_video shape; returns list `cosine` plus softmax probabilities

### Frame Sampler (Video Frame Extractor)

- **Type**: `video-frame-extractor`
- **Driver**: `ffmpeg`
- Pulls ~2 frames/sec up to 32 frames per clip. X-CLIP re-samples to its expected 8 frames internally, so over-sampling here is safe.

### Model Information: X-CLIP ViT-Base/32

- **Developer**: Microsoft
- **Backbone**: ViT-Base/32 image encoder + Multiframe Integration Transformer (MIT) + CLIP text transformer with video-conditioned prompts
- **Projection**: Shared video/text embedding space with learned logit scale
- **Training data**: Kinetics-400 / 600
- **License**: MIT

## Workflow Details

### Workflow 1 — "Score Video × Prompt (pairwise)"

Single video + single caption → scalar cosine. The typical text-to-video quality gate.

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `video` | video | Yes | One video (URL, path, or data URI) |
| `text` | text | Yes | One caption / prompt |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `cosine` | number | Cosine similarity between the video and caption. |

### Workflow 2 — "Zero-shot video classification"

Single video + list of candidate captions → ranked distribution.

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `video` | video | Yes | One video. |
| `text` | text[] | Yes | Candidate captions (treat them as class labels). |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `cosine` | number[] | One cosine per candidate caption. |
| `softmax` | number[] | Softmax probabilities across the captions; the highest-probability index is the top-ranked label. |

#### Scoring Mode Matrix

| `videos` length | `texts` length | Mode | Score shape |
|-----------------|----------------|------|-------------|
| 1 | 1 | `pairwise` | scalar cosine |
| N | N | `pairwise` | one cosine per pair |
| 1 | K (>1) | `texts_to_video` | cosine list + softmax across captions |
| N (>1) | 1 | `videos_to_text` | cosine list + softmax across videos |
| N (>1) | M (>1), N ≠ M | error | — |

## System Requirements

### Minimum Requirements

- **RAM**: 12GB (recommended 16GB+)
- **VRAM**: 4GB+ GPU strongly recommended; CPU inference is 10–20× slower than CLIP because of the Multiframe Integration Transformer
- **Disk Space**: ~600MB for the ViT-B/32 X-CLIP checkpoint
- **CPU**: Multi-core processor (4+ cores)
- **Internet**: Required for the one-time model download

### Performance Notes

- First run downloads the model (~600MB)
- Frame extraction dominates latency for short clips on CPU; use `fps` to cap it
- X-CLIP's MIT does cross-frame attention — longer clips cost more than their frame count alone implies

## Customization

### Scoring Multiple Videos Against the Same Caption

Pack several videos into one call (nested frame lists). The scorer runs one forward over the full `videos_to_text` cross matrix:

```yaml
jobs:
  - id: score
    component: scorer
    action: rank
    input:
      frames:
        - ${jobs.extract-a.output}
        - ${jobs.extract-b.output}
        - ${jobs.extract-c.output}
      text: "a cooking video"
```

The result's `cosine` and `softmax` are lists across the video axis — the highest-softmax index is the top-ranked video.

### Prompt Template for Zero-Shot Classification

As with CLIP, templating helps:

```json
{
  "video": "https://example.com/clip.mp4",
  "text": [
    "a video of cooking",
    "a video of a sports game",
    "a video of a dance performance"
  ]
}
```

### Returning the Raw Logit

X-CLIP's cosine sits in a narrow band; the pre-softmax logit (cosine × logit_scale) stretches it to a wider range for thresholding:

```yaml
params:
  return_logit: true
```

## Troubleshooting

### Common Issues

1. **Length mismatch error** — videos and texts both have >1 elements and the lengths differ. Either match them (pairwise) or set one side to a single element.
2. **Model Download Fails** — check internet connection and disk space.
3. **Softmax looks flat** — captions are too similar, or the clip is out-of-domain for X-CLIP's Kinetics pretraining. Use the "a video of {label}" template or add more differentiated candidates.
4. **Score always close to zero** — raw cosines are near-zero even for correct pairs. Compare softmax probabilities or the raw logit, not the cosine alone.
5. **ffmpeg not found** — install `ffmpeg` and ensure it is on your PATH.

### Performance Optimization

- **GPU**: Set `device: cuda:0` (or `mps` on Apple Silicon) for substantially faster inference
- **Frame budget**: Lower the extractor's `fps` and `max_frame_count` for shorter clips; the model re-samples internally anyway
- **Batch**: Pack multi-video jobs (nested frames) into one call rather than running N separate workflows

## Comparison with video-embedding + Cosine

| Feature | `video-text-scoring` | `video-embedding` + `text-embedding` |
|---------|----------------------|---------------------------------------|
| Returns | cosine (+ logit, softmax) | separate video and text vectors |
| Reproduces the model's own score | Yes | **No** (X-CLIP conditions text embeddings on the video) |
| Caches vectors | No | Yes (persist to a vector store) |
| Best for | one-shot gating, ranking, zero-shot classification | retrieval, dedup, clustering |

Pick scoring when you want the X-CLIP score itself; pick embeddings only when you need video vectors on disk for later retrieval — the retrieved vectors cannot be re-scored to the same cosine X-CLIP reports.
