# vLLM 流式聊天补全示例

此示例演示如何使用本地 vLLM 服务器和 Qwen2-7B-Instruct 模型创建流式聊天界面，提供实时流式响应。

## 概述

此工作流提供流式聊天界面：

1. **本地模型服务**：自动设置和管理带 Qwen2-7B-Instruct 模型的 vLLM 服务器
2. **流式聊天补全**：使用本地模型生成实时流式响应
3. **服务器发送事件**：通过 SSE（Server-Sent Events）提供实时用户体验的响应
4. **温度控制**：允许通过温度参数自定义响应创造性

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- Python 环境管理（推荐使用 pyenv）
- 运行 Qwen2-7B-Instruct 模型所需的足够系统资源

### 为什么使用 pyenv

此示例使用 pyenv 为 vLLM 创建隔离的 Python 环境，以避免与 model-compose 的依赖冲突：

**环境隔离的好处：**
- model-compose 在自己的 Python 环境中运行
- vLLM 在单独的隔离环境（`vllm` 虚拟环境）中运行
- 两个系统仅通过 HTTP API 通信，允许完全的运行时隔离
- model-compose 更新不会影响 vLLM 环境
- vLLM 模型或版本更改不会影响 model-compose
- 每个系统可以使用优化的依赖版本

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/vllm-chat-completion-stream
   ```

2. 确保您有足够的磁盘空间和 RAM（推荐：16GB+ RAM 用于 7B 模型）

## 运行方式

1. **启动服务（首次运行将安装 vLLM）：**
   ```bash
   model-compose up
   ```

2. **等待安装和模型加载：**
   - 首次运行：10-30 分钟（下载模型并安装 vLLM）
   - 后续运行：2-5 分钟（仅模型加载）

3. **运行工作流：**

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "prompt": "Explain the benefits of local AI models",
         "temperature": 0.7
       }
     }'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 输入您的提示词和设置
   - 点击"运行工作流"按钮

   **使用 CLI：**
   ```bash
   model-compose run --input '{
     "prompt": "Explain the benefits of local AI models",
     "temperature": 0.7
   }'
   ```

## 组件详情

### vLLM 聊天服务器组件 (vllm-server)
- **类型**：具有托管生命周期的 HTTP 服务器组件
- **用途**：具有流式聊天补全的本地 AI 模型服务
- **模型**：Qwen/Qwen2-7B-Instruct（70 亿参数指令调优模型）
- **服务器**：vLLM OpenAI 兼容 API 服务器
- **端口**：8000（内部）
- **功能**：
  - 自动模型下载和设置
  - 使用 `streaming: true` 的实时流式响应
  - 可配置的温度和最大 token
  - 服务器发送事件输出格式
  - JSON 流解析用于提取 delta 内容
  - 最大上下文长度：2048 token
  - 最大响应长度：512 token

## 工作流详情

### "与 vLLM 服务器聊天"工作流（默认）

**描述**：使用本地 vLLM 服务器和 Qwen2-7B-Instruct 模型生成流式文本响应

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|-----------|------|----------|---------|-------------|
| `prompt` | text | 是 | - | 要发送给 AI 的用户消息 |
| `temperature` | number | 否 | 0.7 | 控制响应的随机性 (0.0-1.0)<br/>• 较低值（如 0.2）：更专注和确定性<br/>• 较高值（如 0.8）：更有创造性和多样性 |

#### 输出格式

| 字段 | 类型 | 描述 |
|-------|------|-------------|
| - | text (sse-text) | 作为服务器发送事件流传递的 AI 生成响应文本 |

## 模型信息

### Qwen2-7B-Instruct
- **开发者**：阿里云
- **参数**：70 亿
- **类型**：指令调优的大型语言模型
- **语言**：主要是中文和英文
- **专长**：一般对话、指令跟随、推理任务
- **上下文长度**：最多 2048 token（配置限制）
- **许可证**：Apache 2.0

## 系统要求

### 最低要求
- **RAM**：16GB（推荐 24GB+）
- **GPU**：NVIDIA GPU，8GB+ VRAM（可选但推荐）
- **磁盘空间**：20GB+ 用于模型存储
- **CPU**：多核处理器（推荐 8+ 核）

### 性能说明
- 首次启动可能需要几分钟下载模型
- GPU 加速显著提高响应速度
- 模型加载需要大量内存分配

## 自定义

### 模型选择
在配置中替换模型：
```yaml
start:
  - python -m vllm.entrypoints.openai.api_server --model microsoft/DialoGPT-medium --port 8000
```

### 服务器配置
修改 vLLM 服务器参数：
```yaml
start:
  - python -m vllm.entrypoints.openai.api_server
    --model Qwen/Qwen2-7B-Instruct
    --port 8000
    --max-model-len 4096
    --gpu-memory-utilization 0.8
```

### 响应参数
调整生成设置：
```yaml
body:
  model: qwen2-7b-instruct
  max_tokens: ${input.max_tokens as number | 1024}
  temperature: ${input.temperature as number | 0.7}
  top_p: ${input.top_p as number | 0.9}
  streaming: true
```

## 与 OpenAI 的比较

| 功能 | vLLM（本地） | OpenAI（云端） |
|---------|--------------|----------------|
| 成本 | 仅硬件/电费 | 按 token 计费 |
| 隐私 | 完全本地处理 | 数据发送到 OpenAI |
| 延迟 | 取决于本地硬件 | 网络 + API 延迟 |
| 模型控制 | 完全模型选择 | 有限的模型选项 |
| 可扩展性 | 受硬件限制 | 弹性云扩展 |
| 设置复杂度 | 需要本地设置 | 仅需 API 密钥 |
| 自定义 | 高（可进行微调） | 仅限 API 参数 |
