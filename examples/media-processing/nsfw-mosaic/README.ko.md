# NSFW 모자이크 예제

비디오 안의 NSFW(선정성) 영역을 검출된 bounding box 단위로 픽셀화(또는 블러)해서 가리고, 원본 오디오 트랙은 그대로 유지한 채 다시 mp4로 재조립하는 워크플로우 예제입니다. 콘텐츠 모더레이션 용도 — 노출 콘텐츠가 포함될 수 있는 비디오를 안전하게 표시/공유 가능한 버전으로 변환하는 데 사용합니다.

파이프라인 전체가 end-to-end 스트리밍으로 동작하므로 클립 길이에 상관없이 메모리 사용량이 일정하게 유지됩니다.

> **모델은 직접 준비**: 이 예제는 NSFW 가중치를 자동 다운로드하지 않습니다. NSFW 클래스로 학습된 YOLO 포맷 검출기를 `./models/nsfw_detector.pt`에 두어야 합니다. 아래 [검출 모델 준비](#검출-모델-준비) 섹션 참고.

> **책임 있게 사용**: 이 예제의 목적은 "이미 처리 권한이 있는 비디오(모더레이션 큐, 법무 검토, 개인 라이브러리 등)에서 성인 콘텐츠를 한 방향으로 가리는 것"입니다. 사람을 프로파일링하거나 감시하는 용도, 검토 권한이 없는 콘텐츠를 뜯어보는 용도로는 사용하지 마세요. 검출은 완벽하지 않습니다 — 저해상도, 모션 블러, 특이한 각도에서는 일부 영역이 누락될 수 있으므로 안전 크리티컬한 파이프라인이라면 사람 검토 단계를 함께 두는 것을 권장합니다.

## 개요

입력 비디오를 받아, 모든 NSFW 영역이 모자이크로 가려진 같은 비디오를 반환합니다.

전략:

1. **업로드 스트림을 fan-out** — `fan-out` 작업으로 업로드 스트림을 두 개의 독립 브랜치로 나눔. 오디오 extractor와 frame extractor가 병렬로 각자 소비하므로, 디스크에 비디오를 저장할 필요 없이 1회성 업로드 스트림을 공유.
2. **오디오 트랙 분리** — `audio-extractor`로 비디오에서 오디오만 뽑아둠 (그대로 유지).
3. **모든 프레임 스트리밍** — `video-frame-extractor`로 프레임 스트림 생성 (`streaming: true` — 전체 비디오 버퍼링 없음).
4. **프레임 스트림에 object-tracking 실행** — `streaming: true`로, 각 chunk에 원본 이미지와 검출된 NSFW bounding box가 담긴 프레임별 detection chunk 스트림을 emit. 트랙 세그먼트/트랙 집계/종료 메타데이터 chunk는 모두 억제 — 모자이크 스텝은 프레임별 detection만 필요.
5. **각 프레임별 chunk에서 모자이크 적용** — 인라인 `accumulate` 스텝으로 검출된 bounding box들을 한 번에 순차 적용. 검출이 하나도 없는 프레임은 accumulator가 그대로 통과.
6. **모자이크된 프레임 스트림 재인코딩** — `video-encoder`로 mp4로 인코딩하면서 앞서 추출한 오디오를 mux. ffmpeg가 필요할 때 상류 스트림에서 프레임을 당겨오므로 이 단계에서도 전체 비디오 버퍼링 없음.

### 스트리밍이 중요한 이유

단순한 설계라면 모든 프레임을 메모리에 올린 뒤 전체 리스트에 검출을 실행하고, 모자이크된 리스트를 encoder에 넘깁니다. 짧은 클립엔 문제없지만 긴 비디오에서는 메모리가 터집니다 (1080p 30fps 10분 클립 = 18,000 프레임 × 디코딩된 ~6 MB = ~110 GB의 PIL 이미지).

end-to-end 스트리밍이면 최대 `batch_size` 개의 프레임만 모자이크 스텝을 동시에 통과하고, encoder는 도착한 모자이크 프레임을 그때그때 소비합니다. 클립 길이에 상관없이 메모리는 일정하게 유지됩니다.

### 왜 object-tracking인가 (bare object-detection이 아니라)

여기서 object-tracking은 프레임별 검출 + 데이터 캐리어로만 사용합니다 — `track_id`, 세그먼트 등의 identity 정보는 모자이크에 필요없어서 관련 chunk 타입은 모두 억제됩니다. 그럼에도 tracker를 쓰는 이유는 두 가지입니다:

- **프레임별 chunk가 원본 이미지를 함께 실어옴**. 각 `{type: "detection", ...}` chunk가 `objects`와 함께 프레임의 `image`를 이미 담고 있어서 모자이크 스텝은 단일 `for-each` — 프레임당 iteration 하나 — 만 있으면 됩니다. bare `object-detection` 컴포넌트를 쓰면 원본 이미지가 별도 스트림에 남아 프레임별로 zip해야 하므로 detect → accumulate 두 스텝 파이프라인이 강제됩니다.
- **갭 보간으로 짧은 검출 누락을 커버**. 두 히트 사이에서 검출기가 1–2 프레임을 놓쳤을 때, tracker가 놓친 프레임의 `objects` 리스트에 보간된 bounding box를 채워넣습니다 — 원래라면 커버되지 않았을 프레임까지 모자이크가 적용됨. 갭 보간 윈도우는 `params.merge_gap` 초 (기본 `0.5`).

detection chunk는 보간 윈도우가 닫힐 기회를 주기 위해 `merge_gap`만큼 지연 후 emit됩니다 — 스트리밍 지연이 그만큼 생기지만, 이 지연이 갭 보간을 가능하게 하는 메커니즘입니다. `params.min_frame_count`는 detection chunk에는 적용되지 **않고** (non-streaming 결과에서 확정된 트랙에만 적용) 1-프레임 검출도 모자이크 스텝까지 도달합니다. 모자이크 용도로는 이게 올바른 트레이드오프 — false positive는 그냥 모자이크가 한 번 더 씌워질 뿐, miss보다 훨씬 안전.

## 준비

### 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- FFmpeg가 설치되어 PATH에서 사용 가능
- Ultralytics YOLO 트래킹 의존성:
  ```bash
  pip install ultralytics lap
  ```

### 검출 모델 준비

NSFW 영역을 검출하도록 학습된 YOLO 포맷(`.pt`) 검출기가 필요합니다. 권장 기본값은 **NudeNet v3.4 640m** — [notAI-tech](https://github.com/notAI-tech/NudeNet)가 학습한 YOLOv8m 검출기로 18개 클래스(노출/가림 양쪽 커버)를 제공합니다. 라이선스는 AGPL-3.0.

[Hugging Face 미러](https://huggingface.co/vladmandic/nudenet)에서 다운로드하세요 (GitHub 릴리스 다운로드가 이 리포에서는 로그인 페이지로 리다이렉트되는 경우가 있어 미러를 사용합니다):

```bash
curl -fL -o models/nsfw_detector.pt \
  https://huggingface.co/vladmandic/nudenet/resolve/main/nudenet-v34-640m.pt
```

파일이 ~52 MB인지 확인하세요 — HTML 몇 KB만 받아졌다면 다운로드 실패입니다. `file models/nsfw_detector.pt`가 `Zip archive data`라고 나오면 정상 (PyTorch `.pt`는 zip 컨테이너 포맷).

Ultralytics 호환 `.pt` 가중치 중 NSFW 관련 클래스 라벨을 가진 것이면 어떤 것이든 대체 가능 — `model-compose.yml`의 `nsfw-tracker.model.path`를 수정하세요. 더 빠른(대신 정확도는 낮은) 대안은 같은 리포의 320n 변형 (`nudenet-v34-320n.pt`, ~6 MB).

**클래스 선택.** YOLO 모델마다 클래스 라벨 리스트가 다릅니다. 예제의 `nsfw-tracker` 컴포넌트 아래 `labels:` 리스트는 `FEMALE_GENITALIA_EXPOSED`와 `MALE_GENITALIA_EXPOSED`로 검출을 제한합니다 — 대상 범위를 넓히거나 좁히려면 이 리스트를 수정하세요. 알 수 없는 클래스명은 모델 로드 시 사용 가능한 라벨 목록과 함께 명확한 에러로 표시됩니다.

### 설정

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/media-processing/nsfw-mosaic
   ```

2. 검출기 가중치를 `./models/nsfw_detector.pt`에 배치 (위 참고).

3. 처리할 비디오 파일 준비.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 비디오 업로드, 필요시 `mode` / `block_scale` / `blur_radius` / `frame_rate` / `min_confidence` 조정
   - "Run Workflow" 클릭

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'input={"mode": "pixelate", "block_scale": 0.1, "frame_rate": 30};type=application/json' \
     -F 'video=@./video.mp4'
   ```

   **CLI 사용:**
   ```bash
   model-compose run --input '{
     "video": "./video.mp4",
     "mode": "pixelate",
     "block_scale": 0.1,
     "frame_rate": 30
   }'
   ```

## 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `video` | video (파일) | 예 | - | 처리할 입력 비디오 |
| `mode` | string | 아니오 | `pixelate` | 모자이크 알고리즘: `pixelate` 또는 `blur` |
| `block_scale` | number | 아니오 | `0.1` | 각 영역의 짧은 변 대비 픽셀레이트 블록 크기 비율 (0.0 – 1.0). 자동 스케일 — 작은 영역엔 비례해서 더 작은 블록. `mode: pixelate`에서 사용 |
| `blur_radius` | number | 아니오 | `8.0` | 블러 반경 (픽셀). `mode: blur`에서 사용 |
| `min_confidence` | number | 아니오 | `0.35` | 최소 검출 신뢰도 (0.0 – 1.0). 경계 사례까지 더 잡고 싶으면 낮추기 (예: `0.2`) — 모자이크 용도라 false positive가 miss보다 안전 |
| `bounding_box_padding` | number | 아니오 | `0.1` | 검출된 박스를 모자이크 적용 전에 사방으로 확장하는 비율. 작은 패딩(예: `0.1` = 10 %)은 타이트 크롭 경계에서 원본이 1–2 픽셀 새는 것을 막음 |
| `merge_gap` | number | 아니오 | `0.5` | tracker가 갭 보간할 최대 초 (detection chunk의 스트리밍 지연 하한이기도 함). 검출기가 더 긴 구간을 반복적으로 놓치면 올리고(그만큼 버퍼링 지연 증가), 지연이 갭 보간보다 중요하면 낮추세요 |
| `frame_rate` | number | 아니오 | `30` | 출력 프레임 레이트. 오디오 드리프트를 피하려면 원본의 실제 fps를 넘기세요 |

## 컴포넌트 상세

### Audio Extractor (`audio-extractor`)
- **Type**: `audio-extractor`
- **Driver**: `ffmpeg`
- **기능**: 비디오 스트림에서 오디오 트랙만 mp3로 뽑음. 상류 `fan-out` 작업의 한 브랜치에서 흘러들어와 frame extractor와 병렬로 업로드 스트림을 소비. 나중에 encoder가 모자이크된 비디오에 다시 mux할 때 사용.

### Frame Extractor (`frame-extractor`)
- **Type**: `video-frame-extractor`
- **Driver**: `ffmpeg`
- **기능**: ffmpeg가 디코딩하는 대로 모든 프레임(`frame_interval: 1`)을 스트리밍. `streaming: true`라 extractor는 전체 비디오를 버퍼링하지 않고, 각 프레임을 바로 아래 tracker로 흘려보냄.

### NSFW Tracker (`nsfw-tracker`)
- **Type**: `model` — `object-tracking` task
- **Driver**: `custom` (Ultralytics YOLO family)
- **기능**: 프레임 스트림을 받아 `{type: "detection", number, timestamp, objects: [{track_id, label, bounding_box}], image}` 형태의 프레임별 detection chunk 스트림을 emit. tracker의 다른 chunk 타입은 모두 억제 — `return_tracks: false`가 세그먼트/트랙 chunk를 드롭하고 `return_metadata: false`가 종료 `metadata` chunk를 드롭. `return_frame_image: true`가 각 detection chunk에 원본 이미지를 실어와서 모자이크 스텝이 별도 프레임 스트림과 zip할 필요가 없음. `max_concurrent_count: 1`로 GPU 측 작업을 직렬화 — 바깥 `for-each`는 CPU 측 모자이크 작업을 여전히 프레임 간 병렬로 돌림.

### Mosaic (`mosaic`)
- **Type**: `image-processor` (`mosaic` 메서드)
- **Driver**: `native`
- **기능**: bounding box 하나에 모자이크 적용. 인라인 `accumulate` 스텝이 검출된 영역마다 한 번씩 호출.

### Encoder (`encoder`)
- **Type**: `video-encoder`
- **Driver**: `ffmpeg`
- **기능**: 모자이크된 프레임 스트림을 mp4(`libx264 @ 8M`)로 인코딩하고 추출된 오디오(`aac @ 192k`)를 mux. 스트림 입력을 받으므로 ffmpeg가 준비된 대로 프레임을 당겨감.

## 참고 및 튜닝

- **비용**: 모든 프레임에서 NSFW 검출이 실행됩니다. 30fps 10초 클립 = 300회 검출 호출. YOLO는 빠르지만(CPU에서 프레임당 수십 ms, CUDA/CoreML에서 더 빠름) 총 wall time은 프레임 수에 선형 비례.
- **동시성**: 바깥 `for-each`의 `batch_size: 16`은 최대 16개의 프레임 모자이크 파이프라인을 동시에 실행. 메모리를 더 쓰고 처리량을 올리려면 올리고, 모자이크가 병목이 되면 낮추세요.
- **프레임 레이트**: 원본과 출력 프레임 레이트가 다르면 오디오/비디오 드리프트 발생. `frame_rate`에 원본의 실제 fps를 넘기세요.
- **누락된 영역**: 여전히 누락이 있다면 `min_confidence`를 낮추세요 (예: `0.2`) — 어차피 false positive도 모자이크될 뿐이라 모자이크 용도에는 안전한 트레이드오프. 작은 스케일에서 지속적으로 누락된다면 검출기를 더 큰 YOLO 변형으로 바꾸거나 재학습.
- **갭 보간 윈도우**: `merge_gap`이 보간 윈도우(tracker가 몇 초 동안의 검출 누락을 이어줄지)와 detection chunk의 최소 스트리밍 지연을 동시에 결정 (chunk는 보간이 완료될 수 있도록 그만큼 보류됨). 기본 `0.5`초는 30fps에서 몇 프레임 정도의 누락을 이어줌 — 검출기가 더 긴 구간을 반복적으로 놓치면 올리세요 (예: `1.0`). 다만 모든 하류 프레임이 같은 만큼 지연됨을 유의.
- **클래스 선택**: `nsfw-tracker` 컴포넌트의 `labels:` 리스트를 수정해 모자이크할 클래스를 넓히거나 좁히세요 (기본값은 `FEMALE_GENITALIA_EXPOSED`와 `MALE_GENITALIA_EXPOSED`). 클래스 이름은 사용하는 가중치에 종속 — 모델의 라벨 리스트를 확인하세요. 알 수 없는 이름은 로드 시 명확한 에러로 표시됩니다.
- **모자이크 강도**: `pixelate`에서 `block_scale`이 클수록 더 강하게 가림 (일반적으로 `0.05`–`0.2`). 블록 크기는 영역의 짧은 변 기준이라 같은 `block_scale`이 작은 영역과 큰 영역에서 시각적으로 일관된 강도를 냄. `blur`에서는 `blur_radius`를 올리세요 (일반적으로 8–20). 블러는 낮은 반경에서 희미한 윤곽이 남을 수 있으므로 완전히 알아볼 수 없어야 하는 경우엔 `pixelate`가 안전.
- **겹치는 영역**: 박스가 겹치면 뒤 iteration이 이미 모자이크된 픽셀 위에 다시 모자이크를 겹치므로 겹친 영역도 결국 가려짐.
- **박스 패딩**: 검출 박스가 타이트하게 잡혀서 가장자리 픽셀이 새는 경우가 있음. `bounding_box_padding` 파라미터(기본 `0.1` = 10 %)가 검출된 박스를 사방으로 확장한 뒤 모자이크에 넘김 — 여전히 가장자리에서 새 보이면 올리고, 무관한 콘텐츠까지 침범하면 낮추세요.
- **검출이 0개인 프레임**: 검출이 없는 프레임은 인라인 `accumulate` 스텝의 입력 리스트가 비어있어서 accumulator가 그대로 통과 — 원본 프레임이 encoder까지 도달. 워크플로우 수준에서 특별 처리 불필요.
