# API Documentation

## Overview

The PC Voice Control system provides REST and WebSocket APIs for voice-controlled PC operations.

## Base URLs

- **REST API**: `https://localhost:8443/api/v1`
- **WebSocket**: `wss://localhost:8443/voice-assistant`

## Authentication

All API requests require mTLS authentication with client certificates generated during device pairing.

```http
POST /api/v1/pairing/init
Content-Type: application/json

{
  "device_id": "android-device-123",
  "device_name": "Samsung Galaxy S21"
}
```

## REST API Endpoints

### System Operations

#### Get System Information
```http
GET /api/v1/system/info
Authorization: Bearer {token}

Response:
{
  "status": "success",
  "system_info": {
    "cpu": {"usage": 45.2, "cores": 8},
    "memory": {"total_gb": 16, "available_gb": 8.5},
    "disk": {"total_gb": 512, "free_gb": 256},
    "platform": "Windows 10"
  }
}
```

#### Find Files
```http
POST /api/v1/system/find-files
Authorization: Bearer {token}
Content-Type: application/json

{
  "query": "*.pdf",
  "path": "C:/Users/Documents",
  "max_results": 10
}

Response:
{
  "status": "success",
  "files": [
    {"path": "C:/Users/Documents/report.pdf", "size_bytes": 1024000},
    {"path": "C:/Users/Documents/invoice.pdf", "size_bytes": 512000}
  ]
}
```

#### Delete File
```http
DELETE /api/v1/system/file
Authorization: Bearer {token}
Content-Type: application/json

{
  "file_path": "C:/Users/Downloads/temp.txt",
  "confirmed": true
}

Response:
{
  "status": "success",
  "message": "Dosya silindi (File deleted)"
}
```

### Browser Operations

#### Navigate to URL
```http
POST /api/v1/browser/navigate
Authorization: Bearer {token}
Content-Type: application/json

{
  "url": "https://www.example.com",
  "wait_until": "load"
}

Response:
{
  "status": "success",
  "navigation_id": "nav-123",
  "url": "https://www.example.com"
}
```

#### Web Search
```http
POST /api/v1/browser/search
Authorization: Bearer {token}
Content-Type: application/json

{
  "query": "weather forecast",
  "search_engine": "google"
}

Response:
{
  "status": "success",
  "search_url": "https://www.google.com/search?q=weather+forecast"
}
```

#### Extract Page Content
```http
POST /api/v1/browser/extract
Authorization: Bearer {token}
Content-Type: application/json

{
  "url": "https://www.example.com",
  "extract_type": "text"
}

Response:
{
  "status": "success",
  "content": "Example Domain. This domain is for use in illustrative examples..."
}
```

## WebSocket Protocol

### Connection
```javascript
const ws = new WebSocket('wss://localhost:8443/voice-assistant', {
  cert: clientCert,
  key: clientKey,
  ca: caCert
});
```

### Message Types

#### Audio Streaming
```json
{
  "type": "audio_chunk",
  "data": "<base64-encoded-opus-frame>",
  "sequence": 123,
  "timestamp_ms": 1234567890
}
```

#### Command Result
```json
{
  "type": "command_result",
  "command_id": "cmd-456",
  "status": "success",
  "action": "Chrome'u açtım",
  "execution_time_ms": 1500
}
```

#### Error Response
```json
{
  "type": "error",
  "code": 4001,
  "message": "Bağlantı zaman aşımına uğradı (Connection timeout)",
  "details": {}
}
```

## Error Codes

| Code | Description |
|------|-------------|
| 1000 | Normal closure |
| 4001 | Authentication failed |
| 4002 | Invalid message format |
| 4003 | Rate limit exceeded |
| 5000 | Internal server error |

## Rate Limits

- **API Requests**: 100 requests/minute per device
- **WebSocket Messages**: 60 messages/minute
- **Audio Streaming**: Continuous (no limit)

## Examples

### Complete Voice Command Flow

```python
# 1. Connect WebSocket
ws = await websocket.connect('wss://localhost:8443/voice-assistant')

# 2. Stream audio
for audio_chunk in capture_audio():
    await ws.send_bytes(audio_chunk)

# 3. Receive transcription
transcription = await ws.receive_json()
# {"type": "transcription", "text": "Chrome'u aç", "confidence": 0.95}

# 4. Receive command result
result = await ws.receive_json()
# {"type": "command_result", "status": "success", "action": "Chrome açıldı"}
```

## SDK Examples

### Python Client
```python
from pc_control_client import PCControlClient

client = PCControlClient(
    host='192.168.1.100',
    port=8443,
    cert_path='client.crt',
    key_path='client.key'
)

# Execute voice command
result = await client.execute_command("Chrome'u aç")
print(result.status)  # "success"
```

### Android (Kotlin)
```kotlin
val client = PCControlClient(
    host = "192.168.1.100",
    port = 8443,
    context = applicationContext
)

// Stream audio
audioCapture.startCapture { audioData ->
    client.sendAudio(audioData)
}

// Handle results
client.onCommandResult { result ->
    updateUI(result.action)
}
```

## WebSocket Events

| Event | Direction | Description |
|-------|-----------|-------------|
| `audio_chunk` | Client → Server | Opus-encoded audio frame |
| `transcription` | Server → Client | STT transcription result |
| `command_processing` | Server → Client | Command interpretation status |
| `command_result` | Server → Client | Execution result |
| `error` | Server → Client | Error notification |
| `ping`/`pong` | Bidirectional | Connection health check |

## Security

- **mTLS Required**: All connections must use mutual TLS
- **Certificate Rotation**: Certificates expire after 90 days
- **Token Expiration**: Bearer tokens expire after 24 hours
- **Input Validation**: All inputs are sanitized and validated

## Support

- **Spec**: `/specs/001-voice-pc-control/spec.md`
- **Contracts**: `/specs/001-voice-pc-control/contracts/`
- **Quickstart**: `/specs/001-voice-pc-control/quickstart.md`
