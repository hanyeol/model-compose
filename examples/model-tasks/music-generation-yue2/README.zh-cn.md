# 音乐生成 (YuE2) 模型任务示例

此示例演示如何使用 YuE2 在本地生成完整歌曲，通过 model-compose 的内置模型任务功能运行。YuE2 将符号化乐谱规划（ABC）与声学合成结合，可以从头创作歌曲、基于可编辑乐谱生成，或仅导出规划而不渲染音频。

## 概述

此示例针对单个 YuE2 组件公开三个工作流：

1. **generate** — 从风格描述和歌词创作新歌曲
2. **cover** — 以新的风格重新演绎提供的 ABC 乐谱（零样本翻唱通常仅使用旋律）
3. **score** — 仅规划可编辑的 ABC 乐谱，不渲染音频

每个工作流都使用 YuE2 的符号化思维链：`cot_mode: full` 同时编写旋律和和弦符号，`melody` 编写仅旋律的规划（推荐用于翻唱），`off` 跳过乐谱直接从歌词和风格生成。

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- 支持 **BF16 且具有 24 GB VRAM** 的 NVIDIA GPU（YuE2 无需量化即可渲染 48 kHz 立体声音频）
- Python 3.12 环境（`yue2-infer` wheel 及其固定的 `torch==2.10.0` 首次运行时自动安装）
- AR 模型和 VAE 解码器需要 ~15 GB 磁盘空间（首次使用时从 Hugging Face 下载）

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/model-tasks/music-generation-yue2
   ```

2. 无需额外的环境配置 — 模型和依赖项将自动管理。

## 运行方法

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行 "generate" 工作流（默认）：**

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "style": "English, piano-pop, warm lead vocal, tasteful strings",
         "lyrics": "[Verse]\nMorning light on empty streets\n[Chorus]\nWe are the ones who wait"
       }
     }'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 在 *Generate*、*Cover*、*Score* 标签页之间切换
   - 填写风格描述和歌词，然后点击 "Run Workflow"

   **使用 CLI：**
   ```bash
   model-compose run generate --input '{"style": "English, piano-pop", "lyrics": "..."}'
   ```

3. **翻唱现有乐谱：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs/cover \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "style": "English, jazz-funk, warm lead vocal, Rhodes, bass and drums",
         "lyrics": "...新歌词...",
         "abc": "X:1\nT:Sample\nM:4/4\nK:C\n..."
       }
     }'
   ```

4. **仅导出乐谱（无音频）：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs/score \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "style": "Mandarin, city-pop, mid tempo",
         "lyrics": "..."
       }
     }'
   ```
   返回 `{ "abc": "...", "truncated": false }` 供下游编辑。

## 组件详情

### YuE2 音乐生成组件
- **类型**：具有 `music-generation` 任务的模型组件
- **驱动 / 家族**：`custom` / `yue2`
- **模型**：`m-a-p/YuE2-3B`（自回归模型）+ `m-a-p/YuE2-Vae`（解码器，自动下载）
- **设备**：`cuda`
- **输出格式**：48 kHz 立体声音频（`generate`、`cover`）或 `{ abc, truncated }`（`score`）
- **并发**：1（一次一个请求）

### 模型信息：YuE2
- **开发者**：M·A·P 及合作者（详见 [YuE2 项目页面](https://map-yue2.github.io/)）
- **类型**：结合流匹配声学合成和 VAE 解码的 AR–NAR Mixture-of-Transformers
- **思维链模式**：`full`（含和弦的乐谱，默认）、`melody`（最适合翻唱）、`off`（直接生成）
- **后端**：`torch`（默认）、`torch-eager`、`vllm`（需要模型的可选 `[fast]` extras）
- **量化**：AR 模型的可选 `fp8` — 以微小的质量损失将 AR VRAM 减半

## 工作流详情

### "Generate" 工作流（默认）

**描述**：从风格描述和歌词创作新歌曲。

#### 输入参数

| 参数 | 类型 | 必需 | 默认 | 描述 |
|------|------|------|------|------|
| `style` | text | 是 | - | 风格、流派、氛围和乐器描述 |
| `lyrics` | text | 是 | - | 带可选结构标签（例如 `[Verse]`、`[Chorus]`）的歌词 |
| `cot_mode` | text | 否 | `full` | `full`（乐谱 + 和弦）、`melody`（仅旋律）或 `off`（直接） |
| `cfg_scale` | number | 否 | 模型默认 | `[0, 20]` 范围内的 classifier-free guidance 尺度 |
| `seed` | integer | 否 | `831001` | 用于可重现性的随机种子 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| - | audio | 生成的歌曲（48 kHz 立体声 WAV） |

### "Cover" 工作流

**描述**：以新的风格重新演绎提供的 ABC 乐谱。

#### 输入参数

| 参数 | 类型 | 必需 | 默认 | 描述 |
|------|------|------|------|------|
| `style` | text | 是 | - | 目标翻唱风格 |
| `lyrics` | text | 是 | - | 在翻唱乐谱上演唱的歌词 |
| `abc` | text | 是 | - | 用于条件化翻唱的 ABC 乐谱（通常是没有和弦符号的旋律转录） |
| `cot_mode` | text | 否 | `melody` | 翻唱使用 `melody`；如果 ABC 包含和弦符号则使用 `full` |
| `seed` | integer | 否 | `831001` | 随机种子 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| - | audio | 翻唱录音（48 kHz 立体声 WAV） |

### "Score" 工作流

**描述**：仅规划可编辑的 ABC 乐谱，不渲染音频。

#### 输入参数

| 参数 | 类型 | 必需 | 默认 | 描述 |
|------|------|------|------|------|
| `style` | text | 是 | - | 用于规划乐谱的风格描述 |
| `lyrics` | text | 是 | - | 塑造规划的歌词 |
| `cot_mode` | text | 否 | `full` | `full`（含和弦符号）或 `melody`（仅旋律） |
| `seed` | integer | 否 | `831001` | 随机种子 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `abc` | text | 规划歌曲的可编辑 ABC 记谱 |
| `truncated` | boolean | 规划是否达到 token 预算 |

## 系统要求

### 最低要求
- **GPU**：具有 **BF16 支持和 24 GB VRAM** 的 NVIDIA GPU（非量化预设）
- **RAM**：推荐 32 GB
- **磁盘空间**：AR 模型和 VAE 解码器需 15 GB+
- **互联网**：仅初始 Hugging Face 下载需要

### 性能说明
- 首次运行从 Hugging Face 下载模型权重（~15 GB）
- 非量化预设需要 24 GB VRAM；对于较小的 GPU 请使用 `quantization.type: fp8` 和 `offload_ar: true`
- 每个组件单个并发请求以防止 VRAM 耗尽

## 自定义

### 减少 VRAM 使用
```yaml
component:
  quantization:
    type: fp8       # 将 AR 内存减半
  offload_ar: true  # NAR 合成期间将 AR 模型移至 CPU
  memory_budget_gib: 16
  vae:
    tile_size: 512
```

### 使用 vLLM 后端
```yaml
component:
  backend: vllm
  # 需要 `pip install "yue2-infer[fast]"`（安装 vllm/triton）
```

### 调整采样
```yaml
component:
  actions:
    - method: generate
      style: ${input.style as text}
      lyrics: ${input.lyrics as text}
      params:
        cfg_scale: 1.5
        abc_sampling:
          temperature: 0.7
          top_p: 0.9
        semantic_sampling:
          temperature: 1.0
          top_p: 0.95
          repetition_penalty: 1.2
```

## 相关示例

- **[music-generation](../music-generation/)**：使用 ACE-Step 1.5 的本地音乐生成
- **[music-source-separation](../music-source-separation/)**：将混合录音分离为音轨
- **[music-transcription](../music-transcription/)**：将录音转录为乐谱
