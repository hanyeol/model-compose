# Language Codes

model-compose uses standardized ISO 639-1 / BCP 47 language codes across components that support language selection, such as text-to-speech and speech-to-text.

## Supported Codes

| Code | Language | Notes |
|------|----------|-------|
| `en` | English | |
| `zh-CN` | Chinese | Simplified Chinese |
| `ja` | Japanese | |
| `ko` | Korean | |
| `de` | German | |
| `fr` | French | |
| `ru` | Russian | |
| `pt` | Portuguese | |
| `es` | Spanish | |
| `it` | Italian | |

## Usage

### Text-to-Speech

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: qwen
  model: Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
  action:
    method: generate
    text: ${input.text as text}
    language: ko
    voice: ${input.voice | vivian}
```

### Dynamic Language Selection

```yaml
language: ${input.language as select/en,ko,ja,zh-CN}
```

## Notes

- When `language` is omitted, the model will attempt automatic language detection.
- The available languages depend on the specific model being used. Qwen TTS models support all codes listed above.
- model-compose automatically translates these standardized codes to model-specific formats internally.
