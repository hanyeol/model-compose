# Image-Text Scoring Model Task Example

This example shows how to score the semantic alignment between images and captions with a local CLIP model via model-compose's built-in `image-text-scoring` task. Two workflows cover the full matrix: a single-pair CLIPScore and a broadcast ranking that doubles as zero-shot classification.

## Overview

The `image-text-scoring` task runs a CLIP (or SigLIP) model's forward pass and returns dense scores — cosine similarity, optional pre-softmax logits, and optional softmax probabilities — rather than embeddings. The scoring mode is picked automatically from the input shapes:

- `pairwise` — one image × one caption (or N × N). One cosine per pair.
- `texts_to_image` — one image × many captions. One cosine per caption; softmax ranks the captions.
- `images_to_text` — many images × one caption. One cosine per image; softmax ranks the images.

Mismatched lengths (for example, 2 images × 3 captions) raise an error.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Sufficient system resources for CLIP (recommended: 8GB+ RAM, GPU optional)
- Python environment with `transformers` and `torch` (managed automatically)

### Why Score (Instead of Embed)

A bi-encoder embedding task (`image-embedding`, `text-embedding`) hands you raw vectors — you still have to pick a similarity, decide thresholds, and glue the two sides together downstream. `image-text-scoring` collapses that into one call that returns the number you actually want:

- **CLIPScore gating** — accept or reject a generated image based on how well it matches the prompt.
- **Caption ranking** — pick the best caption out of a shortlist for a single image.
- **Zero-shot classification** — treat your labels as captions, score an image against all of them, and read the softmax as class probabilities. No training required.

The task does not replace embeddings when you need a persisted vector for retrieval; it replaces the "glue code" when the final answer is a score.

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/image-text-scoring
   ```

2. No additional environment configuration required — the model is downloaded and cached automatically on first run.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run workflow 1 — CLIPScore (pairwise):**

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/clip-score/runs \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "image": "https://images.unsplash.com/photo-1543852786-1cf6624b9987",
         "text": "a photo of a cat"
       }
     }'
   ```

   **Using CLI:**
   ```bash
   model-compose run clip-score --input '{
     "image": "https://images.unsplash.com/photo-1543852786-1cf6624b9987",
     "text": "a photo of a cat"
   }'
   ```

   Returns a single scalar cosine such as `{"cosine": 0.28}`.

3. **Run workflow 2 — Rank candidates (broadcast):**

   One image × many captions (ranks the captions):
   ```bash
   model-compose run rank-candidates --input '{
     "image": "https://images.unsplash.com/photo-1543852786-1cf6624b9987",
     "text": [
       "a photo of a cat",
       "a photo of a dog",
       "a photo of a car",
       "a photo of a bowl of fruit"
     ]
   }'
   ```

   Returns a list of cosines plus softmax probabilities across the captions, so the highest-softmax caption is the model's zero-shot label.

   Many images × one caption (ranks the images) — same workflow, flip the shape:
   ```bash
   model-compose run rank-candidates --input '{
     "image": [
       "https://images.unsplash.com/photo-1543852786-1cf6624b9987",
       "https://images.unsplash.com/photo-1518717758536-85ae29035b6d",
       "https://images.unsplash.com/photo-1552053831-71594a27632d"
     ],
     "text": "a photo of a cat"
   }'
   ```

   Returns one cosine per image and a softmax across images.

   **Using Web UI:** open http://localhost:8081, pick the workflow, and enter the inputs.

## Component Details

### Image-Text Scoring Model Component

- **Type**: Model component with `image-text-scoring` task
- **Driver**: `huggingface`
- **Architecture**: `clip` (CLIP's joint image/text projection with logit-scale softmax)
- **Model**: `openai/clip-vit-base-patch32`
- **Shared model, two actions**:
  - `score` — pairwise shape; returns scalar `cosine`
  - `rank` — broadcast shape; returns list `cosine` plus softmax probabilities

### Model Information: CLIP ViT-Base/32

- **Developer**: OpenAI
- **Backbone**: ViT-Base/32 image encoder + 12-layer text transformer
- **Projection**: Shared image/text embedding space with learned logit scale
- **License**: MIT

## Workflow Details

### Workflow 1 — "CLIPScore (pairwise)"

Single image + single caption → scalar cosine. The classic CLIPScore signal.

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `image` | image | Yes | One image (URL, path, or base64) |
| `text` | text | Yes | One caption |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `cosine` | number | Cosine similarity between the image and caption (−1 to 1). |

### Workflow 2 — "Rank candidates (broadcast)"

Many-on-one-side scoring. The task automatically picks `texts_to_image` or `images_to_text` from input lengths.

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `image` | image \| image[] | Yes | One image or a list of images. |
| `text` | text \| text[] | Yes | One caption or a list of captions. Exactly one side must be length 1 for broadcast; equal-length lists trigger pairwise instead. |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `cosine` | number[] | One cosine per candidate on the "many" side. |
| `softmax` | number[] | Softmax probabilities across the "many" side; the highest-probability index is the top-ranked candidate. |

#### Scoring Mode Matrix

| `image` length | `text` length | Mode | Score shape |
|----------------|---------------|------|-------------|
| 1 | 1 | `pairwise` | scalar cosine |
| N | N | `pairwise` | one cosine per pair |
| 1 | N (>1) | `texts_to_image` | cosine list + softmax across captions |
| N (>1) | 1 | `images_to_text` | cosine list + softmax across images |
| N (>1) | M (>1), N ≠ M | error | — |

## System Requirements

### Minimum Requirements

- **RAM**: 8GB (recommended 16GB+)
- **VRAM**: Optional; 4GB+ GPU speeds up batched scoring significantly
- **Disk Space**: ~600MB for the ViT-B/32 checkpoint
- **CPU**: Multi-core processor (4+ cores recommended)
- **Internet**: Required for the one-time model download

### Performance Notes

- First run downloads the model (~600MB)
- CPU inference is fine for the pairwise workflow; batched ranking benefits from GPU
- Image preprocessing (resize to 224×224) dominates latency for small images on CPU

## Customization

### Using a Different CLIP / SigLIP Checkpoint

Swap in a larger CLIP or SigLIP checkpoint:

```yaml
components:
  - id: scorer
    type: model
    task: image-text-scoring
    driver: huggingface
    architecture: clip
    model: openai/clip-vit-large-patch14   # Higher accuracy, slower
```

```yaml
components:
  - id: scorer
    type: model
    task: image-text-scoring
    driver: huggingface
    architecture: siglip
    model: google/siglip-base-patch16-224  # SigLIP (sigmoid loss variant)
```

### Zero-Shot Classification Prompt Template

Scores improve markedly when captions follow the "a photo of a {label}" template:

```json
{
  "image": "https://example.com/animal.jpg",
  "text": [
    "a photo of a cat",
    "a photo of a dog",
    "a photo of a horse"
  ]
}
```

Short bare labels (`"cat"`, `"dog"`) work but typically give lower-contrast softmax distributions.

### Returning the Raw Logit

CLIP's cosine is on a tight range (roughly −0.1 to 0.4 for natural images); the pre-softmax logit (cosine × logit_scale) stretches the signal to roughly [−3, 30], which is easier to threshold:

```yaml
params:
  return_logit: true
```

## Troubleshooting

### Common Issues

1. **Length mismatch error** — the two input lists have different lengths and neither is 1. Either make the lengths match (pairwise) or set one side to a single element.
2. **Model Download Fails** — check internet connection and disk space.
3. **Low cosine values across the board** — CLIP cosines sit near zero even for correct pairs. Compare to softmax probabilities or the raw logit for thresholding, not the cosine alone.
4. **Softmax looks flat** — bare labels and very similar captions compress the distribution. Use the "a photo of a {label}" template, or switch to a larger checkpoint.

### Performance Optimization

- **GPU**: Set `device: cuda:0` (or `mps` on Apple Silicon) for significantly faster inference
- **Batch Size**: The huggingface driver batches scoring jobs automatically; keep candidates in one call rather than N calls
- **Model Size**: Use ViT-B/32 for latency-sensitive gates, ViT-L/14 for best accuracy

## Comparison with Image Embedding + Cosine

| Feature | `image-text-scoring` | `image-embedding` + `text-embedding` |
|---------|----------------------|---------------------------------------|
| Returns | cosine (+ logit, softmax) | separate image and text vectors |
| Downstream glue | None | manual cosine / softmax |
| Caches vectors | No | Yes (persist to vector store) |
| Best for | one-shot gating, ranking, classification | retrieval, deduplication, clustering |

Pick scoring when you need a judgment now; pick embeddings when you need vectors on disk for later retrieval.
