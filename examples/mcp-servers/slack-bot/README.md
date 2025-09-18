# Slack Bot MCP Server Example

This example demonstrates how to create a Slack bot using model-compose's MCP (Model Context Protocol) server functionality, providing multiple workflows for Slack channel management and messaging.

## Overview

This MCP server provides Slack integration workflows that:

1. **Message Sending**: Send messages to Slack channels with support for attachments
2. **Channel Management**: List available channels and join new channels
3. **MCP Server**: Exposes workflows through Model Context Protocol for AI agent integration
4. **Multi-Workflow**: Demonstrates multiple related workflows in a single MCP server

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Slack App with appropriate permissions
- Slack App Token (Bot User OAuth Token)

### Slack App Configuration

1. Create a new Slack App at https://api.slack.com/apps
2. Add the following OAuth scopes under "OAuth & Permissions":
   - `channels:read` - View basic information about public channels
   - `channels:join` - Join public channels
   - `chat:write` - Send messages as the bot
   - `groups:read` - View basic information about private channels (optional)

3. Install the app to your workspace
4. Copy the "Bot User OAuth Token" (starts with `xoxb-`)

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/mcp-servers/slack-bot
   ```

2. Copy the sample environment file:
   ```bash
   cp .env.sample .env
   ```

3. Edit `.env` and add your Slack credentials:
   ```env
   SLACK_APP_TOKEN=xoxb-your-actual-bot-token
   DEFAULT_SLACK_CHANNEL_ID=C1234567890
   ```

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
2. **Run the workflows:**

   **Using MCP Client:**
   - Connect to MCP server: http://localhost:8080/mcp
   - Available workflows: send-message, list-channels, join-channel
   - Use your MCP-compatible client to execute workflows

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Select the desired workflow (send-message, list-channels, join-channel)
   - Enter the required parameters
   - Click the "Run" button

   **Using CLI:**
   ```bash
   # Send a message to default channel
   model-compose run send-message --input '{"messsage": "Hello from model-compose!"}'
   
   # Send to specific channel
   model-compose run send-message --input '{
     "channel": "C1234567890",
     "messsage": "Hello specific channel!"
   }'
   
   # List channels
   model-compose run list-channels
   
   # Join a channel
   model-compose run join-channel --input '{"channel": "C1234567890"}'
   ```

## Component Details

### Slack API HTTP Client Component (Default)
- **Type**: HTTP client component with multiple actions
- **Purpose**: Slack Web API integration
- **Base URL**: `https://slack.com/api`
- **Authentication**: Bearer token using `SLACK_APP_TOKEN`
- **Actions**:
  - **chat-post-message**: Send messages to channels
  - **conversations-list**: Retrieve channel listings
  - **conversations-join**: Join public channels
- **Features**:
  - Automatic OAuth token handling
  - JSON and URL-encoded request support
  - Response data filtering and transformation
  - Error handling for Slack API responses

## Workflow Details

### "Send Message to Slack Channel" Workflow

**Description**: Send a text message to a specified Slack channel using the Slack Web API

#### Job Flow

```mermaid
graph TD
    %% Default job (implicit)
    J1((send-message<br/>job))

    %% Component
    C1[Slack API<br/>component]

    %% Job to component connections
    J1 --> C1
    C1 -.-> |API response| J1

    %% Input/Output
    Input((Input)) --> J1
    J1 --> Output((Output))
```

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `channel` | text | No | `DEFAULT_SLACK_CHANNEL_ID` | Slack channel ID for sending a message |
| `message` | text | Yes | - | Message to send to Slack |
| `attachments` | object[] | No | - | Optional message attachments |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| - | json | Complete Slack API response including message metadata |

### "List Slack Channels" Workflow

**Description**: Retrieve a list of all available channels in the Slack workspace

#### Job Flow

```mermaid
graph TD
    %% Default job (implicit)
    J1((list-channels<br/>job))

    %% Component
    C1[Slack API<br/>component]

    %% Job to component connections
    J1 --> C1
    C1 -.-> |channel list| J1

    %% Input/Output
    Input((Input)) --> J1
    J1 --> Output((Output))
```

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | integer | No | 200 | Maximum number of channels to retrieve |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| - | object[] | Array of channel objects with `id` and `name` fields |

### "Join Slack Channel" Workflow

**Description**: Join a specified Slack channel for the bot user

#### Job Flow

```mermaid
graph TD
    %% Default job (implicit)
    J1((join-channel<br/>job))

    %% Component
    C1[Slack API<br/>component]

    %% Job to component connections
    J1 --> C1
    C1 -.-> |join result| J1

    %% Input/Output
    Input((Input)) --> J1
    J1 --> Output((Output))
```

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `channel` | text | No | `DEFAULT_SLACK_CHANNEL_ID` | Slack channel ID to join |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| - | json | Complete Slack API response including channel join status |

## MCP Server Integration

This example serves as an MCP server that can be integrated with AI agents and tools supporting the Model Context Protocol:

### Connection Details
- **Transport**: HTTP
- **Endpoint**: `http://localhost:8080/mcp`
- **Protocol**: Model Context Protocol v1.0

### Available Tools
AI agents can access these workflows as tools:
- `send-message`: Send messages to Slack
- `list-channels`: Get available channels
- `join-channel`: Join public channels

## Slack Web API Reference

### Endpoints Used

1. **chat.postMessage**
   - **Purpose**: Send messages to channels
   - **Documentation**: https://api.slack.com/methods/chat.postMessage

2. **conversations.list**
   - **Purpose**: List conversations (channels)
   - **Documentation**: https://api.slack.com/methods/conversations.list

3. **conversations.join**
   - **Purpose**: Join a conversation
   - **Documentation**: https://api.slack.com/methods/conversations.join

## Error Handling

Common Slack API errors and solutions:

### Authentication Errors
- **invalid_auth**: Check your `SLACK_APP_TOKEN` is correct
- **token_revoked**: Regenerate your bot token in Slack App settings

### Permission Errors
- **missing_scope**: Add required OAuth scopes to your Slack App
- **channel_not_found**: Verify channel ID is correct
- **not_in_channel**: Bot needs to be added to private channels

### Rate Limiting
- Slack API has rate limits - the bot will receive `rate_limited` errors if exceeded
- Implement retry logic or reduce request frequency

## Customization

### Add More Slack Actions
Extend the component with additional Slack API methods:

```yaml
actions:
  - id: users-list
    path: /users.list
    method: GET
    headers:
      Content-Type: application/x-www-form-urlencoded
    output: ${response.members}
```

### Create Custom Workflows
Combine multiple actions in a single workflow:

```yaml
workflows:
  - id: notify-and-join
    jobs:
      - id: join
        action: conversations-join
        input:
          channel: ${input.channel}
      - id: notify
        action: chat-post-message
        input:
          channel: ${input.channel}
          text: "Bot has joined the channel!"
        depends_on: [join]
```

### Environment-Specific Configuration
Use different tokens for different environments:

```yaml
headers:
  Authorization: Bearer ${env.SLACK_BOT_TOKEN_PROD | ${env.SLACK_BOT_TOKEN_DEV}}
```

## Security Considerations

- **Token Security**: Never commit tokens to version control
- **Scope Limitation**: Only request necessary OAuth scopes
- **Channel Permissions**: Be aware of public vs private channel access
- **Message Content**: Validate and sanitize user input before sending
- **Rate Limiting**: Implement appropriate request throttling

## Troubleshooting

### Common Issues

1. **Token Invalid**: Verify bot token starts with `xoxb-` and has correct permissions
2. **Channel Not Found**: Use channel ID (starts with `C`) not channel name
3. **Bot Not in Channel**: Add bot to private channels manually or use public channels
4. **MCP Connection Issues**: Ensure MCP server is running on correct port

### Debugging Tips

- Use Slack's API tester: https://api.slack.com/methods
- Check Slack App event logs for permission issues
- Monitor MCP server logs for request/response details
- Test individual workflows before using in MCP context