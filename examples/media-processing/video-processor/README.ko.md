# Video Processor 예제

이 예제는 ffmpeg를 사용해 비디오의 프레임 단위 변환(resize, crop, pad, flip, rotate)을 수행하는 `video-processor` 컴포넌트를 보여줍니다. 모든 메서드가 ffmpeg 비디오 필터를 통과하므로 비디오 트랙은 항상 재인코딩되며, 오디오 트랙은 기본적으로 stream copy되어 무손실로 유지됩니다.

## 개요

동일한 `video-processor` 컴포넌트를 기반으로 다섯 개의 워크플로우를 제공합니다:

1. **Resize Video**: `fit`, `fill`, `stretch` 방식으로 비디오 크기 조정
2. **Crop Video**: 모든 프레임에서 사각 영역을 잘라냄
3. **Pad Video**: 비디오 주위에 단색 테두리 추가
4. **Flip Video**: 비디오를 수평/수직으로 뒤집음
5. **Rotate Video**: 임의 각도로 비디오 회전, 캔버스 확장 옵션 지원

## 준비

### 필수 요구사항

- PATH에 등록된 model-compose
- PATH에 등록된 [ffmpeg](https://ffmpeg.org/)

### 설정

예제 디렉터리로 이동:
```bash
cd examples/media-processing/video-processor
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
   - 비디오 파일 업로드 및 파라미터 입력
   - "Run Workflow" 클릭

   **CLI 사용:**
   ```bash
   # 지정 박스 안에 종횡비를 유지하며 960x540으로 리사이즈
   model-compose run resize --input '{
     "video": "/path/to/input.mp4",
     "width": 960,
     "height": 540,
     "scale_mode": "fit"
   }'

   # (100, 50)에서 시작하는 640x360 영역 크롭
   model-compose run crop --input '{
     "video": "/path/to/input.mp4",
     "x": 100,
     "y": 50,
     "width": 640,
     "height": 360
   }'

   # 사방으로 20px 빨간 테두리 추가
   model-compose run pad --input '{
     "video": "/path/to/input.mp4",
     "left": 20, "right": 20, "top": 20, "bottom": 20,
     "color": "red"
   }'

   # 수직으로 뒤집기
   model-compose run flip --input '{
     "video": "/path/to/input.mp4",
     "direction": "vertical"
   }'

   # 반시계 방향으로 90도 회전하고 캔버스 확장
   model-compose run rotate --input '{
     "video": "/path/to/input.mp4",
     "angle": 90,
     "expand": true
   }'
   ```

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=resize" \
     -F "video=@/path/to/input.mp4" \
     -F "width=960" \
     -F "height=540" \
     -F "scale_mode=fit"
   ```

## 컴포넌트 상세

### Video Processor 컴포넌트

- **타입**: `video-processor`
- **드라이버**: `ffmpeg`
- **목적**: ffmpeg 비디오 필터를 통해 프레임 단위 변환(resize, crop, pad, flip, rotate)을 비디오에 적용. 비디오 트랙은 재인코딩되며, 오디오 트랙은 기본적으로 stream copy됨.

#### 공통 필드

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|-------|------|----------|---------|-------------|
| `method` | string | 예 | - | `resize`, `crop`, `pad`, `flip`, `rotate` 중 하나 |
| `video` | 비디오 소스 | 예 | - | 입력 비디오 (파일 경로, 업로드, 또는 상위 비디오 참조) |
| `encoding` | 객체 | 아니오 | - | 출력 인코딩 오버라이드 (`format`, `video.codec`, `video.bitrate` 등). 미지정 시 컨테이너는 입력 형식을 따르고 오디오는 stream copy됨 |
| `batch_size` | integer | 아니오 | `1` | 입력이 리스트/스트림일 때 배치당 처리할 비디오 수. 배치는 동시에 실행됨 |

`encoding`이 지정되지 않으면 컨테이너는 입력 형식(없으면 `mp4`)을 따르고, 비디오 코덱은 해당 컨테이너의 기본값(예: `mp4`이면 `libx264`, `webm`이면 `libvpx-vp9`)을 사용하며, 오디오 트랙은 그대로 복사됩니다.

## 워크플로우 상세

### 1. Resize Video

**설명**: 비디오를 목표 `(width, height)` 박스로 리사이즈. 스케일링 방식 설정 가능.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `video` | file | 예 | - | 원본 비디오 파일 |
| `width` | integer | 예 | - | 목표 너비(픽셀) |
| `height` | integer | 예 | - | 목표 높이(픽셀) |
| `scale_mode` | select | 아니오 | `fit` | `fit`(레터박스로 안에 맞춤), `fill`(꽉 채우고 가운데 크롭), `stretch`(비율 무시하고 늘림) |

#### 출력

| 필드 | 타입 | 설명 |
|-------|------|-------------|
| `video` | video | 리사이즈된 비디오 |

### 2. Crop Video

**설명**: 모든 프레임에서 사각 영역을 추출.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `video` | file | 예 | - | 원본 비디오 파일 |
| `x` | integer | 아니오 | `0` | 크롭 영역 좌상단의 X 좌표 |
| `y` | integer | 아니오 | `0` | 크롭 영역 좌상단의 Y 좌표 |
| `width` | integer | 예 | - | 크롭 너비(픽셀) |
| `height` | integer | 예 | - | 크롭 높이(픽셀) |

#### 출력

| 필드 | 타입 | 설명 |
|-------|------|-------------|
| `video` | video | 크롭된 비디오 |

### 3. Pad Video

**설명**: 프레임 내용을 바꾸지 않고 비디오 주위에 단색 테두리를 추가.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `video` | file | 예 | - | 원본 비디오 파일 |
| `left` | integer | 아니오 | `0` | 왼쪽 패딩(픽셀) |
| `right` | integer | 아니오 | `0` | 오른쪽 패딩(픽셀) |
| `top` | integer | 아니오 | `0` | 위쪽 패딩(픽셀) |
| `bottom` | integer | 아니오 | `0` | 아래쪽 패딩(픽셀) |
| `color` | string | 아니오 | `black` | 테두리 색상. ffmpeg 색상 이름(`black`, `red`, `white`), hex 문자열(`#ff0000`, `#00ff00ff`), RGBA 튜플 지원 |

#### 출력

| 필드 | 타입 | 설명 |
|-------|------|-------------|
| `video` | video | 패딩이 추가된 비디오 |

### 4. Flip Video

**설명**: 요청한 축으로 비디오를 반전.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `video` | file | 예 | - | 원본 비디오 파일 |
| `direction` | select | 아니오 | `horizontal` | 반전 축: `horizontal` 또는 `vertical` |

#### 출력

| 필드 | 타입 | 설명 |
|-------|------|-------------|
| `video` | video | 반전된 비디오 |

### 5. Rotate Video

**설명**: 모든 프레임을 반시계 방향으로 `angle`도 회전.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `video` | file | 예 | - | 원본 비디오 파일 |
| `angle` | number | 예 | - | 회전 각도(도, 반시계 방향) |
| `expand` | boolean | 아니오 | `true` | `true`면 캔버스를 확장해 회전된 프레임이 투명 배경 위에 온전히 들어가고, `false`면 원본 프레임 크기를 유지하고 넘치는 부분을 크롭 |

#### 출력

| 필드 | 타입 | 설명 |
|-------|------|-------------|
| `video` | video | 회전된 비디오 |

## 팁

- **비디오는 재인코딩, 오디오는 아님**: 필터 그래프는 프레임을 디코드하므로 `-c:v copy`가 불가능하며 비디오 트랙은 항상 재인코딩됩니다. `encoding.audio.codec`으로 오버라이드하지 않으면 오디오 트랙은 `-c:a copy`로 처리됩니다.
- **출력 컨테이너**: 명시적 `encoding.format`이 없으면 출력 컨테이너는 입력 형식(없으면 `mp4`)을 따릅니다. `encoding`을 지정하면 컨테이너(`mp4` → `webm`), 코덱(`libx264` → `libvpx-vp9`), bitrate, resolution, fps를 한 번에 바꿀 수 있습니다.
- **회전 방향**: `angle`은 `image-processor`의 `rotate`와 동일하게 반시계 방향 도(°) 단위입니다. 내부적으로 ffmpeg의 `rotate` 필터(시계 방향 라디안)로 부호를 반전해 전달합니다.
- **한 축만 지정한 종횡비 유지 리사이즈**: `width` 또는 `height` 중 하나를 비워두면 나머지 축은 소스 종횡비에서 자동 계산됩니다.
- **배치 병렬화**: 입력이 비디오 리스트일 때 배치의 ffmpeg 서브프로세스가 동시에 실행됩니다. 동시에 실행되는 비디오 수는 `batch_size`로 제한할 수 있습니다.

## 문제 해결

### 자주 발생하는 문제

1. **ffmpeg not found**: ffmpeg (및 ffprobe)가 설치되어 있고 `PATH`에 있는지 확인하세요.
2. **지원되지 않는 코덱/컨테이너 조합**: `encoding`을 오버라이드하면 ffmpeg가 mux할 수 없는 조합(예: `avi`에 `vp9`)이 나올 수 있습니다. 대상 컨테이너와 호환되는 코덱을 선택하거나, `encoding`을 비워 컨테이너 기본 코덱을 수용하세요.
3. **회전 시 모서리가 잘림**: `expand: false`이면 출력이 입력과 동일한 크기이므로 회전된 프레임의 모서리가 잘립니다. 모든 내용을 유지하려면 `expand: true`로 설정하세요.
4. **fit / fill vs stretch**: `fit`은 레터박스(비율 유지를 위해 투명 패딩 추가), `fill`은 꽉 채우고 넘치는 부분을 가운데 크롭, `stretch`는 비율을 무시하고 지정 크기로 늘립니다.
