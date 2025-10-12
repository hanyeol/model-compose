# 15. Practical Examples

This chapter provides step-by-step explanations of real-world use cases using model-compose. Each example includes complete configuration and execution instructions.

---

## 15.1 Building a Chatbot

### 15.1.1 OpenAI GPT-4o Chatbot

**Goal**: Build a simple conversational chatbot using OpenAI GPT-4o

**Configuration File** (`model-compose.yml`):

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
  webui:
    driver: gradio
    port: 8081

workflow:
  title: Chat with OpenAI GPT-4o
  description: Generate text responses using OpenAI's GPT-4o
  input: ${input}
  output: ${output}

component:
  type: http-client
  base_url: https://api.openai.com/v1
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

**Environment Variables** (`.env`):

```bash
OPENAI_API_KEY=sk-...
```

**How to Run**:

```bash
# Start controller
model-compose up

# Access Web UI
# http://localhost:8081
```

**Key Features**:
- Automatic Gradio Web UI generation
- Adjustable temperature parameter
- Real-time response display

### 15.1.2 Streaming Chatbot

**Goal**: Build a streaming chatbot with real-time typing effect

**Configuration File**:

```yaml
controller:
  type: http-server
  port: 8080
  webui:
    driver: gradio
    port: 8081

workflow:
  title: Streaming Chat
  output: ${output as text;sse-text}

component:
  type: http-client
  base_url: https://api.openai.com/v1
  path: /chat/completions
  method: POST
  headers:
    Authorization: Bearer ${env.OPENAI_API_KEY}
  body:
    model: gpt-4o
    messages:
      - role: user
        content: ${input.prompt as text}
    stream: true
  stream_format: json
  output: ${response[].choices[0].delta.content}
```

**Features**:
- Real-time streaming using SSE protocol
- Automatic typing effect in Gradio
- Immediate feedback for long responses

---

## 15.2 Voice Generation Pipeline

### 15.2.1 Text-to-Speech (OpenAI TTS)

**Goal**: Convert text to speech using OpenAI TTS API

**Configuration File**:

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
  webui:
    driver: gradio
    port: 8081

workflow:
  title: Generate Speech with OpenAI TTS
  description: Convert input text into natural-sounding speech using OpenAI's TTS models.
  jobs:
    - id: speak
      component: openai-text-to-speech
      input: ${input}
      output: ${output as audio}

components:
  - id: openai-text-to-speech
    type: http-client
    endpoint: https://api.openai.com/v1/audio/speech
    method: POST
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
      Content-Type: application/json
    body:
      model: ${input.model as select/tts-1,tts-1-hd,gpt-4o-mini-tts | tts-1}
      input: ${input.text}
      voice: ${input.voice as select/alloy,ash,ballad,coral,echo,fable,onyx,nova,sage,shimmer,verse | nova}
      response_format: mp3
    output: ${response}
```

**Supported Voices**:
- `alloy`, `ash`, `ballad`, `coral`, `echo`, `fable`
- `onyx`, `nova`, `sage`, `shimmer`, `verse`

**Supported Models**:
- `tts-1`: Fast response
- `tts-1-hd`: High-quality audio
- `gpt-4o-mini-tts`: Latest model

### 15.2.2 Inspiring Quote Voice Generation

**Goal**: Generate motivational quotes with GPT-4o and convert to speech with ElevenLabs TTS

**Configuration File**:

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
  webui:
    driver: gradio
    port: 8081

workflow:
  title: Inspire with Voice
  description: Generate a motivational quote using GPT-4o and bring it to life by converting it into natural speech with ElevenLabs TTS.
  jobs:
    - id: job-quote
      component: write-inspiring-quote
      input: ${input}
      output: ${output}

    - id: job-voice
      component: text-to-speech
      input:
        text: ${jobs.job-quote.output.quote}
        voice_id: ${input.voice_id | JBFqnCBsd6RMkjVDRZzb}
      output:
        quote: ${jobs.job-quote.output.quote}
        audio: ${output as audio/mp3;base64}
      depends_on: [ job-quote ]

components:
  - id: write-inspiring-quote
    type: http-client
    base_url: https://api.openai.com/v1
    path: /chat/completions
    method: POST
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
      Content-Type: application/json
    body:
      model: gpt-4o
      messages:
        - role: user
          content: |
            Write an inspiring quote similar to the example below.
            Don't say anything else—just give me the quote.
            Aim for around 30 words.
            Example – Never give up. If there's something you want to become, be proud of it. Give yourself a chance.
            Don't think you're worthless—there's nothing to gain from that. Aim high. That's how life should be lived.
    output:
      quote: ${response.choices[0].message.content}

  - id: text-to-speech
    type: http-client
    endpoint: https://api.elevenlabs.io/v1/text-to-speech/${input.voice_id}?output_format=mp3_44100_128
    method: POST
    headers:
      Content-Type: application/json
      xi-api-key: ${env.ELEVENLABS_API_KEY}
    body:
      text: ${input.text}
      model_id: eleven_multilingual_v2
    output: ${response as base64}
```

**Environment Variables**:

```bash
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=...
```

**Workflow Description**:
1. GPT-4o generates an inspiring quote
2. ElevenLabs API converts quote to speech
3. Web UI displays both text and audio

---

## 15.3 Image Analysis and Editing

### 15.3.1 Image Captioning (Image-to-Text)

**Goal**: Generate image descriptions using a local Vision model

**Configuration File**:

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
  webui:
    driver: gradio
    port: 8081

workflow:
  title: Generate Text from Image
  description: Generate text based on a given image using a pretrained vision model.
  input: ${input}
  output:
    generated: ${output}

component:
  type: model
  task: image-to-text
  model: Salesforce/blip-image-captioning-large
  architecture: blip
  image: ${input.image as image}
  prompt: ${input.prompt as text}
```

**Execution Example**:

```bash
# Run workflow
model-compose run default --input '{"image": "path/to/image.jpg", "prompt": "Describe this image"}'
```

**Supported Models**:
- `Salesforce/blip-image-captioning-large`
- `Salesforce/blip-image-captioning-base`
- `nlpconnect/vit-gpt2-image-captioning`

### 15.3.2 Image Editing (OpenAI DALL-E)

**Goal**: Edit images using OpenAI DALL-E

**Configuration File**:

```yaml
controller:
  type: http-server
  port: 8080
  webui:
    driver: gradio
    port: 8081

workflow:
  title: Edit Image with DALL-E
  description: Edit an existing image using OpenAI's DALL-E API
  component: dalle-edit
  input: ${input}
  output: ${output as image}

component:
  id: dalle-edit
  type: http-client
  endpoint: https://api.openai.com/v1/images/edits
  method: POST
  headers:
    Authorization: Bearer ${env.OPENAI_API_KEY}
  body:
    image: ${input.image as image}
    mask: ${input.mask as image}
    prompt: ${input.prompt as text}
    n: ${input.n as integer | 1}
    size: ${input.size as select/256x256,512x512,1024x1024 | 1024x1024}
  output: ${response.data[0].url}
```

**Use Cases**:
- Change image backgrounds
- Modify specific regions
- Style transfer

---

## 15.4 RAG System (Using Vector DB)

### 15.4.1 Text Embedding Search with ChromaDB

**Goal**: Generate text embeddings, store in ChromaDB, and perform similarity search

**Configuration File**:

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
  webui:
    driver: gradio
    port: 8081

workflows:
  - id: insert-sentence-embedding
    title: Insert Text Embedding
    description: Generate text embedding and insert it into ChromaDB vector store
    jobs:
      - id: embedding-sentence
        component: embedding-model
        input: ${input}
        output: ${output}

      - id: insert-embedding
        component: vector-store
        action: insert
        input:
          vector: ${jobs.embedding-sentence.output}
          metadata: ${input}
        output: ${output as json}
        depends_on: [ embedding-sentence ]

  - id: search-sentence-embeddings
    title: Search Similar Embeddings
    description: Generate query embedding and search for similar vectors in ChromaDB
    jobs:
      - id: embedding-sentence
        component: embedding-model
        input: ${input}
        output: ${output}

      - id: search-embeddings
        component: vector-store
        action: search
        input:
          vector: ${jobs.embedding-sentence.output}
        output: ${output as object[]/id,score,metadata.text}
        depends_on: [ embedding-sentence ]

  - id: delete-sentence-embedding
    title: Delete Text Embedding
    description: Remove a specific vector from the ChromaDB collection
    component: vector-store
    action: delete
    input: ${input}
    output: ${output as json}

components:
  - id: vector-store
    type: vector-store
    driver: chroma
    actions:
      - id: insert
        collection: test
        method: insert
        vector: ${input.vector}
        metadata: ${input.metadata}

      - id: search
        collection: test
        method: search
        query: ${input.vector}
        output_fields: [ text ]

      - id: delete
        collection: test
        method: delete
        vector_id: ${input.vector_id}

  - id: embedding-model
    type: model
    task: text-embedding
    model: sentence-transformers/all-MiniLM-L6-v2
    text: ${input.text}
```

**API Usage Examples**:

```bash
# 1. Insert text
curl -X POST http://localhost:8080/api/workflows/insert-sentence-embedding/runs \
  -H "Content-Type: application/json" \
  -d '{"input": {"text": "model-compose is a declarative AI orchestrator"}}'

# 2. Search similar text
curl -X POST http://localhost:8080/api/workflows/search-sentence-embeddings/runs \
  -H "Content-Type: application/json" \
  -d '{"input": {"text": "AI workflow tool"}}'

# 3. Delete
curl -X POST http://localhost:8080/api/workflows/delete-sentence-embedding/runs \
  -H "Content-Type: application/json" \
  -d '{"input": {"vector_id": "id123"}}'
```

### 15.4.2 RAG System with Milvus

**Goal**: High-performance RAG system using Milvus vector database

**Configuration File**:

```yaml
controller:
  type: http-server
  port: 8080

workflows:
  - id: rag-query
    title: RAG Query
    description: Retrieve relevant documents and generate answer
    jobs:
      - id: embed-query
        component: embedding-model
        input:
          text: ${input.query}
        output: ${output}

      - id: search-docs
        component: milvus-store
        action: search
        input:
          vector: ${jobs.embed-query.output}
        output: ${output}
        depends_on: [ embed-query ]

      - id: generate-answer
        component: llm
        input:
          context: ${jobs.search-docs.output}
          query: ${input.query}
        output: ${output}
        depends_on: [ search-docs ]

components:
  - id: embedding-model
    type: model
    task: text-embedding
    model: sentence-transformers/all-MiniLM-L6-v2
    text: ${input.text}

  - id: milvus-store
    type: vector-store
    driver: milvus
    host: localhost
    port: 19530
    actions:
      - id: search
        collection: documents
        method: search
        query: ${input.vector}
        top_k: 5
        output_fields: [ text, source ]

  - id: llm
    type: http-client
    base_url: https://api.openai.com/v1
    path: /chat/completions
    method: POST
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
    body:
      model: gpt-4o
      messages:
        - role: system
          content: Answer based on the following context: ${input.context}
        - role: user
          content: ${input.query}
    output: ${response.choices[0].message.content}
```

**Features**:
- 3-stage pipeline: Embedding → Search → Generation
- Milvus high-performance vector search
- Context-based answer generation using GPT-4o

---

## 15.5 Slack Bot (MCP)

### 15.5.1 Building a Slack Bot with MCP Server

**Goal**: Build a Slack bot using MCP (Model Context Protocol) server

**Configuration File**:

```yaml
controller:
  type: mcp-server
  base_path: /mcp
  port: 8080
  webui:
    driver: gradio
    port: 8081

workflows:
  - id: send-message
    title: Send Message to Slack Channel
    description: Send a text message to a specified Slack channel using the Slack Web API
    action: chat-post-message
    input:
      channel: ${input.channel | ${env.DEFAULT_SLACK_CHANNEL_ID} @(description Slack channel ID for sending a message)}
      text: ${input.message @(description Message to send to Slack)}
    output: ${output as json}

  - id: list-channels
    title: List Slack Channels
    description: Retrieve a list of all available channels in the Slack workspace
    action: conversations-list
    output: ${output as object[]}

  - id: join-channel
    title: Join Slack Channel
    description: Join a specified Slack channel for the bot user
    action: conversations-join
    input:
      channel: ${input.channel | ${env.DEFAULT_SLACK_CHANNEL_ID}}
    output: ${output as json}

component:
  type: http-client
  base_url: https://slack.com/api
  headers:
    Authorization: Bearer ${env.SLACK_APP_TOKEN}
  actions:
    - id: chat-post-message
      path: /chat.postMessage
      method: POST
      body:
        channel: ${input.channel}
        text: ${input.text}
        attachments: ${input.attachments}
      headers:
        Content-Type: application/json
      output: ${response}

    - id: conversations-list
      path: /conversations.list
      method: GET
      params:
        limit: ${input.limit as integer | 200 @(description Maximum number of channels to retrieve)}
      headers:
        Content-Type: application/x-www-form-urlencoded
      output: ${response.channels as object[]/id,name}

    - id: conversations-join
      path: /conversations.join
      method: POST
      body:
        channel: ${input.channel}
      headers:
        Content-Type: application/json
      output: ${response}
```

**Environment Variables**:

```bash
SLACK_APP_TOKEN=xoxb-...
DEFAULT_SLACK_CHANNEL_ID=C...
```

**MCP Server Features**:
- Integration with MCP clients like Claude Desktop
- Expose multiple workflows as tools
- Provide parameter descriptions using `@(description ...)` annotations

**Claude Desktop Configuration** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "slack-bot": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-stdio",
        "http://localhost:8080/mcp"
      ]
    }
  }
}
```

### 15.5.2 AI-Powered Slack Auto-Reply Bot

**Goal**: Build a bot that automatically responds to Slack messages using AI

**Configuration File**:

```yaml
controller:
  type: http-server
  port: 8080

listeners:
  - id: slack-events
    type: http-callback
    path: /slack/events
    method: POST
    callback:
      url: https://slack.com/api/chat.postMessage
      method: POST
      headers:
        Authorization: Bearer ${env.SLACK_BOT_TOKEN}
        Content-Type: application/json
      body:
        channel: ${webhook.event.channel}
        text: ${jobs.generate-reply.output.message}

gateway:
  type: ngrok
  port: 8080

workflow:
  title: AI Slack Reply
  jobs:
    - id: generate-reply
      component: gpt4o
      input:
        prompt: ${input.event.text}
      output: ${output}

component:
  id: gpt4o
  type: http-client
  base_url: https://api.openai.com/v1
  path: /chat/completions
  method: POST
  headers:
    Authorization: Bearer ${env.OPENAI_API_KEY}
  body:
    model: gpt-4o
    messages:
      - role: user
        content: ${input.prompt}
  output:
    message: ${response.choices[0].message.content}
```

**Workflow**:
1. Slack message event occurs
2. Workflow triggered via ngrok tunnel
3. GPT-4o generates response
4. Listener callback sends response to Slack

---

## 15.6 Multimodal Workflows

### 15.6.1 Image → Text → Speech Pipeline

**Goal**: Analyze image, generate description, and convert to speech

**Configuration File**:

```yaml
controller:
  type: http-server
  port: 8080
  webui:
    driver: gradio
    port: 8081

workflow:
  title: Image to Speech Pipeline
  description: Analyze image, generate description, and convert to speech
  jobs:
    - id: analyze-image
      component: image-analyzer
      input:
        image: ${input.image}
      output: ${output}

    - id: enhance-description
      component: gpt4o
      input:
        prompt: |
          Make this image description more engaging and detailed:
          ${jobs.analyze-image.output.text}
      output: ${output}
      depends_on: [ analyze-image ]

    - id: text-to-speech
      component: tts
      input:
        text: ${jobs.enhance-description.output.message}
      output:
        description: ${jobs.enhance-description.output.message}
        audio: ${output as audio}
      depends_on: [ enhance-description ]

components:
  - id: image-analyzer
    type: model
    task: image-to-text
    model: Salesforce/blip-image-captioning-large
    image: ${input.image as image}
    output:
      text: ${result}

  - id: gpt4o
    type: http-client
    base_url: https://api.openai.com/v1
    path: /chat/completions
    method: POST
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
    body:
      model: gpt-4o
      messages:
        - role: user
          content: ${input.prompt}
    output:
      message: ${response.choices[0].message.content}

  - id: tts
    type: http-client
    endpoint: https://api.openai.com/v1/audio/speech
    method: POST
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
    body:
      model: tts-1
      input: ${input.text}
      voice: nova
    output: ${response}
```

**3-Stage Pipeline**:
1. **Image Analysis**: BLIP model generates image description
2. **Text Enhancement**: GPT-4o rewrites description to be more detailed and engaging
3. **Speech Conversion**: OpenAI TTS converts text to speech

### 15.6.2 Speech → Text → Translation → Speech Pipeline

**Goal**: Translate spoken language to another language with speech output

**Configuration File**:

```yaml
controller:
  type: http-server
  port: 8080
  webui:
    driver: gradio
    port: 8081

workflow:
  title: Voice Translation Pipeline
  description: Transcribe audio, translate to target language, and synthesize speech
  jobs:
    - id: transcribe
      component: whisper
      input:
        audio: ${input.audio}
      output: ${output}

    - id: translate
      component: translator
      input:
        text: ${jobs.transcribe.output.text}
        target_lang: ${input.target_lang}
      output: ${output}
      depends_on: [ transcribe ]

    - id: synthesize
      component: tts
      input:
        text: ${jobs.translate.output.text}
      output:
        original: ${jobs.transcribe.output.text}
        translated: ${jobs.translate.output.text}
        audio: ${output as audio}
      depends_on: [ translate ]

components:
  - id: whisper
    type: http-client
    endpoint: https://api.openai.com/v1/audio/transcriptions
    method: POST
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
    body:
      file: ${input.audio as audio}
      model: whisper-1
    output:
      text: ${response.text}

  - id: translator
    type: model
    task: translation
    model: Helsinki-NLP/opus-mt-en-ko
    text: ${input.text as text}
    output:
      text: ${result}

  - id: tts
    type: http-client
    endpoint: https://api.openai.com/v1/audio/speech
    method: POST
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
    body:
      model: tts-1
      input: ${input.text}
      voice: nova
    output: ${response}
```

**4-Stage Pipeline**:
1. **Speech Recognition**: Whisper converts speech to text
2. **Translation**: Helsinki-NLP model translates text
3. **Speech Synthesis**: OpenAI TTS converts translated text to speech
4. **Output**: Original text, translated text, and translated audio

---

## Next Steps

Practice:
- Run each example locally
- Modify examples to build custom workflows
- Combine multiple examples to create complex pipelines
- Deploy to production environment

---

**Next Chapter**: [15. Troubleshooting](./15-troubleshooting.md)
