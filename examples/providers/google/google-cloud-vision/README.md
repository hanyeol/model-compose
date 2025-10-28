# Google Cloud Vision API Example

This example demonstrates how to use Google Cloud Vision API for various image analysis tasks including label detection, text recognition (OCR), face detection, object localization, landmark detection, and logo detection.

## Prerequisites

1. **Google Cloud Account**: You need a Google Cloud account with Vision API enabled.

2. **API Key**: Create an API key from the Google Cloud Console:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Enable the Vision API
   - Create credentials (API Key)
   - Set the API key as an environment variable:
     ```bash
     export GOOGLE_CLOUD_API_KEY="your-api-key-here"
     ```

## Features

This example provides the following Vision API capabilities:

### 1. Label Detection
Detects and extracts labels (tags) from images.

**Input:**
- `image`: Image file (multipart/form-data)
- `max_results` (optional): Maximum number of results (default: 10)

**Output:**
- `labels`: Full label annotation objects with scores
- `descriptions`: List of label descriptions

### 2. Text Detection (OCR)
Extracts text from images using Optical Character Recognition.

**Input:**
- `image`: Image file (multipart/form-data)

**Output:**
- `full_text`: Complete extracted text
- `text_annotations`: Detailed text annotations with bounding boxes

### 3. Face Detection
Detects faces and facial features in images.

**Input:**
- `image`: Image file (multipart/form-data)
- `max_results` (optional): Maximum number of faces to detect (default: 10)

**Output:**
- `faces`: Face annotations with landmarks and attributes
- `face_count`: Number of detected faces

### 4. Object Localization
Detects and localizes multiple objects in images.

**Input:**
- `image`: Image file (multipart/form-data)
- `max_results` (optional): Maximum number of objects (default: 10)

**Output:**
- `objects`: Object annotations with bounding boxes
- `object_names`: List of detected object names

### 5. Landmark Detection
Detects popular landmarks in images.

**Input:**
- `image`: Image file (multipart/form-data)
- `max_results` (optional): Maximum number of landmarks (default: 10)

**Output:**
- `landmarks`: Landmark annotations with locations
- `landmark_names`: List of landmark names

### 6. Logo Detection
Detects company logos in images.

**Input:**
- `image`: Image file (multipart/form-data)
- `max_results` (optional): Maximum number of logos (default: 10)

**Output:**
- `logos`: Logo annotations with bounding boxes
- `logo_names`: List of detected logo names

## Usage

### Start the Server

```bash
model-compose up
```

This will start:
- HTTP API server on port 8080
- Gradio Web UI on port 8081

### Using the Web UI

1. Open http://localhost:8081 in your browser
2. Select a workflow from the dropdown (e.g., "Detect Labels in Image")
3. Upload an image file
4. Click submit to see the results

### Using the HTTP API

#### Label Detection Example

```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -F "workflow_id=label-detection" \
  -F "input[image]=@your-image.jpg" \
  -F "input[max_results]=5"
```

#### Text Detection (OCR) Example

```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -F "workflow_id=text-detection" \
  -F "input[image]=@your-image-with-text.jpg"
```

#### Face Detection Example

```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -F "workflow_id=face-detection" \
  -F "input[image]=@your-image-with-faces.jpg" \
  -F "input[max_results]=10"
```

## API Response Examples

### Label Detection Response
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

### Text Detection Response
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

### Face Detection Response
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

## Notes

- The API key should be kept secure and not committed to version control
- Google Cloud Vision API is a paid service - check pricing at https://cloud.google.com/vision/pricing
- Image size limits apply - refer to Google Cloud Vision API documentation
- For production use, consider using service account authentication instead of API keys

## Additional Resources

- [Google Cloud Vision API Documentation](https://cloud.google.com/vision/docs)
- [Vision API Pricing](https://cloud.google.com/vision/pricing)
- [Best Practices](https://cloud.google.com/vision/docs/best-practices)
