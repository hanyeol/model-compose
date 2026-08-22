# 文本转语音（CosyVoice2 语音克隆）模型任务示例

此示例演示如何使用 CosyVoice2 (FunAudioLLM) 以 24 kHz 执行零样本语音克隆，通过 model-compose 的内置模型任务功能在本地运行。

## 概述

此工作流提供本地语音克隆和语音合成：

1. **本地模型执行**：无需外部 API，在本地运行 CosyVoice2-0.5B
2. **零样本语音克隆**：从简短的参考音频样本中复制说话者的声音
3. **可选的参考文本**：提供转录文本以获得更精确的对齐，或省略以使用跨语言模式
4. **24 kHz 输出**：以模型原生 24 kHz 采样率输出合成语音

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- 足够的系统资源（使用 GPU 时推荐：8GB+ VRAM）
- 包含 CosyVoice 依赖的 Python 环境（自动管理）
- 用于语音克隆的参考音频文件（以及可选的转录文本）

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/model-tasks/text-to-speech-clone-cosyvoice
   ```

2. 无需额外的环境配置 - 模型和依赖会自动管理。

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **使用 Web UI（推荐）：**
   - 打开 Web UI：http://localhost:8084
   - 输入要合成的文本
   - 上传参考音频文件
   - 可选择输入参考音频的转录文本
   - 点击"运行工作流"按钮

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8083/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "text": "这是使用克隆语音合成的语音。",
         "reference_audio": "<base64编码的音频>",
         "reference_text": "参考音频的转录文本。"
       }
     }'
   ```

   **使用 CLI：**
   ```bash
   model-compose run --input '{
     "text": "这是使用克隆语音合成的语音。",
     "reference_audio": "<base64编码的音频>",
     "reference_text": "参考音频的转录文本。"
   }'
   ```

## 组件详情

### 文本转语音模型组件（默认）
- **类型**：具有 `text-to-speech` 任务的模型组件
- **用途**：从参考音频进行零样本语音克隆和语音合成
- **模型**：`FunAudioLLM/CosyVoice2-0.5B`
- **驱动**：`custom`
- **系列**：`cosyvoice`
- **设备**：`auto`
- **方法**：`clone` - 从参考音频克隆语音并生成语音
- **并发数**：1（同时处理一个请求）

### 模型信息：CosyVoice2-0.5B
- **开发者**：FunAudioLLM（阿里巴巴达摩院）
- **参数**：约 5 亿
- **类型**：零样本语音克隆 TTS 模型
- **采样率**：24 kHz 输出
- **语言**：多语言支持
- **输出格式**：音频（WAV）

## 工作流详情

### "Text to Speech with Voice Cloning (CosyVoice2)" 工作流（默认）

**描述**：使用 CosyVoice2 (FunAudioLLM) 进行 24 kHz 零样本语音克隆。

#### 作业流程

```mermaid
graph TD
    J1((默认<br/>作业))
    C1[TTS 模型<br/>组件]
    J1 -.-> C1
    C1 -.-> |audio| J1
    Input((输入)) --> J1
    J1 --> Output((输出))
```

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|-----------|------|----------|---------|-------------|
| `text` | text | 是 | - | 使用克隆语音合成的文本 |
| `reference_audio` | audio | 是 | - | 用于克隆语音的参考音频样本 |
| `reference_text` | text | 否 | `""` | 参考音频的转录文本。省略以使用跨语言模式 |

#### 输出格式

| 字段 | 类型 | 描述 |
|-------|------|-------------|
| - | audio | 使用克隆语音生成的语音音频（WAV，24 kHz） |

## 示例输出

工作流返回包含以 24 kHz 使用克隆语音合成的语音的 WAV 音频流。

## 自定义

### 切换到 CosyVoice3

更新 `component.model` 以使用 CosyVoice3 基础模型：

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: cosyvoice
  model: FunAudioLLM/Fun-CosyVoice3-0.5B-2512
  device: auto
```

### 使用内置说话人（SFT 模型）

如果您想使用内置预设说话人而不是零样本克隆，请切换到 SFT 模型并使用 `method: generate`：

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: cosyvoice
  model: iic/CosyVoice-300M-SFT
  device: auto
  action:
    method: generate
    text: ${input.text as text}
    output: ${result as audio/wav}
```

### 跨语言语音克隆

省略 `reference_text`（保持为空），即可在保留说话者音色的同时以与参考音频不同的语言合成文本。

## 相关示例

- **[text-to-speech-clone](../text-to-speech-clone/)**：使用 Qwen3-TTS 的语音克隆
- **[text-to-speech-clone-luxtts](../text-to-speech-clone-luxtts/)**：使用 LuxTTS (ZipVoice) 的 48 kHz 语音克隆
- **[text-to-speech-clone-tada](../text-to-speech-clone-tada/)**：使用 HumeAI TADA 的语音克隆
