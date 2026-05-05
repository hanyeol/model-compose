# Google Cloud Vision API 示例

此示例演示如何使用 Google Cloud Vision API 进行各种图像分析任务，包括标签检测、文本识别（OCR）、人脸检测、对象定位、地标检测和徽标检测。

## 前置条件

1. **Google Cloud 账户**：您需要一个启用了 Vision API 的 Google Cloud 账户。

2. **API 密钥**：从 Google Cloud 控制台创建 API 密钥：
   - 访问 [Google Cloud Console](https://console.cloud.google.com/)
   - 启用 Vision API
   - 创建凭据（API 密钥）
   - 将 API 密钥设置为环境变量：
     ```bash
     export GOOGLE_CLOUD_API_KEY="your-api-key-here"
     ```

## 功能

此示例提供以下 Vision API 功能：

### 1. 标签检测
从图像中检测并提取标签（标记）。

**输入：**
- `image`：图像文件（multipart/form-data）
- `max_results`（可选）：最大结果数（默认：10）

**输出：**
- `labels`：带有分数的完整标签注释对象
- `descriptions`：标签描述列表

### 2. 文本检测（OCR）
使用光学字符识别从图像中提取文本。

**输入：**
- `image`：图像文件（multipart/form-data）

**输出：**
- `full_text`：提取的完整文本
- `text_annotations`：带有边界框的详细文本注释

### 3. 人脸检测
检测图像中的人脸和面部特征。

**输入：**
- `image`：图像文件（multipart/form-data）
- `max_results`（可选）：要检测的最大人脸数（默认：10）

**输出：**
- `faces`：带有地标和属性的人脸注释
- `face_count`：检测到的人脸数量

### 4. 对象定位
检测并定位图像中的多个对象。

**输入：**
- `image`：图像文件（multipart/form-data）
- `max_results`（可选）：最大对象数（默认：10）

**输出：**
- `objects`：带有边界框的对象注释
- `object_names`：检测到的对象名称列表

### 5. 地标检测
检测图像中的著名地标。

**输入：**
- `image`：图像文件（multipart/form-data）
- `max_results`（可选）：最大地标数（默认：10）

**输出：**
- `landmarks`：带有位置的地标注释
- `landmark_names`：地标名称列表

### 6. 徽标检测
检测图像中的公司徽标。

**输入：**
- `image`：图像文件（multipart/form-data）
- `max_results`（可选）：最大徽标数（默认：10）

**输出：**
- `logos`：带有边界框的徽标注释
- `logo_names`：检测到的徽标名称列表

## 用法

### 启动服务器

```bash
model-compose up
```

这将启动：
- HTTP API 服务器在端口 8080
- Gradio Web UI 在端口 8081

### 使用 Web UI

1. 在浏览器中打开 http://localhost:8081
2. 从下拉菜单中选择工作流（例如，"Detect Labels in Image"）
3. 上传图像文件
4. 点击提交查看结果

### 使用 HTTP API

#### 标签检测示例

```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -F "workflow_id=label-detection" \
  -F "input[image]=@your-image.jpg" \
  -F "input[max_results]=5"
```

#### 文本检测（OCR）示例

```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -F "workflow_id=text-detection" \
  -F "input[image]=@your-image-with-text.jpg"
```

#### 人脸检测示例

```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -F "workflow_id=face-detection" \
  -F "input[image]=@your-image-with-faces.jpg" \
  -F "input[max_results]=10"
```

## API 响应示例

### 标签检测响应
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

### 文本检测响应
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

### 人脸检测响应
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

## 注意事项

- API 密钥应保持安全，不要提交到版本控制系统
- Google Cloud Vision API 是付费服务 - 查看定价信息：https://cloud.google.com/vision/pricing
- 图像大小有限制 - 请参阅 Google Cloud Vision API 文档
- 对于生产使用，请考虑使用服务账户身份验证而不是 API 密钥

## 其他资源

- [Google Cloud Vision API 文档](https://cloud.google.com/vision/docs)
- [Vision API 定价](https://cloud.google.com/vision/pricing)
- [最佳实践](https://cloud.google.com/vision/docs/best-practices)
