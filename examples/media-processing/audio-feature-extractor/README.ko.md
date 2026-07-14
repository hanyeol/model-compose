# 오디오 특징 추출기 예제

이 예제는 `audio-feature-extractor` 컴포넌트를 보여주며, model-compose가 오디오 파일을 시각화(이퀄라이저 바, 오실로스코프 파형 등)를 구동하기에 적합한 프레임별 특징 배열로 변환할 수 있는 방법을 설명합니다.

## 개요

두 가지 워크플로우가 제공됩니다:

1. **Spectrum**: 프레임당 FFT 기반 주파수 대역 크기 — 클래식한 바 이퀄라이저 스타일
2. **Waveform**: 프레임당 다운샘플링된 시간 도메인 진폭 — SoundCloud 스타일의 파형 모양

출력은 `frames` 배열이 포함된 JSON 페이로드입니다. 각 항목은 하나의 비디오 프레임의 특징 벡터입니다. 다운스트림 렌더러(Remotion, D3, canvas, SVG)는 오디오에 대한 지식 없이도 이를 직접 소비할 수 있습니다.

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- [ffmpeg](https://ffmpeg.org/)가 설치되어 PATH에서 사용 가능
- numpy (첫 컴포넌트 실행 시 자동 설치됨)

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/media-processing/audio-feature-extractor
   ```

2. ffmpeg 설치 확인:
   ```bash
   ffmpeg -version
   ```

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **웹 UI 사용:**
   - Web UI 열기: http://localhost:8081
   - **Spectrum** 또는 **Waveform** 워크플로우 선택
   - 오디오 파일 업로드
   - 매개변수 조정
   - **Run Workflow** 클릭
   - JSON 출력 확인

   **API 사용:**
   ```bash
   # Spectrum (기본 워크플로우)
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: multipart/form-data" \
     -F "audio=@song.mp3" \
     -F "fps=30" \
     -F "band_count=32"

   # Waveform
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: multipart/form-data" \
     -F "workflow_id=waveform" \
     -F "audio=@song.mp3" \
     -F "fps=30" \
     -F "point_count=100"
   ```

   **CLI 사용:**
   ```bash
   model-compose run spectrum --input '{"audio": "path/to/song.mp3", "band_count": 32}'
   model-compose run waveform --input '{"audio": "path/to/song.mp3", "point_count": 100}'
   ```

## 컴포넌트 세부사항

### Audio Feature Extractor 컴포넌트
- **유형**: `audio-feature-extractor`
- **드라이버**: `ffmpeg` (입력을 모노 PCM으로 디코딩하는 데 사용)
- **계산**: numpy (첫 실행 시 지연 설치)
- **목적**: 오디오 소스에서 프레임별 특징 벡터 생성

컴포넌트는 액션의 `feature` 필드에 따라 계산 경로를 선택합니다:
- `feature: spectrum` — FFT + 로그 스케일 주파수 대역 + 피크 백분위수 정규화
- `feature: waveform` — 버킷당 피크 또는 RMS를 통해 N개 데이터 포인트로 요약된 슬라이딩 윈도우

## 워크플로우 세부사항

### "Spectrum" 워크플로우 (기본)

**설명**: 바 이퀄라이저 시각화에 적합한 주파수 대역 스펙트럼을 추출합니다.

#### 작업 흐름

```mermaid
graph TD
    J1((Default<br/>작업))
    C1[Spectrum<br/>extractor]
    J1 --> C1
    C1 -.-> |frames: number[][]| J1
    Input((입력)) --> J1
    J1 --> Output((출력))
```

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `audio` | file | Yes | - | 오디오 소스 (mp3, wav, flac, aac, m4a, opus, ogg, ...) |
| `fps` | int | No | `30` | 초당 출력 프레임 수 |
| `band_count` | int | No | `32` | 프레임당 주파수 대역 수 |
| `min_frequency` | float | No | `40.0` | 대역 그리드에 포함되는 최저 주파수 (Hz) |
| `window_size` | select | No | `2048` | 샘플 단위의 FFT 윈도우 크기: 512, 1024, 2048, 4096 |
| `window_type` | select | No | `hann` | FFT 윈도우 유형: hann, hamming, blackman |
| `frequency_scale` | select | No | `log` | 주파수 대역 분포 스케일: log, linear |
| `normalize_mode` | select | No | `peak-percentile` | 진폭 정규화: peak-percentile, none |

#### 출력 형식

```json
{
  "fps": 30,
  "band_count": 32,
  "frame_count": 5400,
  "duration": 180.0,
  "sample_rate": 22050,
  "frames": [[0.22, 0.10, ...], [0.24, 0.13, ...], ...]
}
```

`frames`의 각 항목은 하나의 비디오 프레임이며, 그 항목의 각 값은 하나의 주파수 대역의 크기(정규화 시 0..1)입니다. 낮은 인덱스는 저음, 높은 인덱스는 고음입니다.

### "Waveform" 워크플로우

**설명**: 오실로스코프 스타일의 시각화에 적합한 시간 도메인 진폭 파형을 추출합니다.

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `audio` | file | Yes | - | 오디오 소스 |
| `fps` | int | No | `30` | 초당 출력 프레임 수 |
| `point_count` | int | No | `100` | 프레임당 데이터 포인트 수 (파형 표시 해상도) |
| `window_duration` | string | No | `40ms` | 프레임당 분석 윈도우 (예: `40ms`, `0.04s`, `1s`) |
| `summary_mode` | select | No | `peak` | 버킷 요약 통계: `peak` (max\|amplitude\|) 또는 `rms` |
| `rectify` | bool | No | `true` | true이면 크기(0..1) 반환, false이면 부호 있는 값(-1..1) 유지 |

#### 출력 형식

```json
{
  "fps": 30,
  "point_count": 100,
  "frame_count": 5400,
  "duration": 180.0,
  "sample_rate": 22050,
  "frames": [[0.02, 0.15, 0.34, ...], ...]
}
```

`frames`의 각 항목은 하나의 비디오 프레임이며, 그 항목의 각 값은 해당 프레임 윈도우의 한 버킷을 요약하는 하나의 파형 데이터 포인트(피크 또는 RMS)입니다.

## 출력 렌더링

JSON 출력은 의도적으로 렌더러 독립적입니다. 이를 비디오로 변환하는 몇 가지 옵션:

- **Remotion (React)**: `frames`를 props로 `<Composition>`에 전달하고 `useCurrentFrame()`당 막대/경로를 렌더링. 오프라인 배치 렌더링에 좋음
- **SVG / HTML canvas**: 배열을 직접 사용하여 프레임당 막대 또는 폴리라인 그리기
- **기타 도구**: JSON은 짧은 클립의 경우 인라인으로 임베드하기에 충분히 작습니다 (3분 곡, 30 fps × 32 대역 기준 몇 MB)

## 팁

- **`band_count` 선택**: 바 이퀄라이저에는 16-64가 잘 작동. VoyagerFM은 32를 사용합니다.
- **`window_size` 선택 (spectrum)**: 2048이 좋은 균형. 값이 크면 주파수 해상도가 세밀해지지만 시간이 흐려지고, 작으면 반대
- **`min_frequency`와 `max_frequency`**: `max_frequency`는 기본적으로 나이퀴스트 주파수 (`sample_rate / 2`). 가청 불가능한 저음을 건너뛰려면 `min_frequency`를 20-40 Hz 이상으로 올리세요
- **`normalize_mode: peak-percentile`**: 99번째 백분위수를 스케일로 사용. 좋은 기본값. 원시 크기를 원하면 `normalize_mode: none`으로 설정
- **`window_duration` (waveform)**: 20-60 ms가 일반적. 윈도우가 길수록 빠른 트랜지언트가 완화됩니다

## 문제 해결

### 일반적인 문제

1. **ffmpeg를 찾을 수 없음**: ffmpeg가 설치되어 있고 PATH에 있는지 확인 — 컴포넌트는 오디오를 PCM으로 디코딩하기 위해 이를 호출합니다
2. **numpy가 설치되지 않음**: 컴포넌트는 numpy를 지연 요구사항으로 선언하며, 첫 실행 시 pip를 통해 설치됩니다. 설치가 실패하면 수동으로 설치: `pip install numpy`
3. **`window_duration` 값 거부됨**: `"40ms"`, `"0.04s"` 중 하나 또는 순수 숫자(초로 해석)를 사용
4. **반환된 프레임이 0개**: 오디오가 하나의 윈도우보다 짧습니다. `window_size`(spectrum) 또는 `window_duration`(waveform)를 줄이거나 더 긴 입력을 사용하세요
