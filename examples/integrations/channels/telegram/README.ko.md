# Telegram 봇

웹훅으로 메시지를 수신하여 OpenAI GPT-4o로 처리한 뒤 사용자에게 답장을 전송하는 Telegram 봇입니다.

## 설정

### 1. Telegram 봇 생성

1. Telegram을 열고 [@BotFather](https://t.me/BotFather)를 검색
2. `/newbot`을 전송하고 안내에 따라 진행
3. 발급받은 봇 토큰 복사

### 2. 환경 변수 설정

```bash
export TELEGRAM_BOT_TOKEN=<your-bot-token>
export OPENAI_API_KEY=<your-openai-api-key>
```

### 3. 서비스 시작

```bash
model-compose up
```

### 4. 리스너 노출

리스너는 `8091` 포트에서 실행됩니다. ngrok 등으로 인터넷에 노출합니다:

```bash
ngrok http 8091
```

### 5. 웹훅 등록

```bash
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://<your-ngrok-url>/webhook"}'
```

## 동작 방식

```
Telegram --> listener (POST /webhook) --> handle-message 워크플로우
                                            |
                                            +--> generate-reply (OpenAI GPT-4o)
                                            |
                                            +--> send-reply (Telegram sendMessage API)
```

1. Telegram이 웹훅을 통해 `http-trigger` 리스너로 수신 메시지를 전송
2. `generate-reply` 잡이 메시지를 OpenAI GPT-4o에 보내 응답을 생성
3. `send-reply` 잡이 Telegram `sendMessage` API를 통해 생성된 응답을 사용자에게 전송
