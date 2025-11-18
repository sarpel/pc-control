# WebSocket API Documentation
## Voice-Controlled PC Assistant

**Version**: 1.0.0
**WebSocket URL**: `wss://<pc-ip>:8443/ws/voice`
**Protocol**: WSS with mTLS

---

## Table of Contents

1. [Connection](#connection)
2. [Message Format](#message-format)
3. [Message Types](#message-types)
4. [Voice Command Flow](#voice-command-flow)
5. [Error Handling](#error-handling)
6. [Examples](#examples)

---

## Connection

### Establishing Connection

```javascript
const ws = new WebSocket('wss://192.168.1.100:8443/ws/voice', {
  cert: clientCertificate,
  key: clientPrivateKey,
  ca: caCertificate,
  headers: {
    'Authorization': 'Bearer ' + authToken,
    'X-Device-ID': deviceId
  }
});
```

### Connection Lifecycle

1. **Handshake**: Initial authentication with mTLS + Bearer token
2. **Ready**: Server sends `connection_ready` message
3. **Active**: Voice command streaming and execution
4. **Heartbeat**: Ping/pong every 30 seconds
5. **Close**: Graceful disconnection or timeout

### Connection States

| State | Description |
|-------|-------------|
| `CONNECTING` | Establishing WebSocket connection |
| `OPEN` | Connection established and authenticated |
| `STREAMING` | Audio streaming in progress |
| `PROCESSING` | Command being processed |
| `CLOSING` | Connection closing gracefully |
| `CLOSED` | Connection closed |

---

## Message Format

All messages use JSON format with the following structure:

```json
{
  "type": "message_type",
  "id": "unique-message-id",
  "timestamp": "2025-11-18T15:30:45.123Z",
  "payload": {}
}
```

### Binary Messages

Audio data is sent as binary frames with the following structure:

```
[Header: 8 bytes][Audio Data: N bytes]

Header Format:
- Bytes 0-3: Sequence number (uint32, big-endian)
- Bytes 4-7: Payload length (uint32, big-endian)
```

---

## Message Types

### Client → Server

#### 1. Audio Frame

Binary message containing Opus-encoded audio.

**Format**: Binary
**Frequency**: Real-time during voice command

**Header**:
```
Sequence: uint32 (incremental)
Length: uint32 (audio data size)
```

**Payload**: Opus-encoded audio (16kHz, mono)

#### 2. Start Command

Signal the start of a voice command.

```json
{
  "type": "start_command",
  "id": "cmd-uuid",
  "timestamp": "2025-11-18T15:30:45Z",
  "payload": {
    "language": "tr-TR"
  }
}
```

#### 3. End Command

Signal the end of a voice command.

```json
{
  "type": "end_command",
  "id": "cmd-uuid",
  "timestamp": "2025-11-18T15:30:46Z",
  "payload": {
    "duration_ms": 1200
  }
}
```

#### 4. Wake PC

Request PC wake from sleep.

```json
{
  "type": "wake_pc",
  "id": "wake-uuid",
  "timestamp": "2025-11-18T15:30:45Z",
  "payload": {
    "mac_address": "AA:BB:CC:DD:EE:FF"
  }
}
```

#### 5. Heartbeat

Keep-alive ping message.

```json
{
  "type": "ping",
  "id": "ping-uuid",
  "timestamp": "2025-11-18T15:30:45Z",
  "payload": {}
}
```

#### 6. Cancel Command

Cancel an in-progress command.

```json
{
  "type": "cancel_command",
  "id": "cancel-uuid",
  "timestamp": "2025-11-18T15:30:47Z",
  "payload": {
    "command_id": "cmd-uuid",
    "reason": "user_cancelled"
  }
}
```

### Server → Client

#### 1. Connection Ready

Connection established successfully.

```json
{
  "type": "connection_ready",
  "id": "ready-uuid",
  "timestamp": "2025-11-18T15:30:45Z",
  "payload": {
    "server_version": "1.0.0",
    "max_audio_rate": 16000,
    "supported_codecs": ["opus"],
    "connection_id": "conn-uuid"
  }
}
```

#### 2. Transcription

STT transcription result.

```json
{
  "type": "transcription",
  "id": "trans-uuid",
  "timestamp": "2025-11-18T15:30:46Z",
  "payload": {
    "command_id": "cmd-uuid",
    "text": "Chrome'u aç",
    "confidence": 0.94,
    "language": "tr-TR"
  }
}
```

#### 3. Command Interpretation

Interpreted command with action.

```json
{
  "type": "command_interpretation",
  "id": "interp-uuid",
  "timestamp": "2025-11-18T15:30:47Z",
  "payload": {
    "command_id": "cmd-uuid",
    "action_type": "system_launch",
    "parameters": {
      "executable_path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
      "arguments": []
    },
    "requires_confirmation": false
  }
}
```

#### 4. Command Status

Command execution status update.

```json
{
  "type": "command_status",
  "id": "status-uuid",
  "timestamp": "2025-11-18T15:30:48Z",
  "payload": {
    "command_id": "cmd-uuid",
    "status": "executing",
    "progress": 50,
    "message": "Uygulama başlatılıyor..."
  }
}
```

**Status Values**:
- `listening`: Capturing audio
- `processing`: STT in progress
- `interpreting`: LLM interpretation
- `executing`: Command execution
- `completed`: Successfully completed
- `failed`: Execution failed

#### 5. Command Result

Final command execution result.

```json
{
  "type": "command_result",
  "id": "result-uuid",
  "timestamp": "2025-11-18T15:30:49Z",
  "payload": {
    "command_id": "cmd-uuid",
    "success": true,
    "execution_time_ms": 1234,
    "result": {
      "action": "system_launch",
      "details": "Chrome başlatıldı"
    }
  }
}
```

#### 6. Confirmation Request

Request user confirmation for destructive operation.

```json
{
  "type": "confirmation_request",
  "id": "confirm-uuid",
  "timestamp": "2025-11-18T15:30:47Z",
  "payload": {
    "command_id": "cmd-uuid",
    "action": "file_delete",
    "message": "Dosyayı silmek istediğinizden emin misiniz?",
    "details": {
      "file_path": "C:\\Users\\Documents\\temp.txt",
      "file_size": 1024
    }
  }
}
```

Client response:
```json
{
  "type": "confirmation_response",
  "id": "confirm-resp-uuid",
  "timestamp": "2025-11-18T15:30:50Z",
  "payload": {
    "command_id": "cmd-uuid",
    "confirmed": true
  }
}
```

#### 7. Error

Error occurred during processing.

```json
{
  "type": "error",
  "id": "error-uuid",
  "timestamp": "2025-11-18T15:30:48Z",
  "payload": {
    "command_id": "cmd-uuid",
    "error_code": "stt_failed",
    "message": "Ses tanıma başarısız oldu",
    "details": "Confidence too low: 0.45",
    "recoverable": true
  }
}
```

#### 8. Heartbeat Response

Pong response to ping.

```json
{
  "type": "pong",
  "id": "pong-uuid",
  "timestamp": "2025-11-18T15:30:45Z",
  "payload": {
    "latency_ms": 45
  }
}
```

#### 9. Browser Content

Page content extracted from browser.

```json
{
  "type": "browser_content",
  "id": "content-uuid",
  "timestamp": "2025-11-18T15:31:00Z",
  "payload": {
    "command_id": "cmd-uuid",
    "page_title": "Weather Forecast",
    "page_url": "https://weather.com",
    "extracted_content": "Today's forecast: Sunny, 25°C...",
    "extraction_type": "summary"
  }
}
```

#### 10. System Information

System information response.

```json
{
  "type": "system_info",
  "id": "sysinfo-uuid",
  "timestamp": "2025-11-18T15:31:05Z",
  "payload": {
    "command_id": "cmd-uuid",
    "os_name": "Windows 11",
    "os_version": "22H2",
    "cpu_usage": 45,
    "memory_usage": 62,
    "disk_usage": 78
  }
}
```

---

## Voice Command Flow

### Complete Flow Diagram

```
Android                PC Agent
   |                      |
   |---- start_command -->|
   |                      |
   |---- audio_frame ---->|
   |---- audio_frame ---->|
   |---- audio_frame ---->|
   |                      |
   |---- end_command ---->|
   |                      |
   |<-- transcription ----|
   |                      | [STT Processing]
   |                      |
   |<-- command_interp ---|
   |                      | [LLM Processing]
   |                      |
   |<-- command_status ---|
   |     (executing)      | [Action Execution]
   |                      |
   |<-- command_result ---|
   |     (completed)      |
   |                      |
```

### Example Flow (Browser Search)

1. **User speaks**: "hava durumu ara"

2. **Android sends**:
   ```json
   {"type": "start_command", "id": "cmd-123"}
   [Binary audio frames...]
   {"type": "end_command", "id": "cmd-123"}
   ```

3. **PC responds with transcription**:
   ```json
   {
     "type": "transcription",
     "payload": {"text": "hava durumu ara", "confidence": 0.96}
   }
   ```

4. **PC sends interpretation**:
   ```json
   {
     "type": "command_interpretation",
     "payload": {
       "action_type": "browser_search",
       "parameters": {"search_query": "hava durumu", "search_engine": "google"}
     }
   }
   ```

5. **PC sends status updates**:
   ```json
   {"type": "command_status", "payload": {"status": "executing"}}
   ```

6. **PC sends result**:
   ```json
   {
     "type": "command_result",
     "payload": {"success": true, "result": {...}}
   }
   ```

7. **PC sends extracted content**:
   ```json
   {
     "type": "browser_content",
     "payload": {"extracted_content": "Weather summary..."}
   }
   ```

---

## Error Handling

### Error Codes

| Code | Description | Recoverable |
|------|-------------|-------------|
| `auth_failed` | Authentication failed | No |
| `connection_timeout` | Connection timeout | Yes |
| `stt_failed` | Speech recognition failed | Yes |
| `llm_unavailable` | LLM API unavailable | Yes |
| `command_invalid` | Command could not be interpreted | No |
| `execution_failed` | Command execution failed | Depends |
| `rate_limit_exceeded` | Too many requests | Yes |
| `unsupported_action` | Action type not supported | No |

### Error Recovery

```javascript
ws.on('message', (data) => {
  const message = JSON.parse(data);

  if (message.type === 'error') {
    const { error_code, recoverable, command_id } = message.payload;

    if (recoverable) {
      // Retry after delay
      setTimeout(() => retryCommand(command_id), 2000);
    } else {
      // Show error to user
      showError(message.payload.message);
    }
  }
});
```

### Connection Recovery

```javascript
ws.on('close', (code, reason) => {
  console.log(`Connection closed: ${code} - ${reason}`);

  if (code === 1006) { // Abnormal closure
    // Attempt reconnection with exponential backoff
    reconnectWithBackoff();
  }
});

function reconnectWithBackoff() {
  let delay = 1000;
  const maxDelay = 30000;

  function attemptReconnect() {
    connect()
      .then(() => {
        console.log('Reconnected successfully');
        delay = 1000; // Reset delay
      })
      .catch(() => {
        console.log(`Reconnect failed, retrying in ${delay}ms`);
        setTimeout(attemptReconnect, delay);
        delay = Math.min(delay * 2, maxDelay);
      });
  }

  attemptReconnect();
}
```

---

## Examples

### Complete Voice Command (Kotlin)

```kotlin
class VoiceCommandSession(private val webSocket: WebSocket) {

    fun sendVoiceCommand(audioData: ByteArray) {
        // 1. Start command
        val startMessage = JSONObject().apply {
            put("type", "start_command")
            put("id", UUID.randomUUID().toString())
            put("timestamp", Instant.now().toString())
            put("payload", JSONObject().put("language", "tr-TR"))
        }
        webSocket.send(startMessage.toString())

        // 2. Stream audio
        audioData.chunked(1024).forEachIndexed { index, chunk ->
            val header = ByteBuffer.allocate(8)
            header.putInt(index) // Sequence number
            header.putInt(chunk.size) // Payload length

            val frame = ByteBuffer.allocate(8 + chunk.size)
            frame.put(header.array())
            frame.put(chunk.toByteArray())

            webSocket.send(frame.array())
        }

        // 3. End command
        val endMessage = JSONObject().apply {
            put("type", "end_command")
            put("id", UUID.randomUUID().toString())
            put("timestamp", Instant.now().toString())
            put("payload", JSONObject().put("duration_ms", audioData.size / 32))
        }
        webSocket.send(endMessage.toString())
    }
}
```

### Message Handling (Kotlin)

```kotlin
webSocket.addListener(object : WebSocketListener() {
    override fun onMessage(webSocket: WebSocket, text: String) {
        val message = JSONObject(text)

        when (message.getString("type")) {
            "transcription" -> handleTranscription(message)
            "command_interpretation" -> handleInterpretation(message)
            "command_status" -> handleStatus(message)
            "command_result" -> handleResult(message)
            "confirmation_request" -> handleConfirmation(message)
            "error" -> handleError(message)
            "browser_content" -> handleBrowserContent(message)
        }
    }

    override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
        // Binary message (not expected from server)
        Log.w(TAG, "Unexpected binary message from server")
    }
})
```

---

## Best Practices

### Connection Management

1. **Heartbeat**: Send ping every 30 seconds
2. **Reconnection**: Implement exponential backoff
3. **Graceful Shutdown**: Send close frame before disconnecting
4. **Error Handling**: Handle all error types appropriately

### Audio Streaming

1. **Buffer Size**: Use 1024-byte chunks for audio
2. **Sequence Numbers**: Always increment sequence numbers
3. **Error Detection**: Monitor for dropped frames
4. **Compression**: Use Opus codec at 16kHz

### Performance

1. **Batching**: Don't send messages too frequently
2. **Throttling**: Respect rate limits
3. **Latency**: Monitor round-trip times
4. **Cleanup**: Close connections when not in use

---

## Security

### Authentication

- mTLS certificate required
- Bearer token in header
- Device ID verification

### Data Protection

- All messages encrypted (WSS)
- Audio never persisted
- End-to-end encryption (mTLS)

### Audit Logging

All WebSocket events are logged:
- Connection attempts
- Authentication results
- Command executions
- Errors and exceptions

---

**Last Updated**: 2025-11-18
**API Version**: 1.0.0
