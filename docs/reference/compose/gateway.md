# Gateway Configuration Reference

Gateways provide tunneling services that expose local ports to external networks. They enable external access to your model-compose services by creating secure tunnels through firewalls and NAT configurations.

## Basic Structure

### Single Gateway

```yaml
gateway:
  type: http-tunnel | ssh-tunnel
  runtime: native | docker
  port: 8090                    # Single port
  # OR
  port:                         # Multiple ports
    - 8090
    - 8091
    - 8092
  # ... type-specific configuration
```

### Multiple Gateways

```yaml
gateways:
  - type: http-tunnel
    driver: ngrok
    port: 8080
    # ... configuration for first gateway
    
  - type: ssh-tunnel
    port: 8090
    connection:
      # ... SSH connection configuration
```

## Gateway Types

### HTTP Tunnel (`http-tunnel`)

Creates HTTP tunnels using third-party services like ngrok or Cloudflare tunnels to expose local services to the internet.

```yaml
gateway:
  type: http-tunnel
  driver: ngrok | cloudflare
  port: 8080              # Local port to tunnel
  runtime: native
```

### SSH Tunnel (`ssh-tunnel`)

Creates SSH tunnels to expose local services through a remote SSH server.

```yaml
gateway:
  type: ssh-tunnel
  port: 8080              # Local port to tunnel
  connection:
    host: remote-server.com
    port: 22
    auth:
      type: keyfile | password
      username: user
      # ... auth configuration
```

## Common Configuration Options

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Gateway type: `http-tunnel` or `ssh-tunnel` |
| `runtime` | string | `native` | Runtime environment: `native` or `docker` |
| `port` | integer or array | `8090` | Local port(s) to tunnel through the gateway. Can be a single port number or an array of ports |

## HTTP Tunnel Configuration

### Ngrok Driver

Uses ngrok service to create HTTP tunnels.

**Single port:**
```yaml
gateway:
  type: http-tunnel
  driver: ngrok
  port: 8080
  runtime: native
```

**Multiple ports:**
```yaml
gateway:
  type: http-tunnel
  driver: ngrok
  port:
    - 8080
    - 8090
    - 3000
  runtime: native
```

Each port gets its own unique public URL (e.g., `https://abc123.ngrok.io`, `https://def456.ngrok.io`, `https://ghi789.ngrok.io`).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `driver` | string | **required** | Must be `ngrok` |
| `port` | integer or array | **required** | Local port(s) to expose. Can be single port or array of ports |

**Prerequisites:**
- ngrok CLI must be installed and configured
- ngrok account and authtoken (for persistent tunnels)

**Accessing Public URLs:**
Use `${gateway:PORT.public_url}` to access the public URL for each port in your configuration.

### Cloudflare Driver

Uses Cloudflare tunnels to expose local services.

**Single port:**
```yaml
gateway:
  type: http-tunnel
  driver: cloudflare
  port: 8080
  runtime: native
```

**Multiple ports:**
```yaml
gateway:
  type: http-tunnel
  driver: cloudflare
  port:
    - 8080
    - 8090
    - 3000
  runtime: native
```

Each port gets its own unique public URL (e.g., `https://abc-def.trycloudflare.com`, `https://ghi-jkl.trycloudflare.com`).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `driver` | string | **required** | Must be `cloudflare` |
| `port` | integer or array | **required** | Local port(s) to expose. Can be single port or array of ports |

**Prerequisites:**
- Cloudflare tunnel CLI (cloudflared) must be installed
- Cloudflare account with tunnel configured

**Accessing Public URLs:**
Use `${gateway:PORT.public_url}` to access the public URL for each port in your configuration.

## SSH Tunnel Configuration

Creates secure SSH tunnels through remote servers.

**Single port:**
```yaml
gateway:
  type: ssh-tunnel
  port:
    - "9834:8080"              # Remote port 9834 -> Local port 8080
  connection:
    host: tunnel-server.example.com
    port: 22
    auth:
      type: keyfile
      username: tunnel-user
      keyfile: "/path/to/private/key"
```

**Multiple ports:**
```yaml
gateway:
  type: ssh-tunnel
  port:
    - "9834:8080"              # Remote port 9834 -> Local port 8080
    - "9835:8090"              # Remote port 9835 -> Local port 8090
    - "9836:3000"              # Remote port 9836 -> Local port 3000
  connection:
    host: tunnel-server.example.com
    port: 22
    auth:
      type: keyfile
      username: tunnel-user
      keyfile: "/path/to/private/key"
```

**Port Format:** `"remote_port:local_port"`
- The remote port is exposed on the SSH server
- Traffic is forwarded to the local port
- Multiple port mappings can be specified as an array

**Accessing Public Addresses:**
Use `${gateway:LOCAL_PORT.public_address}` to access the public address (returns `remote-host:remote-port`).

### Connection Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `connection` | object | **required** | SSH connection configuration |
| `connection.host` | string | **required** | Host address of the SSH server |
| `connection.port` | integer | `22` | SSH server port |
| `connection.auth` | object | **required** | SSH authentication configuration |

### Authentication Configuration

#### Keyfile Authentication

```yaml
auth:
  type: keyfile
  username: ssh-user
  keyfile: "/home/user/.ssh/id_rsa"
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `keyfile` |
| `username` | string | **required** | SSH username |
| `keyfile` | string | **required** | Path to private key file |

#### Password Authentication

```yaml
auth:
  type: password
  username: ssh-user
  password: secure-password
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `password` |
| `username` | string | **required** | SSH username |
| `password` | string | **required** | SSH password |

## Configuration Examples

### Simple Ngrok Tunnel (Single Port)

```yaml
gateway:
  type: http-tunnel
  driver: ngrok
  port: 8080
```

Exposes local port 8080 through ngrok tunnel with a random public URL.

### Ngrok Tunnel with Multiple Ports

```yaml
gateway:
  type: http-tunnel
  driver: ngrok
  port:
    - 8080    # Main API
    - 8081    # Admin panel
    - 3000    # Frontend app
```

Exposes three local ports through separate ngrok tunnels. Access URLs via:
- `${gateway:8080.public_url}` for the main API
- `${gateway:8081.public_url}` for the admin panel
- `${gateway:3000.public_url}` for the frontend app

### Cloudflare Tunnel (Single Port)

```yaml
gateway:
  type: http-tunnel
  driver: cloudflare
  port: 8080
  runtime: native
```

Creates a Cloudflare tunnel for local port 8080.

### Cloudflare Tunnel with Multiple Ports

```yaml
gateway:
  type: http-tunnel
  driver: cloudflare
  port:
    - 8090    # Callback listener
    - 8091    # Status endpoint
    - 3000    # Web interface
  runtime: native
```

Each port gets its own Cloudflare tunnel URL.

### SSH Tunnel with Key Authentication (Single Port)

```yaml
gateway:
  type: ssh-tunnel
  port:
    - "9834:8080"    # Remote 9834 -> Local 8080
  runtime: native
  connection:
    host: bastion.example.com
    port: 22
    auth:
      type: keyfile
      username: deploy
      keyfile: ~/.ssh/tunnel_key
```

Creates an SSH tunnel through bastion.example.com using SSH key authentication.

### SSH Tunnel with Multiple Ports

```yaml
gateway:
  type: ssh-tunnel
  port:
    - "9834:8080"    # Remote 9834 -> Local 8080
    - "9835:8090"    # Remote 9835 -> Local 8090
    - "9836:3000"    # Remote 9836 -> Local 3000
  connection:
    host: bastion.example.com
    port: 22
    auth:
      type: keyfile
      username: deploy
      keyfile: ~/.ssh/tunnel_key
```

Exposes multiple local ports through different remote ports on the SSH server.

### SSH Tunnel with Password Authentication

```yaml
gateway:
  type: ssh-tunnel
  port:
    - "9834:8080"
  connection:
    host: vpn-server.company.com
    port: 2222
    auth:
      type: password
      username: tunnel-user
      password: ${env.TUNNEL_PASSWORD}
```

Creates an SSH tunnel using password authentication with password stored in environment variable.

### Multiple Gateways

You can configure multiple gateways to expose different services:

```yaml
gateways:
  - type: http-tunnel
    driver: ngrok
    port: 8080    # Expose main API
    
  - type: http-tunnel
    driver: ngrok
    port: 8081    # Expose web UI
    
  - type: ssh-tunnel
    port: 8090    # Expose admin interface through SSH
    connection:
      host: secure-bastion.example.com
      auth:
        type: keyfile
        username: admin
        keyfile: /secure/admin-key
```

## Use Cases

### Development and Testing

Expose local development servers for:
- Webhook testing from external services
- Mobile app testing against local APIs
- Sharing work-in-progress with team members
- Integration testing with external systems

### Production Deployment

Enable external access in environments where:
- Direct port exposure is not possible due to NAT/firewall
- SSL termination is handled by the tunnel service
- Load balancing and DDoS protection are provided by tunnel service

### Hybrid Cloud Architectures

Connect on-premises services to cloud systems:
- Expose internal APIs to cloud-based consumers
- Create secure channels for data synchronization
- Enable cloud-to-on-premises webhook delivery

## Security Considerations

### HTTP Tunnels
- **Public URLs**: HTTP tunnels create publicly accessible URLs
- **Authentication**: Implement proper authentication in your services
- **Rate Limiting**: Configure rate limiting to prevent abuse
- **Monitoring**: Monitor tunnel usage and access patterns

### SSH Tunnels
- **Key Management**: Securely store and manage SSH private keys
- **User Permissions**: Use dedicated SSH users with minimal privileges
- **Network Security**: Ensure SSH servers are properly hardened
- **Access Logging**: Enable SSH access logging for security auditing

## Performance Considerations

- **Latency**: Tunnels add network latency compared to direct connections
- **Bandwidth**: Monitor bandwidth usage, especially for high-traffic services
- **Reliability**: HTTP tunnels may have uptime limitations based on provider
- **Concurrent Connections**: Consider connection limits imposed by tunnel services

## Troubleshooting

### HTTP Tunnel Issues
- Verify tunnel service CLI is installed and authenticated
- Check service status and quota limits
- Ensure local port is accessible and not blocked by firewall

### SSH Tunnel Issues
- Verify SSH connectivity to remote server
- Check SSH key permissions (should be 600 or 400)
- Confirm SSH server allows tunnel/port forwarding
- Validate authentication credentials and user permissions

## Integration with Controllers

Gateways work seamlessly with controllers to expose services:

```yaml
controller:
  type: http-server
  port: 8080

gateway:
  type: http-tunnel
  driver: ngrok
  port: 8080  # Same port as controller
```

This configuration exposes the HTTP controller through an ngrok tunnel, making it accessible from the internet.