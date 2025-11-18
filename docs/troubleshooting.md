# Troubleshooting Guide

## Common Issues and Solutions

### Connection Issues

#### Android App Cannot Connect to PC

**Symptoms:**
- "Bağlantı kurulamadı" (Connection failed) error
- Timeout after 10 seconds
- "PC bulunamadı" (PC not found)

**Solutions:**

1. **Verify both devices on same network**
   ```bash
   # On PC
   ipconfig
   # Note the IPv4 address (e.g., 192.168.1.100)

   # On Android
   # Settings → Wi-Fi → Check connected network matches PC
   ```

2. **Check Windows Firewall**
   ```powershell
   # Run as Administrator
   netsh advfirewall firewall add rule name="Voice Assistant" dir=in action=allow protocol=TCP localport=8443
   ```

3. **Verify PC service is running**
   ```bash
   cd pc-agent
   python src/main.py
   # Should see: "Server started on https://0.0.0.0:8443"
   ```

4. **Test connectivity**
   ```bash
   # From Android via adb
   adb shell ping <PC_IP_ADDRESS>
   ```

---

### Wake-on-LAN Issues

#### PC Does Not Wake from Sleep

**Symptoms:**
- "PC uyandırılamadı" (PC could not be woken) error
- WoL packet sent but PC remains sleeping

**Solutions:**

1. **Enable WoL in BIOS**
   - Restart PC → Enter BIOS (F2/Del during boot)
   - Enable "Wake on LAN" or "PME Event Wake Up"
   - Save and exit

2. **Enable WoL in Windows**
   ```powershell
   # Run as Administrator
   # Get network adapter name
   Get-NetAdapter

   # Enable WoL (replace "Ethernet" with your adapter name)
   Get-NetAdapter -Name "Ethernet" | Set-NetAdapterPowerManagement -WakeOnMagicPacket Enabled
   ```

3. **Configure power settings**
   - Control Panel → Hardware and Sound → Power Options
   - Change plan settings → Change advanced power settings
   - Sleep → Allow wake timers → Enable

4. **Test WoL manually**
   ```bash
   python scripts/test_wol.py --mac AA:BB:CC:DD:EE:FF
   ```

---

### Audio/Speech Recognition Issues

#### Poor Turkish Speech Recognition

**Symptoms:**
- Low confidence scores (<0.60)
- Incorrect transcriptions
- English words recognized as Turkish

**Solutions:**

1. **Verify Whisper language setting**
   ```python
   # In pc-agent/src/services/stt_service.py
   result = whisper.transcribe(
       audio,
       language="tr",  # Ensure Turkish is set
       task="transcribe"
   )
   ```

2. **Improve audio quality**
   - Use in quiet environment
   - Speak clearly and at normal pace
   - Hold phone 15-20cm from mouth
   - Avoid background noise

3. **Check microphone permissions**
   ```
   Android Settings → Apps → PC Voice Control → Permissions → Microphone → Allow
   ```

4. **Test audio streaming**
   ```bash
   # Monitor audio capture
   adb logcat | grep AudioCapture
   ```

---

### Certificate/mTLS Issues

#### "Sertifika geçersiz" (Invalid Certificate) Error

**Symptoms:**
- SSL/TLS handshake failures
- Certificate validation errors
- Connection rejected

**Solutions:**

1. **Regenerate certificates**
   ```bash
   cd pc-agent
   python scripts/generate_certs.py --force
   ```

2. **Import CA certificate to Android**
   ```bash
   # Push certificate to phone
   adb push pc-agent/certs/ca.crt /sdcard/Download/

   # On Android:
   # Settings → Security → Install from storage → ca.crt
   ```

3. **Verify certificate validity**
   ```bash
   openssl x509 -in pc-agent/certs/server.crt -text -noout
   # Check "Not After" date
   ```

4. **Clear Android certificate cache**
   ```
   Settings → Apps → PC Voice Control → Storage → Clear cache
   ```

---

### Performance Issues

#### High Latency (>2 seconds end-to-end)

**Symptoms:**
- Slow command execution
- Delayed responses
- "Zaman aşımı" (Timeout) errors

**Solutions:**

1. **Check network latency**
   ```bash
   # Ping test
   ping -n 10 <PC_IP_ADDRESS>
   # Should be <50ms
   ```

2. **Monitor performance metrics**
   ```bash
   # View performance logs
   tail -f pc-agent/logs/performance.log
   ```

3. **Optimize audio buffer size**
   ```python
   # In audio_processor.py
   BUFFER_SIZE_MS = 200  # Reduce if latency is high
   ```

4. **Check CPU/memory usage**
   ```powershell
   # On PC
   Get-Process python | Select-Object CPU, WorkingSet
   ```

---

### Browser Control Issues

#### Chrome DevTools Not Available

**Symptoms:**
- "Chrome not running with remote debugging"
- Browser commands fail
- "DevTools not found" error

**Solutions:**

1. **Launch Chrome with debugging**
   ```bash
   # Windows
   "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222

   # Or add to startup arguments
   ```

2. **Verify DevTools port**
   ```bash
   curl http://localhost:9222/json
   # Should return list of tabs
   ```

3. **Check firewall for port 9222**
   ```powershell
   netsh advfirewall firewall add rule name="Chrome DevTools" dir=in action=allow protocol=TCP localport=9222
   ```

---

### System Operations Issues

#### File Deletion Fails

**Symptoms:**
- "İzin reddedildi" (Permission denied)
- "Dosya bulunamadı" (File not found)
- System directory protection errors

**Solutions:**

1. **Verify file path**
   ```python
   # Use absolute paths
   "C:/Users/YourName/Documents/file.txt"  # Correct
   "Documents/file.txt"  # May fail
   ```

2. **Check file permissions**
   ```powershell
   icacls "C:\path\to\file.txt"
   ```

3. **Confirm deletion for system files**
   - System directory files require explicit confirmation
   - Set `confirmed: true` in request

4. **Run PC agent as Administrator** (if needed for system operations)
   ```powershell
   # Right-click → Run as Administrator
   python src/main.py
   ```

---

### Database Issues

#### SQLite Database Locked

**Symptoms:**
- "database is locked" errors
- Write failures
- Command history not saving

**Solutions:**

1. **Close other connections**
   ```bash
   # Kill any hanging Python processes
   taskkill /F /IM python.exe
   ```

2. **Delete lock file**
   ```bash
   rm pc-agent/data/voice_control.db-lock
   ```

3. **Enable WAL mode** (already configured, but verify)
   ```python
   # In database/connection.py
   PRAGMA journal_mode=WAL
   ```

---

### Android App Issues

#### Quick Settings Tile Not Appearing

**Symptoms:**
- Tile not visible in Quick Settings panel
- Cannot add tile to panel

**Solutions:**

1. **Add tile manually**
   - Swipe down notification panel
   - Tap edit/pencil icon
   - Drag "Voice Assistant" tile to active area

2. **Restart app**
   ```bash
   adb shell am force-stop com.pccontrol.voice
   adb shell am start -n com.pccontrol.voice/.MainActivity
   ```

3. **Reinstall app**
   ```bash
   adb uninstall com.pccontrol.voice
   adb install app/build/outputs/apk/debug/app-debug.apk
   ```

---

## Debugging Tools

### Enable Debug Logging

**PC Agent:**
```bash
# Set LOG_LEVEL in .env
LOG_LEVEL=DEBUG
```

**Android:**
```kotlin
// In Application class
if (BuildConfig.DEBUG) {
    Timber.plant(Timber.DebugTree())
}
```

### Monitor Logs

**PC Agent:**
```bash
tail -f pc-agent/logs/app.log
```

**Android:**
```bash
adb logcat -s VoiceAssistant:D
```

### Network Traffic Analysis

```bash
# Capture WebSocket traffic
wireshark -i <interface> -f "tcp port 8443"
```

---

## Getting Help

If issues persist:

1. **Check logs** for detailed error messages
2. **Review contracts** in `/specs/001-voice-pc-control/contracts/`
3. **Test with quickstart** guide: `/specs/001-voice-pc-control/quickstart.md`
4. **Report issue** with logs and reproduction steps

## Common Error Codes

| Code | Message (TR) | Meaning | Solution |
|------|--------------|---------|----------|
| 4001 | Kimlik doğrulama başarısız | Authentication failed | Check certificates |
| 4002 | Geçersiz mesaj formatı | Invalid message | Update client app |
| 4003 | İstek limiti aşıldı | Rate limit exceeded | Wait 60 seconds |
| 5000 | Sunucu hatası | Internal error | Check server logs |
| 5001 | STT işleme hatası | STT processing failed | Check Whisper setup |
| 5002 | LLM API kullanılamıyor | LLM API unavailable | Check Claude API key |

---

Last updated: 2025-11-18
