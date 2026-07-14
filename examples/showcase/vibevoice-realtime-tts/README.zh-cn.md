# VibeVoice Realtime TTS

使用通过 WebSocket 在 Docker 容器中运行的 [Microsoft VibeVoice Realtime (0.5B)](https://github.com/microsoft/VibeVoice) 进行文本转语音。

## 要求

- 支持 NVIDIA GPU 的 Docker (`nvidia-container-toolkit`)
- 至少具有 4 GB VRAM 的 NVIDIA GPU

## 使用方法

```bash
model-compose up
```

这将：
1. 构建 Docker 镜像（首次运行需要几分钟）
2. 从 HuggingFace 下载模型（约 2 GB）
3. 在端口 3000 上启动 VibeVoice WebSocket 服务器
4. 在端口 8080 上启动 model-compose API
5. 在端口 8081 上启动 Gradio WebUI

## API

```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -H "Content-Type: application/json" \
  -d '{"input": {"text": "Hello, world!", "voice": "Carter"}}'
```

### 输入参数

| 参数         | 类型   | 默认值   | 描述                              |
|-------------|--------|----------|-----------------------------------|
| `text`      | string | 必需     | 要合成的文本                      |
| `voice`     | string | Carter   | 语音预设名称                      |
| `cfg_scale` | number | 1.5      | Classifier-free guidance scale    |

### 可用语音

包含 25 个预训练语音：Alloy、Ash、Ballad、Carter、Coral、Echo、Ember、Fable、Juniper、Lark、Onyx、Nova、Sage、Shimmer、Vale、Verse 等。

## 工作原理

`websocket-server` 组件：
1. 构建并启动运行 VibeVoice 演示 WebSocket 服务器的 Docker 容器
2. 每次请求时，使用文本/语音作为查询参数连接到 `ws://localhost:3000/stream`
3. 收集通过 WebSocket 发送的二进制 PCM16 音频块
4. 将组装的音频作为 WAV 响应返回
