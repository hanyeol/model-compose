# 10장: 외부 서비스 통합

이 장에서는 OpenAI, Anthropic, Google, ElevenLabs 등 외부 AI 서비스를 model-compose와 통합하는 방법을 다룹니다.

---

## 10.1 OpenAI API

OpenAI API는 GPT 모델, DALL-E 이미지 생성, 오디오 처리 등 다양한 AI 기능을 제공합니다.

### 10.1.1 Chat Completions

GPT 모델을 사용한 대화형 텍스트 생성입니다.

**기본 설정:**

```yaml
component:
  type: http-client
  base_url: https://api.openai.com/v1
  action:
    path: /chat/completions
    method: POST
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
      Content-Type: application/json
    body:
      model: gpt-4o
      messages:
        - role: user
          content: ${input.prompt as text}
      temperature: ${input.temperature as number | 0.7}
    output:
      message: ${response.choices[0].message.content}
```

환경 변수 설정:
```bash
export OPENAI_API_KEY=sk-proj-...
model-compose up
```

**시스템 프롬프트 포함:**

```yaml
component:
  type: http-client
  action:
    endpoint: https://api.openai.com/v1/chat/completions
    method: POST
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
      Content-Type: application/json
    body:
      model: gpt-4o
      messages:
        - role: system
          content: "You are a helpful assistant."
        - role: user
          content: ${input.prompt as text}
      temperature: 0.7
      max_tokens: 1000
    output:
      message: ${response.choices[0].message.content}
      tokens: ${response.usage.total_tokens}
```

**사용 가능한 모델:**
- `gpt-4o`: 최신 GPT-4 Omni
- `gpt-4o-mini`: 경량 GPT-4 Omni
- `gpt-4-turbo`: GPT-4 Turbo
- `gpt-3.5-turbo`: GPT-3.5 Turbo

**주요 파라미터:**
- `temperature`: 생성 랜덤성 (0.0~2.0)
- `max_tokens`: 최대 생성 토큰 수
- `top_p`: Nucleus sampling
- `frequency_penalty`: 단어 반복 패널티
- `presence_penalty`: 주제 반복 패널티

### 10.1.2 Image Generation (DALL-E)

텍스트 프롬프트에서 이미지를 생성합니다.

**DALL-E 3 사용:**

```yaml
component:
  type: http-client
  action:
    endpoint: https://api.openai.com/v1/images/generations
    method: POST
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
      Content-Type: application/json
    body:
      model: dall-e-3
      prompt: ${input.prompt}
      n: 1
      size: 1024x1024
      quality: standard
      response_format: url
    output:
      image_url: ${response.data[0].url}
```

**DALL-E 2 사용:**

```yaml
component:
  type: http-client
  action:
    endpoint: https://api.openai.com/v1/images/generations
    method: POST
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
      Content-Type: application/json
    body:
      model: dall-e-2
      prompt: ${input.prompt}
      n: 1
      size: 1024x1024
      response_format: url
    output:
      image_url: ${response.data[0].url}
```

**다중 액션 컴포넌트:**

```yaml
component:
  type: http-client
  base_url: https://api.openai.com/v1
  headers:
    Authorization: Bearer ${env.OPENAI_API_KEY}
    Content-Type: application/json
  actions:
    - id: dall-e-3
      path: /images/generations
      method: POST
      body:
        model: dall-e-3
        prompt: ${input.prompt}
        n: 1
        size: 1024x1024
        response_format: url
      output:
        image_url: ${response.data[0].url}

    - id: dall-e-2
      path: /images/generations
      method: POST
      body:
        model: dall-e-2
        prompt: ${input.prompt}
        n: 1
        size: 512x512
      output:
        image_url: ${response.data[0].url}
```

**지원 이미지 크기:**
- DALL-E 3: `1024x1024`, `1024x1792`, `1792x1024`
- DALL-E 2: `256x256`, `512x512`, `1024x1024`

### 10.1.3 Audio (TTS, Transcriptions)

**Text-to-Speech (TTS):**

```yaml
component:
  type: http-client
  action:
    endpoint: https://api.openai.com/v1/audio/speech
    method: POST
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
      Content-Type: application/json
    body:
      model: tts-1
      input: ${input.text}
      voice: nova
      response_format: mp3
    output: ${response as audio}
```

**사용 가능한 음성:**
- `alloy`, `ash`, `ballad`, `coral`, `echo`, `fable`
- `nova`, `onyx`, `sage`, `shimmer`, `verse`

**TTS 모델:**
- `tts-1`: 표준 품질, 빠른 응답
- `tts-1-hd`: 고품질
- `gpt-4o-mini-tts`: GPT-4o Mini TTS

**Speech-to-Text (Transcription):**

```yaml
component:
  type: http-client
  action:
    endpoint: https://api.openai.com/v1/audio/transcriptions
    method: POST
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
    body:
      model: whisper-1
      file: ${input.audio_file as file}
      language: ko
    output:
      text: ${response.text}
```

---

## 10.2 Anthropic Claude API

Anthropic의 Claude 모델을 사용합니다.

**기본 설정:**

```yaml
component:
  type: http-client
  action:
    endpoint: https://api.anthropic.com/v1/messages
    method: POST
    headers:
      x-api-key: ${env.ANTHROPIC_API_KEY}
      anthropic-version: "2023-06-01"
      Content-Type: application/json
    body:
      model: claude-3-5-sonnet-20241022
      max_tokens: 1024
      messages:
        - role: user
          content: ${input.prompt as text}
    output:
      message: ${response.content[0].text}
```

환경 변수 설정:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
model-compose up
```

**사용 가능한 모델:**
- `claude-3-5-sonnet-20241022`: 최신 Claude 3.5 Sonnet
- `claude-3-5-haiku-20241022`: Claude 3.5 Haiku (빠르고 경량)
- `claude-3-opus-20240229`: Claude 3 Opus (최고 성능)
- `claude-3-sonnet-20240229`: Claude 3 Sonnet
- `claude-3-haiku-20240307`: Claude 3 Haiku

**시스템 프롬프트:**

```yaml
component:
  type: http-client
  action:
    endpoint: https://api.anthropic.com/v1/messages
    method: POST
    headers:
      x-api-key: ${env.ANTHROPIC_API_KEY}
      anthropic-version: "2023-06-01"
      Content-Type: application/json
    body:
      model: claude-3-5-sonnet-20241022
      max_tokens: 2048
      system: "You are a helpful AI assistant."
      messages:
        - role: user
          content: ${input.prompt as text}
    output:
      message: ${response.content[0].text}
```

**주요 파라미터:**
- `max_tokens`: 최대 생성 토큰 수 (필수)
- `temperature`: 생성 랜덤성 (0.0~1.0)
- `top_p`: Nucleus sampling
- `top_k`: Top-K sampling

---

## 10.3 Google Gemini API

Google의 Gemini 모델을 사용합니다.

**기본 설정:**

```yaml
component:
  type: http-client
  action:
    endpoint: https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent
    method: POST
    params:
      key: ${env.GOOGLE_API_KEY}
    headers:
      Content-Type: application/json
    body:
      contents:
        - parts:
            - text: ${input.prompt as text}
    output:
      message: ${response.candidates[0].content.parts[0].text}
```

환경 변수 설정:
```bash
export GOOGLE_API_KEY=AIza...
model-compose up
```

**사용 가능한 모델:**
- `gemini-2.0-flash-exp`: Gemini 2.0 Flash (실험)
- `gemini-1.5-pro-latest`: Gemini 1.5 Pro (최신)
- `gemini-1.5-flash-latest`: Gemini 1.5 Flash (빠름)
- `gemini-pro`: Gemini Pro

**멀티모달 (텍스트 + 이미지):**

```yaml
component:
  type: http-client
  action:
    endpoint: https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro-latest:generateContent
    method: POST
    params:
      key: ${env.GOOGLE_API_KEY}
    headers:
      Content-Type: application/json
    body:
      contents:
        - parts:
            - text: ${input.prompt as text}
            - inline_data:
                mime_type: image/jpeg
                data: ${input.image as base64}
    output:
      message: ${response.candidates[0].content.parts[0].text}
```

**생성 설정:**

```yaml
component:
  type: http-client
  action:
    endpoint: https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent
    method: POST
    params:
      key: ${env.GOOGLE_API_KEY}
    body:
      contents:
        - parts:
            - text: ${input.prompt as text}
      generationConfig:
        temperature: 0.7
        topK: 40
        topP: 0.95
        maxOutputTokens: 1024
    output:
      message: ${response.candidates[0].content.parts[0].text}
```

---

## 10.4 ElevenLabs (TTS)

ElevenLabs는 고품질 음성 합성 서비스를 제공합니다.

**기본 설정:**

```yaml
component:
  type: http-client
  action:
    endpoint: https://api.elevenlabs.io/v1/text-to-speech/${input.voice_id | JBFqnCBsd6RMkjVDRZzb}
    method: POST
    headers:
      xi-api-key: ${env.ELEVENLABS_API_KEY}
      Content-Type: application/json
    params:
      output_format: mp3_44100_128
    body:
      text: ${input.text}
      model_id: eleven_multilingual_v2
    output: ${response as audio}
```

환경 변수 설정:
```bash
export ELEVENLABS_API_KEY=sk_...
model-compose up
```

**사용 가능한 모델:**
- `eleven_multilingual_v2`: 다국어 지원 v2
- `eleven_turbo_v2_5`: Turbo v2.5 (빠름)
- `eleven_turbo_v2`: Turbo v2
- `eleven_monolingual_v1`: 영어 전용 v1

**음성 설정:**

```yaml
component:
  type: http-client
  action:
    endpoint: https://api.elevenlabs.io/v1/text-to-speech/${input.voice_id}
    method: POST
    headers:
      xi-api-key: ${env.ELEVENLABS_API_KEY}
      Content-Type: application/json
    params:
      output_format: mp3_44100_192
    body:
      text: ${input.text}
      model_id: eleven_multilingual_v2
      voice_settings:
        stability: 0.5
        similarity_boost: 0.75
        style: 0.0
        use_speaker_boost: true
    output: ${response as audio}
```

**출력 포맷:**
- `mp3_22050_32`: MP3 22kHz 32kbps
- `mp3_44100_64`: MP3 44kHz 64kbps
- `mp3_44100_96`: MP3 44kHz 96kbps
- `mp3_44100_128`: MP3 44kHz 128kbps (권장)
- `mp3_44100_192`: MP3 44kHz 192kbps (고품질)
- `pcm_16000`: PCM 16kHz
- `pcm_22050`: PCM 22kHz
- `pcm_24000`: PCM 24kHz
- `pcm_44100`: PCM 44kHz

**인기 음성 ID:**
- `JBFqnCBsd6RMkjVDRZzb`: George (남성, 영어)
- `EXAVITQu4vr4xnSDxMaL`: Sarah (여성, 영어)
- `21m00Tcm4TlvDq8ikWAM`: Rachel (여성, 영어)

---

## 10.5 Stability AI (Image Generation)

Stability AI의 Stable Diffusion 모델을 사용합니다.

**Stable Diffusion 3:**

```yaml
component:
  type: http-client
  action:
    endpoint: https://api.stability.ai/v2beta/stable-image/generate/sd3
    method: POST
    headers:
      Authorization: Bearer ${env.STABILITY_API_KEY}
      Content-Type: multipart/form-data
    body:
      prompt: ${input.prompt}
      model: sd3-large
      aspect_ratio: "1:1"
      output_format: png
    output:
      image: ${response.image as base64}
```

환경 변수 설정:
```bash
export STABILITY_API_KEY=sk-...
model-compose up
```

**사용 가능한 모델:**
- `sd3-large`: Stable Diffusion 3 Large
- `sd3-large-turbo`: Stable Diffusion 3 Large Turbo (빠름)
- `sd3-medium`: Stable Diffusion 3 Medium

**Stable Diffusion XL:**

```yaml
component:
  type: http-client
  action:
    endpoint: https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image
    method: POST
    headers:
      Authorization: Bearer ${env.STABILITY_API_KEY}
      Content-Type: application/json
    body:
      text_prompts:
        - text: ${input.prompt}
          weight: 1
      cfg_scale: 7
      height: 1024
      width: 1024
      steps: 30
      samples: 1
    output:
      image: ${response.artifacts[0].base64}
```

**주요 파라미터:**
- `cfg_scale`: 프롬프트 강도 (0~35)
- `steps`: 생성 스텝 수 (10~50)
- `samples`: 생성할 이미지 수
- `aspect_ratio`: 이미지 비율 (`1:1`, `16:9`, `9:16` 등)

---

## 10.6 Replicate

Replicate는 다양한 AI 모델을 API로 제공하는 플랫폼입니다.

**기본 설정:**

```yaml
component:
  type: http-client
  action:
    endpoint: https://api.replicate.com/v1/predictions
    method: POST
    headers:
      Authorization: Bearer ${env.REPLICATE_API_TOKEN}
      Content-Type: application/json
    body:
      version: ${input.model_version}
      input: ${input.params}
    output:
      prediction_id: ${response.id}
      status: ${response.status}
```

환경 변수 설정:
```bash
export REPLICATE_API_TOKEN=r8_...
model-compose up
```

**FLUX 이미지 생성:**

```yaml
component:
  type: http-client
  action:
    endpoint: https://api.replicate.com/v1/predictions
    method: POST
    headers:
      Authorization: Bearer ${env.REPLICATE_API_TOKEN}
      Content-Type: application/json
    body:
      version: "black-forest-labs/flux-schnell"
      input:
        prompt: ${input.prompt}
        num_inference_steps: 4
        guidance_scale: 0
    output:
      prediction_id: ${response.id}
```

**Llama 3 텍스트 생성:**

```yaml
component:
  type: http-client
  action:
    endpoint: https://api.replicate.com/v1/predictions
    method: POST
    headers:
      Authorization: Bearer ${env.REPLICATE_API_TOKEN}
      Content-Type: application/json
    body:
      version: "meta/meta-llama-3-70b-instruct"
      input:
        prompt: ${input.prompt}
        max_new_tokens: 512
        temperature: 0.7
    output:
      prediction_id: ${response.id}
```

**인기 모델:**
- `black-forest-labs/flux-schnell`: FLUX 이미지 생성
- `stability-ai/sdxl`: Stable Diffusion XL
- `meta/meta-llama-3-70b-instruct`: Llama 3 70B
- `openai/whisper`: Whisper 음성 인식

---

## 10.7 커스텀 HTTP API

임의의 HTTP API를 통합할 수 있습니다.

**기본 REST API:**

```yaml
component:
  type: http-client
  action:
    endpoint: https://api.example.com/v1/process
    method: POST
    headers:
      Authorization: Bearer ${env.API_KEY}
      Content-Type: application/json
    body:
      input: ${input.data}
      options:
        param1: value1
        param2: ${input.param2}
    output:
      result: ${response.result}
```

**인증 방식:**

**Bearer Token:**
```yaml
headers:
  Authorization: Bearer ${env.API_KEY}
```

**API Key:**
```yaml
headers:
  X-API-Key: ${env.API_KEY}
```

**Basic Auth:**
```yaml
headers:
  Authorization: Basic ${env.BASIC_AUTH_CREDENTIALS}
```

**다중 엔드포인트:**

```yaml
component:
  type: http-client
  base_url: https://api.example.com
  headers:
    Authorization: Bearer ${env.API_KEY}
    Content-Type: application/json
  actions:
    - id: create
      path: /v1/items
      method: POST
      body: ${input}
      output: ${response}

    - id: get
      path: /v1/items/${input.id}
      method: GET
      output: ${response}

    - id: update
      path: /v1/items/${input.id}
      method: PUT
      body: ${input.data}
      output: ${response}

    - id: delete
      path: /v1/items/${input.id}
      method: DELETE
      output: ${response}
```

**쿼리 파라미터:**

```yaml
component:
  type: http-client
  action:
    endpoint: https://api.example.com/v1/search
    method: GET
    headers:
      Authorization: Bearer ${env.API_KEY}
    params:
      q: ${input.query}
      limit: ${input.limit | 10}
      offset: ${input.offset | 0}
    output: ${response.results}
```

**타임아웃 설정:**

```yaml
component:
  type: http-client
  timeout: 30000  # 30초
  action:
    endpoint: https://api.example.com/v1/process
    method: POST
    headers:
      Authorization: Bearer ${env.API_KEY}
    body: ${input}
    output: ${response}
```

**재시도 설정:**

```yaml
component:
  type: http-client
  retry:
    max_retry_count: 3
    delay: 1000  # 1초
    backoff: 2   # 지수 백오프
  action:
    endpoint: https://api.example.com/v1/process
    method: POST
    headers:
      Authorization: Bearer ${env.API_KEY}
    body: ${input}
    output: ${response}
```

---

## 10.8 외부 서비스 통합 모범 사례

### 1. 환경 변수로 API 키 관리

API 키를 코드에 하드코딩하지 마세요:

```yaml
# Good
headers:
  Authorization: Bearer ${env.OPENAI_API_KEY}

# Bad
headers:
  Authorization: Bearer sk-hardcoded-key
```

### 2. 에러 처리

```yaml
workflow:
  title: Robust API Call
  jobs:
    - id: api-call
      component: external-api
      input: ${input}
      output:
        result: ${output}
      on_error:
        - id: fallback
          component: fallback-service
          input: ${input}
```

### 3. 비용 최적화

- 적절한 모델 선택 (GPT-4o vs GPT-4o-mini)
- `max_tokens` 제한 설정
- 캐싱 활용

### 4. 속도 제한 준수

외부 API는 일반적으로 요청 속도 제한(rate limit)이 있습니다. 제한을 초과하면 요청이 거부되거나 추가 비용이 발생할 수 있습니다.

**컴포넌트 레벨 제한:**

```yaml
component:
  type: http-client
  rate_limit:
    requests_per_minute: 60    # 분당 최대 60회 요청
    requests_per_day: 10000    # 일당 최대 10,000회 요청
  action:
    endpoint: https://api.example.com/v1/process
    headers:
      Authorization: Bearer ${env.API_KEY}
    body: ${input}
```

**워크플로우에서 지연 추가:**

```yaml
workflow:
  jobs:
    - id: api-call-1
      component: external-api
      input: ${input}

    - id: delay
      component: shell
      command: [ "sleep", "1" ]  # 1초 대기

    - id: api-call-2
      component: external-api
      input: ${input}
```

일반적인 속도 제한:
- OpenAI: 분당 3,500 요청 (Tier 1), 10,000 요청 (Tier 2)
- Anthropic: 분당 50 요청 (Free), 1,000 요청 (Pro)
- Google Gemini: 분당 60 요청 (Free)

### 5. 로깅 및 모니터링

외부 API 사용 시 비용 관리와 문제 해결을 위해 사용량과 요청/응답 정보를 추적하는 것이 중요합니다.

**사용량 추적:**

API 응답에서 토큰 사용량을 추출하여 비용을 모니터링할 수 있습니다:

```yaml
workflow:
  jobs:
    - id: call-gpt
      component: openai-chat
      input: ${input}
      output:
        message: ${output.choices[0].message.content}
        prompt_tokens: ${output.usage.prompt_tokens}
        completion_tokens: ${output.usage.completion_tokens}
        total_tokens: ${output.usage.total_tokens}
```

출력된 토큰 정보를 로그에 기록하거나 데이터베이스에 저장하여 사용 패턴을 분석할 수 있습니다.

**요청/응답 로깅:**

디버깅과 추적을 위해 API 요청 ID와 메타데이터를 기록합니다:

```yaml
component:
  type: http-client
  base_url: https://api.openai.com/v1
  action:
    path: /chat/completions
    method: POST
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
    body: ${input}
    output:
      response: ${response}
      request_id: ${response.id}       # API 요청 추적용 ID
      model: ${response.model}         # 사용된 모델
      created: ${response.created}     # 타임스탬프
```

이 정보는 다음과 같은 경우에 유용합니다:
- API 제공사에 문제 보고 시 request_id 제공
- 응답 시간 분석 및 성능 모니터링
- 실제 사용된 모델 확인 (fallback 등으로 변경될 수 있음)

---

## 다음 단계

실습해보세요:
- 다양한 AI 서비스 API 통합
- 속도 제한 및 재시도 로직 구현
- 여러 서비스를 조합한 멀티모달 워크플로우
- 오류 핸들링 및 로깅 최적화

---

**다음 장**: [11. 스트리밍 모드](./11-streaming-mode.md)
