# Audio Processor MCP 服务器示例

本示例演示如何将本地音频处理流水线通过 **stdio** 传输方式暴露为 MCP 服务器。每个工作流都会被注册为一个 MCP 工具,接收 base64 编码的音频片段,应用 DSP 效果后返回 WAV 字节流。

## 概述

本 MCP 服务器基于 `audio-processor` 组件,提供 20 个音频处理工作流,涵盖格式转换、滤波、EQ、动态处理、音色塑形、空间效果、响度控制以及边缘处理:

**格式与滤波**
1. **重采样**: 转换到不同采样率(例如将 32 kHz 模型输出对齐到 44.1 kHz)
2. **高通滤波器**: 移除截止频率以下的低频内容(隆隆声、嗡嗡声、次声波噪声)
3. **低通滤波器**: 移除截止频率以上的高频内容(嘶嘶声、齿音)

**参数均衡器 (EQ)**
4. **钟形 EQ**: 围绕中心频率进行钟形提升/衰减(精细的音色调整)
5. **低搁架 EQ**: 提升/衰减某个转折频率以下的全部内容(低频温暖或变薄)
6. **高搁架 EQ**: 提升/衰减某个转折频率以上的全部内容(空气感、光泽、抑制嘶声)

**音高**
7. **变调**: 在不改变时长的前提下按半音移动音高

**动态处理**
8. **动态范围压缩器**: 压低响亮部分,保持轻柔部分可闻
9. **噪声门**: 衰减阈值以下的信号,清理安静段的底噪

**音色 / 色彩**
10. **失真**: 作为创意效果的强烈谐波失真
11. **饱和**: 增加微妙的谐波色彩与温暖感,不产生可闻的失真

**空间**
12. **混响**: 增加空间感(房间、大厅)

**响度 (归一化)**
13. **归一化 (RMS)**: 按目标 RMS 电平和峰值上限归一化
14. **归一化 (峰值)**: 缩放音频使最大峰值达到目标 dBFS
15. **归一化 (LUFS)**: 按 ITU-R BS.1770 集成响度目标匹配,并附带真实峰值保护

**响度 (峰值限制)**
16. **峰值限制 (硬)**: 用于保留余量的砖墙式硬削
17. **峰值限制 (平滑)**: 用于透明的母带级峰值控制的前瞻式限幅器

**边缘处理**
18. **裁剪静音**: 裁剪尾部静音并压缩过长的内部静音段
19. **淡入**: 在音频开头应用余弦淡入
20. **淡出**: 在音频结尾应用余弦淡出

由于运行在 **stdio** 上,本示例设计为由 MCP 客户端(例如 Claude Desktop)按需启动进程,而不是作为常驻的 HTTP 服务器。

## 准备工作

### 必要条件

- Python 3.10+
- 已安装 model-compose 并加入 PATH
- `audio-processor` 组件驱动依赖(随 model-compose 一起安装)

### 环境配置

本示例完全在本地运行,无需任何环境变量或 API 密钥。

## 运行方法

### 作为 stdio MCP 服务器运行(常规用法)

在 MCP 客户端中按如下方式配置:

```json
{
  "mcpServers": {
    "audio-processor": {
      "command": "model-compose",
      "args": ["up"],
      "cwd": "/绝对/路径/examples/mcp-servers/audio-processor-mcp"
    }
  }
}
```

客户端会在该目录下启动 `model-compose up`,进程通过标准输入输出承载 MCP 协议。全部 20 个工作流都会以工具形式出现。

### 从 CLI 单独运行某个工作流

也可以在不启动 MCP 服务器的情况下直接调用工作流。音频输入需以 base64 字符串传入:

```bash
# 200 Hz 高通滤波
model-compose run highpass --input '{
  "audio": "<base64-编码的-wav>",
  "cutoff": 200
}'

# 升高 2 个半音
model-compose run pitch-shift --input '{
  "audio": "<base64-编码的-wav>",
  "semitones": 2
}'

# 归一化到 -14 LUFS(流媒体目标)
model-compose run normalize-lufs --input '{
  "audio": "<base64-编码的-wav>",
  "level": -14
}'
```

### 运行冒烟测试

示例中包含一个自包含的冒烟测试,它会启动 stdio 服务器、列出工具,并用一段 1 秒的正弦波依次调用每个工作流:

```bash
python smoke.py
```

## 组件详情

### Audio Processor 组件
- **ID**: `audio`
- **类型**: `audio-processor`
- **用途**: 覆盖格式转换、滤波、参数均衡、动态处理、音色塑形、空间效果、响度归一化、峰值限制、边缘处理的本地 DSP 流水线
- **动作**: `resample`、`highpass`、`lowpass`、`bell`、`low-shelf`、`high-shelf`、`pitch-shift`、`compressor`、`noise-gate`、`distortion`、`saturation`、`reverb`、`normalize-rms`、`normalize-peak`、`normalize-lufs`、`peak-limit-hard`、`peak-limit-smooth`、`trim-silence`、`fade-in`、`fade-out`

## 工作流详情

### "Resample Audio" 工作流

**说明**: 将音频转换到不同的采样率。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | audio (base64) | 是 | - | base64 编码的输入音频 |
| `sample_rate` | number | 否 | `44100` | 目标采样率(Hz) |

### "Apply Highpass Filter" 工作流

**说明**: 移除截止频率以下的低频内容。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | audio (base64) | 是 | - | base64 编码的输入音频 |
| `cutoff` | number | 否 | `80` | 截止频率(Hz) |

### "Apply Lowpass Filter" 工作流

**说明**: 移除截止频率以上的高频内容。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | audio (base64) | 是 | - | base64 编码的输入音频 |
| `cutoff` | number | 否 | `8000` | 截止频率(Hz) |

### "Apply Bell EQ" 工作流

**说明**: 围绕中心频率进行钟形的提升或衰减。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | audio (base64) | 是 | - | base64 编码的输入音频 |
| `frequency` | number | 否 | `3000` | 钟形的中心频率(Hz) |
| `gain` | number | 否 | `0` | 中心频率处的增益(dB),正值提升,负值衰减 |
| `q` | number | 否 | `0.707` | 钟形宽度,Q 越大频带越窄 |

### "Apply Low-Shelf EQ" 工作流

**说明**: 对某个转折频率以下的全部内容进行提升或衰减。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | audio (base64) | 是 | - | base64 编码的输入音频 |
| `frequency` | number | 否 | `150` | 搁架转折频率(Hz) |
| `gain` | number | 否 | `0` | 搁架增益(dB),正值提升,负值衰减 |
| `q` | number | 否 | `0.707` | 搁架斜率,Q 越大转折越陡 |

### "Apply High-Shelf EQ" 工作流

**说明**: 对某个转折频率以上的全部内容进行提升或衰减。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | audio (base64) | 是 | - | base64 编码的输入音频 |
| `frequency` | number | 否 | `10000` | 搁架转折频率(Hz) |
| `gain` | number | 否 | `0` | 搁架增益(dB),正值提升,负值衰减 |
| `q` | number | 否 | `0.707` | 搁架斜率,Q 越大转折越陡 |

### "Apply Pitch Shift" 工作流

**说明**: 在不改变时长的前提下按半音移动音高。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | audio (base64) | 是 | - | base64 编码的输入音频 |
| `semitones` | number | 否 | `0` | 要移动的半音数,正数升高,负数降低 |

### "Apply Dynamic Range Compressor" 工作流

**说明**: 压低响亮部分,保持轻柔部分可闻。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | audio (base64) | 是 | - | base64 编码的输入音频 |
| `threshold` | number | 否 | `-20` | 触发压缩的阈值(dB) |
| `ratio` | number | 否 | `4` | 压缩比(例如 4 表示 4:1) |

### "Apply Noise Gate" 工作流

**说明**: 衰减阈值以下的信号,清理安静段的底噪和编解码器伪影。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | audio (base64) | 是 | - | base64 编码的输入音频 |
| `threshold` | number | 否 | `-40` | 噪声门开始衰减的阈值(dB) |
| `ratio` | number | 否 | `10` | 向下扩展比,越大越激进 |

### "Apply Distortion" 工作流

**说明**: 作为创意效果添加强烈的谐波失真。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | audio (base64) | 是 | - | base64 编码的输入音频 |
| `drive` | number | 否 | `25` | 驱动量(dB),典型范围 15 到 40 |

### "Apply Saturation" 工作流

**说明**: 增加微妙的谐波色彩与温暖感,不产生可闻的失真。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | audio (base64) | 是 | - | base64 编码的输入音频 |
| `drive` | number | 否 | `3` | 驱动量(dB),典型范围 1 到 8 |

### "Apply Reverb" 工作流

**说明**: 添加混响以获得空间感。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | audio (base64) | 是 | - | base64 编码的输入音频 |
| `room_size` | number | 否 | `0.5` | 房间大小(0.0~1.0) |
| `damping` | number | 否 | `0.5` | 高频阻尼(0.0~1.0) |
| `wet_level` | number | 否 | `0.33` | 湿信号电平(0.0~1.0) |

### "Normalize Loudness (RMS)" 工作流

**说明**: 按目标 RMS 电平和峰值上限归一化。适合完整响度计过于笨重的源到源对齐场景。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | audio (base64) | 是 | - | base64 编码的输入音频 |
| `level` | number | 否 | `-20` | 目标 RMS 电平(dBFS) |
| `peak_limit` | number | 否 | `0.85` | 归一化后峰值幅度上限(0.0~1.0) |

### "Normalize Loudness (Peak)" 工作流

**说明**: 缩放音频使最大峰值达到目标 dBFS。当余量控制比感知响度更重要时使用。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | audio (base64) | 是 | - | base64 编码的输入音频 |
| `level` | number | 否 | `-1` | 目标峰值电平(dBFS) |

### "Normalize Loudness (LUFS)" 工作流

**说明**: 按 ITU-R BS.1770 集成响度目标(LUFS)匹配,并附带真实峰值保护。用于流媒体或广播交付。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | audio (base64) | 是 | - | base64 编码的输入音频 |
| `level` | number | 否 | `-14` | 目标集成响度(LUFS)。流媒体用 -14,更有冲击力的母带用 -9 到 -12 |
| `true_peak_ceiling` | number | 否 | `-1` | 响度增益后应用的真实峰值上限(dBTP) |

### "Apply Peak Limit (Hard)" 工作流

**说明**: 以砖墙式硬削限制峰值幅度。快速廉价的余量保护;瞬态密集的素材可能产生可闻失真。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | audio (base64) | 是 | - | base64 编码的输入音频 |
| `level` | number | 否 | `0.95` | 峰值幅度上限(0.0~1.0) |

### "Apply Peak Limit (Smooth)" 工作流

**说明**: 使用带前瞻和平滑释放的限幅器控制峰值。用于透明的母带级峰值控制。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | audio (base64) | 是 | - | base64 编码的输入音频 |
| `level` | number | 否 | `-1` | 上限(dBFS) |
| `release` | duration | 否 | `100ms` | 释放时间(例如 `100ms`) |

### "Trim Trailing Silence" 工作流

**说明**: 裁剪尾部静音并压缩过长的内部静音段。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | audio (base64) | 是 | - | base64 编码的输入音频 |
| `threshold` | number | 否 | `-40` | 静音判定阈值(dBFS) |
| `min_silence` | duration | 否 | `200ms` | 需要保留的最小尾部静音长度 |

### "Apply Fade-In" 工作流

**说明**: 在音频开头应用余弦淡入,使起始更为平滑。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | audio (base64) | 是 | - | base64 编码的输入音频 |
| `duration` | duration | 否 | `20ms` | 淡入时长(例如 `20ms`) |

### "Apply Fade-Out" 工作流

**说明**: 在音频结尾应用余弦淡出,避免突兀结束。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | audio (base64) | 是 | - | base64 编码的输入音频 |
| `duration` | duration | 否 | `20ms` | 淡出时长(例如 `20ms`) |

## MCP 服务器集成

### 连接信息
- **传输方式**: stdio
- **启动命令**: `model-compose up`(在本示例目录中执行)
- **协议**: Model Context Protocol v1.0

### 可用工具
每个工作流以同名 MCP 工具的形式对外暴露:

- `resample`
- `highpass`
- `lowpass`
- `bell`
- `low-shelf`
- `high-shelf`
- `pitch-shift`
- `compressor`
- `noise-gate`
- `distortion`
- `saturation`
- `reverb`
- `normalize-rms`
- `normalize-peak`
- `normalize-lufs`
- `peak-limit-hard`
- `peak-limit-smooth`
- `trim-silence`
- `fade-in`
- `fade-out`

每个工具都返回 `mimeType: audio/wav` 的 MCP `AudioContent`,客户端可直接拿到 base64 编码的 WAV,无需额外下载步骤。

## 故障排查

### 常见问题

1. **工具调用返回 `TextContent` 而不是音频**: `model-compose` 内部的工作流出错了。直接运行 `model-compose up`(不接 stdio 客户端)以查看回溯信息。
2. **`audio requires raw audio bytes, got str` 错误**: 检查 `model-compose.yml` 中 `audio` 变量声明是否带有 `;base64` 解码提示(例如 `as audio;base64`)。
3. **MCP 客户端找不到服务器**: MCP 配置中的 `cwd` 必须是本示例目录的绝对路径。
4. **冒烟测试卡住**: 确认 `model-compose` 已加入 `PATH`,并且没有其他进程占用 stdio。
