# Message Flow Documentation

**Branch**: 001-voice-pc-control | **Date**: 2025-11-18
**Purpose**: Detailed message flow diagrams for WebSocket communication

## Connection Establishment Flow

```mermaid
sequenceDiagram
    participant A as Android App
    participant P as PC Server
    participant S as Setup Wizard

    Note over A,S: Device Pairing (One-time setup)
    A->>S: initiate_pairing(android_device_id, fingerprint)
    S->>A: pairing_id, 6-digit_code
    A->>P: confirm_pairing(pairing_id, code, pc_fingerprint)
    P->>A: authentication_token, pairing_completed

    Note over A,P: WebSocket Connection
    A->>P: WebSocket connect with mTLS
    A->>P: connection_request(auth_token, device_fingerprint)
    P->>A: connection_response(status: authenticated, session_id)

    Note over A,P: Connection Ready for Commands
```

## Voice Command Processing Flow

```mermaid
sequenceDiagram
    participant U as User
    participant A as Android App
    participant P as PC Server
    participant STT as Whisper.cpp
    participant LLM as Claude API
    participant MCP as MCP Tools

    Note over U,A: 1. Audio Capture
    U->>A: Speaks Turkish command
    A->>A: Capture audio (16kHz PCM)
    A->>A: Apply noise suppression

    Note over A,P: 2. Audio Streaming
    loop Audio chunks
        A->>P: audio_data(chunk, sequence_number)
        P->>P: Buffer audio chunks
    end
    A->>P: audio_data(final_chunk, is_final: true)

    Note over P: 3. Speech Recognition
    P->>STT: Process complete audio
    STT->>P: transcription, confidence

    Note over P: 4. Command Status Update
    P->>A: command_status(command_id, status: "işleniyor")

    Note over P,LLM: 5. Command Interpretation
    P->>LLM: Interpret command: "Chrome'u aç"
    LLM->>P: action_type: system_launch, parameters: {application_name: "Chrome"}

    Note over P: 6. Action Execution
    P->>A: command_status(command_id, status: "çalıştırılıyor")
    P->>MCP: Execute system_launch("Chrome")
    MCP->>P: execution_result: success

    Note over P,A: 7. Completion
    P->>A: action_execution(action_id, status: completed, result)
    P->>A: command_status(command_id, status: "tamamlandı")
    A->>U: Display "Tamamlandı" status
```

## Error Handling Flow

```mermaid
sequenceDiagram
    participant A as Android App
    participant P as PC Server
    participant LLM as Claude API
    participant U as User

    Note over A,P: LLM Service Unavailable
    A->>P: voice_command(transcription: "Notepad'i aç")
    P->>LLM: Interpret command
    LLM-->>P: Service unavailable (timeout)

    P->>P: Start 30-second retry timer
    loop Retry attempts (max 30s)
        P->>LLM: Retry interpretation
        alt Service available
            LLM->>P: Interpretation result
            P->>A: Continue normal flow
        else Service still unavailable
            P->>P: Wait 2 seconds, retry
        end
    end

    P->>A: error(error_code: llm_service_unavailable, retry_after: 30000)
    A->>U: Display "Komut yorumlama servisi kullanılamıyor. Lütfen tekrar deneyin."
```

## Wake-on-LAN Flow

```mermaid
sequenceDiagram
    participant A as Android App
    participant P as PC Server
    participant PC as Target PC
    participant U as User

    Note over U,A: User taps Quick Settings tile
    U->>A: Activate voice assistant
    A->>A: Check stored PC connection

    Note over A,PC: PC appears offline
    A->>P: wake_on_lan(mac_address, ip_address)
    P->>PC: Send WoL magic packet (UDP broadcast)

    Note over PC: PC wakes from sleep
    PC->>PC: Boot Windows
    PC->>PC: Start voice assistant service (15s timeout)

    Note over A,P: Connection attempt after wake
    A->>P: WebSocket connect
    P->>A: connection_response(status: authenticated)
    A->>U: Display "Bağlantı kuruldu"
    A->>U: Ready for voice commands
```

## File Deletion Confirmation Flow

```mermaid
sequenceDiagram
    participant U as User
    participant A as Android App
    participant P as PC Server
    participant FS as File System

    Note over U,A: User speaks deletion command
    U->>A: "Windows dizinindeki temp.log dosyasını sil"
    A->>P: voice_command(transcription)
    P->>P: Parse command, detect file path

    Note over P: System directory detection
    P->>P: Check if "C:\Windows\temp.log" is in protected directories
    P->>P: Yes - requires confirmation

    Note over P,A: Request user confirmation
    P->>A: action_execution(action: system_file_delete, status: requires_confirmation, parameters: {file_path: "C:\\Windows\\temp.log"})
    A->>U: Display confirmation: "temp.log Windows dizininden silinsin mi? Bu Windows işlemlerini etkileyebilir. Onayla: Evet/Hayır"

    Note over U,A: User confirms
    U->>A: Taps "Evet"
    A->>P: action_execution(action: system_file_delete, status: executing, parameters: {file_path: "C:\\Windows\\temp.log", confirmation: true})

    Note over P,FS: Execute deletion
    P->>FS: Delete file "C:\Windows\temp.log"
    FS->>P: Deletion successful

    Note over P,A: Report result
    P->>A: action_execution(action: system_file_delete, status: completed, result: {success: true})
    A->>U: Display "Dosya silindi"
```

## Browser Control Flow

```mermaid
sequenceDiagram
    participant U as User
    participant A as Android App
    participant P as PC Server
    participant LLM as Claude API
    participant C as Chrome DevTools

    Note over U,A: User speaks browser command
    U->>A: "YouTube'u aç"
    A->>P: voice_command(transcription: "YouTube'u aç")

    Note over P,LLM: Command interpretation
    P->>LLM: Interpret "YouTube'u aç"
    LLM->>P: action: browser_navigate, parameters: {url: "https://youtube.com"}

    Note over P,C: Browser automation
    P->>C: Launch Chrome if not running
    C->>P: Chrome ready
    P->>C: Navigate to youtube.com
    C->>P: Navigation successful

    Note over P,A: Report result
    P->>A: action_execution(action: browser_navigate, status: completed, result: {success: true, url: "https://youtube.com"})
    A->>U: Display "YouTube açıldı"
```

## Connection Recovery Flow

```mermaid
sequenceDiagram
    participant A as Android App
    participant P as PC Server
    participant N as Network

    Note over A,P: Active voice command session
    A->>P: voice_command("sesi yüzde 50'ye ayarla")
    P->>P: Processing command...

    Note over N: Network disruption occurs
    N-->>A: Connection lost
    N-->>P: Connection lost

    Note over A: Automatic reconnection
    A->>A: Detect connection loss
    A->>A: Start exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s
    loop Reconnection attempts
        A->>P: Attempt WebSocket connection
        alt Connection successful
            P->>A: connection_response(authenticated)
            A->>P: Resend any pending commands
            break
        else Connection failed
            A->>A: Wait backoff period, retry
        end
    end

    Note over A,U: Report to user
    A->>U: Show reconnection status and resume normal operation
```

## Audio Quality Management Flow

```mermaid
sequenceDiagram
    participant A as Android App
    participant P as PC Server
    participant U as User

    Note over A,P: Real-time audio streaming
    loop Audio chunks (20ms intervals)
        A->>A: Capture audio chunk
        A->>A: Measure network latency
        A->>A: Adjust compression bitrate (16-32kbps)
        A->>P: audio_data(chunk, sequence_number)
        P->>P: Check buffer levels
        P->>P: Detect audio quality issues
    end

    Note over P: Audio quality degradation detected
    P->>P: Buffer underrun detected
    P->>A: command_status(status: "Yavaş ağ tespit edildi. Sesli komutlar gecikebilir.")

    Note over A: Adaptive audio handling
    A->>A: Increase audio compression
    A->>A: Reduce frame size if needed
    A->>P: Continue streaming with adjusted parameters

    Note over P,U: Quality recovery
    P->>P: Buffer levels stabilized
    P->>A: command_status(status: "normal")
    A->>U: Display normal status if needed
```

## Session Management Flow

```mermaid
sequenceDiagram
    participant A as Android App
    participant P as PC Server
    participant S as Android System

    Note over A: Quick Settings tile activation
    U->>A: Tap Quick Settings tile
    A->>A: Start foreground service
    A->>S: Start foreground service with notification
    S->>A: Service started

    Note over A,P: Establish connection
    A->>P: Check stored PC connection
    alt PC online and authenticated
        A->>P: WebSocket connect
        P->>A: connection_response(authenticated)
        A->>U: Ready for voice commands (sesli asistan hazır)
    else PC offline
        A->>P: wake_on_lan
        Note over A,P: Follow Wake-on-LAN flow
    end

    Note over A: Service lifecycle management
    A->>A: Maintain connection with keepalive (30s intervals)
    A->>A: Handle screen lock/unlock events
    A->>A: Process voice commands in background

    Note over A: User ends session
    U->>A: Tap notification or Quick Settings again
    A->>P: WebSocket disconnect
    A->>A: Stop foreground service
    A->>S: Service stopped
```

## Message Type Reference

### Connection Messages
- `connection_request`: Authentication handshake
- `connection_response`: Authentication result

### Audio Messages
- `audio_data`: Real-time audio streaming
- `voice_command`: Processed transcription

### Status Messages
- `command_status`: Turkish status updates
- `action_execution`: Action execution details

### System Messages
- `wake_on_lan`: PC wake-up request
- `wake_on_lan_response`: Wake-up result

### Error Messages
- `error`: General error with Turkish message

## Message Timing Constraints

- **Audio chunk interval**: 20ms (50 chunks/second)
- **WebSocket heartbeat**: 30 seconds
- **Command timeout**: 30 seconds (including LLM retry)
- **Connection timeout**: 10 seconds
- **Reconnection backoff**: 1s, 2s, 4s, 8s, 16s, 30s max
- **PC wake timeout**: 15 seconds for service startup
- **Audio buffer limit**: 200ms maximum