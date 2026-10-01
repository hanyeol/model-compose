# Motion Generation (Kimodo) Model Task Example

This example generates 3D human motion sequences from text prompts using NVIDIA's Kimodo diffusion model, running locally via model-compose's built-in model task functionality. Kimodo is a kinematic motion diffusion model trained on ~700 hours of optical motion capture data; the output is a stream of joint positions, rotation matrices, and foot-contact labels suitable for 3D animation tools or physics-based simulation.

## Overview

This example exposes a single `generate` workflow that converts a natural-language prompt into a motion sequence returned as an NPZ file.

The response payload contains, among others:

- `posed_joints` — joint positions in world space, shape `[T, J, 3]`
- `global_rot_mats` / `local_rot_mats` — per-joint rotation matrices, shape `[T, J, 3, 3]`
- `foot_contacts` — binary labels for left heel, left toe, right heel, right toe, shape `[T, 4]`
- `root_positions`, `smooth_root_pos`, `global_root_heading`
- `fps` — frame rate the model generated at

`T` is the number of frames and `J` the number of joints for the chosen skeleton.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- **NVIDIA GPU strongly recommended**. Kimodo was tested on RTX 3090 / 4090 / A100; see [System Requirements](#system-requirements) below for the Mac / CPU situation.
- Internet access on first run (checkpoint and text encoder are pulled from Hugging Face)
- ~20–30 GB of disk space (Kimodo checkpoint + the LLM2Vec-Llama-3-8B text encoder weights)

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/motion-generation-kimodo
   ```

2. No additional environment configuration required — Kimodo and its PyTorch dependencies are installed automatically on first startup.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Generate a motion:**

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "prompt": "a person walks forward, then waves with the right hand",
         "duration": 6.0,
         "diffusion_steps": 20,
         "seed": 42
       }
     }' \
     --output motion.npz
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Enter a motion prompt and adjust duration / diffusion steps
   - Click "Run Workflow" and download the resulting NPZ

   **Using CLI:**
   ```bash
   model-compose run generate --input '{"prompt": "a person jumps and lands"}' --output motion.npz
   ```

3. **Inspect or visualize the NPZ** with any tool that can load NumPy archives — e.g. load it into Blender via an SMPL / SOMA importer, feed G1-skeleton outputs to MuJoCo, or hand SMPL-X outputs to downstream retargeting pipelines.

## Component Details

### Kimodo Motion Generation Component
- **Type**: Model component with `motion-generation` task
- **Driver / Family**: `custom` / `kimodo`
- **Preset**: `Kimodo-SOMA-RP-v1.1` (SOMA 77-joint skeleton, trained on 700 h of Bones Rigplay)
- **Model**: `nvidia/Kimodo-SOMA-RP-v1.1` (derived from `preset`; override with `model:` when needed)
- **Device**: `cuda` (recommended)
- **Output Format**: NPZ file (`application/x-npz`)
- **Concurrency**: 1 (single request at a time)

### Model Information: Kimodo
- **Developer**: NVIDIA Toronto AI Lab (see the [Kimodo project page](https://research.nvidia.com/labs/sil/projects/kimodo/))
- **Type**: Transformer-based motion diffusion model with DDIM sampling and classifier-free guidance
- **Available presets**:
  - `Kimodo-SOMA-RP-v1.1` *(default)* — SOMA skeleton, Bones Rigplay 1
  - `Kimodo-SOMA-SEED-v1.1` — SOMA skeleton, BONES-SEED subset
  - `Kimodo-G1-RP-v1` — Unitree G1 robot skeleton
  - `Kimodo-G1-SEED-v1` — Unitree G1, BONES-SEED subset
  - `Kimodo-SMPLX-RP-v1` — SMPL-X skeleton (research license)
- **CFG types**: `nocfg`, `regular`, `separated` *(default)*. `separated` lets `cfg_weight` be a two-element `[text, constraint]` pair.
- **Text encoder**: LLM2Vec-Llama-3-8B. Can be forced onto CPU to reduce VRAM — see [Reducing VRAM Usage](#reducing-vram-usage).

## Workflow Details

### "Generate" Workflow (Default)

**Description**: Generate a motion sequence from a natural-language prompt.

#### Input Parameters

| Parameter         | Type    | Required | Default | Description |
|-------------------|---------|----------|---------|-------------|
| `prompt`          | text    | Yes      | —       | Natural-language description of the desired motion |
| `duration`        | number  | No       | `4.0`   | Motion duration in seconds |
| `num_samples`     | integer | No       | `1`     | Number of motion variations to generate |
| `diffusion_steps` | integer | No       | `10`    | Number of DDIM denoising steps; more steps improves quality at the cost of speed |
| `cfg_weight`      | number  | No       | `2.0`   | Classifier-free guidance weight; a two-element list `[text, constraint]` when using `separated` CFG |
| `post_processing` | boolean | No       | `true`  | Apply foot-skate and constraint cleanup to the output |
| `seed`            | integer | No       | —       | Random seed for reproducibility |

#### Output Format

| Field | Type                   | Description |
|-------|------------------------|-------------|
| —     | `application/x-npz`    | NPZ archive with `posed_joints`, `global_rot_mats`, `local_rot_mats`, `foot_contacts`, `root_positions`, `smooth_root_pos`, `global_root_heading`, and `fps` |

## System Requirements

### Minimum Requirements

- **GPU**: NVIDIA GPU recommended. Kimodo is tested on RTX 3090 / 4090 / A100 with ~17 GB VRAM for full-GPU inference, or `<3 GB VRAM + CPU text encoder` for low-VRAM setups.
- **RAM**: 32 GB recommended (text encoder is an 8B-parameter model when forced to CPU)
- **Disk Space**: ~20–30 GB for the Kimodo checkpoint and LLM2Vec text encoder cache
- **Internet**: Required for the initial Hugging Face download only

### Apple Silicon / Mac

Kimodo is **not officially supported on macOS**. The upstream project only tests CUDA. Running on `device: cpu` is possible but very slow (minutes per generation) because the 8B-parameter text encoder has to run on CPU as well. Running on `device: mps` may fail on unsupported operators — model-compose will accept the config, but Kimodo itself may raise at inference time.

### Performance Notes

- First run downloads the Kimodo checkpoint + LLM2Vec weights from Hugging Face
- The unquantized text encoder dominates VRAM; use `text_encoder_device: cpu` to drop GPU usage below ~3 GB at the cost of slower text encoding
- Single concurrent request per component to prevent VRAM exhaustion

## Customization

### Reducing VRAM Usage

```yaml
component:
  text_encoder_device: cpu    # keep LLM2Vec on CPU; GPU usage drops to <3 GB
  text_encoder_fp32: false    # bf16 default is faster and uses less memory
```

### Switching Skeletons / Datasets

```yaml
component:
  # Model is auto-derived to nvidia/<preset>; override only if you host a mirror.
  preset: Kimodo-G1-RP-v1     # Unitree G1 robot skeleton
```

Available presets are listed under [Model Information](#model-information-kimodo).

### Tuning Classifier-Free Guidance

```yaml
component:
  cfg_type: separated         # nocfg | regular | separated

actions:
  - method: generate
    params:
      cfg_weight: [2.0, 2.0]  # [text, constraint] under `separated`
```

Use a single number for `nocfg` / `regular`, and a two-element list for `separated` (matching Kimodo's `--cfg_weight` CLI behavior).

### Multiple Variations per Prompt

```yaml
actions:
  - method: generate
    params:
      num_samples: 4
```

Kimodo returns a batched tensor; the generated NPZ carries all samples along the leading axis.

## Limitations

- **No constraints yet**: Kimodo's full-body keyframe, 2D waypoint, and end-effector constraint tracks require Python-side constraint objects and are not exposed through the DSL in this example. For now, generation is text-only. Constraint support may land as a follow-up once the DSL surface is designed.

## Related Examples

- **[image-to-3d-pixal3d](../image-to-3d-pixal3d/)**: Generate 3D meshes from a single image
- **[talking-head-sonic](../talking-head-sonic/)**: Generate talking-head video from a portrait and audio
- **[music-generation-yue2](../music-generation-yue2/)**: Local music generation with YuE2
