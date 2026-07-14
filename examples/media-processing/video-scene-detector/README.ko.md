# 비디오 장면 감지 예제

이 예제는 model-compose의 `video-scene-detector` 컴포넌트를 사용하여 다양한 감지 백엔드로 비디오 파일의 장면 전환을 감지하는 방법을 보여줍니다.

## 개요

이 예제는 4가지 장면 감지 워크플로우를 제공합니다:

1. **적응형 감지**: PySceneDetect의 적응형 감지기 사용 (대부분의 영상에 권장)
2. **콘텐츠 감지**: PySceneDetect의 콘텐츠 인식 감지기 사용
3. **시간 범위 감지**: 특정 시간 범위 내에서 감지기를 선택하여 장면 감지
4. **FFmpeg 감지**: FFmpeg 내장 장면 필터 사용

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- FFmpeg 설치 (`ffmpeg` 드라이버에 필요)
- Python 의존성은 첫 실행 시 자동 설치:
  - `scenedetect[opencv]` (`pyscenedetect` 드라이버용)

### 설정

이 예제 디렉토리로 이동:
```bash
cd examples/video-scene-detector
```

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

   서비스 시작 후:
   - API 엔드포인트: http://localhost:8080/api
   - 웹 UI: http://localhost:8081

2. **워크플로우 실행:**

   **웹 UI 사용:**
   - 웹 UI 열기: http://localhost:8081
   - 드롭다운에서 워크플로우 선택
   - 비디오 파일 업로드
   - "Run Workflow" 버튼 클릭

   **CLI 사용:**
   ```bash
   # 적응형 감지
   model-compose run detect-scenes --input '{"video": "/path/to/video.mp4"}'

   # 콘텐츠 감지 (임계값 커스텀)
   model-compose run detect-scenes-content --input '{"video": "/path/to/video.mp4", "threshold": 30.0}'

   # 시간 범위 감지
   model-compose run detect-scenes-range --input '{
     "video": "/path/to/video.mp4",
     "detector": "content",
     "start_time": "00:01:00",
     "end_time": "00:05:00"
   }'

   # FFmpeg 감지
   model-compose run detect-scenes-ffmpeg --input '{"video": "/path/to/video.mp4", "threshold": 0.4}'
   ```

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=detect-scenes" \
     -F "video=@/path/to/video.mp4"
   ```

## 컴포넌트 세부사항

### 비디오 장면 감지 컴포넌트

- **유형**: `video-scene-detector`
- **목적**: 비디오 파일의 장면 전환 및 변경 감지
- **드라이버**:
  - `pyscenedetect` - 5종 감지기를 제공하는 PySceneDetect 라이브러리 (기본값)
  - `ffmpeg` - FFmpeg 장면 필터
  - `transnetv2` - TransNetV2 딥러닝 모델

## 워크플로우 세부사항

### 1. 장면 감지 (적응형)

**ID**: `detect-scenes`
**설명**: PySceneDetect의 적응형 감지기를 사용하여 장면 전환 감지

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `video` | file | 예 | - | 분석할 비디오 파일 |
| `threshold` | number | 아니오 | `27.0` | 감지 민감도 임계값 |

---

### 2. 장면 감지 (콘텐츠)

**ID**: `detect-scenes-content`
**설명**: PySceneDetect의 콘텐츠 인식 감지기를 사용하여 장면 전환 감지

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `video` | file | 예 | - | 분석할 비디오 파일 |
| `threshold` | number | 아니오 | `27.0` | 감지 민감도 임계값 |

---

### 3. 장면 감지 (시간 범위)

**ID**: `detect-scenes-range`
**설명**: 특정 시간 범위 내에서 장면 전환 감지

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `video` | file | 예 | - | 분석할 비디오 파일 |
| `detector` | select | 아니오 | `adaptive` | 감지기 유형: adaptive, content, threshold, histogram, hash |
| `threshold` | number | 아니오 | - | 감지 민감도 임계값 |
| `start_time` | string | 아니오 | - | 시작 시간 (예: `00:01:00`) |
| `end_time` | string | 아니오 | - | 종료 시간 (예: `00:05:00`) |

---

### 4. 장면 감지 (FFmpeg)

**ID**: `detect-scenes-ffmpeg`
**설명**: FFmpeg의 장면 필터를 사용하여 장면 전환 감지

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `video` | file | 예 | - | 분석할 비디오 파일 |
| `threshold` | number | 아니오 | `0.3` | 장면 전환 임계값 (0.0 - 1.0) |

---

### 출력 형식

모든 워크플로우는 동일한 출력 구조를 반환합니다:

| 필드 | 유형 | 설명 |
|-----|------|------|
| `scenes` | array | 감지된 장면 목록 |
| `scenes[].index` | integer | 장면 인덱스 (0부터 시작) |
| `scenes[].start` | string | 장면 시작 타임코드 (HH:MM:SS.mmm) |
| `scenes[].end` | string | 장면 종료 타임코드 (HH:MM:SS.mmm) |
| `scenes[].start_frame` | integer | 장면 시작 프레임 번호 |
| `scenes[].end_frame` | integer | 장면 종료 프레임 번호 |
| `scenes[].duration` | string | 장면 지속 시간 타임코드 |
| `total_scenes` | integer | 감지된 총 장면 수 |

#### 출력 예시

```json
{
  "scenes": [
    {
      "index": 0,
      "start": "00:00:00.000",
      "end": "00:00:12.345",
      "start_frame": 0,
      "end_frame": 370,
      "duration": "00:00:12.345"
    },
    {
      "index": 1,
      "start": "00:00:12.345",
      "end": "00:00:28.678",
      "start_frame": 370,
      "end_frame": 860,
      "duration": "00:00:16.333"
    }
  ],
  "total_scenes": 2
}
```

## 맞춤화

### 드라이버 변경

`driver` 필드를 변경하여 다른 감지 백엔드를 사용할 수 있습니다:

```yaml
components:
  - id: scene-detector
    type: video-scene-detector
    driver: ffmpeg           # pyscenedetect, ffmpeg, transnetv2
```

### PySceneDetect 감지기 유형

| 감지기 | 설명 | 기본 임계값 |
|--------|------|------------|
| `adaptive` | 적응형 콘텐츠 감지 (권장) | 27.0 |
| `content` | 프레임 차이 기반 콘텐츠 인식 감지 | 27.0 |
| `threshold` | 페이드 인/아웃 감지 | 12.0 |
| `histogram` | HSV 히스토그램 기반 감지 | 0.05 |
| `hash` | 지각 해시 기반 감지 | 0.395 |

### FFmpeg 임계값 가이드

FFmpeg 장면 필터 임계값 범위는 `0.0` ~ `1.0`입니다:
- `0.1` - 매우 민감 (미세한 변화도 감지)
- `0.3` - 기본값 (균형 잡힌 감지)
- `0.5` - 낮은 민감도 (주요 장면 전환만 감지)
