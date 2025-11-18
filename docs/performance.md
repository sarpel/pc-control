# Performance Tuning Guide

## Performance Goals

- **End-to-end latency**: <2s for simple commands (FR-008)
- **PC wake-up**: <10s from sleep
- **Audio streaming**: <200ms buffer delay
- **VAD detection**: <100ms voice activity detection
- **Command success rate**: >95% (SC-004)
- **Battery usage**: <5% per hour (SC-010)

## Latency Optimization

### 1. Audio Pipeline

**Current**: 16kHz PCM → Opus compression → WebSocket → Whisper.cpp STT

**Optimizations:**

```python
# pc-agent/src/services/audio_processor.py

# Reduce buffer size (trade-off: quality vs latency)
BUFFER_SIZE_MS = 150  # Default: 200ms

# Use lower Opus bitrate for faster transmission
OPUS_BITRATE = 16000  # Default: 24000 (VBR)

# Enable DTX (Discontinuous Transmission) for silence
OPUS_DTX_ENABLED = True
```

**Impact**: Reduces audio processing latency by ~50ms

---

### 2. STT Processing

**Whisper Model Selection:**

| Model | Size | Speed | Accuracy | Recommendation |
|-------|------|-------|----------|----------------|
| tiny | 39MB | Fastest | Good | Development only |
| base | 74MB | Fast | Very Good | **Recommended** |
| small | 244MB | Medium | Excellent | High accuracy needs |
| medium | 769MB | Slow | Best | Not recommended |

**Configuration:**

```python
# .env
WHISPER_MODEL=base  # Best balance
WHISPER_DEVICE=cpu  # or 'cuda' if GPU available

# For GPU acceleration
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16  # Faster on GPU
```

**Impact**: Base model provides 1-2s processing time vs 3-5s for small

---

### 3. Network Optimization

**WebSocket Configuration:**

```python
# pc-agent/src/api/websocket_server.py

# Increase message buffer size
MAX_MESSAGE_SIZE = 10 * 1024 * 1024  # 10MB

# Enable compression
COMPRESSION_LEVEL = 6  # Balance of speed/size

# Adjust ping interval
PING_INTERVAL = 20  # seconds
PING_TIMEOUT = 10   # seconds
```

**Android Configuration:**

```kotlin
// WebSocketClient.kt

// Connection pool
val connectionPool = ConnectionPool(
    maxIdleConnections = 2,
    keepAliveDuration = 5,
    timeUnit = TimeUnit.MINUTES
)

// Timeouts
connectTimeout(10, TimeUnit.SECONDS)
readTimeout(30, TimeUnit.SECONDS)
writeTimeout(30, TimeUnit.SECONDS)
```

**Impact**: Reduces connection overhead by ~30%

---

### 4. LLM API Optimization

**Claude API Settings:**

```python
# pc-agent/src/services/command_interpreter.py

# Use fastest model for simple commands
MODEL_FAST = "claude-haiku-3.5"  # <1s response
MODEL_STANDARD = "claude-sonnet-4"  # 1-3s response

# Reduce max_tokens for faster responses
MAX_TOKENS = 150  # Sufficient for command interpretation

# Enable streaming
STREAM_RESPONSE = True

# Timeout configuration
API_TIMEOUT = 5  # seconds
MAX_RETRIES = 2
```

**Command Classification:**

```python
# Route simple commands to fast model
def should_use_fast_model(command: str) -> bool:
    simple_patterns = [
        r"aç|kapat",  # open/close
        r"sesi.*artır|azalt",  # volume
        r"youtube|chrome",  # specific apps
    ]
    return any(re.search(p, command, re.IGNORECASE) for p in simple_patterns)
```

**Impact**: Reduces LLM latency from 2-3s to <1s for 70% of commands

---

## Memory Optimization

### PC Agent

**Current usage**: ~500MB baseline

**Optimizations:**

```python
# Limit Whisper model memory
whisper_model = whisper.load_model(
    "base",
    download_root="./models",
    in_memory=False  # Load from disk
)

# Clear audio buffers after processing
audio_buffer.clear()
gc.collect()  # Force garbage collection

# Limit command history
MAX_COMMAND_HISTORY = 5  # Default
HISTORY_RETENTION_MINUTES = 10
```

### Android App

**Current usage**: ~150MB

**Optimizations:**

```kotlin
// Limit audio buffer pool
private const val MAX_BUFFER_POOL_SIZE = 10
private const val BUFFER_SIZE = 4096

// Release resources when inactive
override fun onPause() {
    audioCapture.release()
    websocket.disconnect()
}

// Use memory cache with size limit
val imageCache = LruCache<String, Bitmap>(
    maxSize = 4 * 1024 * 1024  // 4MB
)
```

---

## Battery Optimization

### Android Settings

```kotlin
// BatteryOptimizationService.kt

// Adaptive audio quality based on battery
fun getAudioQuality(batteryLevel: Int): AudioQuality {
    return when {
        batteryLevel < 15 -> AudioQuality.LOW     // 12kHz, 16kbps
        batteryLevel < 40 -> AudioQuality.MEDIUM  // 16kHz, 20kbps
        else -> AudioQuality.HIGH                 // 16kHz, 24kbps
    }
}

// Reduce wake locks
private const val WAKE_LOCK_TIMEOUT_MS = 30_000L  // 30s max

// Use WorkManager for background tasks
val constraints = Constraints.Builder()
    .setRequiresBatteryNotLow(true)
    .setRequiredNetworkType(NetworkType.CONNECTED)
    .build()
```

### Connection Management

```kotlin
// Aggressive connection pooling
private const val MAX_IDLE_CONNECTIONS = 1
private const val KEEP_ALIVE_DURATION = 2L  // minutes

// Disconnect when screen off (if configured)
override fun onScreenOff() {
    if (settings.disconnectOnScreenOff) {
        websocket.disconnect()
    }
}
```

**Target**: <5% battery drain per hour (SC-010)

---

## Database Performance

### SQLite Tuning

```sql
-- Enable WAL mode for better concurrency
PRAGMA journal_mode = WAL;

-- Increase cache size
PRAGMA cache_size = -64000;  -- 64MB

-- Synchronous mode for performance
PRAGMA synchronous = NORMAL;

-- Memory-mapped I/O
PRAGMA mmap_size = 268435456;  -- 256MB
```

### Query Optimization

```python
# Use indexes for frequent queries
CREATE INDEX idx_commands_timestamp ON command_history(timestamp DESC);
CREATE INDEX idx_pairings_status ON device_pairings(pairing_status);

# Limit query results
SELECT * FROM command_history
ORDER BY timestamp DESC
LIMIT 5;  -- Only get what's needed
```

---

## Monitoring and Profiling

### Performance Metrics Collection

```python
# pc-agent/src/services/performance_monitor.py

class PerformanceMonitor:
    def track_latency(self, operation: str, duration_ms: float):
        """Track operation latency."""
        self.metrics[operation].append(duration_ms)

        # Log if exceeds SLA
        if operation == "end_to_end" and duration_ms > 2000:
            logger.warning(f"SLA violation: {operation} took {duration_ms}ms")
```

### Key Metrics to Monitor

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Audio buffer latency | <200ms | >250ms |
| STT processing | <1500ms | >2000ms |
| LLM API call | <1000ms | >3000ms |
| Command execution | <500ms | >1000ms |
| End-to-end latency | <2000ms | >2500ms |
| WebSocket RTT | <50ms | >100ms |

### Profiling Tools

```bash
# Profile Python performance
python -m cProfile -o profile.stats src/main.py

# Analyze profile
python -m pstats profile.stats
> sort cumulative
> stats 20

# Memory profiling
python -m memory_profiler src/main.py

# Network monitoring
wireshark -i eth0 -f "tcp port 8443"
```

---

## Load Testing

### Concurrent Connections

```python
# tests/load/test_concurrent_users.py

@pytest.mark.asyncio
async def test_concurrent_commands():
    """Test system under concurrent load."""
    num_clients = 10
    commands_per_client = 20

    async with aiohttp.ClientSession() as session:
        tasks = [
            send_commands(session, commands_per_client)
            for _ in range(num_clients)
        ]
        results = await asyncio.gather(*tasks)

    # Verify success rate >95%
    success_rate = sum(r["success"] for r in results) / len(results)
    assert success_rate > 0.95
```

### Stress Testing

```bash
# Use Apache Bench for REST API
ab -n 1000 -c 10 https://localhost:8443/api/v1/system/info

# Use custom script for WebSocket
python scripts/stress_test_websocket.py --clients 50 --duration 300
```

---

## Production Deployment

### System Requirements

**Minimum:**
- CPU: Intel i5 (or equivalent, last 5 years)
- RAM: 8GB
- Network: 100Mbps LAN

**Recommended:**
- CPU: Intel i7 / AMD Ryzen 7
- RAM: 16GB+
- GPU: NVIDIA GPU with CUDA (for Whisper acceleration)
- Network: Gigabit LAN

### Windows Service Configuration

```powershell
# Create Windows Service
nssm install PCVoiceAgent "C:\Python310\python.exe" "C:\pc-agent\src\main.py"
nssm set PCVoiceAgent AppDirectory "C:\pc-agent"
nssm set PCVoiceAgent AppEnvironmentExtra "LOG_LEVEL=INFO"

# Set to start automatically
nssm set PCVoiceAgent Start SERVICE_AUTO_START

# Configure recovery
nssm set PCVoiceAgent AppExit Default Restart
nssm set PCVoiceAgent AppRestartDelay 5000
```

### Auto-scaling (if needed)

```python
# Monitor system load
import psutil

def should_scale_down() -> bool:
    cpu_percent = psutil.cpu_percent(interval=1)
    return cpu_percent < 20  # Idle

def should_scale_up() -> bool:
    cpu_percent = psutil.cpu_percent(interval=1)
    return cpu_percent > 80  # Overloaded
```

---

## Performance Checklist

Before production deployment:

- [ ] Run performance benchmarks
- [ ] Verify end-to-end latency <2s (95th percentile)
- [ ] Test with 10 concurrent connections
- [ ] Measure battery usage (<5% per hour)
- [ ] Profile memory usage (no leaks)
- [ ] Test PC wake-from-sleep (<10s)
- [ ] Verify STT accuracy >90% for Turkish
- [ ] Monitor database query performance
- [ ] Test network failover scenarios
- [ ] Validate WebSocket reconnection logic

---

## Troubleshooting Performance Issues

### High CPU Usage

```bash
# Identify bottleneck
top -p $(pgrep -f "python.*main.py")

# Check Whisper model
# Switch to 'base' if using 'small' or 'medium'

# Verify no infinite loops
py-spy top --pid <python_pid>
```

### High Memory Usage

```bash
# Memory leak detection
python -m memray run src/main.py
python -m memray flamegraph memray.bin

# Check for unclosed resources
# Verify all WebSocket connections are cleaned up
```

### Network Bottleneck

```bash
# Monitor bandwidth
iftop -i eth0

# Check for packet loss
ping -c 100 <android_ip>

# Verify Opus compression is enabled
```

---

Last updated: 2025-11-18
