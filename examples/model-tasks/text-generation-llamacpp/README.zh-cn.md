# 文本生成 (llama.cpp) 示例

本示例演示如何通过 model-compose 的内置 `llamacpp` 驱动，使用 GGUF 格式模型在本地运行基于 llama.cpp 的文本生成。

## 概述

此工作流提供本地文本生成功能：

1. **llama.cpp 后端**：以最小内存占用运行 GGUF 量化模型
2. **CPU 友好**：无需 GPU 即可在 CPU 上良好运行
3. **GGUF 格式**：支持量化模型（Q4、Q5、Q8 等）以减少内存使用
4. **无需外部 API**：完全离线推理，无 API 依赖

## 准备工作

### 先决条件

- 已安装 model-compose 并在 PATH 中可用
- 已安装 `llama-cpp-python`（参见下方安装说明）
- 将 GGUF 模型文件放置在 `./models/llama-3.2-1b-instruct-q4_k_m.gguf`

### 安装 llama-cpp-python

```bash
# 仅 CPU
pip install llama-cpp-python

# macOS 使用 Metal 加速（Apple Silicon / AMD GPU）
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python

# CUDA（NVIDIA GPU）
CMAKE_ARGS="-DLLAMA_CUDA=on" pip install llama-cpp-python
```

### 下载 GGUF 模型

```bash
mkdir -p models

# 从 HuggingFace 下载 Llama-3.2-1B-Instruct Q4_K_M
curl -L -o models/llama-3.2-1b-instruct-q4_k_m.gguf \
  https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf
```

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/model-tasks/text-generation-llamacpp
   ```

2. 将 GGUF 模型文件放置在 `./models/` 下。

## 如何运行

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "prompt": "The history of artificial intelligence begins"
       }
     }'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 输入提示词
   - 点击"Run Workflow"按钮

   **使用 CLI：**
   ```bash
   model-compose run --input '{"prompt": "The history of artificial intelligence begins"}'
   ```

## 组件详情

### 文本生成模型组件
- **类型**：带 text-generation 任务的模型组件
- **驱动**：`llamacpp`
- **模型**：GGUF 量化模型（默认 Q4_K_M）
- **功能**：
  - 通过 llama.cpp 进行 CPU 优化推理
  - 通过 `n_gpu_layers` 进行 GPU 卸载（设为 `-1` 卸载所有层）
  - 可配置的上下文窗口（`context_length`）
  - 流式支持

## 工作流详情

### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|-----|------|------|--------|------|
| `prompt` | text | 是 | - | 用作生成起点的输入文本 |

### 输出格式

| 字段 | 类型 | 描述 |
|-----|------|------|
| `generated` | text | 生成的文本续写 |

## 自定义

### GPU 卸载

要将层卸载到 GPU，请设置 `device` 和 `n_gpu_layers`：

```yaml
component:
  type: model
  task: text-generation
  driver: llamacpp
  model:
    provider: local
    path: ./models/llama-3.2-1b-instruct-q4_k_m.gguf
    format: gguf
  device: cuda        # macOS 使用 "metal"
  n_gpu_layers: -1    # -1 = 卸载所有层
  context_length: 4096
  action:
    text: ${input.prompt as text}
    params:
      max_output_length: 1024
```

### 使用不同的模型

```yaml
component:
  type: model
  task: text-generation
  driver: llamacpp
  model:
    provider: local
    path: ./models/mistral-7b-instruct-v0.2.Q4_K_M.gguf
    format: gguf
  context_length: 8192
  action:
    text: ${input.prompt as text}
```

### 流式输出

```yaml
component:
  action:
    text: ${input.prompt as text}
    streaming: true
    params:
      max_output_length: 2048
```

## 系统要求

### 最低要求（CPU）
- **RAM**：2GB+（取决于模型大小和量化）
- **磁盘空间**：模型文件大小（1B 的 Q4_K_M ≈ 0.8GB）
- **CPU**：任何现代 x86_64 或 ARM64 处理器

### 推荐（GPU）
- **VRAM**：1B 模型 2GB+，7B 模型 6GB+
- **GPU**：NVIDIA (CUDA) 或 Apple Silicon (Metal)

## GGUF 量化指南

| 量化 | 内存 | 质量 | 推荐用途 |
|-----|------|-----|---------|
| Q2_K | 最低 | 最低 | RAM 非常有限时 |
| Q4_K_M | 低 | 良好 | 一般使用（默认） |
| Q5_K_M | 中 | 更好 | 更好的质量 |
| Q8_0 | 高 | 最好 | 最高质量 |
| F16 | 最高 | 无损 | 大 VRAM 的 GPU |

## 故障排除

1. **找不到 `llama_cpp`**：使用 `pip install llama-cpp-python` 安装
2. **内存不足**：使用较低的量化（Q4 或 Q2）或较小的模型
3. **推理缓慢**：通过 `n_gpu_layers: -1` 启用 GPU 卸载
4. **找不到模型文件**：验证 YAML 中的 `path` 与您的文件位置匹配
