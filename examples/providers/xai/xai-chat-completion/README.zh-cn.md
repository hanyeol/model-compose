# xAI Chat Completion 示例

此示例演示如何通过 Chat Completions API 使用 xAI 的 Grok 模型创建简单的聊天界面。

## 概述

此工作流提供了一个简单的聊天界面：

1. **Chat Completion**：接受用户提示并使用 xAI 的 Grok-3 模型生成响应
2. **温度控制**：通过温度参数自定义响应的创造性

## 准备工作

### 前置要求

- 已安装 model-compose 并在 PATH 中可用
- xAI API 密钥

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/providers/xai/xai-chat-completion
   ```

2. 复制示例环境文件：
   ```bash
   cp .env.sample .env
   ```

3. 编辑 `.env` 并添加您的 xAI API 密钥：
   ```env
   XAI_API_KEY=your-actual-xai-api-key
   ```

## 运行方法

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
         "prompt": "Explain the importance of renewable energy",
         "temperature": 0.7
       }
     }'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 输入您的提示和设置
   - 点击 "Run Workflow" 按钮

   **使用 CLI：**
   ```bash
   model-compose run --input '{
     "prompt": "Explain the importance of renewable energy",
     "temperature": 0.7
   }'
   ```

## 组件详情

### xAI HTTP Client 组件（默认）
- **类型**：HTTP client 组件
- **用途**：AI 驱动的文本生成和聊天完成
- **API**：xAI Grok Chat Completions
- **端点**：`https://api.x.ai/v1/chat/completions`
- **功能**：
  - 可配置的温度以调整响应创造性
  - 支持各种提示类型和对话风格

## 工作流详情

### "Chat with Grok" 工作流（默认）

**描述**：使用 Grok 生成文本响应

#### 作业流程

此示例使用简化的单组件配置，没有显式作业。

```mermaid
graph TD
    %% Default job (implicit)
    J1((默认<br/>作业))

    %% Component
    C1[xAI Grok-3<br/>组件]

    %% Job to component connections (solid: invokes, dotted: returns)
    J1 --> C1
    C1 -.-> J1

    %% Input/Output
    Input((输入)) --> J1
    J1 --> Output((输出))
```

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `prompt` | text | 是 | - | 发送给 AI 的用户消息 |
| `temperature` | number | 否 | 0.7 | 控制响应的随机性 (0.0-1.0)<br/>• 较低值（例如 0.2）：更专注和确定性<br/>• 较高值（例如 0.8）：更有创造性和多样性 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `message` | text | AI 生成的响应文本 |

## 自定义

- **模型**：将 `grok-3` 更改为其他可用的 Grok 模型
- **系统提示**：添加系统消息以定义 AI 的行为和个性
- **附加参数**：包含其他 API 参数，如 `max_tokens`、`presence_penalty` 等
- **多条消息**：扩展以通过接受消息数组来支持对话历史

## 高级配置

要添加系统提示和对话历史：

```yaml
body:
  model: grok-3
  messages:
    - role: system
      content: "You are a helpful assistant specialized in technical explanations."
    - role: user
      content: ${input.prompt as text}
  temperature: ${input.temperature as number | 0.7}
  max_tokens: ${input.max_tokens as number | 1000}
```