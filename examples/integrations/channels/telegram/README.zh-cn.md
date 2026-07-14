# Telegram 机器人

一个通过 webhook 接收消息、使用 OpenAI GPT-4o 处理消息，并将回复发送回用户的 Telegram 机器人。

## 设置

### 1. 创建 Telegram 机器人

1. 打开 Telegram 并搜索 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot` 并按照说明操作
3. 复制机器人 token

### 2. 设置环境变量

```bash
export TELEGRAM_BOT_TOKEN=<your-bot-token>
export OPENAI_API_KEY=<your-openai-api-key>
```

### 3. 启动服务

```bash
model-compose up
```

### 4. 暴露监听器

监听器在 `8091` 端口运行。使用 ngrok 或类似工具将其暴露到互联网：

```bash
ngrok http 8091
```

### 5. 注册 Webhook

```bash
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://<your-ngrok-url>/webhook"}'
```

## 工作原理

```
Telegram --> listener (POST /webhook) --> handle-message 工作流
                                            |
                                            +--> generate-reply (OpenAI GPT-4o)
                                            |
                                            +--> send-reply (Telegram sendMessage API)
```

1. Telegram 通过 webhook 将传入消息发送到 `http-trigger` 监听器
2. `generate-reply` 作业将消息发送到 OpenAI GPT-4o 以生成响应
3. `send-reply` 作业通过 Telegram 的 `sendMessage` API 将生成的响应发送回用户
