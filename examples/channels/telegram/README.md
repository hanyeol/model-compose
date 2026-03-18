# Telegram Bot

A Telegram bot that receives messages via webhook, processes them with OpenAI GPT-4o, and sends replies back to the user.

## Setup

### 1. Create a Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the instructions
3. Copy the bot token

### 2. Set Environment Variables

```bash
export TELEGRAM_BOT_TOKEN=<your-bot-token>
export OPENAI_API_KEY=<your-openai-api-key>
```

### 3. Start the Service

```bash
model-compose up
```

### 4. Expose the Listener

The listener runs on port `8091`. Expose it to the internet using ngrok or similar:

```bash
ngrok http 8091
```

### 5. Register the Webhook

```bash
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://<your-ngrok-url>/webhook"}'
```

## How It Works

```
Telegram --> listener (POST /webhook) --> handle-message workflow
                                            |
                                            +--> generate-reply (OpenAI GPT-4o)
                                            |
                                            +--> send-reply (Telegram sendMessage API)
```

1. Telegram sends incoming messages to the `http-trigger` listener via webhook
2. The `generate-reply` job sends the message to OpenAI GPT-4o to generate a response
3. The `send-reply` job sends the generated response back to the user via Telegram's `sendMessage` API
