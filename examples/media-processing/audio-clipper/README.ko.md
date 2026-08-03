# Audio Clipper 예제

이 예제는 `audio-clipper` 컴포넌트를 사용해 오디오 파일에서 하나 이상의 구간을 잘라내는 방법을 보여줍니다. 재인코딩 없이 ffmpeg의 `-c copy`로 컷하므로 빠르고 무손실입니다.

## 개요

동일한 `audio-clipper` 컴포넌트를 기반으로 세 개의 워크플로우를 제공합니다:

1. **단일 구간 클리핑**: 한 개의 구간을 잘라 오디오 파일로 반환
2. **다중 구간 클리핑**: 여러 구간을 잘라 오디오 리스트로 반환
3. **클리핑 후 병합**: 여러 구간을 잘라 하나의 오디오 파일로 이어붙임

## 준비

### 필수 요구사항

- PATH에 등록된 model-compose
- PATH에 등록된 [ffmpeg](https://ffmpeg.org/)

### 설정

예제 디렉터리로 이동:
```bash
cd examples/media-processing/audio-clipper
```

ffmpeg 설치 확인:
```bash
ffmpeg -version
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
   - 오디오 파일 업로드 및 구간 입력
   - "Run Workflow" 클릭

   **CLI 사용:**
   ```bash
   # 단일 구간 (10s..25s)
   model-compose run clip-single --input '{
     "audio": "/path/to/input.mp3",
     "start_time": "10s",
     "end_time": "25s"
   }'

   # 여러 구간을 리스트로 반환
   model-compose run clip-multiple --input '{
     "audio": "/path/to/input.mp3",
     "spans": [
       {"start_time": 0, "end_time": 5},
       {"start_time": 30, "end_time": 45}
     ]
   }'

   # 여러 구간을 하나로 병합
   model-compose run clip-and-merge --input '{
     "audio": "/path/to/input.mp3",
     "spans": [
       {"start_time": "00:00:10", "end_time": "00:00:20"},
       {"start_time": "00:01:00", "end_time": "00:01:15"}
     ]
   }'
   ```

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=clip-single" \
     -F "audio=@/path/to/input.mp3" \
     -F "start_time=10s" \
     -F "end_time=25s"
   ```

## 컴포넌트 상세

### Audio Clipper 컴포넌트

- **타입**: `audio-clipper`
- **드라이버**: `ffmpeg`
- **목적**: `ffmpeg -c copy`로 오디오 파일에서 하나 이상의 구간을 재인코딩 없이 잘라냄

#### 주요 필드

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|-------|------|----------|---------|-------------|
| `audio` | 오디오 소스 | 예 | - | 클리핑할 오디오 파일 |
| `span` | 객체 또는 객체 리스트 | 예 | - | 하나 이상의 `{start_time, end_time}` 항목. 단일 객체는 요소 1개짜리 리스트로 자동 승격 |
| `merge` | boolean | 아니오 | `false` | `true`면 모든 클립을 하나의 오디오 파일로 이어붙임 |
| `batch_size` | integer | 아니오 | `1` | 입력이 리스트/스트림일 때 배치당 처리할 오디오 수 |

`start_time`과 `end_time`은 다음 형식을 지원합니다:
- 숫자(초 단위): `10`, `10.5`
- 기간 문자열: `"10s"`, `"1m"`, `"250ms"`
- 타임코드: `"00:00:10"`, `"01:23:45"`

출력 형식은 입력 컨테이너에서 그대로 유지됩니다 (`audio.format` → 파일 확장자 → 최후 수단으로 ffprobe 감지). `-c copy`의 정확성을 보장합니다.

## 워크플로우 상세

### 1. 단일 구간 클리핑

**설명**: 입력 오디오에서 `[start_time, end_time]` 구간 하나를 추출.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `audio` | file | 예 | - | 원본 오디오 파일 |
| `start_time` | 문자열/숫자 | 아니오 | `0s` | 클립 시작 |
| `end_time` | 문자열/숫자 | 아니오 | `10s` | 클립 끝 |

#### 출력

| 필드 | 타입 | 설명 |
|-------|------|-------------|
| `audio` | audio | 추출된 클립 |

### 2. 다중 구간 클리핑

**설명**: 여러 구간을 추출해 오디오 파일 리스트로 반환.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|-----------|------|----------|-------------|
| `audio` | file | 예 | 원본 오디오 파일 |
| `spans` | json | 예 | `{start_time, end_time}` 객체의 JSON 배열 |

#### 출력

| 필드 | 타입 | 설명 |
|-------|------|-------------|
| `audios` | 오디오 리스트 | 입력 순서대로 span마다 하나씩 |

### 3. 클리핑 후 병합

**설명**: 여러 구간을 추출한 뒤 ffmpeg concat demuxer로 하나의 출력 오디오로 이어붙임.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|-----------|------|----------|-------------|
| `audio` | file | 예 | 원본 오디오 파일 |
| `spans` | json | 예 | `{start_time, end_time}` 객체의 JSON 배열 |

#### 출력

| 필드 | 타입 | 설명 |
|-------|------|-------------|
| `audio` | audio | 병합된 클립 |

## 팁

- **무손실**: `-c copy`이므로 재인코딩이 없습니다. 출력은 입력 코덱/컨테이너를 그대로 유지하며, 컷 지점은 컨테이너가 지원하는 가장 가까운 키프레임/프레임 경계에 맞춰집니다.
- **스트리밍 입력**: 파일이 아닌 오디오 소스(bytes, HTTP 업로드)는 임시 파일로 정확히 1회 spool되어 각 구간이 독립적으로 seek할 수 있게 됩니다.
- **스트리밍 span**: `spans` 리스트는 선행 컴포넌트가 생성한 스트리밍 이터레이터일 수도 있으며, 각 span이 도착하는 대로 처리됩니다 (`merge=true`는 예외로, 모든 span이 도착해야 concat이 실행됩니다).
- **merge 시 형식 일관성**: `merge=true`는 ffmpeg `concat` demuxer + `-c copy`를 사용합니다. 모든 클립이 같은 소스에서 나왔기 때문에 코덱/컨테이너 일관성이 보장됩니다.

## 문제 해결

### 자주 발생하는 문제

1. **ffmpeg not found**: ffmpeg (및 ffprobe)가 설치되어 있고 `PATH`에 있는지 확인하세요.
2. **`end_time must be greater than start_time`**: 각 span의 end는 start보다 반드시 커야 합니다.
3. **Unknown format**: 오디오 소스에 format 힌트와 파일 확장자가 모두 없으면 ffprobe로 컨테이너를 감지합니다. 매우 특이하거나 손상된 입력은 이 단계에서 실패할 수 있으니, 파일 확장자를 제공하거나 상위에서 명시적 format을 가진 `MediaSource`로 감싸주세요.
