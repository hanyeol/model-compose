# Web Scraper Examples

This example demonstrates various web scraping capabilities using the `web-scraper` component with multiple workflows for different scraping scenarios.

## Overview

This example provides 7 different web scraping workflows that demonstrate:

1. **Basic Scraping**: Extract text content using CSS selectors
2. **Link Extraction**: Extract all hyperlinks from a webpage
3. **JavaScript Rendering**: Scrape dynamically loaded content with Playwright
4. **Form Submission**: Fill and submit forms, then extract results
5. **Multiple Elements**: Extract content from multiple matching elements
6. **XPath Extraction**: Use XPath expressions for precise element targeting
7. **HTML Extraction**: Extract raw HTML markup for further processing

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Web scraping dependencies:
  ```bash
  pip install playwright beautifulsoup4 lxml
  playwright install chromium
  ```

### Setup

Navigate to this example directory:
```bash
cd examples/web-scraper
```

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

   The service will start:
   - API endpoint: http://localhost:8080/api
   - Web UI: http://localhost:8081

2. **Run workflows:**

   **Using API:**
   ```bash
   # Basic scraping
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "workflow": "basic-scraping",
       "input": {
         "url": "https://example.com",
         "selector": "h1"
       }
     }'

   # Extract links
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "workflow": "extract-links",
       "input": {
         "url": "https://example.com"
       }
     }'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Select a workflow from the dropdown
   - Enter input parameters
   - Click "Run Workflow"

   **Using CLI:**
   ```bash
   # Basic scraping
   model-compose run basic-scraping --input '{
     "url": "https://example.com",
     "selector": "h1"
   }'

   # JavaScript rendering
   model-compose run javascript-rendering --input '{
     "url": "https://spa-example.com",
     "selector": ".content",
     "wait_for": ".loaded"
   }'
   ```

## Component Details

### Web Scraper Component

- **Type**: Web scraper component
- **Purpose**: Extract content from web pages
- **Features**:
  - CSS selector and XPath support
  - JavaScript rendering with Playwright
  - Form filling and submission
  - Multiple extraction modes (text, HTML, attribute)
  - Custom headers and timeout configuration

## Workflow Details

### 1. Basic Scraping Workflow

**ID**: `basic-scraping`
**Description**: Extract text content from a webpage using CSS selectors

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | text | Yes | - | The webpage URL to scrape |
| `selector` | text | No | `"body"` | CSS selector to locate elements |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `content` | text | Extracted text content |

---

### 2. Extract Links Workflow

**ID**: `extract-links`
**Description**: Extract all links from a webpage using attribute extraction

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | text | Yes | - | The webpage URL to scrape |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `links` | array | List of extracted href attributes |

---

### 3. JavaScript Rendering Workflow

**ID**: `javascript-rendering`
**Description**: Extract content from JavaScript-rendered webpages using Playwright

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | text | Yes | - | The webpage URL to scrape |
| `selector` | text | No | `".content"` | CSS selector to locate elements |
| `wait_for` | text | No | - | CSS selector to wait for before extraction |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `content` | text | Extracted text content from JavaScript-rendered page |

**Note**: This workflow uses Playwright for JavaScript execution, making it suitable for Single Page Applications (SPAs) and dynamically loaded content.

---

### 4. Form Submission Workflow

**ID**: `form-submission`
**Description**: Fill and submit a web form, then extract the resulting content

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | text | Yes | - | The webpage URL with the form |
| `username` | text | Yes | - | Username value to fill |
| `password` | text | Yes | - | Password value to fill |
| `form_selector` | text | No | `"form"` | CSS selector for the form |
| `result_selector` | text | No | `".result"` | CSS selector to wait for after submission |
| `content_selector` | text | No | `".result"` | CSS selector for content extraction |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `result` | text | Extracted content after form submission |

---

### 5. Multiple Elements Workflow

**ID**: `multiple-elements`
**Description**: Extract text from multiple elements matching a selector

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | text | Yes | - | The webpage URL to scrape |
| `selector` | text | No | `"article h2"` | CSS selector to locate elements |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `titles` | array | List of extracted text content from matching elements |

**Note**: This workflow automatically includes a custom User-Agent header.

---

### 6. XPath Extraction Workflow

**ID**: `xpath-extraction`
**Description**: Use XPath expressions to extract specific content from a webpage

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | text | Yes | - | The webpage URL to scrape |
| `xpath` | text | No | `"//div[@class='content']//p"` | XPath expression to locate elements |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `paragraphs` | array | List of extracted text content from matching elements |

---

### 7. HTML Extraction Workflow

**ID**: `html-extraction`
**Description**: Extract HTML markup of specific elements for further processing

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | text | Yes | - | The webpage URL to scrape |
| `selector` | text | No | `"article"` | CSS selector to locate elements |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `html` | text | Extracted HTML markup |

---

## Customization

### Modifying Extraction Mode

Change the `extract_mode` to extract different types of content:

```yaml
component:
  type: web-scraper
  action:
    extract_mode: text    # Options: text, html, attribute
    attribute: href       # Required when extract_mode is "attribute"
```

### Adding Custom Headers

Include custom HTTP headers for authentication or identification:

```yaml
component:
  type: web-scraper
  headers:
    Authorization: Bearer ${env.API_TOKEN}
    User-Agent: MyCustomBot/1.0
```

### Adjusting Timeout

Configure timeout for slow-loading pages:

```yaml
component:
  type: web-scraper
  timeout: 120s  # 2 minutes
```

### Form Submission Without Input

To just click a submit button without filling form fields:

```yaml
submit:
  selector: button[type="submit"]
  # No form field specified - just clicks the button
```

## Best Practices

- **Respect robots.txt**: Always check and respect website crawling policies
- **Rate Limiting**: Add delays between requests when scraping multiple pages
- **User-Agent**: Use a descriptive User-Agent to identify your scraper
- **Error Handling**: Handle cases where elements might not be found
- **JavaScript Rendering**: Only use when necessary as it consumes more resources
- **Authentication**: Never hardcode credentials - use environment variables

## Troubleshooting

### Playwright Installation

If you encounter Playwright errors:
```bash
playwright install chromium
```

### Timeout Errors

For slow-loading pages, increase the timeout:
```yaml
timeout: 120s
```

### Element Not Found

- Verify the selector using browser DevTools
- Check if the element loads dynamically (use `enable_javascript: true`)
- Use `wait_for` to wait for specific elements

## Advanced Usage

### Multi-Step Scraping

Combine multiple components in a workflow:

```yaml
workflows:
  - id: multi-step-scraping
    jobs:
      - id: get-links
        component: link-extractor
      - id: scrape-each-page
        component: page-scraper
        input:
          url: ${jobs.get-links.output.links[0]}
```

### Dynamic Form Values

Use workflow input for dynamic form submission:

```yaml
submit:
  form:
    input[name="search"]: ${input.query}
    select[name="category"]: ${input.category}
```
