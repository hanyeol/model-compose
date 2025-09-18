# OpenAI Image Generation Example

This example demonstrates how to generate images from text prompts using OpenAI's image generation models, including both DALL-E and GPT image models.

## Overview

This multi-workflow example provides two different approaches to AI image generation:

1. **DALL-E Workflow**: Generate images using OpenAI's specialized DALL-E models with URL-based output
2. **GPT Image Workflow**: Generate images using OpenAI's GPT image models with base64-encoded output

Both workflows use the same underlying OpenAI Images API but with different models and output formats, allowing you to choose the best approach for your specific use case.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- OpenAI API key with access to image generation models

### API Access Requirements

**Required OpenAI API Access:**
- Image Generation API access
- DALL-E 2 and/or DALL-E 3 model access
- GPT image model access (gpt-image-1)

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/openai-image-generations
   ```

2. Set your OpenAI API key as an environment variable:
   ```bash
   export OPENAI_API_KEY=your-actual-openai-api-key
   ```

   Or create a `.env` file:
   ```env
   OPENAI_API_KEY=your-actual-openai-api-key
   ```

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Generate image with DALL-E (URL format) - Default workflow
   curl -X POST http://localhost:8080/api/workflows/dall-e/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "A serene mountain landscape at sunset", "model": "dall-e-3"}}'
   
   # Generate image with GPT Image (Base64 format)
   curl -X POST http://localhost:8080/api/workflows/gpt-image-1/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "A futuristic city skyline"}}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Select the workflow from the tab
   - Enter your prompt and settings
   - Click the "Run Workflow" button

   **Using CLI:**
   ```bash
   # Generate image with DALL-E (URL format)
   model-compose run dall-e --input '{"prompt": "A serene mountain landscape at sunset", "model": "dall-e-3"}'
   
   # Generate image with GPT Image (Base64 format)
   model-compose run gpt-image-1 --input '{"prompt": "A futuristic city skyline"}'
   ```

## Component Details

### OpenAI HTTP Client Component
- **Type**: HTTP client component
- **Purpose**: Interface with OpenAI's Images API
- **Base URL**: https://api.openai.com/v1
- **Authentication**: Bearer token using OpenAI API key
- **Actions**: Supports both DALL-E and GPT image generation endpoints

#### Actions Available:

**1. DALL-E Action (dall-e)**
- **Endpoint**: `/images/generations`
- **Models**: DALL-E 2, DALL-E 3
- **Output Format**: URL to generated image
- **Image Size**: 1024x1024 (fixed)

**2. GPT Image Action (gpt-image-1)**
- **Endpoint**: `/images/generations`
- **Model**: gpt-image-1
- **Output Format**: Base64-encoded image data
- **Image Size**: 1024x1024 (fixed)

## Workflow Details

### 1. "Generate Images with OpenAI DALL·E" Workflow (Default)

**Description**: Generate high-quality images from text prompts using OpenAI's DALL-E models with URL-based output for easy sharing and embedding.

#### Job Flow

This workflow uses a simplified single-component configuration.

```mermaid
graph TD
    %% Default job (implicit)
    J1((dall-e<br/>workflow))

    %% Component
    C1[OpenAI GPT-4o Model<br/>component]

    %% Job to component connections
    J1 --> C1
    C1 -.-> |image URL| J1

    %% Input/Output
    Input((Input)) --> J1
    J1 --> Output((Image URL))
```

#### Input Parameters

| Parameter | Type | Required | Options | Default | Description |
|-----------|------|----------|---------|---------|-------------|
| `prompt` | string | Yes | - | - | Text description of the image to generate |
| `model` | string | No | `dall-e-2`, `dall-e-3` | `dall-e-2` | DALL-E model version to use |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `image_url` | string (URL) | Direct URL to the generated image hosted by OpenAI |

### 2. "Generate Images with OpenAI GPT" Workflow

**Description**: Generate images using OpenAI's GPT image model with base64-encoded output for direct embedding in applications.

#### Job Flow

```mermaid
graph TD
    %% Default job (implicit)
    J1((gpt-image-1<br/>workflow))

    %% Component
    C1[OpenAI HTTP Client<br/>GPT Image Action]

    %% Job to component connections
    J1 --> C1
    C1 -.-> |base64 image| J1

    %% Input/Output
    Input((Input)) --> J1
    J1 --> Output((Output))
```

#### Input Parameters

| Parameter | Type | Required | Options | Default | Description |
|-----------|------|----------|---------|---------|-------------|
| `prompt` | string | Yes | - | - | Text description of the image to generate |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `image_data` | string (base64) | Base64-encoded PNG image data |

## Model Comparison

### DALL-E 2 vs DALL-E 3

| Feature | DALL-E 2 | DALL-E 3 |
|---------|----------|----------|
| Image Quality | High | Very High |
| Prompt Adherence | Good | Excellent |
| Fine Details | Good | Superior |
| Creative Interpretation | Standard | Enhanced |
| Cost per Image | Lower | Higher |
| Generation Speed | Faster | Slower |

### DALL-E vs GPT Image

| Feature | DALL-E | GPT Image |
|---------|--------|-----------|
| Output Format | URL | Base64 |
| Model Options | 2 versions | Single model |
| Typical Use Case | Web display | App embedding |
| Storage | OpenAI hosted | Self-managed |
| URL Expiration | Yes (temporary) | N/A |

## API Information

### Rate Limits and Pricing

**DALL-E 2:**
- Rate Limit: 50 images per minute
- Cost: $0.020 per image (1024×1024)

**DALL-E 3:**
- Rate Limit: 7 images per minute per user
- Cost: $0.080 per image (1024×1024)

**GPT Image:**
- Rate limits and pricing may vary based on OpenAI's current policies

### Image Specifications

- **Resolution**: 1024×1024 pixels (fixed)
- **Format**: PNG
- **Color Space**: RGB
- **Compression**: Optimized for web delivery

## Customization

### Using Different Models

Modify the model selection in the workflow:

```yaml
body:
  model: ${input.model as select/dall-e-2,dall-e-3 | dall-e-3}  # Default to DALL-E 3
```

### Adding Size Options

Extend the configuration to support different image sizes:

```yaml
body:
  model: ${input.model as select/dall-e-2,dall-e-3 | dall-e-2}
  prompt: ${input.prompt}
  size: ${input.size as select/1024x1024,1792x1024,1024x1792 | 1024x1024}
  n: ${input.count as integer | 1}
```

### Custom Output Processing

Add post-processing for generated images:

```yaml
workflows:
  - id: dall-e-with-metadata
    title: Generate Image with Metadata
    jobs:
      - id: generate-image
        component: dall-e
        input: ${input}
        output:
          image_url: ${output.image_url}

      - id: analyze-image
        component: gpt-4-vision
        input:
          image_url: ${jobs.generate-image.output.image_url}
          prompt: "Analyze this generated image and provide a detailed description"
```

### Multiple Image Generation

Generate multiple variations:

```yaml
body:
  model: ${input.model as select/dall-e-2,dall-e-3 | dall-e-2}
  prompt: ${input.prompt}
  n: ${input.count as integer | 3}
  size: 1024x1024
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify OpenAI API key is correctly set
   - Ensure API key has image generation permissions
   - Check for any account billing issues

2. **Rate Limit Exceeded**
   - Reduce request frequency
   - Implement retry logic with exponential backoff
   - Consider upgrading to higher rate limits

3. **Content Policy Violations**
   - Review OpenAI's usage policies
   - Modify prompts to comply with content guidelines
   - Use more general, less specific descriptions

4. **Image URL Expiration**
   - DALL-E URLs expire after a certain period
   - Download and store images locally if needed
   - Use base64 output for immediate embedding

### Error Handling

**Invalid Prompt:**
```json
{
  "error": {
    "message": "Your request was rejected as a result of our safety system.",
    "type": "content_policy_violation"
  }
}
```

**Rate Limit Error:**
```json
{
  "error": {
    "message": "Rate limit reached for images per minute.",
    "type": "rate_limit_exceeded"
  }
}
```

**Insufficient Credits:**
```json
{
  "error": {
    "message": "You exceeded your current quota",
    "type": "insufficient_quota"
  }
}
```

## Use Cases and Applications

### Creative Applications
- **Art Generation**: Create original artwork for projects
- **Concept Visualization**: Transform ideas into visual representations
- **Style Exploration**: Generate images in different artistic styles
- **Character Design**: Create characters for games and stories

### Business Applications
- **Marketing Materials**: Generate unique visuals for campaigns
- **Product Mockups**: Create product visualization concepts
- **Social Media Content**: Generate eye-catching social posts
- **Presentation Graphics**: Create custom illustrations for presentations

### Development Applications
- **Prototype Assets**: Generate placeholder images for development
- **Game Assets**: Create textures and concept art
- **App Icons**: Generate icon concepts and variations
- **UI Illustrations**: Create custom interface graphics

### Educational Applications
- **Visual Learning**: Create educational illustrations
- **Historical Visualization**: Visualize historical concepts and events
- **Science Communication**: Generate diagrams and concept illustrations
- **Language Learning**: Create visual vocabulary aids

## Advanced Workflows

### Multi-Style Generation

Create a workflow that generates the same prompt in different styles:

```yaml
workflow:
  title: Multi-Style Image Generation
  jobs:
    - id: realistic
      component: dall-e
      input:
        prompt: "${input.base_prompt}, photorealistic style"
        model: "dall-e-3"

    - id: artistic
      component: dall-e
      input:
        prompt: "${input.base_prompt}, artistic painting style"
        model: "dall-e-3"

    - id: cartoon
      component: dall-e
      input:
        prompt: "${input.base_prompt}, cartoon animation style"
        model: "dall-e-2"
```

### Image Generation with Analysis

Combine image generation with AI analysis:

```yaml
workflow:
  title: Generate and Analyze Image
  jobs:
    - id: generate
      component: dall-e
      input: ${input}

    - id: analyze
      component: gpt-4-vision
      input:
        image_url: ${jobs.generate.output.image_url}
        prompt: "Describe this image in detail, including artistic elements, composition, and visual impact"
      depends_on: [generate]
```

## Best Practices

### Prompt Engineering
- **Be Specific**: Include details about style, composition, lighting
- **Use Descriptive Language**: Rich adjectives improve results
- **Specify Art Styles**: Reference known artistic movements or styles
- **Include Technical Details**: Mention camera angles, lighting conditions

### Workflow Selection
- **Use DALL-E URLs** for web applications and sharing
- **Use GPT base64** for immediate app integration
- **Choose DALL-E 3** for highest quality and prompt adherence
- **Choose DALL-E 2** for faster, cost-effective generation

### Performance Optimization
- **Batch Requests**: Group multiple generations when possible
- **Cache Results**: Store generated images to avoid regeneration
- **Monitor Usage**: Track API consumption and costs
- **Implement Fallbacks**: Handle rate limits and errors gracefully