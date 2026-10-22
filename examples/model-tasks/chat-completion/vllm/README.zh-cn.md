# vLLM 聊天完成示例

此示例演示如何使用内置 **vLLM** 驱动运行 `chat-completion` 任务：将一个小型 instruction-tuned 模型加载到专用虚拟环境中并生成聊天响应。

## 概述

该工作流执行非流式聊天完成：

1. **vLLM 引擎**：模型由 vLLM 在隔离的 `virtualenv` 运行时中加载，这样 vLLM 的依赖不会污染主 model-compose 环境。
2. **小型指令模型**：使用 `Qwen/Qwen2.5-0.5B-Instruct`（约 1GB），下载便宜、启动快速，便于后续替换为更大的模型。
3. **标准聊天格式**：接收一个 `system` 提示和一个 `user` 提示，一次性返回完整响应。

## 准备工作

### 前置条件

- 已安装 model-compose 并在 `PATH` 中可用。
- 强烈推荐支持 CUDA 的 GPU。vLLM 主要面向 Linux + NVIDIA，macOS/仅 CPU 环境无法运行此示例。
- Python 3.10+（用于构建虚拟环境）。

### 环境配置

1. 进入示例目录：
   ```bash
   cd examples/model-tasks/chat-completion/vllm
   ```

2. 首次运行时，组件会自动构建 `.venv/vllm`、安装 vLLM 并下载 Qwen 模型，无需手动配置。

## 运行方法

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **执行工作流：**

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "system_prompt": "You are a helpful AI assistant.",
         "user_prompt": "Explain quantum computing in simple terms."
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
     "user_prompt": "Explain quantum computing in simple terms."
   }'
   ```

## 组件详情

### 聊天完成模型组件（vLLM）
- **类型**：`model` 组件，`task: chat-completion`，`driver: vllm`
- **模型**：`Qwen/Qwen2.5-0.5B-Instruct`（0.5B 参数，instruction-tuned）
- **运行时**：位于 `.venv/vllm` 的 `virtualenv` —— vLLM 仅安装于此
- **引擎选项**：
  - `max_model_len: 2048` —— 上下文窗口上限
  - `gpu_memory_utilization: 0.9` —— 引擎可占用的 GPU 显存比例

### 为何使用 vLLM
- **吞吐量**：PagedAttention 和持续批处理在并发请求下的 tokens/sec 高于朴素的 HuggingFace generate。
- **确定性配置**：隔离的 virtualenv 使 vLLM 的庞大依赖树不污染主环境。

### 输入参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `system_prompt` | 文本 | 否 | 设定助手行为的 system 消息 |
| `user_prompt` | 文本 | 是 | 助手需要回应的 user 轮次 |

### 输出格式

| 字段 | 类型 | 说明 |
|------|------|------|
| `generated` | 文本 | 助手完整响应（单个字符串） |

## 自定义

### 使用其他模型

替换为其他 instruction-tuned 聊天模型：
```yaml
component:
  model: Qwen/Qwen2.5-1.5B-Instruct  # 或 Qwen/Qwen2.5-7B-Instruct 等
```

### 更大的上下文窗口

```yaml
component:
  options:
    max_model_len: 8192
```

### 采样参数

```yaml
action:
  params:
    temperature: 0.9
    top_p: 0.95
    do_sample: true
```

## 故障排查

- **CUDA 错误 / 显存不足**：降低 `gpu_memory_utilization`（如 `0.7`）或 `max_model_len`，或改用更小的模型。
- **首次运行较慢**：vLLM 安装和模型下载发生在首次启动，后续运行会复用缓存。
- **vLLM 安装失败**：确认 CUDA 工具链版本在 vLLM 发行说明的支持范围内。

## 参考

- `../huggingface/` —— HuggingFace 驱动下的相同任务（不依赖 vLLM）
- `../llamacpp/` —— llama.cpp 驱动下的相同任务（CPU/GGUF）
- `../vllm-stream/` —— 本示例的流式版本
