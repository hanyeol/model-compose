# Slack Bot MCP 服务器示例

此示例演示如何使用 model-compose 的 MCP（模型上下文协议）服务器功能创建 Slack 机器人，为 Slack 频道管理和消息传递提供多个工作流。

## 概述

此 MCP 服务器提供 Slack 集成工作流，包括：

1. **消息发送**：向 Slack 频道发送消息，支持附件
2. **频道管理**：列出可用频道并加入新频道
3. **MCP 服务器**：通过模型上下文协议公开工作流以实现 AI 代理集成
4. **多工作流**：在单个 MCP 服务器中演示多个相关工作流

## 准备工作

### 前置条件

- 已安装 model-compose 并在 PATH 中可用
- 具有适当权限的 Slack App
- Slack App 令牌（Bot User OAuth Token）

### Slack App 配置

1. 在 https://api.slack.com/apps 创建新的 Slack App
2. 在 "OAuth & Permissions" 下添加以下 OAuth 范围：
   - `channels:read` - 查看公共频道的基本信息
   - `channels:join` - 加入公共频道
   - `chat:write` - 以机器人身份发送消息
   - `groups:read` - 查看私有频道的基本信息（可选）

3. 将应用安装到您的工作区
4. 复制 "Bot User OAuth Token"（以 `xoxb-` 开头）

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/mcp-servers/slack-bot
   ```

2. 复制示例环境文件：
   ```bash
   cp .env.sample .env
   ```

3. 编辑 `.env` 并添加您的 Slack 凭据：
   ```env
   SLACK_APP_TOKEN=xoxb-your-actual-bot-token
   DEFAULT_SLACK_CHANNEL_ID=C1234567890
   ```

## 运行方法

1. **启动服务：**
   ```bash
   model-compose up
   ```
2. **运行工作流：**

   **使用 MCP 客户端：**
   - 连接到 MCP 服务器：http://localhost:8080/mcp
   - 可用工作流：send-message、list-channels、join-channel
   - 使用兼容 MCP 的客户端执行工作流

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 选择所需的工作流（send-message、list-channels、join-channel）
   - 输入必需的参数
   - 点击 "Run" 按钮

   **使用 CLI：**
   ```bash
   # 向默认频道发送消息
   model-compose run send-message --input '{"messsage": "Hello from model-compose!"}'

   # 发送到特定频道
   model-compose run send-message --input '{
     "channel": "C1234567890",
     "messsage": "Hello specific channel!"
   }'

   # 列出频道
   model-compose run list-channels

   # 加入频道
   model-compose run join-channel --input '{"channel": "C1234567890"}'
   ```

## 组件详情

### Slack API HTTP Client 组件（默认）
- **类型**：具有多个操作的 HTTP client 组件
- **目的**：Slack Web API 集成
- **基础 URL**：`https://slack.com/api`
- **身份验证**：使用 `SLACK_APP_TOKEN` 的 Bearer 令牌
- **操作**：
  - **chat-post-message**：向频道发送消息
  - **conversations-list**：检索频道列表
  - **conversations-join**：加入公共频道
- **功能**：
  - 自动 OAuth 令牌处理
  - JSON 和 URL 编码请求支持
  - 响应数据过滤和转换
  - Slack API 响应的错误处理

## 工作流详情

### "向 Slack 频道发送消息" 工作流

**描述**：使用 Slack Web API 向指定的 Slack 频道发送文本消息

#### 作业流程

```mermaid
graph TD
    %% Default job (implicit)
    J1((send-message<br/>job))

    %% Component
    C1[Slack API<br/>component]

    %% Job to component connections
    J1 --> C1
    C1 -.-> |API response| J1

    %% Input/Output
    Input((Input)) --> J1
    J1 --> Output((Output))
```

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|-----------|------|----------|---------|-------------|
| `channel` | text | 否 | `DEFAULT_SLACK_CHANNEL_ID` | 用于发送消息的 Slack 频道 ID |
| `message` | text | 是 | - | 要发送到 Slack 的消息 |
| `attachments` | object[] | 否 | - | 可选的消息附件 |

#### 输出格式

| 字段 | 类型 | 描述 |
|-------|------|-------------|
| - | json | 完整的 Slack API 响应，包括消息元数据 |

### "列出 Slack 频道" 工作流

**描述**：检索 Slack 工作区中所有可用频道的列表

#### 作业流程

```mermaid
graph TD
    %% Default job (implicit)
    J1((list-channels<br/>job))

    %% Component
    C1[Slack API<br/>component]

    %% Job to component connections
    J1 --> C1
    C1 -.-> |channel list| J1

    %% Input/Output
    Input((Input)) --> J1
    J1 --> Output((Output))
```

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|-----------|------|----------|---------|-------------|
| `limit` | integer | 否 | 200 | 要检索的最大频道数 |

#### 输出格式

| 字段 | 类型 | 描述 |
|-------|------|-------------|
| - | object[] | 具有 `id` 和 `name` 字段的频道对象数组 |

### "加入 Slack 频道" 工作流

**描述**：为机器人用户加入指定的 Slack 频道

#### 作业流程

```mermaid
graph TD
    %% Default job (implicit)
    J1((join-channel<br/>job))

    %% Component
    C1[Slack API<br/>component]

    %% Job to component connections
    J1 --> C1
    C1 -.-> |join result| J1

    %% Input/Output
    Input((Input)) --> J1
    J1 --> Output((Output))
```

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|-----------|------|----------|---------|-------------|
| `channel` | text | 否 | `DEFAULT_SLACK_CHANNEL_ID` | 要加入的 Slack 频道 ID |

#### 输出格式

| 字段 | 类型 | 描述 |
|-------|------|-------------|
| - | json | 完整的 Slack API 响应，包括频道加入状态 |

## MCP 服务器集成

此示例作为 MCP 服务器，可以与支持模型上下文协议的 AI 代理和工具集成：

### 连接详情
- **传输**：HTTP
- **端点**：`http://localhost:8080/mcp`
- **协议**：模型上下文协议 v1.0

### 可用工具
AI 代理可以将这些工作流作为工具访问：
- `send-message`：向 Slack 发送消息
- `list-channels`：获取可用频道
- `join-channel`：加入公共频道

## Slack Web API 参考

### 使用的端点

1. **chat.postMessage**
   - **目的**：向频道发送消息
   - **文档**：https://api.slack.com/methods/chat.postMessage

2. **conversations.list**
   - **目的**：列出对话（频道）
   - **文档**：https://api.slack.com/methods/conversations.list

3. **conversations.join**
   - **目的**：加入对话
   - **文档**：https://api.slack.com/methods/conversations.join

## 错误处理

常见的 Slack API 错误和解决方案：

### 身份验证错误
- **invalid_auth**：检查您的 `SLACK_APP_TOKEN` 是否正确
- **token_revoked**：在 Slack App 设置中重新生成您的机器人令牌

### 权限错误
- **missing_scope**：向您的 Slack App 添加所需的 OAuth 范围
- **channel_not_found**：验证频道 ID 是否正确
- **not_in_channel**：机器人需要添加到私有频道

### 速率限制
- Slack API 有速率限制 - 如果超出，机器人将收到 `rate_limited` 错误
- 实施重试逻辑或减少请求频率

## 自定义

### 添加更多 Slack 操作
使用其他 Slack API 方法扩展组件：

```yaml
actions:
  - id: users-list
    path: /users.list
    method: GET
    headers:
      Content-Type: application/x-www-form-urlencoded
    output: ${response.members}
```

### 创建自定义工作流
在单个工作流中组合多个操作：

```yaml
workflows:
  - id: notify-and-join
    jobs:
      - id: join
        action: conversations-join
        input:
          channel: ${input.channel}
      - id: notify
        action: chat-post-message
        input:
          channel: ${input.channel}
          text: "Bot has joined the channel!"
        depends_on: [join]
```

### 特定于环境的配置
为不同环境使用不同的令牌：

```yaml
headers:
  Authorization: Bearer ${env.SLACK_BOT_TOKEN_PROD | ${env.SLACK_BOT_TOKEN_DEV}}
```

## 安全考虑

- **令牌安全**：永远不要将令牌提交到版本控制
- **范围限制**：仅请求必要的 OAuth 范围
- **频道权限**：注意公共频道与私有频道的访问权限
- **消息内容**：在发送之前验证和清理用户输入
- **速率限制**：实施适当的请求节流

## 故障排除

### 常见问题

1. **令牌无效**：验证机器人令牌以 `xoxb-` 开头并具有正确的权限
2. **未找到频道**：使用频道 ID（以 `C` 开头）而不是频道名称
3. **机器人不在频道中**：手动将机器人添加到私有频道或使用公共频道
4. **MCP 连接问题**：确保 MCP 服务器在正确的端口上运行

### 调试提示

- 使用 Slack 的 API 测试器：https://api.slack.com/methods
- 检查 Slack App 事件日志以查找权限问题
- 监控 MCP 服务器日志以获取请求/响应详情
- 在 MCP 上下文中使用之前测试各个工作流
