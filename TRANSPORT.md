# MCP Server Transport Modes

This MCP server supports multiple transport modes for different use cases.

## Available Transport Modes

### 1. **stdio** (Default)
Standard input/output transport for local process-based integrations like Claude Code and Cursor.

**Usage:**
```bash
python server.py
# or explicitly
python server.py --transport=stdio
```

**Best for:**
- Claude Code integration
- Cursor IDE integration
- Local development tools
- Process-spawned integrations

### 2. **SSE**
Server-Sent Events (SSE) transport with HTTP for client requests. Good for remote servers and web clients.

**Usage:**
```bash
python server.py --transport=sse --port=3000
```

**Endpoints:**
- `GET http://localhost:3000/sse` - Establish SSE connection for server messages
- `POST http://localhost:3000/messages/` - Send client requests

**Best for:**
- Remote server deployments
- Web-based clients
- Microservices integration
- Development and testing

**Features:**
- Server-to-client notifications via SSE
- CORS enabled for browser clients
- Simple request/response model

## Configuration Options

### Port Configuration
Specify a custom port for SSE transport:

```bash
python server.py --transport=sse --port=8080
```

## Installation

Install Python dependencies:

```bash
pip install -r requirements.txt
```

## Client Connection Examples

### Connecting via stdio (Claude Code / Cursor)
Configure in your MCP client settings:
```json
{
  "mcpServers": {
    "sdk-mcp-server": {
      "command": "python",
      "args": ["path/to/server.py"]
    }
  }
}
```

### Connecting via SSE
First, establish an SSE connection to receive server messages:
```bash
curl -N http://localhost:3000/sse
```

Then, send requests to the message endpoint:
```bash
curl -X POST http://localhost:3000/messages/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {
        "name": "my-client",
        "version": "1.0.0"
      }
    },
    "id": 1
  }'
```

Send subsequent requests to the same message endpoint:
```bash
curl -X POST http://localhost:3000/messages/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 2
  }'
```

## Troubleshooting

### Port Already in Use
If port 3000 is already in use, specify a different port:
```bash
python server.py --transport=sse --port=3001
```

### CORS Issues
The server has CORS enabled with `allow_origins: ["*"]` for development. For production, configure appropriate CORS restrictions in `server.py`.

### Connection Issues
Make sure to:
1. Establish the SSE connection first (GET /sse)
2. Send requests to the message endpoint (POST /messages/)
3. Keep the SSE connection open to receive responses

## Notes

- **stdio** is the default transport to maintain compatibility with Claude Code and Cursor
- **SSE** transport uses Server-Sent Events for server-to-client messages
- All transports share the same tools, resources, and capabilities
