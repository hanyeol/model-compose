# Google Cloud Vision API 예제

이 예제는 라벨 감지, 텍스트 인식(OCR), 얼굴 감지, 객체 위치 인식, 랜드마크 감지, 로고 감지 등 다양한 이미지 분석 작업에 Google Cloud Vision API를 사용하는 방법을 보여줍니다.

## 필수 요구사항

1. **Google Cloud 계정**: Vision API가 활성화된 Google Cloud 계정이 필요합니다.

2. **API 키**: Google Cloud Console에서 API 키를 생성합니다:
   - [Google Cloud Console](https://console.cloud.google.com/) 접속
   - Vision API 활성화
   - 자격 증명 생성 (API 키)
   - API 키를 환경 변수로 설정:
     ```bash
     export GOOGLE_CLOUD_API_KEY="your-api-key-here"
     ```

## 기능

이 예제는 다음과 같은 Vision API 기능을 제공합니다:

### 1. 라벨 감지
이미지에서 라벨(태그)을 감지하고 추출합니다.

**입력:**
- `image`: 이미지 파일 (multipart/form-data)
- `max_results` (선택): 최대 결과 수 (기본값: 10)

**출력:**
- `labels`: 점수가 포함된 전체 라벨 주석 객체
- `descriptions`: 라벨 설명 목록

### 2. 텍스트 감지 (OCR)
광학 문자 인식을 사용하여 이미지에서 텍스트를 추출합니다.

**입력:**
- `image`: 이미지 파일 (multipart/form-data)

**출력:**
- `full_text`: 추출된 전체 텍스트
- `text_annotations`: 경계 상자가 포함된 상세 텍스트 주석

### 3. 얼굴 감지
이미지에서 얼굴과 얼굴 특징을 감지합니다.

**입력:**
- `image`: 이미지 파일 (multipart/form-data)
- `max_results` (선택): 감지할 최대 얼굴 수 (기본값: 10)

**출력:**
- `faces`: 랜드마크 및 속성이 포함된 얼굴 주석
- `face_count`: 감지된 얼굴 수

### 4. 객체 위치 인식
이미지에서 여러 객체를 감지하고 위치를 파악합니다.

**입력:**
- `image`: 이미지 파일 (multipart/form-data)
- `max_results` (선택): 최대 객체 수 (기본값: 10)

**출력:**
- `objects`: 경계 상자가 포함된 객체 주석
- `object_names`: 감지된 객체 이름 목록

### 5. 랜드마크 감지
이미지에서 유명한 랜드마크를 감지합니다.

**입력:**
- `image`: 이미지 파일 (multipart/form-data)
- `max_results` (선택): 최대 랜드마크 수 (기본값: 10)

**출력:**
- `landmarks`: 위치가 포함된 랜드마크 주석
- `landmark_names`: 랜드마크 이름 목록

### 6. 로고 감지
이미지에서 회사 로고를 감지합니다.

**입력:**
- `image`: 이미지 파일 (multipart/form-data)
- `max_results` (선택): 최대 로고 수 (기본값: 10)

**출력:**
- `logos`: 경계 상자가 포함된 로고 주석
- `logo_names`: 감지된 로고 이름 목록

## 사용법

### 서버 시작

```bash
model-compose up
```

다음이 시작됩니다:
- HTTP API 서버 (포트 8080)
- Gradio Web UI (포트 8081)

### Web UI 사용

1. 브라우저에서 http://localhost:8081 열기
2. 드롭다운에서 워크플로우 선택 (예: "Detect Labels in Image")
3. 이미지 파일 업로드
4. 제출 버튼을 클릭하여 결과 확인

### HTTP API 사용

#### 라벨 감지 예제

```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -F "workflow_id=label-detection" \
  -F "input[image]=@your-image.jpg" \
  -F "input[max_results]=5"
```

#### 텍스트 감지 (OCR) 예제

```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -F "workflow_id=text-detection" \
  -F "input[image]=@your-image-with-text.jpg"
```

#### 얼굴 감지 예제

```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -F "workflow_id=face-detection" \
  -F "input[image]=@your-image-with-faces.jpg" \
  -F "input[max_results]=10"
```

## API 응답 예제

### 라벨 감지 응답
```json
{
  "labels": [
    {
      "mid": "/m/0k4j",
      "description": "car",
      "score": 0.98,
      "topicality": 0.98
    },
    {
      "mid": "/m/07yv9",
      "description": "vehicle",
      "score": 0.95,
      "topicality": 0.95
    }
  ],
  "descriptions": ["car", "vehicle", "automotive", "wheel", "tire"]
}
```

### 텍스트 감지 응답
```json
{
  "full_text": "Hello World\nWelcome to Vision API",
  "text_annotations": [
    {
      "locale": "en",
      "description": "Hello World\nWelcome to Vision API",
      "boundingPoly": {
        "vertices": [...]
      }
    }
  ]
}
```

### 얼굴 감지 응답
```json
{
  "faces": [
    {
      "boundingPoly": {...},
      "fdBoundingPoly": {...},
      "landmarks": [...],
      "rollAngle": 0.5,
      "panAngle": -2.3,
      "tiltAngle": 1.2,
      "detectionConfidence": 0.99,
      "landmarkingConfidence": 0.87,
      "joyLikelihood": "VERY_LIKELY",
      "sorrowLikelihood": "VERY_UNLIKELY",
      "angerLikelihood": "VERY_UNLIKELY",
      "surpriseLikelihood": "UNLIKELY"
    }
  ],
  "face_count": 1
}
```

## 참고사항

- API 키는 안전하게 관리하고 버전 관리 시스템에 커밋하지 마세요
- Google Cloud Vision API는 유료 서비스입니다 - 가격 정보 확인: https://cloud.google.com/vision/pricing
- 이미지 크기에는 제한이 있습니다 - Google Cloud Vision API 문서 참고
- 프로덕션 환경에서는 API 키 대신 서비스 계정 인증 사용을 권장합니다

## 추가 자료

- [Google Cloud Vision API 문서](https://cloud.google.com/vision/docs)
- [Vision API 가격](https://cloud.google.com/vision/pricing)
- [모범 사례](https://cloud.google.com/vision/docs/best-practices)
