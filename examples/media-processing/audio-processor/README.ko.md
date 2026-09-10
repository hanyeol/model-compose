# Audio Processor 예제

이 예제는 pedalboard, librosa, soxr, pyloudnorm을 사용해 오디오 스트림에 DSP 변환(time/rate, EQ, dynamics, spatial, level, edit, effect)을 체이닝하는 `audio-processor` 컴포넌트를 보여줍니다.

## 개요

동일한 `audio-processor` 컴포넌트를 기반으로 스물일곱 개의 워크플로우를 제공합니다:

1. **Resample Audio** — 샘플레이트 변경
2. **Change Speed** — 배속 변경 (음정 유지 옵션)
3. **Highpass Filter** — 컷오프 이하 감쇠
4. **Lowpass Filter** — 컷오프 이상 감쇠
5. **Bell EQ** — 중심 주파수 대역 부스트/컷
6. **Low Shelf EQ** — 코너 이하 부스트/컷
7. **High Shelf EQ** — 코너 이상 부스트/컷
8. **Pitch Shift** — 반음 단위 피치 시프트 (길이 유지)
9. **DC Shift** — DC 바이어스 제거 / 오프셋 적용
10. **Compress Dynamics** — 임계값 이상 다운워드 컴프레션
11. **Noise Gate** — 임계값 이하 감쇠
12. **Distortion** — 강한 하모닉 디스토션
13. **Saturation** — 미묘한 하모닉 컬러링
14. **Apply Gain** — dB 단위 볼륨 부스트/감쇠
15. **Chorus** — 모듈레이션 코러스
16. **Delay** — 딜레이/에코
17. **Add Reverb** — Freeverb 스타일 리버브
18. **Normalize (RMS)** — 목표 RMS 레벨(dBFS)
19. **Normalize (Peak)** — 목표 peak 레벨(dBFS)
20. **Normalize (LUFS)** — 목표 통합 라우드니스 + true-peak 제한
21. **Peak Limit (Hard)** — 선형 진폭 상한에서 하드 클립
22. **Peak Limit (Smooth)** — 릴리즈 시간이 있는 스무스 리미터
23. **Trim Edges** — peak 대비 임계값 기준 앞뒤 무음 제거
24. **Trim Silence** — 앞뒤 및 긴 내부 무음 제거
25. **Fade In** — 시작 부분에 cosine 페이드 인
26. **Fade Out** — 끝 부분에 cosine 페이드 아웃
27. **Anonymize Voice** — 피치/포먼트 시프트와 지터로 화자 은닉

## 준비

### 필수 요구사항

- PATH에 등록된 model-compose
- Python 3.10+ 및 `pedalboard`, `librosa`, `soxr`, `pyloudnorm`, `torchaudio` (컴포넌트가 처음 실행될 때 자동 설치됩니다)

### 설정

예제 디렉터리로 이동:
```bash
cd examples/media-processing/audio-processor
```

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

   서비스가 다음 위치에서 시작됩니다:
   - API 엔드포인트: http://localhost:8080/api
   - 웹 UI: http://localhost:8081

2. **워크플로우 실행:**

   **웹 UI 사용:**
   - 웹 UI 열기: http://localhost:8081
   - 드롭다운에서 워크플로우 선택
   - 오디오 파일 업로드 및 파라미터 입력
   - "Run Workflow" 클릭

   **CLI 사용:**
   ```bash
   # 16 kHz로 리샘플
   model-compose run resample --input '{
     "audio": "/path/to/input.wav",
     "sample_rate": 16000
   }'

   # 음정을 유지한 채 1.5배속 재생
   model-compose run speed --input '{
     "audio": "/path/to/input.wav",
     "speed": 1.5,
     "preserve_pitch": true
   }'

   # 120 Hz 이하 감쇠 (저역 럼블 제거)
   model-compose run highpass --input '{
     "audio": "/path/to/input.wav",
     "cutoff": 120
   }'

   # 3 kHz 근처 좁은 대역을 +3 dB 부스트
   model-compose run bell --input '{
     "audio": "/path/to/input.wav",
     "frequency": 3000,
     "gain": 3,
     "q": 1.2
   }'

   # 반음 2개만큼 피치 업 (길이 유지)
   model-compose run pitch-shift --input '{
     "audio": "/path/to/input.wav",
     "semitones": 2
   }'

   # -20 dB 이상에 4:1 비율로 컴프레션
   model-compose run compressor --input '{
     "audio": "/path/to/input.wav",
     "threshold": -20,
     "ratio": 4
   }'

   # -14 LUFS로 정규화 (스트리밍 타겟)
   model-compose run normalize-lufs --input '{
     "audio": "/path/to/input.wav",
     "level": -14
   }'

   # -40 dBFS 임계값으로 무음 트림
   model-compose run trim-silence --input '{
     "audio": "/path/to/input.wav",
     "threshold": -40
   }'

   # 약한 피치/포먼트 시프트로 화자 은닉
   model-compose run anonymize --input '{
     "audio": "/path/to/input.wav",
     "pitch_shift": -2,
     "formant_shift": 1.15
   }'
   ```

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=speed" \
     -F "audio=@/path/to/input.wav" \
     -F "speed=1.5" \
     -F "preserve_pitch=true"
   ```

## 컴포넌트 상세

### Audio Processor 컴포넌트

- **타입**: `audio-processor`
- **드라이버**: `native`
- **목적**: PCM 스트림에 DSP 변환을 적용. 스트리밍 method(gain, EQ 필터, compressor, noise-gate, distortion, saturation, chorus, delay, reverb, fade-in, fade-out)는 청크 단위로 실행되며, 전역 통계가 필요한 method(normalize, peak-limit, trim-edges, trim-silence, speed, pitch-shift, dc-shift, anonymize)는 버퍼를 먼저 수집한 뒤 처리합니다.

#### 공통 필드

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|-------|------|----------|---------|-------------|
| `method` | string | 예 | - | 지원되는 액션 method 중 하나 (아래 워크플로우 참조) |
| `audio` | 오디오 소스 | 예 | - | 입력 오디오 (파일 경로, 업로드, 또는 상위 오디오 참조) |
| `batch_size` | integer | 아니오 | `1` | 입력이 리스트/스트림일 때 배치당 처리할 오디오 수 |

출력은 항상 PCM 스트림입니다. 컨테이너/코덱은 결과를 기록하는 쪽에서 결정합니다 (워크플로우 출력의 `${output as audio}`는 기본적으로 WAV 인코딩).

## 워크플로우 상세

### 1. Resample Audio

**설명**: soxr를 사용한 스트리밍 리샘플. 음정과 길이는 유지되고 샘플레이트 레이블만 바뀝니다.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `sample_rate` | integer | 예 | - | 목표 샘플레이트(Hz, 예: `16000`, `44100`, `48000`) |

### 2. Change Speed

**설명**: 오디오 배속을 조절합니다. `preserve_pitch: true`이면 길이는 바뀌지만 음정은 유지됩니다(phase-vocoder time-stretch). `preserve_pitch: false`이면 파형을 리샘플하므로 음정이 배속에 반비례해 함께 변합니다 — chipmunk / slowed-down 효과.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `speed` | number | 예 | - | 배속 배수 (예: `2.0` = 2배속, `0.5` = 절반 속도) |
| `preserve_pitch` | boolean | 아니오 | `true` | 배속 변경 시 원본 음정 유지 여부 |

### 3. Highpass Filter

**설명**: 컷오프 이하 주파수를 감쇠합니다. 저역 럼블이나 DC 오프셋 제거에 유용합니다.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `cutoff` | number | 예 | - | 필터 컷오프 주파수(Hz) |

### 4. Lowpass Filter

**설명**: 컷오프 이상 주파수를 감쇠합니다. 거친 고역대를 부드럽게 하는 데 유용합니다.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `cutoff` | number | 예 | - | 필터 컷오프 주파수(Hz) |

### 5. Bell EQ

**설명**: 중심 주파수 주변의 좁은 대역을 부스트/컷합니다. Q가 클수록 대역이 좁아집니다.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `frequency` | number | 예 | - | 중심 주파수(Hz) |
| `gain` | number | 예 | - | 중심의 게인(dB, 양수 부스트/음수 컷) |
| `q` | number | 아니오 | `0.707` | 대역 폭; Q가 크면 더 좁음 |

### 6. Low Shelf EQ

**설명**: 코너 주파수 이하 전체를 고정 dB만큼 부스트/컷합니다.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `frequency` | number | 예 | - | 셀프 코너 주파수(Hz) |
| `gain` | number | 예 | - | 셀프 게인(dB) |
| `q` | number | 아니오 | `0.707` | 셀프 기울기; Q가 크면 더 가파름 |

### 7. High Shelf EQ

**설명**: 코너 주파수 이상 전체를 고정 dB만큼 부스트/컷합니다.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `frequency` | number | 예 | - | 셀프 코너 주파수(Hz) |
| `gain` | number | 예 | - | 셀프 게인(dB) |
| `q` | number | 아니오 | `0.707` | 셀프 기울기; Q가 크면 더 가파름 |

### 8. Pitch Shift

**설명**: 길이는 유지하면서 반음(semitone) 단위로 피치를 시프트합니다.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `semitones` | number | 예 | - | 피치 시프트 양 (양수 올림/음수 내림) |

### 9. DC Shift

**설명**: 신호의 DC 바이어스(평균 오프셋)를 제거하고 선택적으로 고정 DC 오프셋을 적용합니다.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `offset` | number | 아니오 | `0` | 센터링 후 적용할 DC 오프셋 (-1.0 ~ 1.0) |

### 10. Compress Dynamics

**설명**: `threshold` 이상에 지정된 `ratio`로 다운워드 컴프레션. 큰 부분 레벨을 낮춰 전체를 더 크게 밀 여유를 만듭니다.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `threshold` | number | 아니오 | `-20` | 컴프레션 발동 임계값(dB) |
| `ratio` | number | 아니오 | `4` | 컴프레션 비율 (예: `4` = 4:1) |
| `attack_time` | duration | 아니오 | `1ms` | 어택 타임 |
| `release_time` | duration | 아니오 | `100ms` | 릴리즈 타임 |

### 11. Noise Gate

**설명**: `threshold` 이하 신호를 지정된 `ratio`로 감쇠. 원치 않는 저레벨 노이즈를 정리합니다.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `threshold` | number | 아니오 | `-40` | 게이트 감쇠 임계값(dB) |
| `ratio` | number | 아니오 | `10` | 다운워드 확장 비율 |
| `attack_time` | duration | 아니오 | `1ms` | 게이트 어택 타임 |
| `release_time` | duration | 아니오 | `100ms` | 게이트 릴리즈 타임 |

### 12. Distortion

**설명**: 드라이브 기반 강한 디스토션. 특성 있는 왜곡을 위한 드라이브 범위는 `15`–`40` dB 정도입니다.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `drive` | number | 예 | - | 드라이브 양(dB, 클수록 강함) |

### 13. Saturation

**설명**: 미묘한 하모닉 컬러링. Distortion과 동일 알고리즘이지만 낮은 드라이브(`1`–`8` dB)를 상정합니다.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `drive` | number | 아니오 | `3` | 부드러운 컬러링을 위한 드라이브(dB) |

### 14. Apply Gain

**설명**: 지정된 dB 값에서 유도된 선형 게인을 신호에 곱합니다.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `level` | number | 예 | - | 게인(dB, 양수 부스트/음수 감쇠) |

### 15. Chorus

**설명**: 디튠된 카피를 섞어 소리를 두껍게 만드는 모듈레이션 딜레이 이펙트.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `rate` | number | 아니오 | `1.0` | 코러스 LFO 속도(Hz) |
| `depth` | number | 아니오 | `0.25` | 모듈레이션 깊이 (0.0–1.0) |
| `feedback` | number | 아니오 | `0` | 피드백 양 (0.0–1.0) |
| `delay` | duration | 아니오 | `7ms` | 중심 딜레이 시간 |
| `mix` | number | 아니오 | `0.5` | 드라이/웻 믹스 (0.0=dry, 1.0=wet) |

### 16. Delay

**설명**: 피드백과 웻/드라이 믹스를 가진 단순 딜레이/에코.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `time` | duration | 아니오 | `500ms` | 딜레이 타임 |
| `feedback` | number | 아니오 | `0` | 피드백 양 (0.0–1.0) |
| `mix` | number | 아니오 | `0.5` | 드라이/웻 믹스 |

### 17. Add Reverb

**설명**: 크기, 댐핑, dry/wet 믹스 설정이 가능한 Freeverb 스타일 룸 리버브.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `room_size` | number | 아니오 | `0.5` | 시뮬레이션 룸 크기 (0.0–1.0) |
| `damping` | number | 아니오 | `0.5` | 고주파 댐핑 (0.0–1.0) |
| `wet_level` | number | 아니오 | `0.33` | 리버브 신호 레벨 (0.0–1.0) |
| `dry_level` | number | 아니오 | `0.4` | 드라이 신호 레벨 (0.0–1.0) |
| `width` | number | 아니오 | `1.0` | 리버브 스테레오 폭 (0.0–1.0) |

### 18. Normalize (RMS)

**설명**: 오디오의 RMS(평균 에너지)가 목표 레벨(dBFS)에 도달하도록 스케일링. 게인 적용 후 peak 상한을 씌웁니다.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `level` | number | 아니오 | `-20` | 목표 RMS 레벨(dBFS) |
| `peak_limit` | number | 아니오 | `0.85` | 정규화 후 적용할 peak 진폭 상한 (0.0–1.0) |

### 19. Normalize (Peak)

**설명**: 오디오의 최고 샘플이 목표 peak 레벨(dBFS)에 도달하도록 스케일링.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `level` | number | 아니오 | `-1` | 목표 peak 레벨(dBFS, 예: `-1`은 1 dB 헤드룸 유지) |

### 20. Normalize (LUFS)

**설명**: 통합 라우드니스를 반복 측정·게인 조정하여 목표 LUFS에 맞춘 뒤 true-peak 리미터를 적용.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `level` | number | 아니오 | `-14` | 목표 통합 라우드니스(LUFS) |
| `tolerance` | number | 아니오 | `0.5` | 반복 종료 허용 오차(LU) |
| `max_gain` | number | 아니오 | `30` | 반복이 적용할 수 있는 최대 절대 게인(dB) |
| `true_peak_ceiling` | number | 아니오 | `-1` | 게인 후 강제되는 true-peak 상한(dBTP) |

### 21. Peak Limit (Hard)

**설명**: 입력 peak가 선형 진폭 상한을 넘을 때만 하드 클립. 빠르고 저렴하지만 강하게 밀면 클리핑 아티팩트가 생김.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `level` | number | 아니오 | `0.95` | peak 진폭 상한 (0.0–1.0) |

### 22. Peak Limit (Smooth)

**설명**: 릴리즈 타임이 있는 true-peak 리미터(pedalboard `Limiter`). 하드 클립보다 깨끗함.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `level` | number | 아니오 | `-1` | 상한(dBFS, 예: `-1`은 1 dB 헤드룸 유지) |
| `release_time` | duration | 아니오 | `100ms` | 리미터 릴리즈 타임 |

### 23. Trim Edges

**설명**: peak 대비 임계값(dB) 기준으로 앞뒤 무음을 감지해 잘라냅니다.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `threshold` | number | 아니오 | `40` | peak 이하 무음 임계값(dB) |
| `padding` | duration | 아니오 | `0ms` | 트림 후 각 끝에 복원할 패딩 |

### 24. Trim Silence

**설명**: 무음 구간을 감지해 앞뒤 무음과 `max_internal_silence`보다 긴 내부 무음을 잘라냅니다. 짧은 cosine 페이드가 트림 경계의 클릭을 방지합니다.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `window` | duration | 아니오 | `20ms` | RMS 분석 윈도우 크기 |
| `threshold` | number | 아니오 | `-40` | 무음 임계값(dBFS) |
| `min_silence` | duration | 아니오 | `200ms` | 유지할 최소 뒷 무음 |
| `max_internal_silence` | duration | 아니오 | `1s` | 이보다 긴 내부 무음은 잘라냄 |
| `fade` | duration | 아니오 | `30ms` | 트림 끝에 적용할 cosine 페이드 아웃 |

### 25. Fade In

**설명**: 오디오 시작 부분에 `sin^2` 코사인 커브를 적용.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `duration` | duration | 아니오 | `500ms` | 페이드 인 길이 |

### 26. Fade Out

**설명**: 오디오 끝 부분에 `cos^2` 커브를 적용.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `duration` | duration | 아니오 | `500ms` | 페이드 아웃 길이 |

### 27. Anonymize Voice

**설명**: 피치 시프트, 포먼트 스케일링, 시간 가변 지터로 화자를 은닉하고, 선택적으로 후단에 lowpass를 걸어 고주파 화자 단서를 감쇠.

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `pitch_shift` | number | 아니오 | `-2` | 피치 시프트(반음) |
| `formant_shift` | number | 아니오 | `1.15` | 포먼트 스케일링 비율 (>1은 포먼트 위로) |
| `pitch_jitter` | number | 아니오 | `0.3` | 랜덤 피치 모듈레이션 깊이(반음) |
| `jitter_rate` | number | 아니오 | `4` | 지터 모듈레이션 속도(Hz) |
| `lowpass_cutoff` | number | 아니오 | `6000` | 후단 lowpass 컷오프(Hz, 0 이하는 비활성) |

## 팁

- **스트리밍 vs collect**: 스트리밍 method(`gain`, EQ 필터, `compressor`, `noise-gate`, `distortion`, `saturation`, `chorus`, `delay`, `reverb`, `fade-in`, `fade-out`)는 전체 버퍼를 구체화하지 않고 청크 단위로 실행됩니다. 전역 통계가 필요한 method(`normalize`, `peak-limit`, `trim-edges`, `trim-silence`, `speed`, `pitch-shift`, `dc-shift`, `anonymize`)는 입력을 먼저 수집합니다.
- **`speed` vs `resample` vs `pitch-shift`**: `speed`는 길이를 바꾸고, `resample`은 샘플레이트 레이블만 바꾸며(시간/음정 변화 없음), `pitch-shift`는 음정을 바꾸고 길이를 유지합니다.
- **`speed` with `preserve_pitch: false`**: 순수 리샘플. 배속을 2배로 하면 감지되는 음정 주기가 절반이 되어(한 옥타브 위) chipmunk 효과가 납니다.
- **`normalize` vs `peak-limit`**: `normalize`는 전체 신호를 목표 레벨로 스케일하고, `peak-limit`은 임계값을 넘는 peak만 낮춥니다.
- **LUFS normalize**: 측정 → 게인 → true-peak-limit 루프를 반복. 스트리밍 타겟(Spotify/YouTube)은 `-14`, 펀치감 있는 마스터는 `-9`~`-12`.
- **Trim-silence 튜닝**: `threshold`가 낮을수록(`-50`, `-60`) 무음 판정이 엄격해지고, `max_internal_silence`가 크면 자연스러운 정적을 더 남깁니다.
- **여러 method 체이닝**: `${jobs.<id>.output}`으로 여러 액션을 연결해 `trim-silence → compressor → normalize-lufs → fade-in` 같은 조합을 구성할 수 있습니다.

## 문제 해결

### 자주 발생하는 문제

1. **의존성 누락 (`pedalboard`, `librosa`, `soxr`, `pyloudnorm`)**: 컴포넌트가 이들을 setup requirement로 선언하고 최초 실행 시 자동 설치합니다. 오프라인 등 자동 설치가 실패하는 환경에서는 Python 환경에 수동으로 설치하세요.
2. **트림 경계에서 클릭 발생**: `trim-silence`의 `fade`를 늘리거나(예: `50ms`) 트림 후 명시적 `fade-out`을 이어붙이세요.
3. **`normalize`가 목표 LUFS에 도달하지 못함**: LUFS 루프는 최대 3회 반복하고 `max_gain`을 준수합니다. 매우 작은 소재는 이 한계에 걸릴 수 있으니 `max_gain`을 올리거나 여러 단계로 정규화하세요.
4. **`speed`에서 큰 값 사용 시 아티팩트**: `preserve_pitch: true`가 사용하는 phase-vocoder는 극단적 배속에서 품질이 떨어집니다. `0.5..2.0`을 크게 벗어나는 값은 아티팩트를 감수하거나 `preserve_pitch: false`(리샘플 기반)로 전환하세요.
5. **`distortion` 또는 `peak-limit-hard`가 거칠게 들림**: 둘 다 의도적으로 비선형 왜곡을 넣습니다. 더 부드러운 처리가 필요하면 `saturation`(약한 드라이브) 또는 `peak-limit-smooth`(true-peak 리미터)를 사용하세요.
