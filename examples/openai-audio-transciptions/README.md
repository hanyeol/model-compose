# OpenAI Audio Transcriptions Example

This example demonstrates how to use model-compose with OpenAI's Speech-to-Text (STT) API to transcribe audio files into text. OpenAI's transcription service supports multiple audio formats and provides high-accuracy speech recognition with usage tracking.

## Overview

OpenAI's Audio Transcriptions API provides advanced speech-to-text capabilities powered by the Whisper model family. This configuration showcases:

- Multiple STT model options (gpt-4o-transcribe, gpt-4o-mini-transcribe, whisper-1)
- Multi-format audio file support
- High-accuracy transcription with usage metrics
- Cost-effective transcription options
- Web UI for interactive testing

## Prerequisites

### OpenAI API Setup

1. **Create Account**: Sign up at [OpenAI](https://platform.openai.com/)
2. **Get API Key**: Navigate to API Keys section
3. **Add Billing**: Set up billing information for API usage

### Environment Setup

```bash
# Set your OpenAI API key
export OPENAI_API_KEY="sk-your_api_key_here"

# Install model-compose
pip install -e .
```

### Optional Dependencies
```bash
# For audio processing and conversion
pip install pydub ffmpeg-python
```

## Architecture

### Component Configuration

#### OpenAI Speech-to-Text (`openai-speech-to-text`)
- **Type**: HTTP client
- **Endpoint**: `https://api.openai.com/v1/audio/transcriptions`
- **Method**: POST
- **Content Type**: multipart/form-data
- **Response Type**: Binary buffer
- **Default Model**: `whisper-1`

### API Configuration

| Parameter | Value | Description |
|-----------|-------|-------------|
| `endpoint` | `/v1/audio/transcriptions` | OpenAI STT endpoint |
| `method` | POST | HTTP method |
| `content_type` | multipart/form-data | Audio file upload format |
| `response_type` | buffer | Binary response handling |

## Workflow

### Generate Transcriptions with OpenAI STT

Converts audio files into accurate text transcriptions using OpenAI's advanced speech recognition models.

```mermaid
graph LR
    A[Audio File + Model] --> B[OpenAI STT API]
    B --> C[Speech Recognition]
    C --> D[Text + Usage Stats]
```

**Input Parameters:**
| Parameter | Type | Required | Options | Default | Description |
|-----------|------|----------|---------|---------|-------------|
| `file` | audio | Yes | Various audio formats | - | Audio file to transcribe |
| `model` | string | No | gpt-4o-transcribe, gpt-4o-mini-transcribe, whisper-1 | whisper-1 | STT model selection |

**Output:**
| Field | Type | Description |
|-------|------|-------------|
| `text` | string | Transcribed text from audio |
| `seconds` | float | Duration of audio processed (for billing) |

## Model Options

### Available STT Models

| Model | Quality | Speed | Use Case | Pricing |
|-------|---------|-------|----------|---------|
| **whisper-1** | High | Standard | General transcription | Standard cost |
| **gpt-4o-transcribe** | Highest | Slower | High-accuracy needs | Higher cost |
| **gpt-4o-mini-transcribe** | Good | Fast | Cost-effective transcription | Lower cost |

## Supported Audio Formats

### Compatible File Types

| Format | Extension | Quality | Notes |
|--------|-----------|---------|-------|
| **MP3** | .mp3 | Good | Most common format |
| **MP4** | .mp4 | High | Video files (audio extracted) |
| **MPEG** | .mpeg | High | Video files (audio extracted) |
| **MPGA** | .mpga | Good | MPEG audio format |
| **M4A** | .m4a | High | Apple audio format |
| **WAV** | .wav | Excellent | Uncompressed, best quality |
| **WEBM** | .webm | Good | Web-optimized format |

### File Size Limits

- **Maximum file size**: 25 MB
- **Maximum duration**: No specific limit
- **Recommended**: Use compressed formats for large files

## How to Run Instructions

### 1. Start the Service

```bash
# Navigate to the example directory
cd examples/openai-audio-transciptions

# Start the controller
model-compose up
```

This starts:
- HTTP API server on port 8080 (base path: `/api`)
- Gradio web interface on port 8081

### 2. Access the Web UI

Open http://localhost:8081 in your browser to interact with the transcription service through a web interface.

### 3. API Usage

#### Basic Audio Transcription
```bash
curl -X POST http://localhost:8080/api \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample_audio.mp3" \
  -F "model=whisper-1"
```

#### High-Accuracy Transcription
```bash
curl -X POST http://localhost:8080/api \
  -H "Content-Type: multipart/form-data" \
  -F "file=@interview.wav" \
  -F "model=gpt-4o-transcribe"
```

#### Cost-Optimized Transcription
```bash
curl -X POST http://localhost:8080/api \
  -H "Content-Type: multipart/form-data" \
  -F "file=@podcast.mp3" \
  -F "model=gpt-4o-mini-transcribe"
```

#### Using Different Audio Formats
```bash
# WAV file (highest quality)
curl -X POST http://localhost:8080/api \
  -H "Content-Type: multipart/form-data" \
  -F "file=@recording.wav" \
  -F "model=whisper-1"

# M4A file (Apple format)
curl -X POST http://localhost:8080/api \
  -H "Content-Type: multipart/form-data" \
  -F "file=@voice_memo.m4a" \
  -F "model=gpt-4o-mini-transcribe"

# WebM file (web format)
curl -X POST http://localhost:8080/api \
  -H "Content-Type: multipart/form-data" \
  -F "file=@video_call.webm" \
  -F "model=whisper-1"
```

### Sample Response

```json
{
  "text": "Hello, this is a sample audio transcription. The quality of the speech recognition is quite impressive, and it handles various accents and speaking styles well.",
  "seconds": 12.5
}
```

## Customization Options

### Model Selection Configuration

#### Standard Quality (Default)
```yaml
body:
  model: whisper-1
  file: ${input.file as audio}
```

#### High Accuracy
```yaml
body:
  model: gpt-4o-transcribe
  file: ${input.file as audio}
```

#### Cost-Optimized
```yaml
body:
  model: gpt-4o-mini-transcribe
  file: ${input.file as audio}
```

### Advanced Configuration

#### With Additional Parameters
```yaml
components:
  - id: openai-speech-to-text-advanced
    type: http-client
    endpoint: https://api.openai.com/v1/audio/transcriptions
    method: POST
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
      Content-Type: multipart/form-data
    timeout: 120000  # 2 minutes for large files
    retry_attempts: 3
    body:
      model: ${input.model as select/gpt-4o-transcribe,gpt-4o-mini-transcribe,whisper-1 | whisper-1}
      file: ${input.file as audio}
      language: ${input.language | auto}  # Optional language hint
      prompt: ${input.prompt}  # Optional context prompt
      response_format: json
      temperature: 0  # Deterministic output
```

### Batch Processing Workflow

```yaml
workflows:
  - id: batch-transcription
    title: Batch Audio Transcription
    jobs:
      - id: process-files
        component: openai-speech-to-text
        input:
          file: ${input.audio_files[*]}
          model: ${input.model | whisper-1}
        output:
          transcriptions: ${output[*].text}
          total_seconds: ${output[*].seconds | sum}
```

### Multi-Language Support

```yaml
workflows:
  - id: multilingual-transcription
    title: Multi-Language Transcription
    jobs:
      - id: transcribe
        component: openai-speech-to-text
        input:
          file: ${input.file}
          model: ${input.model | whisper-1}
          language: ${input.language as select/en,es,fr,de,it,pt,ru,ja,ko,zh | auto}
        output:
          text: ${output.text}
          detected_language: ${output.language}
          confidence: ${output.confidence}
```

## Pricing and API Limits

### Pricing Structure (as of 2024)

| Model | Price per Minute | Quality | Use Case |
|-------|------------------|---------|----------|
| **whisper-1** | $0.006 | High | General transcription |
| **gpt-4o-transcribe** | $0.010 | Highest | Critical accuracy needs |
| **gpt-4o-mini-transcribe** | $0.003 | Good | Budget-conscious apps |

### Rate Limits

- **Requests per minute (RPM)**: 50
- **Files per day**: 1,000 (varies by plan)
- **Concurrent uploads**: 10

### How to Run Optimization

1. **Choose Appropriate Model**: Use mini for cost, standard for accuracy
2. **Audio Preprocessing**: Clean audio for better results
3. **Format Selection**: Use compressed formats for large files
4. **Batch Processing**: Group related files

## Advanced Features

### Language Detection and Hints

```bash
# Let the model auto-detect language
curl -X POST http://localhost:8080/api \
  -H "Content-Type: multipart/form-data" \
  -F "file=@multilingual.mp3" \
  -F "model=whisper-1" \
  -F "language=auto"

# Provide language hint for better accuracy
curl -X POST http://localhost:8080/api \
  -H "Content-Type: multipart/form-data" \
  -F "file=@spanish_audio.mp3" \
  -F "model=whisper-1" \
  -F "language=es"
```

### Context Prompts

```bash
# Provide context for better transcription
curl -X POST http://localhost:8080/api \
  -H "Content-Type: multipart/form-data" \
  -F "file=@technical_meeting.mp3" \
  -F "model=gpt-4o-transcribe" \
  -F "prompt=This is a technical discussion about machine learning and artificial intelligence."
```

### Response Format Options

```yaml
# Different response formats
body:
  model: ${input.model | whisper-1}
  file: ${input.file as audio}
  response_format: ${input.format as select/json,text,srt,verbose_json,vtt | json}
```

## Use Cases

### Content Creation
- **Podcast Transcription**: Convert audio content to text
- **Video Subtitles**: Generate captions for videos
- **Interview Documentation**: Transcribe interviews and meetings
- **Content Repurposing**: Turn audio into blog posts

### Business Applications
- **Meeting Minutes**: Automated meeting transcription
- **Customer Support**: Transcribe support calls
- **Training Materials**: Convert audio training to text
- **Legal Documentation**: Court proceeding transcription

### Accessibility Solutions
- **Hearing Impairment**: Real-time captioning
- **Language Learning**: Transcription for pronunciation
- **Voice Notes**: Convert voice memos to text
- **Medical Documentation**: Patient interaction transcription

### Media and Entertainment
- **News Broadcasting**: Automated news transcription
- **Radio Shows**: Convert radio content to text
- **Gaming**: Transcribe voice chat for moderation
- **Social Media**: Convert audio posts to text

## Error Handling and Troubleshooting

### Common Issues

#### Authentication Errors
```bash
# Verify API key
curl -X GET "https://api.openai.com/v1/models" \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

#### File Format Issues
```bash
# Check supported formats
echo "Supported: mp3, mp4, mpeg, mpga, m4a, wav, webm"

# Convert unsupported formats
ffmpeg -i input.flac output.mp3
```

#### File Size Issues
```bash
# Check file size (should be < 25MB)
ls -lh audio_file.mp3

# Compress large files
ffmpeg -i large_audio.wav -b:a 128k compressed_audio.mp3
```

### Common Error Responses

| Status Code | Error | Solution |
|-------------|--------|----------|
| 400 | File too large | Compress or split audio file |
| 400 | Unsupported format | Convert to supported format |
| 401 | Invalid API key | Check OPENAI_API_KEY |
| 429 | Rate limit exceeded | Implement retry with backoff |
| 500 | Server error | Check OpenAI status page |

### Quality Optimization

#### Audio Preprocessing
```yaml
workflows:
  - id: enhanced-transcription
    jobs:
      - id: preprocess-audio
        component: audio-preprocessor
        input:
          file: ${input.file}
          operations:
            - noise_reduction
            - normalize_volume
            - enhance_speech

      - id: transcribe
        component: openai-speech-to-text
        input:
          file: ${jobs.preprocess-audio.output}
          model: ${input.model | whisper-1}
        depends_on: [preprocess-audio]
```

## Integration Examples

### Real-time Transcription Service

```yaml
workflows:
  - id: realtime-transcription
    title: Real-time Audio Transcription
    jobs:
      - id: segment-audio
        component: audio-segmenter
        input:
          stream: ${input.audio_stream}
          segment_duration: 30  # seconds

      - id: transcribe-segments
        component: openai-speech-to-text
        input:
          file: ${jobs.segment-audio.output}
          model: gpt-4o-mini-transcribe  # Fast model for real-time
        depends_on: [segment-audio]

      - id: combine-results
        component: text-combiner
        input:
          segments: ${jobs.transcribe-segments.output[*].text}
        depends_on: [transcribe-segments]
```

### Meeting Assistant Integration

```yaml
workflows:
  - id: meeting-assistant
    title: Meeting Transcription and Analysis
    jobs:
      - id: transcribe-meeting
        component: openai-speech-to-text
        input:
          file: ${input.meeting_audio}
          model: gpt-4o-transcribe
          prompt: "This is a business meeting discussing project updates and decisions."

      - id: extract-action-items
        component: text-analyzer
        input:
          text: ${jobs.transcribe-meeting.output.text}
          task: extract_action_items
        depends_on: [transcribe-meeting]

      - id: generate-summary
        component: text-summarizer
        input:
          text: ${jobs.transcribe-meeting.output.text}
          style: meeting_minutes
        depends_on: [transcribe-meeting]
```

### Podcast Workflow

```yaml
workflows:
  - id: podcast-processing
    title: Podcast Transcription and SEO
    jobs:
      - id: transcribe-podcast
        component: openai-speech-to-text
        input:
          file: ${input.podcast_audio}
          model: whisper-1

      - id: generate-chapters
        component: chapter-generator
        input:
          text: ${jobs.transcribe-podcast.output.text}
          duration: ${jobs.transcribe-podcast.output.seconds}
        depends_on: [transcribe-podcast]

      - id: create-seo-content
        component: seo-generator
        input:
          transcript: ${jobs.transcribe-podcast.output.text}
          title: ${input.podcast_title}
        depends_on: [transcribe-podcast]
```

## Security Considerations

### API Key Protection
```bash
# Use environment variables
export OPENAI_API_KEY="sk-..."

# For production, use secrets management
# AWS Secrets Manager, Azure Key Vault, etc.
```

### Audio Data Privacy
- Audio files are processed by OpenAI and may be retained temporarily
- For sensitive content, review OpenAI's data usage policies
- Consider local transcription solutions for highly confidential audio

### Content Filtering
```yaml
# Add content validation
workflows:
  - id: secure-transcription
    jobs:
      - id: validate-audio
        component: audio-validator
        input:
          file: ${input.file}
          max_duration: 3600  # 1 hour limit

      - id: transcribe
        component: openai-speech-to-text
        input: ${input}
        depends_on: [validate-audio]

      - id: content-filter
        component: content-moderator
        input:
          text: ${jobs.transcribe.output.text}
        depends_on: [transcribe]
```

## Performance Optimization

### Audio Quality Optimization
```bash
# Optimize audio for transcription
ffmpeg -i input.mp3 \
  -ar 16000 \          # 16kHz sample rate
  -ac 1 \              # Mono channel
  -c:a libmp3lame \    # MP3 codec
  -b:a 64k \           # 64kbps bitrate
  optimized.mp3
```

### Batch Processing
```yaml
# Efficient batch processing
workflows:
  - id: batch-optimize
    jobs:
      - id: queue-files
        component: file-queue
        input:
          files: ${input.audio_files}
          batch_size: 10

      - id: process-batch
        component: openai-speech-to-text
        input:
          file: ${jobs.queue-files.output}
          model: gpt-4o-mini-transcribe  # Cost-effective for batches
        depends_on: [queue-files]
```

### Caching and Storage
```yaml
# Add caching for processed files
workflows:
  - id: cached-transcription
    jobs:
      - id: check-cache
        component: transcription-cache
        input:
          file_hash: ${input.file | hash}

      - id: transcribe-if-needed
        component: openai-speech-to-text
        input: ${input}
        condition: ${jobs.check-cache.output.cache_miss}
        depends_on: [check-cache]

      - id: store-result
        component: cache-store
        input:
          key: ${input.file | hash}
          result: ${jobs.transcribe-if-needed.output}
        depends_on: [transcribe-if-needed]
```