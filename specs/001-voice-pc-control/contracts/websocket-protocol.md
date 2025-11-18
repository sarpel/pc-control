# WebSocket Protocol Contract: Voice-Controlled PC Assistant

**Feature**: 001-voice-pc-control
**Version**: 1.0.0
**Date**: 2025-11-18

## Overview

This document defines the WebSocket communication protocol between the Android app and Python Windows service. All communication uses a persistent WebSocket connection with mTLS encryption.

## Connection Establishment

### Endpoint
```
wss://<PC_IP>:8443/voice-assistant
```

### Authentication
- **Protocol**: mTLS with certificate pinning
- **Client Certificate**: Required, issued during pairing
- **CA Certificate**: Self-signed, pinned in Android app
- **Bearer Token**: Sent in first message after WebSocket handshake

### Handshake Sequence
1. Android initiates WebSocket connection with mTLS client certificate
2. Python validates client certificate against trusted store
3. Android sends `auth` message with bearer token
4. Python validates token and responds with `auth_success` or `auth_failed`
5. Connection ready for voice command streaming

## Message Types

### 1. Authentication Messages

#### `auth` (Android ’ Python)
```json
{
  "type": "auth",
  "version": "1.0.0",
  "token": "<bearer_token>",
  "deviceId": "<android_device_id>",
  "timestamp": "2025-11-18T15:30:00Z"
}
```

#### `auth_success` (Python ’ Android)
```json
{
  "type": "auth_success",
  "sessionId": "<uuid>",
  "serverVersion": "1.0.0",
  "capabilities": ["wol", "system_ops", "browser_ops"],
  "timestamp": "2025-11-18T15:30:00.500Z"
}
```

#### `auth_failed` (Python ’ Android)
```json
{
  "type": "auth_failed",
  "errorCode": "TOKEN_EXPIRED",
  "message": "Token süresi dolmu_. Lütfen yeniden e_leyin.",
  "timestamp": "2025-11-18T15:30:00.500Z"
}
```

---

### 2. Audio Streaming Messages

#### `audio_start` (Android ’ Python)
```json
{
  "type": "audio_start",
  "sessionId": "<uuid>",
  "commandId": "<uuid>",
  "audioFormat": {
    "codec": "opus",
    "sampleRate": 16000,
    "channels": 1,
    "bitrate": 24000
  },
  "timestamp": "2025-11-18T15:30:45Z"
}
```

#### `audio_frame` (Binary Message: Android ’ Python)
**Format**: Binary WebSocket frame
```
| 16 bytes (UUID commandId) | 8 bytes (sequence number) | N bytes (Opus audio data) |
```

**Fields**:
- `commandId`: UUID of voice command (for frame ordering)
- `sequence`: Monotonic counter starting from 0
- `audio`: Opus-encoded audio frame (20ms = 480 samples @ 16kHz)

#### `audio_end` (Android ’ Python)
```json
{
  "type": "audio_end",
  "commandId": "<uuid>",
  "totalFrames": 60,
  "durationMs": 1200,
  "timestamp": "2025-11-18T15:30:46.200Z"
}
```

---

### 3. Command Processing Messages

#### `processing_status` (Python ’ Android)
```json
{
  "type": "processing_status",
  "commandId": "<uuid>",
  "stage": "transcription" | "interpretation" | "execution",
  "progress": 0.5,
  "message": "0_leniyor...",
  "timestamp": "2025-11-18T15:30:46.500Z"
}
```

#### `transcription_complete` (Python ’ Android)
```json
{
  "type": "transcription_complete",
  "commandId": "<uuid>",
  "text": "Chrome'u aç",
  "confidence": 0.94,
  "language": "tr-TR",
  "timestamp": "2025-11-18T15:30:47Z"
}
```

#### `action_interpretation` (Python ’ Android)
```json
{
  "type": "action_interpretation",
  "commandId": "<uuid>",
  "action": {
    "actionType": "browser",
    "operation": "navigate_url",
    "parameters": {"url": "https://youtube.com"},
    "requiresConfirmation": false
  },
  "timestamp": "2025-11-18T15:30:47.500Z"
}
```

#### `confirmation_required` (Python ’ Android)
```json
{
  "type": "confirmation_required",
  "commandId": "<uuid>",
  "action": {
    "operation": "delete_file",
    "parameters": {"path": "C:\\Windows\\System32\\test.dll"}
  },
  "message": "test.dll dosyas1 sistem dizininden silinsin mi? Bu Windows i_lemlerini etkileyebilir.",
  "confirmOptions": ["Evet", "Hay1r"],
  "timestamp": "2025-11-18T15:30:47.500Z"
}
```

#### `confirmation_response` (Android ’ Python)
```json
{
  "type": "confirmation_response",
  "commandId": "<uuid>",
  "confirmed": true | false,
  "timestamp": "2025-11-18T15:30:50Z"
}
```

#### `command_complete` (Python ’ Android)
```json
{
  "type": "command_complete",
  "commandId": "<uuid>",
  "status": "success" | "failed" | "cancelled",
  "result": {
    "message": "Tamamland1",
    "details": "Chrome ba_lat1ld1"
  },
  "executionTimeMs": 850,
  "timestamp": "2025-11-18T15:30:48Z"
}
```

#### `command_error` (Python ’ Android)
```json
{
  "type": "command_error",
  "commandId": "<uuid>",
  "errorCode": "EXECUTION_FAILED",
  "message": "Chrome ba_lat1lamad1. Uygulama yüklü mü?",
  "retryable": true,
  "timestamp": "2025-11-18T15:30:48Z"
}
```

---

### 4. Connection Management Messages

#### `ping` (Bidirectional)
```json
{
  "type": "ping",
  "timestamp": "2025-11-18T15:30:50Z"
}
```

#### `pong` (Bidirectional)
```json
{
  "type": "pong",
  "timestamp": "2025-11-18T15:30:50.050Z"
}
```

#### `health_check` (Android ’ Python)
```json
{
  "type": "health_check",
  "timestamp": "2025-11-18T15:30:50Z"
}
```

#### `health_response` (Python ’ Android)
```json
{
  "type": "health_response",
  "status": "healthy",
  "services": {
    "whisper": "ready",
    "llm": "ready",
    "mcp": "ready"
  },
  "latencyMs": 45,
  "timestamp": "2025-11-18T15:30:50.045Z"
}
```

#### `disconnect` (Bidirectional)
```json
{
  "type": "disconnect",
  "reason": "USER_INITIATED" | "TIMEOUT" | "ERROR",
  "message": "Balant1 kapat1ld1",
  "timestamp": "2025-11-18T16:00:00Z"
}
```

---

### 5. Wake-on-LAN Messages

#### `wake_pc` (Android ’ Python - sent to LAN broadcast if PC disconnected)
**Note**: Sent as UDP packet, not over WebSocket
```
Magic packet format (standard WoL): FF FF FF FF FF FF + (MAC address * 16)
```

#### `pc_wake_status` (Python ’ Android)
```json
{
  "type": "pc_wake_status",
  "status": "waking" | "awake" | "timeout",
  "message": "PC uyan1yor...",
  "elapsedMs": 5000,
  "timestamp": "2025-11-18T15:30:05Z"
}
```

---

## Error Codes

### Authentication Errors (1xxx)
- `1001`: `TOKEN_EXPIRED` - Auth token expired (24-hour limit)
- `1002`: `INVALID_CERTIFICATE` - Client certificate invalid or revoked
- `1003`: `DEVICE_NOT_PAIRED` - Device not in trusted list
- `1004`: `MAX_CONNECTIONS` - Another device already connected

### Audio Errors (2xxx)
- `2001`: `INVALID_AUDIO_FORMAT` - Audio format not supported
- `2002`: `AUDIO_PROCESSING_FAILED` - STT processing error
- `2003`: `CONFIDENCE_TOO_LOW` - STT confidence below threshold (0.60)
- `2004`: `AUDIO_TIMEOUT` - No audio received within expected window

### LLM Errors (3xxx)
- `3001`: `LLM_UNAVAILABLE` - Claude API unreachable (retry for 30s)
- `3002`: `INTERPRETATION_FAILED` - Cannot parse command intent
- `3003`: `AMBIGUOUS_COMMAND` - Command unclear, needs clarification
- `3004`: `RATE_LIMIT` - API rate limit exceeded

### Execution Errors (4xxx)
- `4001`: `EXECUTION_FAILED` - Action execution failed on PC
- `4002`: `APP_NOT_FOUND` - Requested application not installed
- `4003`: `FILE_NOT_FOUND` - Requested file does not exist
- `4004`: `PERMISSION_DENIED` - Insufficient permissions for operation
- `4005`: `OPERATION_TIMEOUT` - Execution exceeded 30-second timeout

### Network Errors (5xxx)
- `5001`: `DISCONNECTED` - WebSocket connection lost
- `5002`: `HIGH_LATENCY` - Latency >500ms (warning threshold)
- `5003`: `HEARTBEAT_TIMEOUT` - No heartbeat for 60 seconds

---

## Protocol Constraints

### Latency Requirements
- **Heartbeat interval**: 10 seconds
- **Heartbeat timeout**: 60 seconds (3 missed heartbeats)
- **Command execution timeout**: 30 seconds
- **LLM retry window**: 30 seconds with exponential backoff

### Message Size Limits
- **JSON messages**: 10 KB max
- **Audio frames**: 2 KB max (20ms Opus frame @ 24kbps)
- **Binary frame header**: 24 bytes fixed

### State Management
- **Connection state**: tracked per session
- **Command state**: tracked per `commandId`
- **Frame ordering**: enforced via sequence numbers
- **Reconnection**: automatic with exponential backoff (100ms ’ 30s)

### Security Constraints
- **mTLS required**: No plain WebSocket connections
- **Certificate pinning**: Android pins PC's CA certificate
- **Token rotation**: Before 24-hour expiration
- **Session timeout**: 1 hour of inactivity

---

## Message Flow Examples

### Successful Voice Command
```
Android ’ Python: auth (with token)
Python ’ Android: auth_success

Android ’ Python: audio_start
Android ’ Python: audio_frame (binary) × 60
Android ’ Python: audio_end
Python ’ Android: processing_status (transcription)
Python ’ Android: transcription_complete
Python ’ Android: processing_status (interpretation)
Python ’ Android: action_interpretation
Python ’ Android: processing_status (execution)
Python ’ Android: command_complete
```

### Command with Confirmation
```
Android ’ Python: audio_start ’ frames ’ audio_end
Python ’ Android: transcription_complete
Python ’ Android: confirmation_required
Android ’ Python: confirmation_response (confirmed=true)
Python ’ Android: command_complete
```

### LLM Unavailable Scenario
```
Android ’ Python: audio_start ’ frames ’ audio_end
Python ’ Android: transcription_complete
Python ’ Android: processing_status (interpretation, retrying...)
[30 seconds elapse with retries]
Python ’ Android: command_error (LLM_UNAVAILABLE)
```

### PC Wake and Command
```
[PC is sleeping, WebSocket disconnected]
Android ’ LAN: wake_pc (UDP broadcast)
[Wait up to 15 seconds]
Android ’ Python: WebSocket connection attempt
Python ’ Android: pc_wake_status (awake)
Android ’ Python: auth
Python ’ Android: auth_success
[Proceed with normal command flow]
```

---

## Versioning and Compatibility

### Protocol Version
- **Current**: 1.0.0
- **Negotiation**: Android sends version in `auth`, Python responds with server version
- **Compatibility**: Versions with same MAJOR number are compatible

### Backward Compatibility Rules
- **MAJOR**: Breaking changes (incompatible message formats)
- **MINOR**: New message types or optional fields
- **PATCH**: Bug fixes, no protocol changes

### Deprecation Policy
- **Notice Period**: 6 months for deprecated message types
- **Migration Path**: Both old and new formats supported during transition
- **End-of-Life**: Remove deprecated formats after 1 year

---

## Testing Requirements

### Contract Tests
- Verify all message schemas with JSON Schema validation
- Test binary frame parsing (header + payload)
- Validate error code coverage
- Test authentication flows (success, expired, invalid)

### Integration Tests
- End-to-end command execution (audio ’ action ’ result)
- Reconnection scenarios (network drop, timeout)
- Concurrent command handling
- Wake-on-LAN with service startup delay

### Performance Tests
- Latency measurement (p50, p95, p99)
- Message throughput (frames per second)
- Connection stability (1-hour session)
- Memory usage (audio buffer management)

---

## Summary

This WebSocket protocol contract defines:
-  Authentication and session management
-  Binary audio streaming with Opus compression
-  Command processing pipeline (transcription ’ interpretation ’ execution)
-  Confirmation prompts for destructive operations
-  Connection health monitoring and reconnection
-  Wake-on-LAN integration
-  Comprehensive error handling with Turkish messages
-  Security via mTLS and token authentication