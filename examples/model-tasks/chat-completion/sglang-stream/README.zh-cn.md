# SGLang 聊天完成流式示例

此示例演示使用内置 **SGLang** 驱动进行 **按 token 流式** 聊天完成。token 在生成时逐步发出，客户端无需等待完整响应即可看到输出。

## 概述

此工作流与 `../sglang/` 相同，仅在两处启用了流式：

1. **action 中的 `streaming: true`** —— 驱动返回增量迭代器而非最终字符串。
2. **job 中的 `output: ${output as stream/text}`** —— 工作流将 chunk 原样作为文本流转发，而不进行聚合。

## 准备工作

### 前置条件

- 已安装 model-compose 并在 `PATH` 中可用。
- SGLang 需要支持 CUDA 的 GPU（Linux + NVIDIA）。
- 支持消费流式响应的 HTTP 客户端（如 `curl -N`）。

### 环境配置

1. 进入示例目录：
   ```bash
   cd examples/model-tasks/chat-completion/sglang-stream
   ```

2. 首次运行时，组件会自动构建 `.venv/sglang`、安装 SGLang 并下载 Qwen 模型。

## 运行方法

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **执行工作流（流式）：**

   **使用 API（`curl -N` 禁用缓冲）：**
   ```bash
   curl -N -X POST http://localhost:8080/api/workflows/runs \
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
   - token 流入时将在输出区域逐步显示。

## 组件详情

### 聊天完成模型组件（SGLang，流式）
- **类型**：`model` 组件，`task: chat-completion`，`driver: sglang`
- **模型**：`Qwen/Qwen2.5-0.5B-Instruct`
- **运行时**：位于 `.venv/sglang` 的 `virtualenv`
- **Action 标志**：`streaming: true` —— token 逐步发出。

### 输入参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `system_prompt` | 文本 | 否 | 设定助手行为的 system 消息 |
| `user_prompt` | 文本 | 是 | 助手需要回应的 user 轮次 |

### 输出格式

job 输出为文本流 —— HTTP 响应逐步交付 chunk，`${output as stream/text}` 指示 model-compose 将流原样转发给客户端。

## 自定义

### 更大模型

```yaml
component:
  model: Qwen/Qwen2.5-7B-Instruct
  options:
    context_length: 8192
```

### 采样

```yaml
action:
  params:
    temperature: 0.9
    top_p: 0.95
    do_sample: true
```

## 故障排查

- **终端没有逐步输出**：在 `curl` 中加 `-N`，或禁用客户端缓冲，否则 chunk 会被缓冲，看起来像单次最终响应。
- **CUDA 显存不足**：降低 `mem_fraction_static` 或 `context_length`，或使用更小的模型。
- **流突然停止**：查看服务端日志 —— 引擎命中 `max_output_length` 或 stop sequence 时流式会终止。

## 参考

- `../sglang/` —— 一次返回完整响应的非流式版本
- `../vllm-stream/` —— vLLM 驱动下的相同流式工作流
