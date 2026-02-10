# MCP Server Transport Modes

This MCP server now supports multiple transport modes for different use cases.

## Available Transport Modes

### 1. **stdio** (Default)
Standard input/output transport for local process-based integrations like Cursor.

**Usage:**
```bash
npm start
# or
node server.js
# or explicitly
node server.js --transport=stdio
```

**Best for:**
- Cursor IDE integration
- Local development tools
- Process-spawned integrations

### 2. **HTTP/SSE**
Server-Sent Events (SSE) transport with HTTP for client requests. Good for remote servers and web clients.

**Usage:**
```bash
npm run start:http
# or
node server.js --transport=http --port=3000
```

**Endpoints:**
- `GET http://localhost:3000/sse` - Establish SSE connection for server messages
- `POST http://localhost:3000/message` - Send client requests

**Best for:**
- Remote server deployments
- Web-based clients
- Microservices integration
- Development and testing

**Features:**
- Server-to-client notifications via SSE
- CORS enabled for browser clients
- Simple request/response model

### 3. **SSE**
Alias for HTTP mode - both use the same SSE transport implementation.

**Usage:**
```bash
npm run start:sse
# or
node server.js --transport=sse --port=3000
```

## Configuration Options

### Port Configuration
Specify a custom port for HTTP/SSE transports:

```bash
node server.js --transport=http --port=8080
```

### Multiple Arguments
Combine transport and port arguments:

```bash
node server.js --transport=http --port=3001
```

## Installation

After adding the new transport support, install the updated dependencies:

```bash
npm install
```

## Client Connection Examples

### Connecting via stdio (Cursor)
Configure in your Cursor MCP settings:
```json
{
  "mcpServers": {
    "sdk-mcp-server": {
      "command": "node",
      "args": ["path/to/server.js"]
    }
  }
}
```

### Connecting via HTTP/SSE
First, establish an SSE connection to receive server messages:
```bash
curl -N http://localhost:3000/sse
```

Then, send requests to the message endpoint:
```bash
curl -X POST http://localhost:3000/message \
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
curl -X POST http://localhost:3000/message \
  -H "Content-Type": application/json" \
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
node server.js --transport=http --port=3001
```

### CORS Issues
The server has CORS enabled with `origin: '*'` for development. For production, configure appropriate CORS restrictions in `server.js`.

### Connection Issues
Make sure to:
1. Establish the SSE connection first (GET /sse)
2. Send requests to the message endpoint (POST /message)
3. Keep the SSE connection open to receive responses

## Notes

- **stdio** is the default transport to maintain compatibility with Cursor
- **HTTP/SSE** transport uses Server-Sent Events for server-to-client messages
- All transports share the same tools, resources, and capabilities
- Uses MCP SDK v1 (stable) - v2 packages are not yet available on npm
