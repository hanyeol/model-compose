# Image Handling Guide

This guide covers working with images in model-compose, including upload, processing, format support, and best practices for image-based AI workflows.

## Overview

model-compose supports various image processing tasks:
- **Image-to-Text**: Generate descriptions and captions
- **Image Classification**: Classify and categorize images
- **Image Upscaling**: Enhance image resolution
- **Object Detection**: Identify objects within images
- **Image Analysis**: Extract features and metadata

## Image Upload Methods

### API Upload (multipart/form-data)

For web APIs, images are uploaded using multipart form data:

```bash
# Basic image upload
curl -X POST http://localhost:8080/api/workflows/runs \
  -F "image=@/path/to/image.jpg" \
  -F "input={\"image\": \"@image\"}"

# Multiple images
curl -X POST http://localhost:8080/api/workflows/runs \
  -F "image1=@/path/to/first.jpg" \
  -F "image2=@/path/to/second.png" \
  -F "input={\"images\": [\"@image1\", \"@image2\"]}"
```

### CLI (File Path)

For command-line usage, specify file paths directly:

```bash
# Single image
model-compose run image-workflow --input '{"image": "/path/to/image.jpg"}'

# Multiple images
model-compose run image-workflow --input '{
  "images": [
    "/path/to/first.jpg",
    "/path/to/second.png"
  ]
}'
```

### Base64 Encoding

Images can also be provided as base64-encoded strings:

```json
{
  "image_data": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQ..."
}
```

## Supported Image Formats

### Common Formats
- **JPEG/JPG**: Most widely used, good compression
- **PNG**: Lossless compression, supports transparency
- **BMP**: Uncompressed bitmap format
- **TIFF**: High-quality format for professional use
- **GIF**: Supports animation (static frames processed)
- **WebP**: Modern format with excellent compression

### Format Recommendations

| Use Case | Recommended Format | Why |
|----------|-------------------|-----|
| **Photos** | JPEG | Good compression, small file size |
| **Screenshots** | PNG | Crisp text and graphics |
| **Logos/Icons** | PNG/SVG | Transparency support, scalability |
| **Print Quality** | TIFF | Highest quality, no compression loss |
| **Web Optimization** | WebP | Best compression for web |

## Image Configuration

### Basic Image Input

```yaml
components:
  - id: image-processor
    type: model
    model: Salesforce/blip-image-captioning-large
    task: image-to-text
    input:
      image: ${input.image as image}
```

### Advanced Configuration

```yaml
components:
  - id: advanced-image-processor
    type: model
    model: Salesforce/blip-image-captioning-large
    task: image-to-text
    input:
      image: ${input.image as image}

    # Model parameters
    params:
      max_length: 50
      num_beams: 3
      temperature: 1.0
```

## Image Preprocessing

### Automatic Preprocessing

model-compose automatically handles:
- **Format Conversion**: Converts all formats to RGB
- **Resizing**: Scales images to model requirements
- **Normalization**: Adjusts pixel values to expected range
- **Memory Optimization**: Efficient loading and processing

### Manual Preprocessing Options

```yaml
# Custom preprocessing pipeline
components:
  - id: preprocessor
    type: shell
    command: [ python, preprocess_image.py ]
    input:
      image_path: ${input.image}
      
  - id: model
    type: model
    model: microsoft/DialoGPT-medium
    task: image-to-text
    input:
      image: ${jobs.preprocessor.output.processed_image}
    depends_on: [ preprocessor ]
```

## Image Size and Memory Management

### Size Limits

| Component | Recommended Max Size | Memory Usage |
|-----------|---------------------|--------------|
| **Image-to-Text** | 2048x2048 px | ~500MB |
| **Classification** | 1024x1024 px | ~200MB |
| **Upscaling** | 512x512 px input | ~1GB+ |
| **Object Detection** | 1280x1280 px | ~800MB |

### Memory Optimization

```yaml
components:
  - id: memory-efficient-processor
    type: model
    model: Salesforce/blip-image-captioning-base  # Use smaller model
    task: image-to-text
    
    # Memory optimization settings
    device_map: auto
    torch_dtype: float16          # Half precision
    low_cpu_mem_usage: true       # Reduce CPU memory
```

## Batch Processing

### Multiple Images in Single Request

```yaml
workflows:
  - id: batch-image-processing
    jobs:
      - id: process-images
        component: image-processor
        input:
          images: ${input.image_list}
        params:
          batch_size: 4             # Process 4 images at once
```

### API Batch Upload

```bash
# Batch processing via API
curl -X POST http://localhost:8080/api/workflows/runs \
  -F "image1=@photo1.jpg" \
  -F "image2=@photo2.jpg" \
  -F "image3=@photo3.jpg" \
  -F "input={\"images\": [\"@image1\", \"@image2\", \"@image3\"]}"
```

## Image Quality Guidelines

### Optimal Image Characteristics

1. **Resolution**: 
   - Minimum: 224x224 pixels
   - Optimal: 512x512 to 1024x1024 pixels
   - Maximum: 2048x2048 pixels (depending on task)

2. **Quality**:
   - Good lighting and contrast
   - Sharp focus on main subjects
   - Minimal noise and artifacts
   - Proper exposure (not too dark/bright)

3. **Composition**:
   - Clear subject matter
   - Minimal clutter in background
   - Standard orientation (not rotated)
   - Centered or well-composed subjects

### Quality Issues and Solutions

| Issue | Impact | Solution |
|-------|--------|----------|
| **Blurry Images** | Poor accuracy | Use sharper images or image enhancement |
| **Low Resolution** | Missing details | Upscale images or use higher resolution |
| **Poor Lighting** | Reduced performance | Improve lighting or use image enhancement |
| **Heavy Compression** | Artifacts affect results | Use higher quality images |

## Best Practices

### Image Preparation

1. **Optimize Before Processing**:
   - Resize to appropriate dimensions
   - Compress without losing essential details
   - Enhance contrast and brightness if needed

2. **Batch Processing**:
   - Group similar images together
   - Process multiple images concurrently
   - Use appropriate batch sizes for memory

3. **Caching Strategy**:
   - Cache processed results
   - Store common images locally
   - Use CDN for frequently accessed images

### Workflow Design

1. **Error Handling**:
   - Validate images before processing
   - Implement fallback strategies
   - Log errors for debugging

2. **Resource Management**:
   - Monitor memory usage
   - Set appropriate timeouts
   - Clean up temporary files

3. **Quality Control**:
   - Review AI-generated results
   - Implement confidence scoring
   - Use human validation for critical tasks

## Example Workflows

### Complete Image Analysis Pipeline

```yaml
controller:
  type: http-server
  port: 8080
  webui:
    port: 8081

components:
  - id: image-validator
    type: shell
    command: [ python, validate_image.py ]
    
  - id: image-enhancer
    type: shell
    command: [ python, enhance_image.py ]
    
  - id: caption-generator
    type: model
    model: Salesforce/blip-image-captioning-large
    task: image-to-text
    
  - id: classifier
    type: model
    model: microsoft/DialoGPT-medium
    task: image-classification

workflows:
  - id: complete-image-analysis
    jobs:
      - id: validate
        component: image-validator
        input:
          image: ${input.image}
          
      - id: enhance
        component: image-enhancer
        input:
          image: ${input.image}
        depends_on: [ validate ]
        condition: ${jobs.validate.output.valid}
        
      - id: generate-caption
        component: caption-generator
        input:
          image: ${jobs.enhance.output.enhanced_image}
        depends_on: [ enhance ]
        
      - id: classify
        component: classifier
        input:
          image: ${jobs.enhance.output.enhanced_image}
        depends_on: [ enhance ]
        
      - id: combine-results
        component: result-combiner
        input:
          caption: ${jobs.generate-caption.output.generated}
          classification: ${jobs.classify.output.label}
          confidence: ${jobs.classify.output.score}
        depends_on: [ generate-caption, classify ]
```

## Related Documentation

- [CLI Reference](../cli.md)
- [Model Component](../compose/components/model.md)
- [Image-to-Text Example](../../examples/model-tasks/image-to-text/README.md)
- [Image Upscaling Example](../../examples/model-tasks/image-upscale/README.md)
- [Computer Vision Guide](computer-vision.md)
- [Performance Optimization](performance/optimization.md)