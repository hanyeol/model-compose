# Media Inspector 예제

이 예제는 `media-inspector` 컴포넌트를 사용해 미디어 파일(오디오, 비디오, 이미지)의 메타데이터를 디코딩 없이 조회하는 방법을 보여줍니다. `ffprobe`(FFmpeg 번들)와 `exiftool`을 래핑하여, 정규화된 필드와 원본 툴 출력을 함께 반환합니다.

## 개요

세 개의 워크플로우를 제공합니다:

1. **미디어 조회 (ffprobe)**: 오디오/비디오 파일의 전체 메타데이터 페이로드 반환
2. **AV 요약**: 컨테이너 포맷·재생시간·크기·주요 비디오/오디오 스트림만 간추린 요약 반환
3. **이미지 조회 (exiftool)**: 이미지의 EXIF/XMP/GPS 메타데이터 반환

## 준비

### 필수 요구사항

- PATH에 등록된 model-compose
- `ffmpeg` 드라이버용: PATH에 등록된 [FFmpeg](https://ffmpeg.org/) (`ffprobe` 바이너리)
- `exiftool` 드라이버용: PATH에 등록된 [ExifTool](https://exiftool.org/)

### 설정

예제 디렉터리로 이동:
```bash
cd examples/media-processing/media-inspector
```

툴 설치 확인:
```bash
ffprobe -version
exiftool -ver
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

   **CLI 사용:**
   ```bash
   # 오디오/비디오 파일의 전체 메타데이터
   model-compose run inspect --input '{
     "media": "/path/to/input.mp4"
   }'

   # 포맷/재생시간/크기 + 주요 스트림 요약
   model-compose run summary --input '{
     "media": "/path/to/input.mp4"
   }'

   # 이미지의 EXIF/XMP/GPS
   model-compose run inspect-image --input '{
     "image": "/path/to/photo.jpg"
   }'
   ```

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=summary" \
     -F "media=@/path/to/input.mp4"
   ```

## 컴포넌트 상세

### Media Inspector 컴포넌트

- **타입**: `media-inspector`
- **드라이버**: `ffmpeg`(`ffprobe` 사용), `exiftool`
- **목적**: 미디어 파일에서 컨테이너/스트림/EXIF 메타데이터를 디코딩 없이 조회

#### 주요 필드

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|-------|------|----------|---------|-------------|
| `media` | 미디어 소스 | 예 | - | 파일 경로, URL, 또는 보간 변수 |
| `return_raw` | boolean | 아니오 | `true` | 드라이버 원본 출력을 `raw` 필드에 포함할지 여부 |

## 워크플로우 상세

### 1. 미디어 조회 (ffprobe)

**설명**: ffprobe의 전체 페이로드 - 컨테이너 포맷, 스트림별 코덱/비트레이트/재생시간/해상도/fps, 원본 JSON.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|-----------|------|----------|-------------|
| `media` | file | 예 | 원본 오디오/비디오 파일 |

#### 출력 (주요 필드)

| 필드 | 타입 | 설명 |
|-------|------|-------------|
| `format` | string | 컨테이너 포맷 (예: `mp4`, `mkv`, `wav`) |
| `duration` | float | 재생 시간(초) |
| `bitrate` | integer | 전체 비트레이트(bit/s) |
| `video_streams` | list | 비디오 스트림별 항목 (codec, width, height, fps 등) |
| `audio_streams` | list | 오디오 스트림별 항목 (codec, sample_rate, channels 등) |
| `raw` | object | ffprobe 원본 JSON |

### 2. AV 요약

**설명**: ffprobe 페이로드를 짧은 요약으로 축약 - 로깅, 간단한 UI 표시, 라우팅 결정에 유용.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|-----------|------|----------|-------------|
| `media` | file | 예 | 원본 오디오/비디오 파일 |

#### 출력

| 필드 | 타입 | 설명 |
|-------|------|-------------|
| `format` | string | 컨테이너 포맷 |
| `duration` | float | 재생 시간(초) |
| `size` | integer | 파일 크기(바이트) |
| `video` | object \| null | 주 비디오 스트림, 없으면 `null` |
| `audio` | object \| null | 주 오디오 스트림, 없으면 `null` |

### 3. 이미지 조회 (exiftool)

**설명**: 이미지 파일의 EXIF/XMP/GPS 메타데이터. 카메라 설정(ISO, 조리개, 초점거리)과 GPS 좌표가 임베드된 경우 함께 반환.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|-----------|------|----------|-------------|
| `image` | file | 예 | 원본 이미지 파일 (JPEG, PNG, HEIC 등) |

#### 출력 (주요 필드)

| 필드 | 타입 | 설명 |
|-------|------|-------------|
| `width`, `height` | integer | 이미지 크기 |
| `camera` | object | 제조사/모델/렌즈 + 노출 설정 |
| `gps` | object \| null | 위도/경도/고도, 임베드되지 않으면 `null` |
| `metadata.exif` | object | EXIF 태그 블록 |
| `metadata.xmp` | object | XMP 태그 블록 |

## 팁

- **목적에 맞는 드라이버 선택**: 스트림 레벨 상세(코덱, 샘플레이트, fps)는 `ffmpeg`, 임베드 메타데이터(EXIF, XMP, GPS)는 `exiftool`을 사용하세요. 둘 다 필요하면 같은 compose 파일에서 두 드라이버를 각각의 컴포넌트로 정의할 수 있습니다.
- **프로덕션에서는 `return_raw: false`**: `raw` 페이로드는 크며 주로 필드 탐색·디버깅 용도입니다.
- **스트리밍 입력은 spool됨**: 파일이 아닌 소스(업로드, HTTP 스트림)는 두 툴 모두 seek 가능한 입력이 필요하므로 임시 파일로 spool된 후 조회됩니다.

## 문제 해결

### 자주 발생하는 문제

1. **`ffprobe` / `exiftool` not found**: 해당 툴을 설치하고 `PATH`에 등록되어 있는지 확인하세요.
2. **`raw` 페이로드가 너무 큼**: 액션에 `return_raw: false`를 설정하거나 워크플로우의 `output:`에서 필요한 필드만 매핑하세요.
3. **일부 입력에서 `fps: null`**: ffprobe는 알 수 없는 프레임 레이트에 대해 `0/0`을 반환하며, 드라이버는 이를 `null`로 정규화해 "fps 정보 없음"과 "0 fps"를 구분합니다.
