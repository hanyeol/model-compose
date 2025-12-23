# Web Scraper Component

The web scraper component enables extracting data from web pages using CSS selectors or XPath expressions. It supports both simple HTTP requests and JavaScript rendering with browser automation, form submission, and cookie injection.

## Basic Configuration

```yaml
component:
  type: web-scraper
  url: https://example.com
  selector: .content
  extract_mode: text
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `web-scraper` |
| `headers` | object | `{}` | Default HTTP headers to include in all requests |
| `cookies` | object | `{}` | Default cookies to include in all requests |
| `timeout` | string | `60s` | Default timeout for all requests |
| `actions` | array | `[]` | List of web scraping actions |

### Action Configuration

Web scraper actions support the following options:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | **required** | URL to scrape |
| `headers` | object | `{}` | HTTP headers to include in the request |
| `cookies` | object | `{}` | Cookies to include in the request |
| `selector` | string | `null` | CSS selector to extract elements (mutually exclusive with `xpath`) |
| `xpath` | string | `null` | XPath expression to extract elements (mutually exclusive with `selector`) |
| `extract_mode` | string | `text` | Extraction mode: `text`, `html`, or `attribute` |
| `attribute` | string | `null` | Attribute name to extract when `extract_mode='attribute'` |
| `multiple` | boolean | `false` | Extract multiple elements (returns list) or single element |
| `enable_javascript` | boolean | `false` | Enable JavaScript rendering (requires playwright) |
| `wait_for` | string | `null` | CSS selector to wait for when `enable_javascript=true` |
| `timeout` | string | `null` | Maximum time to wait for request completion |
| `submit` | object | `null` | Form submission configuration (requires `enable_javascript=true`) |

### Form Submission Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `selector` | string | `null` | CSS selector to locate form or submit button |
| `xpath` | string | `null` | XPath expression to locate form or submit button |
| `form` | object | `null` | Form input values to fill. Keys are input selectors, values are input values |
| `wait_for` | string | `null` | CSS selector to wait for after form submission |

## Usage Examples

### Simple Page Scraping

Extract text content using CSS selector:

```yaml
component:
  type: web-scraper
  url: https://example.com/blog
  selector: article.post-content
  extract_mode: text
  output:
    content: ${result}
```

### Extract Multiple Elements

Scrape multiple items from a list:

```yaml
component:
  type: web-scraper
  url: https://news.ycombinator.com
  selector: .titleline > a
  extract_mode: text
  multiple: true
  output:
    titles: ${result}
```

### Extract Attributes

Get links from anchor tags:

```yaml
component:
  type: web-scraper
  url: https://example.com
  selector: a.product-link
  extract_mode: attribute
  attribute: href
  multiple: true
  output:
    product_urls: ${result}
```

### Using XPath

Extract data using XPath expressions:

```yaml
component:
  type: web-scraper
  url: https://example.com
  xpath: //div[@class='price']/text()
  extract_mode: text
  output:
    price: ${result}
```

### JavaScript Rendering

Scrape dynamic content that requires JavaScript:

```yaml
component:
  type: web-scraper
  url: https://spa.example.com
  enable_javascript: true
  wait_for: .dynamic-content
  selector: .data
  extract_mode: text
  output:
    scraped_data: ${result}
```

### Cookie Injection

Scrape authenticated pages using cookies:

```yaml
component:
  type: web-scraper
  url: https://example.com/dashboard
  cookies:
    session_id: ${env.SESSION_ID}
    auth_token: ${env.AUTH_TOKEN}
  selector: .user-data
  extract_mode: text
  output:
    user_info: ${result}
```

### Custom Headers

Include custom headers in requests:

```yaml
component:
  type: web-scraper
  url: https://api.example.com/data
  headers:
    User-Agent: "Mozilla/5.0 (Custom Bot)"
    Accept-Language: "en-US"
  selector: .api-response
  extract_mode: text
```

### Form Submission

Fill and submit forms before extraction:

```yaml
component:
  type: web-scraper
  url: https://example.com/search
  enable_javascript: true
  submit:
    selector: form#search-form
    form:
      input[name="q"]: ${input.search_query}
      input[name="category"]: technology
    wait_for: .search-results
  selector: .result-item
  extract_mode: text
  multiple: true
  output:
    search_results: ${result}
```

## Multiple Actions Component

Define multiple scraping tasks for different pages:

```yaml
component:
  type: web-scraper
  headers:
    User-Agent: "Mozilla/5.0 (Custom Bot)"
  cookies:
    session: ${env.SESSION_COOKIE}
  timeout: 30s
  actions:
    - id: scrape-homepage
      url: https://example.com
      selector: .hero-title
      extract_mode: text
      output:
        title: ${result}

    - id: scrape-products
      url: https://example.com/products
      selector: .product-card
      extract_mode: html
      multiple: true
      output:
        products: ${result}

    - id: scrape-prices
      url: https://example.com/products
      selector: .price
      extract_mode: text
      multiple: true
      output:
        prices: ${result}
```

## Advanced Configuration Examples

### Dynamic Scraping with Variable URLs

```yaml
component:
  type: web-scraper
  url: https://example.com/product/${input.product_id}
  selector: .product-details
  extract_mode: html
  output:
    details: ${result}
```

### Scraping with Authentication

Combine cookies and headers for authenticated scraping:

```yaml
component:
  type: web-scraper
  url: https://secure.example.com/data
  headers:
    Authorization: Bearer ${env.API_TOKEN}
    X-Request-ID: ${input.request_id}
  cookies:
    session_id: ${env.SESSION_ID}
    preferences: ${input.user_prefs}
  selector: .protected-content
  extract_mode: text
  output:
    content: ${result}
```

### Multi-Step Scraping

Scrape data after multiple interactions:

```yaml
component:
  type: web-scraper
  url: https://example.com/search
  enable_javascript: true
  submit:
    selector: form#search-form
    form:
      input[name="query"]: ${input.search_term}
      select[name="filter"]: ${input.filter_option}
    wait_for: .results-loaded
  selector: .search-result
  extract_mode: html
  multiple: true
  timeout: 60s
  output:
    results: ${result}
```

### Extract Full Page Content

Get the entire page content without selectors:

```yaml
component:
  type: web-scraper
  url: https://example.com/article
  extract_mode: text
  output:
    full_text: ${result}
```

### Extract Raw HTML

Get HTML source of specific elements:

```yaml
component:
  type: web-scraper
  url: https://example.com
  selector: article
  extract_mode: html
  output:
    article_html: ${result}
```

## Integration with Workflows

### Sequential Scraping

Scrape multiple pages in sequence:

```yaml
workflows:
  - id: multi-page-scraper
    jobs:
      - id: scrape-list
        component: list-scraper
        input:
          url: https://example.com/products
        output:
          product_links: ${output.links}

      - id: scrape-details
        component: detail-scraper
        input:
          urls: ${scrape-list.output.product_links}
        depends_on: [ scrape-list ]

components:
  - id: list-scraper
    type: web-scraper
    url: ${input.url}
    selector: a.product-link
    extract_mode: attribute
    attribute: href
    multiple: true
    output:
      links: ${result}

  - id: detail-scraper
    type: web-scraper
    url: ${input.url}
    selector: .product-description
    extract_mode: text
    output:
      description: ${result}
```

### Scraping and Processing

Combine scraping with data processing:

```yaml
workflows:
  - id: scrape-and-analyze
    jobs:
      - id: scrape
        component: web-scraper
        input:
          url: ${input.target_url}
        output:
          raw_content: ${output.content}

      - id: analyze
        component: text-analyzer
        input:
          text: ${scrape.output.raw_content}
        depends_on: [ scrape ]

components:
  - id: web-scraper
    type: web-scraper
    url: ${input.url}
    selector: .main-content
    extract_mode: text
    output:
      content: ${result}
```

### Authenticated Scraping Pipeline

```yaml
workflows:
  - id: authenticated-scraping
    jobs:
      - id: login
        component: login-form
        input:
          username: ${env.USERNAME}
          password: ${env.PASSWORD}
        output:
          session_cookie: ${output.cookie}

      - id: scrape-protected
        component: protected-scraper
        input:
          session: ${login.output.session_cookie}
        depends_on: [ login ]

components:
  - id: login-form
    type: web-scraper
    url: https://example.com/login
    enable_javascript: true
    submit:
      selector: form#login-form
      form:
        input[name="username"]: ${input.username}
        input[name="password"]: ${input.password}
      wait_for: .dashboard
    # Extract session cookie from browser context
    output:
      cookie: ${result}

  - id: protected-scraper
    type: web-scraper
    url: https://example.com/protected/data
    cookies:
      session: ${input.session}
    selector: .protected-content
    extract_mode: text
    output:
      data: ${result}
```

## Extract Modes Comparison

### Text Mode

Extracts clean text content without HTML tags:

```yaml
component:
  type: web-scraper
  url: https://example.com
  selector: .article
  extract_mode: text
  # Output: "This is the article content"
```

### HTML Mode

Extracts full HTML including tags:

```yaml
component:
  type: web-scraper
  url: https://example.com
  selector: .article
  extract_mode: html
  # Output: "<div class='article'>This is the article content</div>"
```

### Attribute Mode

Extracts specific HTML attributes:

```yaml
component:
  type: web-scraper
  url: https://example.com
  selector: img.product
  extract_mode: attribute
  attribute: src
  # Output: "https://example.com/image.jpg"
```

## Timeout Configuration

### Component-Level Timeout

Apply to all actions:

```yaml
component:
  type: web-scraper
  timeout: 30s
  actions:
    - id: scrape-1
      url: https://example.com/page1
      selector: .content

    - id: scrape-2
      url: https://example.com/page2
      selector: .content
```

### Action-Level Timeout

Override for specific actions:

```yaml
component:
  type: web-scraper
  timeout: 30s
  actions:
    - id: quick-scrape
      url: https://example.com/fast
      selector: .content
      timeout: 10s

    - id: slow-scrape
      url: https://example.com/slow
      selector: .content
      timeout: 120s
      enable_javascript: true
```

## Cookie Management

### Component-Level Cookies

Shared across all actions:

```yaml
component:
  type: web-scraper
  cookies:
    session_id: ${env.SESSION_ID}
    tracking_consent: "true"
  actions:
    - id: scrape-page-1
      url: https://example.com/page1
      selector: .content

    - id: scrape-page-2
      url: https://example.com/page2
      selector: .content
```

### Action-Level Cookie Override

Override cookies for specific actions:

```yaml
component:
  type: web-scraper
  cookies:
    default_cookie: "value"
  actions:
    - id: normal-scrape
      url: https://example.com/public
      selector: .content
      # Uses default_cookie

    - id: special-scrape
      url: https://example.com/special
      selector: .content
      cookies:
        special_auth: ${env.SPECIAL_TOKEN}
        # Merges with default_cookie
```

### Dynamic Cookie Injection

Use variables for dynamic cookie values:

```yaml
component:
  type: web-scraper
  url: https://example.com/user/profile
  cookies:
    user_id: ${input.user_id}
    session_token: ${input.session}
    preferences: ${input.prefs | "default"}
  selector: .user-data
  extract_mode: text
```

## Best Practices

1. **Use CSS Selectors for Simplicity**: Prefer CSS selectors over XPath when possible
2. **Enable JavaScript Sparingly**: Only use `enable_javascript` when necessary (it's slower)
3. **Set Appropriate Timeouts**: Adjust timeout based on page complexity
4. **Handle Multiple Elements**: Use `multiple: true` for lists and collections
5. **Respect robots.txt**: Check site's scraping policy before deployment
6. **Use Headers Wisely**: Set realistic User-Agent and other headers
7. **Cookie Security**: Store sensitive cookies in environment variables
8. **Error Handling**: Implement fallback strategies for failed scraping
9. **Rate Limiting**: Add delays between requests to avoid overwhelming servers

## Variable Interpolation

Web scraper supports dynamic configuration:

```yaml
component:
  type: web-scraper
  url: ${input.target_url}
  selector: ${input.selector_pattern}
  extract_mode: ${input.mode | "text"}
  multiple: ${input.extract_multiple as boolean | false}
  enable_javascript: ${input.needs_js as boolean | false}
  headers:
    User-Agent: ${input.user_agent | "Mozilla/5.0"}
  cookies:
    session: ${env.SESSION_COOKIE}
    custom: ${input.custom_cookie}
```

## Common Use Cases

- **Data Aggregation**: Collect data from multiple web sources
- **Price Monitoring**: Track product prices across e-commerce sites
- **Content Extraction**: Extract articles, blog posts, or news content
- **SEO Analysis**: Gather meta tags, headings, and page structure
- **Market Research**: Collect competitor data and market intelligence
- **Form Automation**: Auto-fill and submit web forms
- **Testing**: Validate web page content and structure
- **Monitoring**: Check website availability and content changes
