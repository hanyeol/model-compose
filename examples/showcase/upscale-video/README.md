# Upscale Video Example

This example demonstrates a workflow that upscales every frame of a video with a super-resolution model and reassembles it — preserving the original audio track.

## Overview

Given an input video, the workflow returns a super-resolved version of the same video with the original audio track muxed back in.

The strategy is:

1. **Split the audio track** out of the input video with `audio-extractor` (preserved unchanged).
2. **Extract every frame** as a still image with `video-frame-extractor`.
3. **For each frame**, run `image-upscale` (Real-ESRGAN x4) via a `for-each` job.
4. **Encode the upscaled frames** back into a video with `video-encoder`, muxing the extracted audio into the output.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- FFmpeg installed and available in your PATH
- Python dependencies for Real-ESRGAN inference:
  ```bash
  pip install torch torchvision realesrgan
  ```
- The Real-ESRGAN weights (`RealESRGAN_x4.pth`) will be downloaded automatically from `ai-forever/Real-ESRGAN` on Hugging Face on first run.

### Setup

1. Navigate to this example directory:
   ```bash
   cd examples/showcase/upscale-video
   ```

2. Prepare a video file to upscale. Short clips are recommended — per-frame super-resolution is expensive.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload the video and optionally override `frame_rate`
   - Click "Run Workflow"

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'input={"frame_rate": 30};type=application/json' \
     -F 'video=@./video.mp4'
   ```

   **Using CLI:**
   ```bash
   model-compose run --input '{
     "video": "./video.mp4",
     "frame_rate": 30
   }'
   ```

## Component Details

### Audio Extractor (`audio-extractor`)
- **Type**: `audio-extractor`
- **Driver**: `ffmpeg`
- **Function**: Splits the audio track out of the input video into a standalone mp3 file. Used later by the encoder to mux the audio back into the upscaled video.

### Frame Extractor (`frame-extractor`)
- **Type**: `video-frame-extractor`
- **Driver**: `ffmpeg`
- **Function**: Decodes the video into a list of every frame (`frame_interval: 1`) with timestamps. `streaming: false` so the `for-each` job can iterate over a materialized list.

### Upscaler (`upscaler`)
- **Type**: `model` — `image-upscale` task
- **Driver**: `custom` (Real-ESRGAN family)
- **Model**: `RealESRGAN_x4.pth` from `ai-forever/Real-ESRGAN` on Hugging Face
- **Scale**: 4x
- **Tiling**: `tile_size: 256`, `tile_pad_size: 24`, `tile_batch_size: 4` — keeps VRAM bounded for high-resolution frames.

### Encoder (`encoder`)
- **Type**: `video-encoder`
- **Driver**: `ffmpeg`
- **Function**: Encodes the upscaled frames back into an mp4 (`libx264 @ 8M`) and muxes the extracted audio (`aac @ 192k`). `frame_rate` controls the output timing.

## Notes and Tuning

- **Cost**: Real-ESRGAN x4 on every frame is heavy. A 10-second 30 fps clip = 300 model invocations. Start with short clips.
- **Frame rate**: If the source and output frame rates differ, the audio and video will drift. Pass the source's true fps as `frame_rate` (the default `30` is a fallback).
- **Choosing a different upscaler**: Swap `family: real-esrgan` and the model file for another supported family (`esrgan`, `swinir`, `ldsr`). Each family exposes its own tiling parameters — see the `image-upscale` docs.
- **Batching**: The `for-each` job runs frames sequentially by default. Set `batch_size` on the `for-each` job to process frames concurrently (bounded by GPU memory).
