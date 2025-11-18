# AI-Powered Voice Assistant System: Production Specification

## Role & Objectives

You are the **Lead Architect and Implementation Engineer** for a production-grade AI voice assistant system. You are responsible for the complete end-to-end design, implementation, testing, and documentation of both components:

1. **Android Controller App** (Native Kotlin)
2. **Python Desktop Agent** (Windows PC)

**Primary Objective**: Deliver a reliable, secure, and performant voice-to-action pipeline that enables hands-free control of a Windows PC through natural language commands processed by local STT and remote LLM inference.

**Critical Success Factors**:
- Production-ready code following the ELITE CODING AGENT PROTOCOL
- Comprehensive testing (minimum 80% coverage)
- Security-first design with encryption and authentication
- Performance targets met (<2s end-to-end latency)
- Complete documentation and deployment packages

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERACTION                         │
│  Quick Settings Tile / In-App Button → Voice Command            │
└─────────────────┬───────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ANDROID CONTROLLER APP                        │
│  • Wake-on-LAN → PC Activation                                  │
│  • Audio Capture (16kHz PCM + Noise Suppression)                │
│  • Opus Codec Compression                                       │
│  • WebSocket Streaming → Python Agent                           │
└─────────────────┬───────────────────────────────────────────────┘
                  │ mTLS Encrypted Connection
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PYTHON DESKTOP AGENT                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  1. WebSocket Server (FastAPI) + Audio Reception          │  │
│  │  2. Voice Activity Detection (VAD) → Segmentation         │  │
│  │  3. Whisper.cpp → Speech-to-Text (Local)                  │  │
│  │  4. Claude LLM → Command Interpretation (Remote/CLI)      │  │
│  │  5. MCP Tool Router → Action Execution:                   │  │
│  │     ├─ Windows MCP (System Operations)                    │  │
│  │     └─ Chrome DevTools MCP (Browser Automation)           │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────┬───────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ACTIONS & FEEDBACK                            │
│  • System Operations (Volume, Apps, Files)                      │
│  • Browser Automation (Navigation, DOM, Forms)                  │
│  • Status Notifications (Android Push / Windows Toast)          │
│  • Optional TTS Feedback                                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Android Controller App: Technical Specification

### Technology Stack
```yaml
Language: Kotlin
Min SDK: 30 (Android 11)
Target SDK: 34+ (Android 14+)
Architecture: MVVM (Model-View-ViewModel)
UI Framework: Jetpack Compose with Material You theming
Background: WorkManager + Foreground Service
Build Tool: Gradle with Kotlin DSL
```

### Core Features

#### 1. Activation Methods
- **Quick Settings Tile** (Primary)
  - One-tap activation from notification shade
  - Visual state indicators (idle/listening/processing)
  - Immediate feedback via pulse animation
  
- **In-App Button** (Secondary)
  - Floating Action Button (FAB) in main UI
  - Consistent behavior with Quick Settings tile
  - Status dashboard showing connection state

#### 2. PC Wake & Connection Management
```kotlin
// Implementation Requirements:
1. Wake-on-LAN packet transmission:
   - Target: PC MAC address (user-configurable)
   - UDP port 9 (standard WoL port)
   - Magic packet format: FF FF FF FF FF FF + [MAC × 16]

2. Health Check Protocol:
   - HTTP GET request to http://{PC_IP}:8765/status
   - Retry logic: 3 attempts with 2s exponential backoff
   - Timeout: 10s total wait before failure notification

3. Connection States:
   - IDLE: PC sleeping, no active connection
   - WAKING: WoL sent, awaiting PC response
   - CONNECTED: WebSocket established, ready to stream
   - LISTENING: Actively capturing and streaming audio
   - PROCESSING: Audio sent, awaiting LLM response
   - ERROR: Connection failed, retry available
```

#### 3. Voice Capture & Streaming

**Primary Implementation: Built-in Streaming**
```kotlin
Audio Specifications:
  - Sample Rate: 16000 Hz (16kHz)
  - Channels: Mono (1 channel)
  - Encoding: PCM 16-bit signed integer
  - Compression: Opus codec (bitrate: 24kbps, VBR enabled)
  - Buffer Size: 160ms chunks (2560 bytes per chunk)

Features Required:
  - Automatic Gain Control (AGC): Enabled
  - Noise Suppression: Android AcousticEchoCanceler + NoiseSuppressor
  - Voice Activity Detection (Client-side): Optional, for UI feedback
  - Stream Pause/Resume: Manual control via button tap
  
Protocol:
  - Transport: WebSocket (wss:// for encrypted connection)
  - Message Format: Binary frames containing Opus-encoded audio
  - Heartbeat: Ping every 30s to keep connection alive
```

**Fallback Implementation: External App Integration**
```yaml
Supported Apps:
  - WoMic (Wireless Microphone)
  - RTPMic (Real-Time Protocol Microphone)

Configuration Required:
  - Document exact connection parameters (IP, port, protocol)
  - Provide in-app toggle: "Use External Mic App"
  - Auto-detect when external app is streaming
  - Python agent must support both native and external sources
```

#### 4. User Experience Requirements

**Visual Feedback**:
- Recording indicator: Pulsing red circle animation
- Status text: "Listening...", "Processing...", "Done"
- Last command preview: Show transcribed text briefly
- Connection quality indicator: Signal strength bars

**Error Handling**:
- Network errors: "Cannot reach PC. Check WiFi connection."
- Audio errors: "Microphone access denied. Enable in settings."
- Timeout errors: "PC took too long to respond. Try again."
- All errors logged locally for debugging

**Notifications**:
- Persistent notification during foreground service
- Shows current status (listening/processing)
- Quick action buttons: Stop, Pause, Settings
- Low battery warning if service running for >30 min

#### 5. Configuration Screen
```yaml
Required Settings:
  - PC Configuration:
      MAC Address: [Format: AA:BB:CC:DD:EE:FF]
      IP Address: [Format: 192.168.x.x or hostname]
      Port: [Default: 8765]
      
  - Audio Settings:
      Use External App: [Toggle]
      Noise Suppression Level: [Low/Medium/High]
      Voice Sensitivity: [Slider 1-10]
      
  - Security:
      API Key / Auth Token: [Encrypted storage]
      TLS Certificate Pinning: [Enable/Disable]
      
  - Developer Options:
      Enable Debug Logging: [Toggle]
      Show Network Stats: [Toggle]
      Test Connection: [Button]
```

#### 6. Security Implementation

**Required Security Measures**:
```kotlin
1. Network Security:
   - mTLS (Mutual TLS) for WebSocket connections
   - Certificate pinning to prevent MITM attacks
   - TLS 1.3 minimum protocol version

2. Credential Storage:
   - Android EncryptedSharedPreferences for API keys
   - Hardware-backed KeyStore for certificate private keys
   - Biometric authentication for sensitive settings

3. Permissions:
   - RECORD_AUDIO: Request at runtime with rationale
   - INTERNET: Required for WebSocket
   - ACCESS_NETWORK_STATE: Check connectivity before streaming
   - FOREGROUND_SERVICE: For persistent operation
   - WAKE_LOCK: Optional, only if needed for reliability

4. Code Protection:
   - ProGuard/R8 obfuscation enabled
   - Remove all logging in release builds
   - Certificate transparency logging
```

#### 7. Testing Requirements

**Unit Tests** (Target: 90% coverage):
- ViewModel logic for state management
- Audio encoding/decoding utilities
- Network request formatting
- Configuration validation

**Integration Tests**:
- End-to-end activation flow (tile → streaming)
- Connection management (connect, disconnect, reconnect)
- Audio capture and streaming pipeline
- Error recovery scenarios

**UI Tests** (Espresso/Compose Testing):
- Quick Settings tile interactions
- Main app button functionality
- Settings screen configuration
- Error dialog displays

---

## Python Desktop Agent: Technical Specification

### Technology Stack
```yaml
Language: Python 3.11+
Package Manager: uv (for fast dependency management)
Web Framework: FastAPI (for WebSocket + REST API)
STT Engine: whisper.cpp (local model)
LLM Interface: Claude Code CLI (primary), API fallback
Service Management: NSSM or pywin32 for Windows Service
Configuration: TOML format (config.toml)
Logging: loguru with rotation and structured output
```

### Core Components

#### 1. Startup & Wake Protocol

**Windows Service Implementation**:
```python
Service Requirements:
  - Auto-start on system boot (Startup Type: Automatic)
  - Restart on failure (3 attempts with 60s delay)
  - Run as: Local System account (configurable)
  - Dependencies: Network service must be running

Service Operations:
  - Start: Initialize all components (audio server, STT model, MCP clients)
  - Stop: Graceful shutdown (close connections, save state)
  - Restart: Clean restart without losing configuration
  - Status: HTTP endpoint /status returns {"healthy": true, "uptime": 3600}
```

**HTTP REST API** (for Android communication):
```python
Endpoints:
  GET  /status
    Response: {"status": "ready", "uptime_seconds": 1234, "connections": 0}
    
  POST /wake
    Description: Explicit wake signal (redundant, but useful for testing)
    Response: {"acknowledged": true}
    
  GET  /config
    Description: Returns safe configuration info (no secrets)
    Response: {"version": "1.0.0", "features": ["windows_mcp", "chrome_mcp"]}
```

#### 2. Audio Reception Module

**WebSocket Server** (FastAPI-based):
```python
Configuration:
  - Host: 0.0.0.0 (bind to all interfaces)
  - Port: 8765 (configurable)
  - Path: /audio/stream
  - Connection Limit: 1 (only one Android device at a time)
  - Timeout: 300s idle timeout (5 minutes)

Message Handling:
  - Binary frames: Opus-encoded audio chunks
  - Text frames: Control messages (pause, resume, stop)
  - Heartbeat: Pong response to client ping

Audio Buffer Management:
  - Circular buffer: 30-second rolling window
  - Chunk size: 160ms (matches Android sender)
  - Overflow handling: Drop oldest chunks, warn via log
```

**Audio Decoding Pipeline**:
```python
1. Opus Decoding:
   - Library: opuslib or PyOgg
   - Output format: 16kHz PCM, 16-bit, mono
   - Error handling: Log corrupt frames, continue with next

2. Voice Activity Detection (VAD):
   - Library: webrtcvad or silero-vad
   - Mode: Aggressive (mode 3 for low false positives)
   - Purpose: Auto-segment commands, detect silence

3. Audio Buffering for STT:
   - Accumulate audio until VAD detects silence (>500ms)
   - Maximum command length: 30 seconds
   - Pass complete audio segment to Whisper.cpp
```

**Fallback: External App Support**:
```python
If Android uses WoMic/RTPMic:
  - Listen on configured port (e.g., 5900 for RTPMic)
  - Detect audio format from stream headers
  - Convert to 16kHz PCM if necessary (using ffmpeg-python)
  - Feed into same VAD + STT pipeline
```

#### 3. Speech-to-Text Engine (Whisper.cpp)

**Model Configuration**:
```python
Model Selection:
  - Primary: ggml-base.en.bin (English-only, balanced speed/accuracy)
  - Fallback: ggml-tiny.en.bin (if RAM < 4GB)
  - Optional: ggml-small.en.bin (if user wants higher accuracy)

Whisper.cpp Parameters:
  model_path: "./models/ggml-base.en.bin"
  language: "en"
  n_threads: 4                    # CPU threads
  n_max_text_ctx: 16384           # Context window
  word_timestamps: true           # For better punctuation
  beam_size: 5                    # Beam search width
  best_of: 5                      # Number of candidates
  temperature: 0.0                # Deterministic output
  gpu_device: 0                   # GPU index (if available)
  gpu_layers: 10                  # Offload 10 layers to GPU
  
GPU Acceleration:
  - Vulkan: Preferred for NVIDIA/AMD (no CUDA dependency)
  - CUDA: If Vulkan unavailable, use CUDA backend
  - CPU fallback: If no GPU detected, use CPU-only mode
```

**Streaming & Real-Time Processing**:
```python
Implementation Options:

Option A (Recommended): Chunked Processing
  - Process audio in 5-second overlapping chunks
  - Combine results with overlap removal
  - Reduces latency to ~1-2s for short commands

Option B: Full Buffer Processing
  - Wait for complete VAD-detected command
  - Process entire audio segment at once
  - Higher accuracy, slightly higher latency (~2-3s)

Confidence Scoring:
  - Threshold: 0.7 (below this, ask user to repeat)
  - Log low-confidence transcriptions for debugging
  - Return confidence score to Android app
```

**Error Handling**:
```python
Error Scenarios:
  1. Model file not found:
     - Log: "ERROR: Whisper model not found at {path}"
     - Action: Check config, download model if missing
     
  2. Audio format incompatible:
     - Log: "WARNING: Unexpected audio format, converting..."
     - Action: Use ffmpeg to convert to supported format
     
  3. GPU initialization failed:
     - Log: "WARNING: GPU initialization failed, falling back to CPU"
     - Action: Disable GPU, use CPU-only mode
     
  4. Transcription timeout (>30s):
     - Log: "ERROR: Whisper.cpp transcription timeout"
     - Action: Kill process, return error to user
```

#### 4. LLM Integration (Claude Code CLI)

**Primary Method: Claude Code CLI**
```python
CLI Configuration:
  executable_path: "claude"           # Assumes in PATH
  model: "claude-sonnet-4-20250514"   # Latest Sonnet model
  max_tokens: 2000                    # Response limit
  temperature: 0.0                    # Deterministic for commands
  timeout: 30                         # Seconds before timeout

Command Execution:
  command = [
      "claude",
      "--model", "claude-sonnet-4-20250514",
      "--max-tokens", "2000",
      "--prompt", f"{system_prompt}\n\nUser: {transcribed_text}"
  ]
  
  result = subprocess.run(
      command,
      capture_output=True,
      text=True,
      timeout=30
  )

System Prompt Template:
  """You are a voice command interpreter for a Windows PC automation system.
  
  Your role:
  1. Parse the user's natural language command
  2. Determine if it requires Windows MCP (system) or Chrome MCP (browser)
  3. Return a JSON response with the following structure:
  
  {
    "tool": "windows_mcp" | "chrome_mcp",
    "action": "specific_action_name",
    "parameters": {
      "param1": "value1",
      "param2": "value2"
    },
    "reasoning": "Brief explanation of why this tool/action was chosen"
  }
  
  Available Actions:
  
  Windows MCP:
  - open_application(name: str)
  - close_application(name: str)
  - set_volume(level: int)  # 0-100
  - get_system_info()
  - find_file(query: str)
  - execute_command(cmd: str)  # Use cautiously
  
  Chrome MCP:
  - open_url(url: str)
  - search_web(query: str)
  - get_page_content()
  - click_element(selector: str)
  - fill_form(selector: str, value: str)
  - close_tabs(count: int)
  
  User Command: {transcribed_text}
  
  Respond ONLY with valid JSON. Do not include any other text.
  """

Response Parsing:
  try:
      response_json = json.loads(result.stdout)
      tool = response_json["tool"]
      action = response_json["action"]
      params = response_json["parameters"]
      
  except json.JSONDecodeError:
      # LLM returned non-JSON text, log and ask user
      log.error(f"LLM returned invalid JSON: {result.stdout}")
      return {"error": "Failed to parse command"}
```

**Fallback Method: Claude API**
```python
API Configuration (if CLI not available):
  import anthropic
  
  client = anthropic.Anthropic(
      api_key=os.environ.get("ANTHROPIC_API_KEY")
  )
  
  response = client.messages.create(
      model="claude-sonnet-4-20250514",
      max_tokens=2000,
      temperature=0.0,
      messages=[
          {"role": "user", "content": f"{system_prompt}\n\nUser: {transcribed_text}"}
      ]
  )
  
  response_json = json.loads(response.content[0].text)
```

**Context Window Management**:
```python
Multi-Turn Conversation Support:
  - Maintain history of last 5 commands and responses
  - Include in system prompt: "Previous commands: [list]"
  - Use for follow-up commands: "Do that again", "Close the previous tab"
  - Clear history on explicit user request or after 10 minutes idle

History Structure:
  conversation_history = [
      {"user": "Open Chrome", "assistant": {...}, "timestamp": 1234567890},
      {"user": "Search for weather", "assistant": {...}, "timestamp": 1234567900},
      # ... up to 5 entries
  ]
```

#### 5. MCP Tool Router & Execution

**Routing Logic**:
```python
def route_and_execute(tool: str, action: str, params: dict):
    """
    Routes LLM-interpreted command to appropriate MCP tool.
    
    Args:
        tool: "windows_mcp" or "chrome_mcp"
        action: Specific action name (e.g., "open_application")
        params: Dictionary of action parameters
        
    Returns:
        Result dictionary with status and output
    """
    
    if tool == "windows_mcp":
        return execute_windows_mcp(action, params)
    elif tool == "chrome_mcp":
        return execute_chrome_mcp(action, params)
    else:
        return {"error": f"Unknown tool: {tool}"}

# Tool-specific executors
def execute_windows_mcp(action: str, params: dict):
    # Import and use Windows MCP client
    pass

def execute_chrome_mcp(action: str, params: dict):
    # Import and use Chrome DevTools MCP client
    pass
```

**Windows MCP Integration**:
```python
Windows MCP Tool Requirements:
  - PowerShell execution via subprocess
  - Windows API access via ctypes (for GUI automation)
  - Registry access via winreg (for settings)
  - Process management via psutil

Action Implementations:

1. open_application(name: str):
   - Search Start Menu for application
   - Launch via subprocess.Popen()
   - Return PID and success status

2. set_volume(level: int):
   - Use pycaw library (Windows Core Audio)
   - Set master volume to specified percentage
   - Return current volume level

3. find_file(query: str):
   - Use Windows Search index via pywin32
   - Return list of file paths matching query
   - Max results: 10

4. execute_command(cmd: str):
   - SECURITY: Whitelist only safe commands
   - Require user confirmation for destructive actions
   - Log all executions with timestamps

Security Measures:
  - Command whitelist: ["ipconfig", "systeminfo", "tasklist", etc.]
  - Blacklist: ["format", "del /f", "rd /s", "shutdown", etc.]
  - User confirmation for: File deletion, registry edits, system changes
  - Audit log: All commands logged to ./logs/windows_mcp_audit.log
```

**Chrome DevTools MCP Integration**:
```python
Chrome DevTools MCP Requirements:
  - Chrome instance with remote debugging enabled
  - Port: 9222 (default Chrome DevTools Protocol port)
  - Playwright or Selenium for automation

Configuration:
  chrome_debugging_port: 9222
  chrome_executable: "C:/Program Files/Google/Chrome/Application/chrome.exe"
  user_data_dir: "./chrome_profile"  # Persistent session

Launch Chrome with Remote Debugging:
  subprocess.Popen([
      chrome_executable,
      f"--remote-debugging-port={chrome_debugging_port}",
      f"--user-data-dir={user_data_dir}"
  ])

Action Implementations:

1. open_url(url: str):
   - Connect to existing Chrome instance
   - Open new tab or navigate current tab
   - Return tab ID

2. search_web(query: str):
   - Navigate to https://www.google.com/search?q={query}
   - Return first 5 result titles and URLs

3. get_page_content():
   - Extract text content from current tab
   - Remove scripts, styles, and navigation
   - Return cleaned text (max 5000 chars)

4. click_element(selector: str):
   - Find element by CSS selector
   - Scroll into view if necessary
   - Click element, return success status

5. fill_form(selector: str, value: str):
   - Find input element by selector
   - Clear existing value
   - Type new value, return success status

Security Measures:
  - Cross-origin restrictions: Only allow localhost and safe domains
  - User confirmation for: Form submissions, file downloads, payments
  - Sanitize selectors to prevent XSS
  - Log all browser actions to ./logs/chrome_mcp_audit.log
```

#### 6. Configuration Management

**Configuration File Format** (config.toml):
```toml
[server]
host = "0.0.0.0"
port = 8765
wol_port = 9

[audio]
sample_rate = 16000
channels = 1
buffer_duration_seconds = 30

[whisper]
model_path = "./models/ggml-base.en.bin"
language = "en"
n_threads = 4
beam_size = 5
gpu_layers = 10  # 0 for CPU-only

[claude]
# Option 1: CLI (recommended)
use_cli = true
cli_path = "claude"
model = "claude-sonnet-4-20250514"

# Option 2: API (fallback)
# use_cli = false
# api_key = "sk-ant-..."  # Or use environment variable

[mcp]
windows_enabled = true
chrome_enabled = true
chrome_port = 9222
chrome_executable = "C:/Program Files/Google/Chrome/Application/chrome.exe"

[security]
tls_enabled = true
cert_file = "./certs/server.crt"
key_file = "./certs/server.key"
require_client_cert = true

[logging]
level = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
file_path = "./logs/voice_assistant.log"
max_size_mb = 100
backup_count = 5
```

**Environment Variables** (for secrets):
```bash
# .env file (never commit to version control)
ANTHROPIC_API_KEY=sk-ant-api03-...
CHROME_DEBUGGING_SECRET=random_secret_here
TLS_PRIVATE_KEY_PASSWORD=secure_password
```

**Configuration Validation**:
```python
def validate_config(config: dict) -> tuple[bool, list[str]]:
    """
    Validates configuration and returns (is_valid, error_messages).
    """
    errors = []
    
    # Required files
    if not os.path.exists(config["whisper"]["model_path"]):
        errors.append(f"Whisper model not found: {config['whisper']['model_path']}")
    
    # Required executables
    if config["claude"]["use_cli"]:
        if not shutil.which(config["claude"]["cli_path"]):
            errors.append("Claude CLI not found in PATH")
    
    # Valid ports
    if not (1024 <= config["server"]["port"] <= 65535):
        errors.append("Server port must be between 1024 and 65535")
    
    # Security checks
    if config["security"]["tls_enabled"]:
        if not os.path.exists(config["security"]["cert_file"]):
            errors.append("TLS certificate file not found")
    
    return (len(errors) == 0, errors)
```

#### 7. Logging & Monitoring

**Structured Logging** (loguru):
```python
from loguru import logger

# Configure logger
logger.add(
    config["logging"]["file_path"],
    rotation=f"{config['logging']['max_size_mb']} MB",
    retention=config["logging"]["backup_count"],
    level=config["logging"]["level"],
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} | {message}",
    serialize=True  # JSON output for structured parsing
)

# Usage
logger.info("WebSocket connection established", client_ip="192.168.1.100")
logger.warning("Low confidence transcription", confidence=0.65, text="...")
logger.error("MCP tool execution failed", tool="windows_mcp", action="open_app", error="...")
```

**Telemetry & Metrics** (optional, but recommended):
```python
Metrics to Track:
  - command_latency_seconds: End-to-end time from audio to action completion
  - whisper_transcription_seconds: Time spent in STT
  - llm_inference_seconds: Time spent waiting for LLM
  - mcp_execution_seconds: Time spent executing MCP actions
  - error_count: Number of errors by type
  - active_connections: Current WebSocket connections

Implementation:
  - Use OpenTelemetry for standardized metrics
  - Export to Prometheus or local file
  - Create simple dashboard with Grafana (optional)
```

---

## Integration & Communication Protocol

### Network Architecture

**Local Network Requirements**:
```yaml
Network Type: WiFi (same LAN required)
IP Assignment: Static IP recommended for PC (or DHCP reservation)
Firewall Rules:
  - Allow inbound UDP on port 9 (WoL)
  - Allow inbound TCP on port 8765 (WebSocket)
  - Allow outbound TCP on port 443 (Claude API)
```

**Communication Flow**:
```
1. Android → PC Wake-on-LAN (UDP port 9)
   Packet: Magic Packet (FF FF FF FF FF FF + MAC×16)
   
2. Android → PC Health Check (HTTP GET)
   URL: http://{PC_IP}:8765/status
   Timeout: 10s
   
3. Android ⇄ PC WebSocket Handshake (Upgrade request)
   URL: wss://{PC_IP}:8765/audio/stream
   TLS: Required (with cert pinning)
   
4. Android → PC Audio Streaming (WebSocket binary frames)
   Format: Opus-encoded audio chunks (160ms each)
   Frequency: ~6 messages per second
   
5. PC → Android Status Updates (WebSocket text frames)
   Examples:
   - {"status": "transcribing"}
   - {"status": "processing_llm"}
   - {"status": "executing_action"}
   - {"status": "complete", "result": "..."}
```

### Message Protocol

**WebSocket Message Types**:
```json
// Audio chunk (binary frame)
Binary data: Opus-encoded audio bytes

// Control messages (text frames)
{
  "type": "control",
  "action": "pause" | "resume" | "stop"
}

{
  "type": "heartbeat",
  "timestamp": 1234567890
}

// Status updates (text frames, PC → Android)
{
  "type": "status",
  "state": "transcribing" | "processing" | "executing" | "complete" | "error",
  "message": "Human-readable status message",
  "data": {
    "transcribed_text": "...",  // Only if state == "processing"
    "result": "...",              // Only if state == "complete"
    "error_code": "...",          // Only if state == "error"
  }
}
```

### Security Protocol

**Mutual TLS (mTLS) Configuration**:
```python
# Server-side (Python)
ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain(
    certfile="certs/server.crt",
    keyfile="certs/server.key"
)
ssl_context.load_verify_locations(cafile="certs/client_ca.crt")
ssl_context.verify_mode = ssl.CERT_REQUIRED  # Require client certificate

# Client-side (Android Kotlin)
val trustManager = CustomX509TrustManager(serverCertificate)
val sslContext = SSLContext.getInstance("TLS")
sslContext.init(null, arrayOf(trustManager), SecureRandom())
```

**Authentication Flow**:
```
1. Certificate Exchange:
   - Generate self-signed CA
   - Issue server certificate (Python PC)
   - Issue client certificate (Android)
   - Both sides pin each other's certificates

2. HMAC Request Signing (optional additional layer):
   - Shared secret exchanged via QR code (one-time setup)
   - Each message signed with HMAC-SHA256
   - Signature included in message header
   - Server verifies signature before processing

3. API Key Protection:
   - Claude API key stored encrypted (AES-256)
   - Decrypted only in memory, never logged
   - Rotatable via configuration update
```

**Certificate Generation Scripts**:
```bash
# Generate CA
openssl genrsa -out ca.key 4096
openssl req -new -x509 -days 3650 -key ca.key -out ca.crt

# Generate server certificate
openssl genrsa -out server.key 4096
openssl req -new -key server.key -out server.csr
openssl x509 -req -days 3650 -in server.csr -CA ca.crt -CAkey ca.key -set_serial 01 -out server.crt

# Generate client certificate
openssl genrsa -out client.key 4096
openssl req -new -key client.key -out client.csr
openssl x509 -req -days 3650 -in client.csr -CA ca.crt -CAkey ca.key -set_serial 02 -out client.crt

# Convert to Android-compatible format (PKCS12)
openssl pkcs12 -export -out client.p12 -inkey client.key -in client.crt -certfile ca.crt
```

---

## Quality Standards & Performance Targets

### Performance Requirements

**Latency Targets**:
```yaml
End-to-End Latency: <2s (voice command → action complete)
  Breakdown:
    - Audio streaming: <200ms (negligible, real-time)
    - Speech-to-Text: <800ms (Whisper.cpp with GPU)
    - LLM inference: <800ms (Claude API with good network)
    - MCP execution: <200ms (local operations)

Network Requirements:
  - Minimum bandwidth: 200 kbps (for Opus audio stream)
  - Recommended latency: <50ms (local network)
  - Jitter tolerance: <20ms

Resource Usage:
  - Android App:
      RAM: <100MB during idle, <150MB during streaming
      Battery: <5% drain per hour of active streaming
      CPU: <15% during audio capture
      
  - Python Agent:
      RAM: <500MB idle, <1GB during processing (with Whisper loaded)
      CPU: <10% idle, <60% during STT (CPU-only), <25% (with GPU)
      GPU: <2GB VRAM (if using GPU acceleration)
      Disk: <100MB for logs (with rotation)
```

**Availability Targets**:
```yaml
Uptime: 99.9% when PC is powered on
  - Automatic restart on crash: Yes
  - Restart attempts: 3 (with exponential backoff)
  - Health check interval: 60s

Connection Recovery:
  - Auto-reconnect attempts: 5
  - Backoff strategy: Exponential (2s, 4s, 8s, 16s, 32s)
  - Manual retry: Always available via UI button
```

### Code Quality Standards

**Type Safety**:
```python
# Python: Use type hints everywhere
from typing import Optional, Dict, List, Union

def process_audio(audio_data: bytes, sample_rate: int = 16000) -> tuple[str, float]:
    """
    Process audio and return transcription with confidence score.
    
    Args:
        audio_data: Raw PCM audio bytes
        sample_rate: Audio sample rate in Hz
        
    Returns:
        Tuple of (transcribed_text, confidence_score)
    """
    pass

# Kotlin: Leverage null safety
fun connectToServer(ipAddress: String, port: Int): Result<WebSocket> {
    // Return Result type for explicit error handling
}
```

**Error Handling**:
```python
# Python: Use specific exceptions
class WhisperTranscriptionError(Exception):
    """Raised when Whisper.cpp fails to transcribe audio."""
    pass

class LLMConnectionError(Exception):
    """Raised when Claude API/CLI is unreachable."""
    pass

# Never use bare except
try:
    transcription = whisper.transcribe(audio)
except WhisperTranscriptionError as e:
    logger.error("Transcription failed", error=str(e))
    return {"error": "Speech recognition failed"}

# Kotlin: Use sealed classes for result types
sealed class AudioStreamResult {
    data class Success(val data: ByteArray) : AudioStreamResult()
    data class Error(val exception: Exception) : AudioStreamResult()
}
```

**Testing Requirements**:
```yaml
Minimum Coverage: 80% (target: 90%)

Unit Tests Required For:
  - Audio encoding/decoding functions
  - Configuration validation
  - LLM response parsing
  - MCP action routing logic
  - Security: HMAC signature verification
  - All utility functions

Integration Tests Required For:
  - End-to-end audio pipeline (capture → stream → decode)
  - WebSocket connection lifecycle
  - Whisper.cpp integration
  - Claude CLI/API integration
  - Windows MCP actions (mocked file system)
  - Chrome MCP actions (headless browser)

UI Tests Required For (Android):
  - Quick Settings tile activation
  - Settings configuration
  - Connection status updates
  - Error dialog displays

Performance Tests:
  - Load test: 100 consecutive commands
  - Stress test: 10 commands per second for 1 minute
  - Memory leak test: 1000 commands without restart
  - Battery drain test: 1 hour continuous streaming
```

**Documentation Requirements**:
```yaml
Code Documentation:
  - Python: Google-style docstrings for all public functions
  - Kotlin: KDoc comments for all public APIs
  - Inline comments for complex logic (WHY, not WHAT)
  - Architecture Decision Records (ADRs) for major design choices

User Documentation:
  - README.md: Project overview, features, installation
  - SETUP.md: Step-by-step setup guide with screenshots
  - CONFIG.md: All configuration options explained
  - TROUBLESHOOTING.md: Common issues and solutions
  - SECURITY.md: Security model and best practices

Developer Documentation:
  - ARCHITECTURE.md: System architecture with diagrams
  - API.md: WebSocket protocol and message formats
  - CONTRIBUTING.md: How to contribute, code style guide
  - CHANGELOG.md: Version history with breaking changes
```

---

## Security & Privacy Requirements

### Data Protection

**Voice Data Handling**:
```yaml
Recording:
  - Audio stored in memory only (never written to disk)
  - Cleared immediately after transcription
  - No persistent storage of audio files

Transcriptions:
  - Stored in memory for context (last 5 commands only)
  - Automatically cleared after 10 minutes of inactivity
  - Optional: User can disable transcription history

LLM Communication:
  - Commands sent to Claude API via HTTPS only
  - No conversation history stored on Anthropic servers (per API settings)
  - User can opt out of telemetry/analytics

Logging:
  - Logs contain no audio data or full transcriptions
  - Sensitive parameters redacted (API keys, passwords)
  - Log files encrypted at rest (BitLocker on Windows)
  - Automatic rotation and deletion after 30 days
```

**Authentication & Authorization**:
```yaml
User Authentication:
  - Android app: Biometric unlock for settings access
  - Python agent: Windows user account permissions
  - API keys: Encrypted storage with hardware-backed keys (Android KeyStore)

Authorization Model:
  - Whitelist approach for all MCP actions
  - User confirmation required for:
      * File deletion or modification
      * System settings changes
      * Browser form submissions
      * Any command with "destructive" flag
  - Audit log of all authorized actions

Network Security:
  - mTLS with certificate pinning (prevent MITM)
  - TLS 1.3 minimum (no fallback to older versions)
  - Perfect Forward Secrecy enabled
  - Regular certificate rotation (every 90 days)
```

**Secure Development Practices**:
```yaml
Code Security:
  - Static analysis: Run Bandit (Python), Detekt (Kotlin) on every commit
  - Dependency scanning: Automated vulnerability checks (Dependabot)
  - Secret scanning: No hardcoded secrets, use environment variables
  - Code review: Required for all changes to security-critical code

Deployment Security:
  - Android: ProGuard/R8 obfuscation enabled
  - Python: PyInstaller with encryption (--key option)
  - Windows Service: Run with minimal privileges (no admin rights)
  - Auto-updates: Signed releases with SHA-256 checksums
```

### Privacy Controls

**User-Configurable Privacy Settings**:
```yaml
Settings Screen (Android App):
  - "Save Command History": ON/OFF (default: ON, 5 commands)
  - "Send Telemetry": ON/OFF (default: OFF)
  - "Enable Cloud Backup": ON/OFF (default: OFF)
  - "Delete All Data": Button (clears all local data)

Python Agent Configuration:
  - log_level: "INFO" | "WARNING" | "ERROR" (hide DEBUG in production)
  - telemetry_enabled: false (default)
  - data_retention_days: 30 (default)
```

---

## Implementation Workflow

### Phase 1: Foundation Setup

**Week 1-2: Project Structure & Dependencies**
1. Initialize Android project (Gradle + Kotlin DSL)
2. Initialize Python project (Poetry/uv + virtual environment)
3. Set up CI/CD pipelines (GitHub Actions or GitLab CI)
4. Configure linters and formatters:
   - Python: Black, isort, Flake8, mypy
   - Kotlin: ktlint, Detekt
5. Create initial project documentation (README, ARCHITECTURE)

**Required MCP Tool Usage**:
```yaml
- Context7: Lookup official documentation for:
    * Android Jetpack Compose
    * FastAPI WebSocket
    * whisper.cpp Python bindings
    * Anthropic Claude API
- Tavily: Search for:
    * "Android Quick Settings Tile best practices 2025"
    * "Windows Service Python implementation"
    * "Opus codec real-time streaming"
```

### Phase 2: Core Components

**Week 3-4: Android App Foundation**
1. Implement Quick Settings Tile
2. Create main app UI with Jetpack Compose
3. Set up MVVM architecture (ViewModel, Repository, DataSource)
4. Implement audio capture (AudioRecord API)
5. Add Opus encoding (using native library)
6. Create configuration screen (EncryptedSharedPreferences)

**Week 5-6: Python Agent Foundation**
1. Implement FastAPI WebSocket server
2. Add Opus decoding pipeline
3. Integrate Whisper.cpp (using ctypes or Cython bindings)
4. Create configuration loader (TOML parser)
5. Implement logging system (loguru)
6. Set up Windows Service wrapper (NSSM)

**Required Testing**:
- Unit tests for each component
- Integration tests for audio pipeline
- Manual testing on real devices

### Phase 3: Intelligence Layer

**Week 7-8: LLM & MCP Integration**
1. Implement Claude Code CLI wrapper
2. Create LLM prompt templates
3. Build JSON response parser with validation
4. Implement MCP tool router
5. Add Windows MCP actions:
   - Application launching
   - Volume control
   - File search
   - System info queries
6. Add Chrome MCP actions:
   - URL navigation
   - Web search
   - Page content extraction
   - Element interaction

**Required Testing**:
- Unit tests for parsing and routing
- Integration tests with mock LLM responses
- End-to-end tests with real Claude API (limited)

### Phase 4: Security & Polish

**Week 9-10: Security Implementation**
1. Generate TLS certificates (self-signed CA)
2. Implement mTLS in FastAPI server
3. Add certificate pinning in Android app
4. Implement HMAC request signing
5. Set up encrypted storage (Android KeyStore, AES-256 for Python)
6. Add user confirmation prompts for sensitive actions
7. Create audit logging system

**Week 11-12: User Experience & Testing**
1. Add visual feedback animations (Compose animations)
2. Implement error handling with user-friendly messages
3. Create notification system (Android + Windows)
4. Add connection status indicators
5. Implement auto-reconnect logic
6. Comprehensive integration testing
7. Performance testing and optimization
8. Beta testing with real users

### Phase 5: Documentation & Deployment

**Week 13-14: Finalization**
1. Complete all documentation (see Documentation Requirements)
2. Create setup wizard scripts
3. Build Android APK (release variant with ProGuard)
4. Package Python agent (PyInstaller single executable)
5. Create Windows installer (Inno Setup or NSIS)
6. Write user guides with screenshots
7. Prepare GitHub releases

**Deliverables Checklist**:
- [ ] Android APK (signed, obfuscated)
- [ ] Python agent executable (Windows installer)
- [ ] Certificate generation scripts
- [ ] Configuration templates (config.toml, .env.example)
- [ ] Complete documentation set
- [ ] Test suite (unit + integration + UI)
- [ ] Deployment guide
- [ ] Troubleshooting guide

---

## Deliverables

### 1. Android Controller App

**Source Code**:
```
android-app/
├── app/
│   ├── src/
│   │   ├── main/
│   │   │   ├── kotlin/com/voiceassistant/
│   │   │   │   ├── ui/              # Compose UI screens
│   │   │   │   ├── viewmodel/       # ViewModels
│   │   │   │   ├── repository/      # Data repositories
│   │   │   │   ├── network/         # WebSocket client
│   │   │   │   ├── audio/           # Audio capture & encoding
│   │   │   │   ├── service/         # Foreground service, Quick Settings Tile
│   │   │   │   ├── security/        # TLS, encryption utilities
│   │   │   │   └── util/            # Helper functions
│   │   │   ├── AndroidManifest.xml
│   │   │   └── res/                 # Resources
│   │   ├── test/                    # Unit tests
│   │   └── androidTest/             # UI tests
│   └── build.gradle.kts
├── gradle/
├── settings.gradle.kts
└── README.md
```

**Build Outputs**:
- `app-release.apk`: Signed, obfuscated production build
- `app-debug.apk`: Debug build for testing
- `mapping.txt`: ProGuard mapping file (for crash analysis)

### 2. Python Desktop Agent

**Source Code**:
```
python-agent/
├── src/
│   ├── voice_assistant/
│   │   ├── __init__.py
│   │   ├── server.py              # FastAPI WebSocket server
│   │   ├── audio/
│   │   │   ├── decoder.py         # Opus decoding
│   │   │   ├── vad.py             # Voice Activity Detection
│   │   │   └── buffer.py          # Audio buffering
│   │   ├── stt/
│   │   │   ├── whisper_client.py  # Whisper.cpp integration
│   │   │   └── transcriber.py     # Transcription logic
│   │   ├── llm/
│   │   │   ├── claude_cli.py      # CLI wrapper
│   │   │   ├── claude_api.py      # API client (fallback)
│   │   │   └── prompt_templates.py
│   │   ├── mcp/
│   │   │   ├── router.py          # Tool routing logic
│   │   │   ├── windows_mcp.py     # Windows actions
│   │   │   └── chrome_mcp.py      # Browser automation
│   │   ├── security/
│   │   │   ├── tls.py             # mTLS configuration
│   │   │   ├── hmac_auth.py       # HMAC signing
│   │   │   └── encryption.py      # AES-256 utilities
│   │   ├── config.py              # Configuration loader
│   │   └── logger.py              # Logging setup
│   └── main.py                    # Entry point
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── config.toml.example            # Template configuration
├── .env.example                   # Template environment variables
├── requirements.txt               # Python dependencies
├── pyproject.toml                 # Poetry/uv configuration
└── README.md
```

**Build Outputs**:
- `voice_assistant.exe`: Single executable (PyInstaller)
- `voice_assistant_installer.exe`: Windows installer (Inno Setup)
- `voice_assistant-service.xml`: NSSM service definition

### 3. Configuration Files

**config.toml** (template):
```toml
# See full example in "Configuration Management" section above
[server]
host = "0.0.0.0"
port = 8765
# ... (complete example provided earlier)
```

**.env** (template):
```bash
# Secrets (NEVER commit to version control)
ANTHROPIC_API_KEY=your_api_key_here
TLS_PRIVATE_KEY_PASSWORD=your_password_here
```

**Android settings** (SharedPreferences, configured via UI):
```json
{
  "pc_mac_address": "AA:BB:CC:DD:EE:FF",
  "pc_ip_address": "192.168.1.100",
  "pc_port": 8765,
  "use_external_mic": false,
  "noise_suppression_level": "medium",
  "save_command_history": true,
  "auth_token": "<encrypted>"
}
```

### 4. Documentation

**User Documentation**:
1. **README.md**: Project overview, features, quick start
2. **SETUP.md**: Complete setup guide:
   - Android app installation
   - Python agent installation
   - Certificate generation
   - Network configuration
   - First-time pairing
3. **USER_GUIDE.md**: How to use the system:
   - Activating voice commands
   - Common commands and examples
   - Settings configuration
   - Privacy controls
4. **TROUBLESHOOTING.md**: Solutions for common issues:
   - Connection failures
   - Audio not streaming
   - Commands not executing
   - Performance issues

**Developer Documentation**:
1. **ARCHITECTURE.md**: System architecture with Mermaid diagrams
2. **API.md**: WebSocket protocol, message formats, REST endpoints
3. **SECURITY.md**: Security model, threat analysis, mitigations
4. **CONTRIBUTING.md**: Development setup, code style, PR guidelines
5. **TESTING.md**: How to run tests, test coverage reports
6. **CHANGELOG.md**: Version history with breaking changes

### 5. Testing Artifacts

**Test Reports**:
- `coverage_report.html`: Code coverage visualization
- `test_results.xml`: JUnit-format test results
- `performance_benchmarks.json`: Latency measurements

**Test Data**:
- Sample audio files (various languages, accents, noise levels)
- Mock LLM responses (for integration testing)
- Expected transcription outputs

### 6. Deployment Package

**Windows Installer** (`VoiceAssistant_Setup_v1.0.0.exe`):
- Installs Python agent to `C:\Program Files\VoiceAssistant\`
- Registers Windows Service
- Installs dependencies (Whisper model, certificates)
- Creates Start Menu shortcuts
- Optionally starts service on boot

**Android APK** (`VoiceAssistant_v1.0.0.apk`):
- Signed with release key
- ProGuard obfuscation enabled
- Size: <50MB (with all dependencies)
- Compatible with Android 11+

**Certificate Package** (`certificates.zip`):
- CA certificate (`ca.crt`)
- Server certificate and key (`server.crt`, `server.key`)
- Client certificate (`client.p12`) for Android import
- Generation scripts (`generate_certs.sh`)

---

## Acceptance Criteria

The system is considered complete and production-ready when ALL of the following criteria are met:

### Functional Requirements
- [ ] User taps Quick Settings tile → PC wakes within 10 seconds
- [ ] Android app streams audio to Python agent within 2 seconds of connection
- [ ] Python agent transcribes audio with >90% accuracy (for clear English)
- [ ] LLM correctly interprets commands and routes to appropriate MCP tool in >95% of cases
- [ ] Example commands work reliably:
  - [ ] "Open Chrome and search for weather" → Executes correctly
  - [ ] "Set volume to 50%" → Volume changes to 50%
  - [ ] "What's on the current tab?" → Returns page content
  - [ ] "Find my resume file" → Returns file path(s)
- [ ] System handles errors gracefully (no crashes, user-friendly error messages)
- [ ] Works on locked Android screen with foreground service

### Performance Requirements
- [ ] End-to-end latency <2 seconds for simple commands
- [ ] Android app uses <150MB RAM during streaming
- [ ] Python agent uses <1GB RAM during operation
- [ ] Battery drain <5% per hour of active streaming
- [ ] System maintains 99% uptime during 24-hour stress test

### Security Requirements
- [ ] All network communication encrypted with mTLS
- [ ] No secrets stored in plaintext (code or config files)
- [ ] User confirmation required for destructive actions
- [ ] Audit log captures all commands and actions
- [ ] Static analysis tools report no high-severity vulnerabilities

### Testing Requirements
- [ ] Unit test coverage >80% for both Android and Python
- [ ] All integration tests pass
- [ ] UI tests pass on 3+ Android devices (different manufacturers)
- [ ] Load test: 100 consecutive commands without errors
- [ ] No memory leaks detected after 1000 commands

### Documentation Requirements
- [ ] README clearly explains what the system does
- [ ] SETUP guide allows non-technical user to install and configure
- [ ] API documentation covers all WebSocket messages
- [ ] TROUBLESHOOTING guide addresses 10+ common issues
- [ ] Code comments explain all complex logic

### Usability Requirements
- [ ] Setup wizard completes in <10 minutes
- [ ] First command works without manual configuration (after setup)
- [ ] Error messages are clear and actionable
- [ ] Settings screen is intuitive (no technical jargon)
- [ ] System provides visual/audible feedback for all actions

---

## Critical Reminders for Implementation

### Adherence to ELITE CODING AGENT PROTOCOL

**You MUST follow the user's coding protocol at ALL times:**

1. **Consistency Protocol**:
   - ALWAYS use `view` tool before and after modifying files
   - Create identifier inventory before cross-file changes
   - Verify all identifiers exist with exact spelling
   - No typos in identifiers (function names, variables, imports)

2. **MCP Tool Usage**:
   - **Context7**: Use for official documentation (Android, FastAPI, Whisper, Claude API)
   - **Tavily**: Use for current best practices and troubleshooting
   - **Sequential-Thinking**: Use for complex multi-step problems (e.g., planning MCP router logic)
   - **View Tool**: Use before/after every file modification

3. **Testing Requirement**:
   - Write tests FIRST (TDD when practical)
   - All code must have tests before completion
   - No code is done without passing tests

4. **Documentation Requirement**:
   - All official sources via Context7/Tavily
   - Add comments explaining WHY (not WHAT)
   - Update documentation when API changes

5. **Code Quality**:
   - Strict typing: No `any`, `object`, or dynamic types
   - Explicit error handling: No bare except/catch
   - Single responsibility principle
   - No hardcoded secrets

6. **Security**:
   - Validate all inputs
   - Sanitize user data
   - Use parameterized queries
   - No hardcoded secrets
   - Follow principle of least privilege

### Research Before Implementation

**BEFORE writing any code, you must:**

1. Use Context7 to get official documentation for libraries/frameworks
2. Use Tavily to research current best practices (2025)
3. Use Sequential-Thinking for complex design decisions
4. Read existing code files with `view` tool

**Example Research Workflow**:
```
USER: "Implement audio streaming"

CORRECT APPROACH:
1. Context7: resolve-library-id("android audio capture")
2. Context7: get-library-docs(library_id, topic="AudioRecord")
3. Tavily: search("Android real-time audio streaming best practices 2025")
4. Sequential-Thinking: Plan audio pipeline architecture
5. Implement with verified patterns
6. Write tests

INCORRECT APPROACH:
1. Immediately start writing code based on assumptions
2. Use deprecated APIs
3. Miss critical security considerations
```

### Identifier Consistency Example

**BAD** (causes errors):
```python
# file1.py
def processAudioData(audio: bytes) -> str:
    pass

# file2.py
from file1 import process_audio_data  # WRONG! Function name mismatch
```

**GOOD** (following protocol):
```
1. view file1.py (verify exact function name)
2. Confirm function is called `processAudioData` (camelCase)
3. Use exact name in import:
   from file1 import processAudioData  # CORRECT
```

### Never Proceed Without Verification

**ABSOLUTE PROHIBITIONS**:
- ✗ Guessing identifier names without verification
- ✗ Using deprecated APIs when alternatives exist
- ✗ Skipping tests assuming "it should work"
- ✗ Ignoring compiler/linter warnings
- ✗ Suppressing errors silently
- ✗ Committing code without reading it back
- ✗ Using global state without justification
- ✗ Hardcoding secrets in code or config

**MANDATORY PRACTICES**:
- ✓ Verify every identifier before use
- ✓ Consult documentation before implementation
- ✓ Test thoroughly before completion
- ✓ Follow established patterns
- ✓ Use tools appropriately
- ✓ Maintain consistency across files
- ✓ Document complex decisions

---

## Final Notes

This specification represents a synthesis of five comprehensive prompts, harmonized into a single production-ready document. It prioritizes:

1. **Clarity**: Each requirement is explicit and unambiguous
2. **Completeness**: All technical details, from audio codecs to security protocols
3. **Quality**: Non-negotiable testing, security, and documentation standards
4. **Practicality**: Realistic performance targets and deployment considerations
5. **Security**: Defense-in-depth approach with multiple layers
6. **Maintainability**: Clean architecture, type safety, comprehensive testing

**You are expected to deliver production-grade code that:**
- Works reliably in real-world conditions
- Handles errors gracefully
- Protects user privacy and security
- Performs within specified targets
- Is thoroughly tested and documented

**The bar is set high. Meet it.**

---

**END OF SPECIFICATION**
