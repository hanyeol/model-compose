# Chat Completion (llama.cpp) 示例

本示例演示如何使用 model-compose 的内置 `llamacpp` 驱动，通过 llama.cpp 使用 GGUF 格式模型在本地运行 chat completion。

## 概述

此工作流提供本地 chat completion 功能：

1. **llama.cpp 后端**：以最小的内存占用运行 GGUF 量化模型
2. **OpenAI 兼容的 Chat 格式**：支持 system/user/assistant 消息角色
3. **Tool Use (Function Calling)**：支持用于函数调用工作流的工具定义
4. **无需外部 API**：无 API 依赖的完全离线推理

## 准备工作

### 先决条件

- 已安装 model-compose 并在 PATH 中可用
- 已安装 `llama-cpp-python`（请参阅下方安装说明）
- 在 `./.models/llama-3.2-1b-instruct-q4_k_m.gguf` 路径下放置 GGUF instruct 模型文件

### 安装 llama-cpp-python

```bash
# 仅 CPU
pip install llama-cpp-python

# macOS Metal 加速 (Apple Silicon / AMD GPU)
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python

# CUDA (NVIDIA GPU)
CMAKE_ARGS="-DLLAMA_CUDA=on" pip install llama-cpp-python
```

### 下载 GGUF 模型

```bash
mkdir -p models

# 从 HuggingFace 下载 Llama-3.2-1B-Instruct Q4_K_M
curl -L -o .models/llama-3.2-1b-instruct-q4_k_m.gguf \
  https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf
```

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/model-tasks/chat-completion-llamacpp
   ```

2. 将 GGUF instruct 模型文件放置在 `./.models/` 目录下。

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
         "system_prompt": "You are a helpful AI assistant.",
         "user_prompt": "Explain what a GGUF file is in simple terms."
       }
     }'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 输入 system prompt 和 user prompt
   - 点击 "Run Workflow" 按钮

   **使用 CLI：**
   ```bash
   model-compose run --input '{
     "system_prompt": "You are a helpful AI assistant.",
     "user_prompt": "Explain what a GGUF file is in simple terms."
   }'
   ```

## 组件详情

### Chat Completion Model 组件
- **类型**：具有 chat-completion 任务的 Model 组件
- **驱动**：`llamacpp`
- **模型**：GGUF 量化 instruct 模型（默认为 Q4_K_M）
- **功能**：
  - 通过 llama.cpp 实现 CPU 优化推理
  - 支持 System 和 user 消息角色
  - 支持 Tool use (function calling)
  - 通过 `n_gpu_layers` 进行 GPU 卸载
  - 支持流式输出

## 工作流详情

### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|---------|------|------|--------|------|
| `system_prompt` | text | 否 | - | 定义 assistant 角色的 system 消息 |
| `user_prompt` | text | 是 | - | assistant 应响应的 user 消息 |

### 输出格式

| 字段 | 类型 | 描述 |
|-----|------|------|
| `generated` | text | assistant 的响应 |

## 自定义

### GPU 卸载

```yaml
component:
  type: model
  task: chat-completion
  driver: llamacpp
  model:
    provider: local
    path: ./.models/llama-3.2-1b-instruct-q4_k_m.gguf
    format: gguf
  device: cuda        # macOS 上使用 "metal"
  n_gpu_layers: -1    # -1 = 卸载全部层
  context_length: 4096
  action:
    messages:
      - role: system
        content: ${input.system_prompt}
      - role: user
        content: ${input.user_prompt}
```

### 流式输出

```yaml
component:
  action:
    messages:
      - role: system
        content: ${input.system_prompt}
      - role: user
        content: ${input.user_prompt}
    streaming: true
```

### Tool Use (Function Calling)

```yaml
component:
  action:
    messages:
      - role: user
        content: ${input.user_prompt}
    tools:
      - name: get_weather
        description: 获取指定位置的当前天气
        parameters:
          type: object
          properties:
            location:
              type: string
              description: 城市名称
          required:
            - location
```

## 系统要求

### 最低要求 (CPU)
- **RAM**：2GB+（取决于模型大小和量化）
- **磁盘空间**：模型文件大小（1B Q4_K_M ≈ 0.8GB）
- **CPU**：任何现代 x86_64 或 ARM64 处理器

### 推荐配置 (GPU)
- **VRAM**：1B 模型 2GB+，7B 模型 6GB+
- **GPU**：NVIDIA (CUDA) 或 Apple Silicon (Metal)

## 故障排除

1. **未找到 `llama_cpp`**：使用 `pip install llama-cpp-python` 安装
2. **响应质量差**：使用 instruct/chat 微调的 GGUF 模型，而非 base 模型
3. **内存不足**：使用更低的量化（Q4 或 Q2）或更小的模型
4. **推理速度慢**：使用 `n_gpu_layers: -1` 启用 GPU 卸载
