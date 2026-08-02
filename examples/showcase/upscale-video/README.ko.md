# 비디오 업스케일 예제

이 예제는 초해상도 모델로 비디오의 모든 프레임을 업스케일하고 재조립하는 워크플로우를 보여줍니다 — 원본 오디오 트랙은 보존됩니다.

## 개요

입력 비디오가 주어지면, 워크플로우는 원본 오디오 트랙이 다시 먹싱된 초해상화된 동일 비디오를 반환합니다.

전략은 다음과 같습니다:

1. `audio-extractor`로 입력 비디오에서 **오디오 트랙을 분리**합니다 (변경 없이 보존).
2. `video-frame-extractor`로 **모든 프레임을 정지 이미지로 추출**합니다.
3. **각 프레임에 대해** `for-each` job을 통해 `image-upscale`(Real-ESRGAN x4)을 실행합니다.
4. `video-encoder`로 **업스케일된 프레임을 다시 인코딩**하며, 추출한 오디오를 출력에 먹싱합니다.

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- FFmpeg이 설치되어 PATH에서 사용 가능
- Real-ESRGAN 추론을 위한 Python 의존성:
  ```bash
  pip install torch torchvision realesrgan
  ```
- Real-ESRGAN 가중치(`RealESRGAN_x4.pth`)는 최초 실행 시 Hugging Face의 `ai-forever/Real-ESRGAN`에서 자동으로 다운로드됩니다.

### 설정

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/showcase/upscale-video
   ```

2. 업스케일할 비디오 파일을 준비합니다. 짧은 클립을 권장합니다 — 프레임별 초해상도는 비용이 큽니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **웹 UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 비디오 업로드하고 선택적으로 `frame_rate` 재정의
   - "Run Workflow" 클릭

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: multipart/form-data" \
     -F 'input={"frame_rate": 30};type=application/json' \
     -F 'video=@./video.mp4'
   ```

   **CLI 사용:**
   ```bash
   model-compose run --input '{
     "video": "./video.mp4",
     "frame_rate": 30
   }'
   ```

## 컴포넌트 세부사항

### Audio Extractor (`audio-extractor`)
- **유형**: `audio-extractor`
- **드라이버**: `ffmpeg`
- **기능**: 입력 비디오에서 오디오 트랙을 독립 mp3 파일로 분리. 이후 인코더가 업스케일된 비디오에 오디오를 다시 먹싱할 때 사용됨.

### Frame Extractor (`frame-extractor`)
- **유형**: `video-frame-extractor`
- **드라이버**: `ffmpeg`
- **기능**: 비디오를 모든 프레임의 리스트로 디코딩합니다 (`frame_interval: 1`, 타임스탬프 포함). `streaming: false`이므로 `for-each` job이 실체화된 리스트를 순회할 수 있습니다.

### Upscaler (`upscaler`)
- **유형**: `model` — `image-upscale` 태스크
- **드라이버**: `custom` (Real-ESRGAN family)
- **모델**: Hugging Face의 `ai-forever/Real-ESRGAN`에서 가져온 `RealESRGAN_x4.pth`
- **스케일**: 4x
- **타일링**: `tile_size: 256`, `tile_pad_size: 24`, `tile_batch_size: 4` — 고해상도 프레임에서 VRAM 사용을 제한.

### Encoder (`encoder`)
- **유형**: `video-encoder`
- **드라이버**: `ffmpeg`
- **기능**: 업스케일된 프레임을 mp4(`libx264 @ 8M`)로 다시 인코딩하고 추출한 오디오(`aac @ 192k`)를 먹싱합니다. `frame_rate`가 출력 타이밍을 제어합니다.

## 노트 및 튜닝

- **비용**: 모든 프레임에 Real-ESRGAN x4는 무겁습니다. 10초 30fps 클립 = 300회의 모델 호출. 짧은 클립부터 시작하세요.
- **프레임 레이트**: 소스와 출력 프레임 레이트가 다르면 오디오와 비디오가 어긋납니다. 소스의 실제 fps를 `frame_rate`로 전달하세요 (기본 `30`은 폴백입니다).
- **다른 업스케일러 선택**: `family: real-esrgan`과 모델 파일을 다른 지원 family (`esrgan`, `swinir`, `ldsr`)로 교체하세요. 각 family는 자체 타일링 매개변수를 노출합니다 — `image-upscale` 문서를 참조하세요.
- **배칭**: `for-each` job은 기본적으로 프레임을 순차 실행합니다. `for-each` job에 `batch_size`를 설정하여 프레임을 동시 처리할 수 있습니다 (GPU 메모리에 의해 제한).
