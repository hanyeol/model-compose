# 얼굴 모자이크 예제

비디오의 모든 얼굴을 검출된 bounding box 단위로 픽셀화(또는 블러)해서 가리고, 원본 오디오 트랙은 그대로 유지한 채 다시 mp4로 재조립하는 워크플로우 예제입니다. 파이프라인 전체가 end-to-end 스트리밍으로 동작하므로 클립 길이에 상관없이 메모리 사용량이 일정하게 유지됩니다.

> **라이선스 주의**: 이 예제는 InsightFace의 `antelopev2` 모델 팩을 자동 다운로드하며, 이 팩의 학습 데이터셋은 **비상업 연구 목적으로만** 라이선싱되어 있습니다. 개인 사용, 연구, 오픈소스 데모, 자체 호스팅 유틸리티는 문제없습니다. 다만 **상업 제품이나 유료 서비스에는 이 팩을 포함하지 마세요** — 그런 경우 상업 사용 가능한 검출기(`family: blazeface`)로 교체하거나 직접 학습한 모델을 사용하세요.

## 개요

입력 비디오를 받아, 모든 얼굴이 모자이크로 가려진 같은 비디오를 반환합니다.

전략:

1. **업로드 스트림을 fan-out** — `fan-out` 작업으로 업로드 스트림을 두 개의 독립 브랜치로 나눔. 오디오 extractor와 frame extractor가 병렬로 각자 소비하므로, 디스크에 비디오를 저장할 필요 없이 1회성 업로드 스트림을 공유.
2. **오디오 트랙 분리** — `audio-extractor`로 비디오에서 오디오만 뽑아둠 (그대로 유지).
3. **모든 프레임 스트리밍** — `video-frame-extractor`로 프레임 스트림 생성 (`streaming: true` — 전체 비디오 버퍼링 없음).
4. **프레임별 검출 + 모자이크** — `face-detection` (InsightFace `antelopev2`)으로 얼굴 bbox를 얻고, 그 리스트를 `image-processor mosaic`에 한 번에 넘겨서 한 프레임의 모든 얼굴을 한 패스로 가림. extractor가 스트림을 emit하므로 `for-each`의 output도 스트림 — 모자이크된 프레임이 encoder로 지연 흐름.
5. **모자이크된 프레임 스트림 재인코딩** — `video-encoder`로 mp4로 인코딩하면서 앞서 추출한 오디오를 mux. ffmpeg가 필요할 때 상류 스트림에서 프레임을 당겨오므로 이 단계에서도 전체 비디오 버퍼링 없음.

프레임별 detect+mosaic 쌍은 프라이빗 서브워크플로우(`mosaic-faces-in-frame`)로 감싸서 메인 워크플로우의 `for-each`가 깔끔하게 유지되도록 했습니다.

### 스트리밍이 중요한 이유

단순한 설계라면 모든 프레임을 메모리에 올린 뒤 전체 리스트에 검출을 실행하고, 모자이크된 리스트를 encoder에 넘깁니다. 짧은 클립엔 문제없지만 긴 비디오에서는 메모리가 터집니다 (1080p 30fps 10분 클립 = 18,000 프레임 × 디코딩된 ~6 MB = ~110 GB의 PIL 이미지).

end-to-end 스트리밍이면 최대 `batch_size` 개의 프레임만 검출 파이프라인을 동시에 통과하고, encoder는 도착한 모자이크 프레임을 그때그때 소비합니다. 클립 길이에 상관없이 메모리는 일정하게 유지됩니다.

## 준비

### 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- FFmpeg가 설치되어 PATH에서 사용 가능
- InsightFace 검출용 의존성:
  ```bash
  pip install insightface opencv-python onnxruntime
  ```
- `antelopev2` InsightFace 모델 팩은 첫 실행 시 `~/.cache/models/insightface/`로 자동 다운로드됩니다.

### 설정

1. 예제 디렉터리로 이동:
   ```bash
   cd examples/media-processing/face-mosaic
   ```

2. 모자이크 처리할 비디오 파일 준비.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **Web UI:**
   - Web UI 열기: http://localhost:8081
   - 비디오 업로드하고 필요 시 `mode` / `block_scale` / `blur_radius` / `frame_rate` / `min_confidence` 조정
   - "Run Workflow" 클릭

   **API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'input={"mode": "pixelate", "block_scale": 0.08, "frame_rate": 30};type=application/json' \
     -F 'video=@./video.mp4'
   ```

   **CLI:**
   ```bash
   model-compose run --input '{
     "video": "./video.mp4",
     "mode": "pixelate",
     "block_scale": 0.08,
     "frame_rate": 30
   }'
   ```

## 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `video` | video (file) | Yes | - | 처리할 입력 비디오 |
| `mode` | string | No | `pixelate` | 모자이크 알고리즘: `pixelate` 또는 `blur` |
| `block_scale` | number | No | `0.1` | 각 얼굴의 짧은 변에 대한 상대 블록 크기 비율 (0.0 – 1.0). region 크기에 자동으로 적응 — 멀리 있는 작은 얼굴과 가까이 있는 큰 얼굴이 시각적으로 동일한 강도로 처리됩니다. `mode: pixelate`일 때 사용 |
| `blur_radius` | number | No | `8.0` | 블러 반경(픽셀). `mode: blur`일 때 사용 |
| `min_confidence` | number | No | `0.5` | 얼굴 검출 최소 신뢰도(0.0 – 1.0). InsightFace `det_thresh`로 전달됨. 얼굴이 놓쳐지면 낮추세요(예: `0.3`) — 마스킹 목적에는 놓치는 얼굴보다 오탐지가 낫습니다 |
| `frame_rate` | number | No | `30` | 출력 프레임 레이트. 원본 fps에 맞추지 않으면 오디오 싱크가 어긋남 |

## 컴포넌트 상세

### Audio Extractor (`audio-extractor`)
- **타입**: `audio-extractor`
- **드라이버**: `ffmpeg`
- **역할**: 비디오 스트림에서 오디오만 mp3로 분리. 상류 `fan-out` 작업의 한 브랜치에서 흘러들어와 frame extractor와 병렬로 업로드 스트림을 소비. 나중에 encoder가 이 오디오를 모자이크된 비디오에 다시 mux.

### Frame Extractor (`frame-extractor`)
- **타입**: `video-frame-extractor`
- **드라이버**: `ffmpeg`
- **역할**: 매 프레임(`frame_interval: 1`)을 ffmpeg가 디코딩하는 대로 스트림으로 emit. `streaming: true`이므로 extractor는 비디오 전체를 버퍼링하지 않고, 각 `{image, timestamp}` chunk가 곧바로 아래 `for-each`로 흐름.

### Face Detector (`face-detector`)
- **타입**: `model` — `face-detection` 태스크
- **드라이버**: `custom` (InsightFace family, `antelopev2` 팩)
- **역할**: 각 프레임에서 `{faces: [{bounding_box: {x, y, width, height}, score, ...}], width, height}` 반환. 하류에서는 `bounding_box`만 사용. 옆모습·작은·비정면 얼굴에 강해서 BlazeFace 대신 선택 — 마스킹 워크플로우에서 가장 중요한 특성.

### Mosaic (`mosaic`)
- **타입**: `image-processor` (`mosaic` 메서드)
- **드라이버**: `native`
- **역할**: 여러 region에 한 번에 모자이크 적용. `region`은 단일 `{x, y, width, height}` dict 또는 그 리스트를 받으며, `${jobs.detect.output.faces[*].bounding_box}`가 검출기의 얼굴들을 그 형태로 바로 흘려보냄.

### Per-Frame Wrapper (`mosaic-faces-in-frame`)
- **타입**: `workflow` (프라이빗 서브워크플로우 `mosaic-faces-in-frame` 호출)
- **역할**: 메인 워크플로우의 `for-each`가 두 단계(detect + mosaic) 파이프라인을 하나의 컴포넌트처럼 호출할 수 있도록 감쌈.

### Encoder (`encoder`)
- **타입**: `video-encoder`
- **드라이버**: `ffmpeg`
- **역할**: 모자이크된 프레임 스트림을 mp4(`libx264 @ 8M`)로 인코딩하고 오디오(`aac @ 192k`)를 mux. 스트림 입력을 지원하므로 ffmpeg가 필요할 때 프레임을 당겨감.

## 참고와 튜닝

- **비용**: 얼굴 검출이 매 프레임 실행됩니다. 10초 30fps 클립 = 300회 호출. InsightFace의 SCRFD 검출기는 BlazeFace보다 무겁지만 여전히 빠릅니다(CPU에서 프레임당 수십 ms, CoreML/CUDA에서 더 빠름). 전체 소요 시간은 프레임 수에 선형 비례.
- **동시성**: `for-each`의 `batch_size: 4`는 최대 4개의 detect+mosaic 파이프라인을 동시에 실행. 값을 올리면 메모리와 처리량을 교환하고, 모델 컴포넌트가 경합의 병목이 되면 낮추세요.
- **프레임 레이트**: 원본과 출력 fps가 다르면 오디오/비디오 싱크가 어긋납니다. 원본의 실제 fps를 `frame_rate`로 넘기세요.
- **놓치는 얼굴**: 그래도 얼굴이 놓쳐지면 `min_confidence`를 낮추세요(예: `0.3`) — 오탐지도 모자이크되지만 마스킹 목적엔 옳은 트레이드오프입니다. 매우 작은 얼굴이라면 `face-detector`의 `params.detection_size`를 올리세요(예: `[960, 960]`, `[1280, 1280]`) — 검출기가 이 입력 해상도에서 실행되므로 크기를 키우면 작은 얼굴을 더 많이 잡지만 처리량이 낮아집니다.
- **모자이크 강도**: `pixelate`는 `block_scale`이 클수록 강하게 가림(일반적으로 `0.05`–`0.2`). 블록 크기는 각 region의 짧은 변을 기준으로 계산되므로 같은 `block_scale`이면 원근과 무관하게 시각적으로 일관된 강도를 유지합니다. 계산된 블록은 `min_block_size`(기본 `8`)로 하한, `max_block_size`(기본 `32`)로 상한이 걸려 — 작은 얼굴은 1–2픽셀짜리 무의미한 블록 대신 여전히 눈에 띄는 모자이크가 되고, 화면을 꽉 채우는 큰 얼굴이 픽셀아트 같은 커다란 타일 몇 개로 바뀌지 않습니다. 어느 한쪽 극단이 여전히 어색하면 해당 하/상한을 조정하세요. 절대 픽셀 크기를 고정하고 싶으면(mosaic 컴포넌트 config에서) `block_size`를 대신 사용하세요. `blur`는 `blur_radius`를 올림(일반적으로 8–20). 블러는 반경이 낮으면 얼굴 윤곽이 남을 수 있으니, 완전히 알아볼 수 없게 하려면 `pixelate` 추천.
- **겹치는 얼굴**: 박스가 겹칠 때 뒤 region은 앞 region이 이미 모자이크한 픽셀 위에 다시 적용되므로, 겹친 얼굴도 모두 가려집니다.
- **박스 여유**: 검출기가 눈/코 위주로 타이트하게 잡아 머리/턱이 남는 경우가 있습니다. `face-detector`에 `bounding_box_padding`(예: `0.2`)을 지정하면 각 반환 박스를 모든 방향으로 20% 확장한 뒤 mosaic으로 흘려보냅니다.
