# VibeVoice Realtime TTS

Text-to-speech using [Microsoft VibeVoice Realtime (0.5B)](https://github.com/microsoft/VibeVoice) running in a Docker container via WebSocket.

## Requirements

- Docker with NVIDIA GPU support (`nvidia-container-toolkit`)
- NVIDIA GPU with at least 4 GB VRAM

## Usage

```bash
model-compose up
```

This will:
1. Build the Docker image (first run takes several minutes)
2. Download the model from HuggingFace (~2 GB)
3. Start the VibeVoice WebSocket server on port 3000
4. Start the model-compose API on port 8080
5. Start the Gradio WebUI on port 8081

## API

```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -H "Content-Type: application/json" \
  -d '{"input": {"text": "Hello, world!", "voice": "Carter"}}'
```

### Input Parameters

| Parameter   | Type   | Default  | Description                        |
|-------------|--------|----------|------------------------------------|
| `text`      | string | required | Text to synthesize                 |
| `voice`     | string | Carter   | Voice preset name                  |
| `cfg_scale` | number | 1.5      | Classifier-free guidance scale     |

### Available Voices

25 pre-trained voices are included: Alloy, Ash, Ballad, Carter, Coral, Echo, Ember, Fable, Juniper, Lark, Onyx, Nova, Sage, Shimmer, Vale, Verse, etc.

## How It Works

The `websocket-server` component:
1. Builds and starts a Docker container running VibeVoice's demo WebSocket server
2. On each request, connects to `ws://localhost:3000/stream` with text/voice as query params
3. Collects binary PCM16 audio chunks sent over WebSocket
4. Returns the assembled audio as a WAV response
