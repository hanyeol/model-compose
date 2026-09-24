# Model-Compose 예제

이 디렉터리에는 model-compose의 기능과 사용 사례를 시연하는 실용 예제들이 담겨 있습니다. 각 예제는 바로 실행 가능한 `model-compose.yml` 설정 파일과 언어별 README를 포함합니다.

## 📋 빠른 시작

예제 실행:

```bash
cd examples/<category>/<example-name>
model-compose up
```

특정 워크플로만 실행:

```bash
cd examples/<category>/<example-name>
model-compose run <workflow-name> --input '{"key": "value"}'
```

---

## 📂 예제 구조

각 예제 디렉터리에는 일반적으로 다음이 포함됩니다:

```
example-name/
├── model-compose.yml       # 메인 설정 파일
├── README.md               # 영어 문서
├── README.ko.md            # 한국어 문서
├── README.zh-cn.md         # 중국어 간체 문서
└── .env.sample             # 환경 변수 템플릿 (선택)
```

---

## 🔑 환경 변수

많은 예제가 API 키를 필요로 합니다. 예제 디렉터리에 `.env` 파일을 만들어 주세요:

```bash
# OpenAI 예제
OPENAI_API_KEY=your-api-key

# Anthropic 예제
ANTHROPIC_API_KEY=your-api-key

# xAI 예제
XAI_API_KEY=your-api-key

# ElevenLabs 예제
ELEVENLABS_API_KEY=your-api-key

# HuggingFace 예제
HUGGINGFACE_TOKEN=your-token-here
```

---

## 🗂️ 카테고리

예제는 다음과 같이 최상위 카테고리로 정리되어 있습니다:

| 카테고리 | 다루는 내용 |
|---|---|
| [`model-providers/`](./model-providers/) | 외부 모델 API (OpenAI, Anthropic, xAI, Google, ElevenLabs, vLLM) |
| [`model-tasks/`](./model-tasks/) | 로컬 모델 태스크 (chat, embedding, TTS, vision 등) — HuggingFace / llama.cpp / vLLM |
| [`agents/`](./agents/) | ReAct 루프와 도구 사용을 활용한 자율 에이전트 |
| [`showcase/`](./showcase/) | 여러 컴포넌트를 조합한 end-to-end 파이프라인 |
| [`media-processing/`](./media-processing/) | 오디오, 비디오, 이미지 처리 컴포넌트 |
| [`media-broadcast/`](./media-broadcast/) | 라이브 방송 파이프라인 (RTMP, YouTube Live) |
| [`web-automation/`](./web-automation/) | 웹 스크래핑과 브라우저 자동화 |
| [`text-processing/`](./text-processing/) | 텍스트 분할과 전처리 |
| [`data-streaming/`](./data-streaming/) | 스트리밍 입출력 (프레임, 라이브 채팅) |
| [`job-flow/`](./job-flow/) | 워크플로 제어: 조건 분기, hook, interrupt |
| [`workflow-queue/`](./workflow-queue/) | 큐 기반 분산 워크플로 실행 |
| [`mcp-servers/`](./mcp-servers/) | MCP (Model Context Protocol) 서버 구축 |
| [`integrations/`](./integrations/) | 외부 인프라 (channels, stores, search, datasets, gateway) |
| [`runtime/`](./runtime/) | 컴포넌트 실행 런타임 (Docker, Apple Container, virtualenv 등) |

---

## 🎯 카테고리별 예제

### Model Providers

HTTP 클라이언트를 통해 접근하는 외부 모델 API.

#### OpenAI
- [openai-chat-completions](./model-providers/openai/openai-chat-completions/) — GPT 모델과 채팅
- [openai-chat-completions-stream](./model-providers/openai/openai-chat-completions-stream/) — 스트리밍 채팅
- [openai-audio-speech](./model-providers/openai/openai-audio-speech/) — OpenAI TTS로 음성 합성
- [openai-audio-transciptions](./model-providers/openai/openai-audio-transciptions/) — Whisper 음성 인식
- [openai-image-generations](./model-providers/openai/openai-image-generations/) — DALL-E 이미지 생성
- [openai-image-generations-multi](./model-providers/openai/openai-image-generations-multi/) — 다중 이미지 생성
- [openai-image-edits](./model-providers/openai/openai-image-edits/) — DALL-E 이미지 편집
- [openai-image-variations](./model-providers/openai/openai-image-variations/) — 이미지 변형 생성

#### Anthropic
- [anthropic-chat-completions](./model-providers/anthropic/anthropic-chat-completions/) — Claude 모델과 채팅
- [anthropic-chat-completions-stream](./model-providers/anthropic/anthropic-chat-completions-stream/) — Claude 스트리밍 채팅

#### xAI
- [xai-chat-completion](./model-providers/xai/xai-chat-completion/) — Grok 모델과 채팅

#### Google Cloud
- [google-cloud-vision](./model-providers/google/google-cloud-vision/) — Google Cloud Vision API로 이미지 분석

#### ElevenLabs
- [elevenlabs-text-to-speech](./model-providers/elevenlabs/elevenlabs-text-to-speech/) — 고품질 TTS

#### vLLM
- [vllm-chat-completion-stream](./model-providers/vllm/vllm-chat-completion-stream/) — vLLM 서버를 통한 스트리밍 채팅
- [vllm-text-to-speech](./model-providers/vllm/vllm-text-to-speech/) — vLLM-Omni + Qwen3-TTS 음성 합성

### 로컬 모델 태스크

HuggingFace, llama.cpp, vLLM을 통한 로컬 모델 실행.

#### 채팅 및 텍스트 생성
- [chat-completion/huggingface](./model-tasks/chat-completion/huggingface/) — HuggingFace LLM 채팅
- [chat-completion/llamacpp](./model-tasks/chat-completion/llamacpp/) — llama.cpp로 GGUF 모델 채팅
- [text-generation](./model-tasks/text-generation/) — 텍스트 생성
- [text-generation-lora](./model-tasks/text-generation-lora/) — LoRA 어댑터 기반 텍스트 생성
- [text-generation-llamacpp](./model-tasks/text-generation-llamacpp/) — llama.cpp로 텍스트 생성

#### 텍스트 처리
- [summarization](./model-tasks/summarization/) — 텍스트 요약
- [summarization-stream](./model-tasks/summarization-stream/) — 스트리밍 요약
- [translation](./model-tasks/translation/) — 텍스트 번역
- [translation-stream](./model-tasks/translation-stream/) — 스트리밍 번역
- [text-classification](./model-tasks/text-classification/) — 텍스트 분류
- [text-reranking](./model-tasks/text-reranking/) — 쿼리 대비 문서 재랭킹
- [typed-decision-nimble](./model-tasks/typed-decision-nimble/) — 후보별 확률과 함께 타입 지정 결정 (Bespoke Nimble-9B)
- [typed-decision-kev](./model-tasks/typed-decision-kev/) — 후보별 확률과 함께 원샷 타입 지정 결정 (Kev-4B)

#### 임베딩
- [text-embedding](./model-tasks/text-embedding/) — 텍스트 임베딩
- [text-embedding-llamacpp](./model-tasks/text-embedding-llamacpp/) — llama.cpp 임베딩
- [text-embedding-lfm2](./model-tasks/text-embedding-lfm2/) — LFM2.5-Encoder-350M 기반 다국어 임베딩
- [face-embedding](./model-tasks/face-embedding/) — InsightFace 얼굴 임베딩
- [voice-embedding](./model-tasks/voice-embedding/) — pyannote.audio 화자 임베딩
- [music-embedding-sampleid](./model-tasks/music-embedding-sampleid/) — Sony Sample ID 음악 임베딩
- [video-embedding](./model-tasks/video-embedding/) — X-CLIP 기반 비디오 레벨 임베딩

#### 비전
- [image-to-text](./model-tasks/image-to-text/) — 이미지 캡셔닝
- [image-text-to-text/huggingface](./model-tasks/image-text-to-text/huggingface/) — HuggingFace VLM (Qwen2.5-VL)
- [image-text-to-text/vllm](./model-tasks/image-text-to-text/vllm/) — vLLM 기반 VLM OCR (olmOCR)
- [image-generation-qwen-image](./model-tasks/image-generation-qwen-image/) — Qwen-Image 2.1로 이미지 생성
- [image-upscale](./model-tasks/image-upscale/) — 이미지 업스케일
- [image-background-removal](./model-tasks/image-background-removal/) — 배경 제거
- [image-segmentation](./model-tasks/image-segmentation/) — SAM 기반 세그멘테이션 마스크
- [face-swap](./model-tasks/face-swap/) — 얼굴 스왑
- [pose-detection](./model-tasks/pose-detection/) — 인체 포즈 감지
- [object-detection](./model-tasks/object-detection/) — YOLO 기반 객체 감지

#### 3D 복원
- [image-to-3d-anigen](./model-tasks/image-to-3d-anigen/) — 단일 이미지에서 리깅된 3D 메시 생성 (AniGen)
- [image-to-3d-pixal3d](./model-tasks/image-to-3d-pixal3d/) — 단일 이미지에서 텍스처 3D 메시 생성 (Pixal3D)
- [image-to-3d-pixal3d-mv](./model-tasks/image-to-3d-pixal3d-mv/) — 멀티뷰 이미지에서 텍스처 3D 메시 생성 (Pixal3D MV)
- [image-to-3d-world-mirror](./model-tasks/image-to-3d-world-mirror/) — HunyuanWorld-Mirror 2.0 기반 3D 씬 복원

#### 비디오
- [video-to-video-animatediff](./model-tasks/video-to-video-animatediff/) — AnimateDiff(SD 1.5)로 프롬프트 기반 비디오 리스타일링
- [shot-boundary-detection](./model-tasks/shot-boundary-detection/) — TransNetV2 기반 샷 경계 감지
- [object-tracking](./model-tasks/object-tracking/) — 비디오 프레임 간 객체 추적 (YOLO + ByteTrack/BoT-SORT)
- [face-tracking](./model-tasks/face-tracking/) — 비디오 프레임 간 얼굴 추적 (InsightFace)
- [pose-tracking](./model-tasks/pose-tracking/) — 비디오 프레임 간 인체 포즈 추적 (YOLOv8-pose)

#### Talking Head / 립싱크
- [talking-head-sadtalker](./model-tasks/talking-head-sadtalker/) — SadTalker 기반 포트레이트 토킹헤드
- [talking-head-echomimic](./model-tasks/talking-head-echomimic/) — EchoMimic 기반 포트레이트/반신 토킹헤드
- [talking-head-float](./model-tasks/talking-head-float/) — Float 기반 감정 조건 토킹헤드
- [talking-head-hallo2](./model-tasks/talking-head-hallo2/) — Hallo2 기반 고해상도 장시간 토킹헤드
- [talking-head-hallo3](./model-tasks/talking-head-hallo3/) — Hallo3 기반 DiT 토킹헤드 (CogVideoX-5B)
- [talking-head-sonic](./model-tasks/talking-head-sonic/) — Sonic 기반 포트레이트 토킹헤드
- [lip-sync-wav2lip](./model-tasks/lip-sync-wav2lip/) — Wav2Lip 립싱크
- [lip-sync-latentsync](./model-tasks/lip-sync-latentsync/) — LatentSync 립싱크
- [lip-sync-musetalk](./model-tasks/lip-sync-musetalk/) — MuseTalk 립싱크

#### 음성 / 오디오
- [speech-to-text](./model-tasks/speech-to-text/) — 음성 인식
- [speech-to-text-crisper-whisper](./model-tasks/speech-to-text-crisper-whisper/) — CrisperWhisper 2.0 기반 축어식 전사
- [speech-to-text-vibevoice](./model-tasks/speech-to-text-vibevoice/) — VibeVoice-ASR 기반 장시간 전사
- [speech-to-text-vibevoice-streaming](./model-tasks/speech-to-text-vibevoice-streaming/) — VibeVoice-ASR-Streaming 기반 스트리밍 전사
- [text-to-speech-generate](./model-tasks/text-to-speech-generate/) — 기본 TTS
- [text-to-speech-design](./model-tasks/text-to-speech-design/) — 음성 디자인 기반 TTS
- [text-to-speech-design-fireredtts3](./model-tasks/text-to-speech-design-fireredtts3/) — FireRedTTS3-Instruct 기반 음성 디자인
- [text-to-speech-edit-fireredtts3](./model-tasks/text-to-speech-edit-fireredtts3/) — FireRedTTS3-Instruct 기반 음성 편집
- [text-to-speech-clone](./model-tasks/text-to-speech-clone/) — 음성 클로닝 TTS
- [text-to-speech-clone-cosyvoice](./model-tasks/text-to-speech-clone-cosyvoice/) — CosyVoice2 기반 제로샷 음성 클로닝
- [text-to-speech-clone-fireredtts3](./model-tasks/text-to-speech-clone-fireredtts3/) — FireRedTTS3-Base 기반 제로샷 음성 클로닝
- [text-to-speech-clone-luxtts](./model-tasks/text-to-speech-clone-luxtts/) — LuxTTS(ZipVoice) 기반 제로샷 음성 클로닝
- [text-to-speech-clone-tada](./model-tasks/text-to-speech-clone-tada/) — HumeAI TADA 기반 음성 클로닝
- [text-to-speech-to-text](./model-tasks/text-to-speech-to-text/) — TTS → STT 왕복
- [audio-text-alignment](./model-tasks/audio-text-alignment/) — 단어 단위 강제 정렬 (Wav2Vec2 CTC)
- [voice-activity-detection](./model-tasks/voice-activity-detection/) — Silero VAD 기반 발화 구간 감지
- [speaker-diarization](./model-tasks/speaker-diarization/) — pyannote.audio로 "누가 언제 말했는지" 분석

#### 음악
- [music-generation](./model-tasks/music-generation/) — 음악 생성
- [music-generation-yue2](./model-tasks/music-generation-yue2/) — YuE2 기반 전곡 생성 (스코어 + 음향 합성)
- [music-source-separation](./model-tasks/music-source-separation/) — Demucs v4 기반 보컬 스템 분리
- [music-source-separation-mdx23c-drumsep](./model-tasks/music-source-separation-mdx23c-drumsep/) — MDX23C DrumSep 기반 드럼 파트별 스템 분리
- [music-transcription](./model-tasks/music-transcription/) — Spotify Basic Pitch 기반 노트/MIDI 전사
- [music-beat-tracking-beat-this](./model-tasks/music-beat-tracking-beat-this/) — Beat This!로 비트 및 다운비트 검출

### Agents

ReAct 루프와 도구 사용을 활용한 자율 에이전트.

- [code-reviewer](./agents/code-reviewer/) — 자동 코드 리뷰 에이전트
- [design-md-generator](./agents/design-md-generator/) — 웹사이트 분석 기반 DESIGN.md 생성
- [disk-analyzer](./agents/disk-analyzer/) — 디스크 사용량 분석 에이전트
- [human-in-the-loop](./agents/human-in-the-loop/) — 위험한 작업에 대한 승인 게이트
- [kpop-fancam-collector](./agents/kpop-fancam-collector/) — K-pop 팬캠 탐색/수집 에이전트
- [multi-tool](./agents/multi-tool/) — 다중 도구 에이전트 시연
- [rag-assistant](./agents/rag-assistant/) — RAG 기반 지식 Q&A
- [web-page-analyzer](./agents/web-page-analyzer/) — 웹 페이지 콘텐츠 분석
- [web-researcher](./agents/web-researcher/) — 자율 웹 리서치 에이전트
- [web3-airdrop-hunter](./agents/web3-airdrop-hunter/) — Web3 에어드랍 탐색 에이전트

### Showcase

여러 컴포넌트를 조합한 end-to-end 파이프라인.

- [analyze-disk-usage](./showcase/analyze-disk-usage/) — 디스크 사용량 수집 → GPT-4o 분석
- [make-inspiring-quote-voice](./showcase/make-inspiring-quote-voice/) — 명언 생성 → 음성 변환
- [find-person-scenes](./showcase/find-person-scenes/) — 얼굴 임베딩으로 비디오 내 인물 등장 장면 검색
- [vibevoice-realtime-tts](./showcase/vibevoice-realtime-tts/) — Microsoft VibeVoice 기반 실시간 WebSocket TTS
- [upscale-video](./showcase/upscale-video/) — 비디오를 프레임 단위 슈퍼레졸루션으로 업스케일 (오디오 보존)
- [echo-server](./showcase/echo-server/) — 최소 HTTP 에코 서버

### Media Processing

오디오, 비디오, 이미지 처리 컴포넌트.

#### 오디오
- [audio-extractor](./media-processing/audio-extractor/) — 비디오에서 오디오 추출
- [audio-feature-extractor](./media-processing/audio-feature-extractor/) — 스펙트럼/파형 특성 추출
- [audio-analyzer](./media-processing/audio-analyzer/) — 라우드니스, 피크, 게인, 무음, 에너지 분석
- [audio-capture](./media-processing/audio-capture/) — 마이크/시스템 루프백을 AAC 스트림으로 캡처
- [audio-clipper](./media-processing/audio-clipper/) — ffmpeg 기반 무손실 구간 자르기
- [audio-mixer](./media-processing/audio-mixer/) — ffmpeg로 여러 오디오 소스 믹싱
- [audio-normalizer](./media-processing/audio-normalizer/) — 트루피크 상한 적용 LUFS 라우드니스 정규화
- [audio-processor](./media-processing/audio-processor/) — DSP 체인 (EQ, 다이내믹, 공간, 이펙트)
- [audio-refiner](./media-processing/audio-refiner/) — Silero VAD + 클리퍼로 무음/노이즈 제거
- [audio-silence-detector](./media-processing/audio-silence-detector/) — ffmpeg `silencedetect`로 무음 구간 검출
- [audio-spectrum-to-video](./media-processing/audio-spectrum-to-video/) — 오디오를 이퀄라이저 스타일 MP4로 렌더링
- [audio-synchronizer](./media-processing/audio-synchronizer/) — 멀티소스 녹음 간 시간 오프셋 계산
- [music-analyzer](./media-processing/music-analyzer/) — 리듬/조성/스펙트럼 속성 추출
- [music-segment-detector](./media-processing/music-segment-detector/) — 인트로/버스/코러스 구간 경계 검출
- [speech-to-text-with-correction](./media-processing/speech-to-text-with-correction/) — 참조 스크립트에 정렬한 Whisper STT
- [speech-to-text-with-vad](./media-processing/speech-to-text-with-vad/) — Silero VAD 프리세그멘테이션 + Whisper STT

#### 비디오
- [video-converter](./media-processing/video-converter/) — 비디오 포맷/코덱 변환
- [video-scene-detector](./media-processing/video-scene-detector/) — 비디오 장면 변화 감지
- [video-scene-splitter](./media-processing/video-scene-splitter/) — 씬을 감지해 파일별로 분할 저장
- [video-capture](./media-processing/video-capture/) — 로컬 카메라를 프래그먼트 MP4 스트림으로 캡처
- [video-clipper](./media-processing/video-clipper/) — ffmpeg 기반 무손실 구간 자르기
- [video-mixer](./media-processing/video-mixer/) — ffmpeg로 여러 비디오 컴포지트
- [video-playback](./media-processing/video-playback/) — ffplay로 OS 네이티브 창에서 비디오 재생
- [video-processor](./media-processing/video-processor/) — 프레임 단위 리사이즈/크롭/패딩/플립/회전
- [video-refiner](./media-processing/video-refiner/) — VAD 기반 발화 구간만 남긴 비디오 재조립
- [video-dubbing](./media-processing/video-dubbing/) — 엔드투엔드 더빙 (Whisper → 번역 → TTS → Wav2Lip)
- [video-to-gif](./media-processing/video-to-gif/) — 비디오(또는 클립)를 애니메이션 GIF로 변환
- [screen-capture](./media-processing/screen-capture/) — 화면/영역/마이크를 연속 스트림으로 캡처
- [youtube-downloader](./media-processing/youtube-downloader/) — 쿠키 인증 기반 YouTube 다운로드
- [face-mosaic](./media-processing/face-mosaic/) — 비디오 내 얼굴 픽셀화/블러 (스트리밍, 오디오 보존)
- [pose-skeleton-overlay](./media-processing/pose-skeleton-overlay/) — 모든 프레임에 YOLOv8-pose 스켈레톤 오버레이
- [nsfw-mosaic](./media-processing/nsfw-mosaic/) — 비디오 내 NSFW 영역 픽셀화/블러 (스트리밍, 오디오 보존)

#### 이미지
- [image-processor](./media-processing/image-processor/) — 리사이즈, 크롭, 회전, 필터, 조정
- [image-processor-dual-input](./media-processing/image-processor-dual-input/) — URL + 업로드 이미지 처리
- [face-gender-annotate](./media-processing/face-gender-annotate/) — 남/여 색상 구분 얼굴 바운딩 박스 표시
- [nsfw-annotate](./media-processing/nsfw-annotate/) — NSFW 감지 결과에 레이블 바운딩 박스 표시
- [pose-brightness-sweep](./media-processing/pose-brightness-sweep/) — 밝기 변형별 YOLO-pose 비교
- [html-animation-to-video](./media-processing/html-animation-to-video/) — HTML 애니메이션을 MP4로 렌더링

#### 메타데이터 / 3D
- [media-inspector](./media-processing/media-inspector/) — ffprobe + exiftool로 메타데이터 조회
- [model-3d-converter](./media-processing/model-3d-converter/) — 3D 에셋 포맷 간 변환

### Media Broadcast

라이브 방송 파이프라인.

- [youtube-live](./media-broadcast/youtube-live/) — 공유 데이터 큐 기반 연속 YouTube Live RTMP 송출

### Web Automation

- [web-scraper](./web-automation/web-scraper/) — CSS/XPath 셀렉터 기반 웹 스크래핑
- [web-browser](./web-automation/web-browser/) — 헤드리스 브라우저 자동화 (CAPTCHA 대응)
- [capture-youtube-video](./web-automation/capture-youtube-video/) — 브라우저 기반 YouTube 재생 캡처

### Text Processing

- [split-text](./text-processing/split-text/) — 오버랩 설정 가능한 텍스트 청킹
- [load-document](./text-processing/load-document/) — PDF/DOCX/HTML 문서 로드 및 청킹 (Docling, pypdf)

### Data Streaming

스트리밍 입출력.

- [video-to-frames](./data-streaming/video-to-frames/) — 비디오 프레임 스트리밍
- [video-to-frames-bulk](./data-streaming/video-to-frames-bulk/) — 디렉터리 내 모든 비디오 프레임 스트리밍
- [youtube-live-chat](./data-streaming/youtube-live-chat/) — YouTube 라이브 채팅 스트리밍
- [data-queue-basic](./data-streaming/data-queue-basic/) — 공유 `data-queue` 기반 생산자/소비자
- [data-queue-audio-playback](./data-streaming/data-queue-audio-playback/) — 워크플로 간 큐 기반 오디오 재생
- [sentence-splitter](./data-streaming/sentence-splitter/) — OpenAI 스트림을 문장 분할기에 연결
- [llm-streaming-voice](./data-streaming/llm-streaming-voice/) — LLM → 문장 분할 → TTS → 큐 재생 엔드투엔드

### Job Flow

워크플로 제어 패턴.

#### Conditional Routing
- [conditional-routing/if](./job-flow/conditional-routing/if/) — `if` 조건 분기
- [conditional-routing/switch](./job-flow/conditional-routing/switch/) — `switch` 분기
- [conditional-routing/random](./job-flow/conditional-routing/random/) — 랜덤 분기

#### Job 생명주기
- [hook](./job-flow/hook/) — before/after Python hook
- [interrupt](./job-flow/interrupt/) — 인간 승인 게이트

### Workflow Queue

Redis 큐를 통한 분산 워크플로 실행.

- [non-stream](./workflow-queue/non-stream/) — 기본 dispatcher/subscriber 패턴
- [stream](./workflow-queue/stream/) — Redis Streams와 SSE 기반 스트리밍 출력

### MCP Servers

model-compose로 MCP (Model Context Protocol) 서버 구축.

- [korea-dart-mcp](./mcp-servers/korea-dart-mcp/) — Korea DART 공시 정보를 노출하는 MCP 서버
- [slack-bot](./mcp-servers/slack-bot/) — Slack 봇을 위한 MCP 서버
- [audio-processor-mcp](./mcp-servers/audio-processor-mcp/) — DSP 오디오 이펙트를 stdio로 노출하는 MCP 서버

### Integrations

외부 인프라 통합.

#### Channels
- [channels/telegram](./integrations/channels/telegram/) — 웹훅 기반 Telegram 봇

#### Vector Stores
- [vector-store/chroma](./integrations/vector-store/chroma/) — ChromaDB
- [vector-store/milvus](./integrations/vector-store/milvus/) — Milvus

#### Graph Stores
- [graph-store/neo4j](./integrations/graph-store/neo4j/) — Neo4j
- [graph-store/arangodb](./integrations/graph-store/arangodb/) — ArangoDB

#### Key-Value Stores
- [key-value-store/redis](./integrations/key-value-store/redis/) — Redis
- [key-value-store/memory](./integrations/key-value-store/memory/) — 인메모리 키-값 저장소
- [key-value-store/sqlite](./integrations/key-value-store/sqlite/) — SQLite 키-값 저장소

#### Search Engines
- [search-engine/sqlite](./integrations/search-engine/sqlite/) — SQLite FTS

#### Datasets
- [datasets/huggingface](./integrations/datasets/huggingface/) — HuggingFace datasets

#### Gateway (터널)
- [gateway/http-tunnel/ngrok](./integrations/gateway/http-tunnel/ngrok/) — ngrok HTTP 터널
- [gateway/http-tunnel/cloudflare](./integrations/gateway/http-tunnel/cloudflare/) — Cloudflare 터널
- [gateway/http-tunnel/cloudflare-named](./integrations/gateway/http-tunnel/cloudflare-named/) — Cloudflare Named 터널
- [gateway/ssh-tunnel](./integrations/gateway/ssh-tunnel/) — SSH 원격 포트 포워딩

### Runtime

컴포넌트 실행 런타임.

- [process](./runtime/process/) — 네이티브 프로세스
- [embedded](./runtime/embedded/) — 컨트롤러 프로세스 내 임베디드 실행
- [virtualenv-python](./runtime/virtualenv-python/) — Python virtualenv
- [virtualenv-pyenv](./runtime/virtualenv-pyenv/) — pyenv 관리 virtualenv
- [docker-shell](./runtime/docker-shell/) — Docker 컨테이너 내 셸 명령
- [docker-model](./runtime/docker-model/) — Docker 컨테이너 내 로컬 모델
- [docker-custom-image](./runtime/docker-custom-image/) — 커스텀 Docker 이미지 빌드
- [docker-nginx](./runtime/docker-nginx/) — Nginx 컨테이너 정적 파일 서버
- [apple-container](./runtime/apple-container/) — Apple Container 런타임

---

## 🚀 다음 단계

1. 사용 사례에 맞는 카테고리를 둘러보세요
2. 예제를 프로젝트 시작점으로 복사하세요
3. 필요에 맞게 `model-compose.yml`을 수정하세요
4. 자세한 설명은 [User Guide](../docs/user-guide/)를 참고하세요

---

## 🤝 예제 기여하기

공유할 유용한 예제가 있으신가요?

1. `examples/` 아래 적절한 카테고리에 새 디렉터리를 만드세요
2. `model-compose.yml` 파일을 추가하세요
3. 주변 예제의 스타일을 따라 `README.md`, `README.ko.md`, `README.zh-cn.md`를 작성하세요
4. 이 인덱스를 업데이트하세요
5. Pull Request를 보내주세요

---

## 📚 추가 리소스

- [User Guide](../docs/user-guide/) — 종합 문서
- [GitHub Repository](https://github.com/hanyeol/model-compose) — 소스 코드와 이슈

---

## 📖 다른 언어

- **🇬🇧 English**: [English User Guide](README.md)
- **🇨🇳 简体中文**: [简体中文用户指南](README.zh-cn.md)

---

**즐거운 컴포징 되세요! 🎉**
