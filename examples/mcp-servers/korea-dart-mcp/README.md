# Korea DART MCP Server Example

This example demonstrates how to create an MCP server for querying Korean financial disclosure data from [DART (Data Analysis, Retrieval and Transfer System)](https://opendart.fss.or.kr), operated by South Korea's Financial Supervisory Service.

Inspired by [dart-mcp](https://github.com/2geonhyup/dart-mcp).

## Overview

This MCP server provides financial data workflows for Korean listed companies (KOSPI/KOSDAQ):

1. **Disclosure Search**: Search recent periodic disclosures and extract key financial metrics
2. **Financial Statements**: Retrieve structured financial data (balance sheet, income statement, cash flow)
3. **Company Overview**: Get basic company information (stock code, CEO, industry, etc.)
4. **Corporation Code Lookup**: Find a company's DART corp_code by name
5. **Dividend Information**: Retrieve dividend per share, yield, and payout ratio
6. **Major Shareholders**: Get information about major shareholders and holdings

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- DART Open API key

### Getting a DART API Key

1. Visit [DART Open API](https://opendart.fss.or.kr)
2. Sign up for an account
3. Request an API authentication key
4. The API key will be issued (free of charge)

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/mcp-servers/korea-dart-mcp
   ```

2. Copy the sample environment file:
   ```bash
   cp .env.sample .env
   ```

3. Edit `.env` and add your DART API key:
   ```env
   DART_API_KEY=your-actual-dart-api-key
   ```

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflows:**

   **Using MCP Client:**
   - Connect to MCP server: http://localhost:8080/mcp
   - Available workflows: search-disclosure, get-financial-statements, get-company-overview, get-company-code, get-dividend-info, get-major-shareholders
   - Use your MCP-compatible client to execute workflows

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Select the desired workflow
   - Enter the required parameters
   - Click the "Run" button

   **Using CLI:**
   ```bash
   # Look up a company's corp_code by name
   model-compose run get-company-code --input '{"corp_name": "삼성전자"}'

   # Search disclosures for a company
   model-compose run search-disclosure --input '{
     "corp_code": "00126380",
     "bgn_de": "20240101",
     "end_de": "20241231"
   }'

   # Get annual financial statements (consolidated)
   model-compose run get-financial-statements --input '{
     "corp_code": "00126380",
     "bsns_year": "2024",
     "reprt_code": "11011",
     "fs_div": "CFS"
   }'

   # Get company overview
   model-compose run get-company-overview --input '{"corp_code": "00126380"}'

   # Get dividend information
   model-compose run get-dividend-info --input '{
     "corp_code": "00126380",
     "bsns_year": "2024"
   }'

   # Get major shareholders
   model-compose run get-major-shareholders --input '{
     "corp_code": "00126380",
     "bsns_year": "2024"
   }'
   ```

## Component Details

### Corp Code Lookup (Shell Component)
- **ID**: `corp-code-lookup`
- **Type**: Shell component (Python script)
- **Purpose**: Download DART corp code ZIP/XML file, parse it, and search by company name
- **Authentication**: Uses `DART_API_KEY` environment variable

### DART Open API HTTP Client Component
- **ID**: `dart-api`
- **Type**: HTTP client component with multiple actions
- **Purpose**: DART Open API integration
- **Base URL**: `https://opendart.fss.or.kr/api`
- **Authentication**: API key passed as query parameter
- **Actions**:
  - **search-disclosure**: Search periodic disclosure filings
  - **get-financial-statements**: Retrieve full financial statement data
  - **get-company-overview**: Get company basic information
  - **get-dividend-info**: Retrieve dividend data
  - **get-major-shareholders**: Get major shareholder information

## Workflow Details

### "Search DART Disclosure" Workflow

**Description**: Search recent periodic disclosures for a Korean listed company

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `corp_code` | text | Yes | - | DART corporation code (8-digit) |
| `bgn_de` | text | Yes | - | Search start date (YYYYMMDD) |
| `end_de` | text | Yes | - | Search end date (YYYYMMDD) |
| `last_reprt_at` | text | No | `Y` | Only return the latest report (Y/N) |
| `pblntf_ty` | text | No | `A` | Disclosure type (A=annual, B=semi-annual, C=quarterly) |

### "Get Financial Statements" Workflow

**Description**: Retrieve structured financial data by year and report type

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `corp_code` | text | Yes | - | DART corporation code (8-digit) |
| `bsns_year` | text | Yes | - | Business year (YYYY) |
| `reprt_code` | text | No | `11011` | Report code (11011=annual, 11012=semi-annual, 11013=Q1, 11014=Q3) |
| `fs_div` | text | No | `CFS` | Financial statement division (CFS=consolidated, OFS=separate) |

### "Get Company Overview" Workflow

**Description**: Get basic company information

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `corp_code` | text | Yes | - | DART corporation code (8-digit) |

### "Get Company Code" Workflow

**Description**: Search for a company's DART corporation code by name (downloads and parses the full DART corp code ZIP/XML)

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `corp_name` | text | Yes | - | Company name to search (Korean or English) |

### "Get Dividend Information" Workflow

**Description**: Retrieve dividend data for a listed company

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `corp_code` | text | Yes | - | DART corporation code (8-digit) |
| `bsns_year` | text | Yes | - | Business year (YYYY) |
| `reprt_code` | text | No | `11011` | Report code |

### "Get Major Shareholders" Workflow

**Description**: Retrieve major shareholder information

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `corp_code` | text | Yes | - | DART corporation code (8-digit) |
| `bsns_year` | text | Yes | - | Business year (YYYY) |
| `reprt_code` | text | No | `11011` | Report code |

## MCP Server Integration

### Connection Details
- **Transport**: HTTP
- **Endpoint**: `http://localhost:8080/mcp`
- **Protocol**: Model Context Protocol v1.0

### Available Tools
AI agents can access these workflows as tools:
- `search-disclosure`: Search disclosure filings
- `get-financial-statements`: Retrieve financial statements
- `get-company-overview`: Get company information
- `get-company-code`: Find corporation codes by company name
- `get-dividend-info`: Get dividend data
- `get-major-shareholders`: Get shareholder information

## DART Open API Reference

### Endpoints Used

1. **list.json** - Search disclosure filings
   - Documentation: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001

2. **fnlttSinglAcntAll.json** - Full financial statements (single account)
   - Documentation: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019020

3. **company.json** - Company overview
   - Documentation: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019002

4. **corpCode.xml** - Corporation code lookup
   - Documentation: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019018

5. **alotMatter.json** - Dividend information
   - Documentation: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS004&apiId=2019006

6. **hyslrSttus.json** - Major shareholders
   - Documentation: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS004&apiId=2019004

## Error Handling

### Common API Errors

| Status | Message | Solution |
|--------|---------|----------|
| `010` | Unregistered API key | Check your `DART_API_KEY` |
| `011` | Usage limit exceeded | Wait and retry (daily limit) |
| `012` | No data found | Verify corp_code and date range |
| `013` | Undisclosed data | Data not yet available for the period |
| `020` | Invalid parameter | Check parameter format and values |
| `100` | Field limit exceeded | Reduce request scope |
| `800` | IP not allowed | Register your IP in DART settings |
| `900` | Unspecified error | Contact DART support |

## Troubleshooting

### Common Issues

1. **No results returned**: Verify the `corp_code` is correct (use `get-company-code` first)
2. **Authentication error**: Ensure `DART_API_KEY` is set correctly in `.env`
3. **Empty financial data**: The company may not have filed for the requested period
4. **get-company-code slow**: The corp code API downloads a ~3MB ZIP file on each call; this is expected behavior
