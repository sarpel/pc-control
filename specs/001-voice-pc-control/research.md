# Research Documentation: Voice-Controlled PC Assistant

**Branch**: 001-voice-pc-control | **Date**: 2025-11-18
**Purpose**: Technical research and decision documentation for Phase 0 planning

## Research Summary

This document captures research findings and decisions for the voice-controlled PC assistant implementation. The feature specification provides detailed requirements, allowing us to proceed with concrete technical decisions rather than clarification tasks.

## Technical Decisions

### 1. Architecture Pattern: Mobile + Backend Distributed System

**Decision**: Android client + Python backend with WebSocket communication
**Rationale**:
- Feature specification explicitly requires Android app (FR-020) and Windows PC control
- Natural language processing with LLM API requires server-side processing
- Real-time audio streaming demands low-latency bidirectional communication
- Security requirements (mTLS, encryption) easier to implement with dedicated backend

**Alternatives Considered**:
- Pure Android solution with embedded STT/NLP: Rejected due to complexity and LLM dependency
- Web-based client: Rejected - spec requires Android Quick Settings integration (FR-015)
- Direct PC-to-PC communication: Rejected - mobile use case is primary requirement

### 2. Audio Processing Pipeline

**Decision**: 16kHz PCM capture → Opus compression → WebSocket transmission → Whisper.cpp STT
**Rationale**:
- Constitution mandates <200ms audio buffering delay
- Opus provides optimal compression for speech at 24kbps VBR
- Whisper.cpp offers local processing avoiding cloud STT dependencies
- 16kHz standard provides good balance of quality and bandwidth

**Alternatives Considered**:
- Cloud STT (Google Speech, Azure): Rejected - adds latency and cost
- Raw PCM transmission: Rejected - bandwidth inefficient
- Higher sample rates (22kHz, 44kHz): Rejected - unnecessary for voice commands

### 3. Command Interpretation Strategy

**Decision**: Claude API with MCP tool routing for system and browser operations
**Rationale**:
- Natural language understanding in Turkish with English technical terms
- MCP provides standardized tool interface for Windows and Chrome automation
- Cloud-based LLM offers superior intent recognition vs local models
- Queue-and-retry pattern handles API unavailability (FR-004)

**Alternatives Considered**:
- Local NLP models: Rejected - insufficient Turkish support and accuracy
- Rule-based parsing: Rejected - cannot handle natural language variety
- Multiple LLM providers: Rejected - adds complexity for initial version

### 4. Security Implementation

**Decision**: mTLS with self-signed certificates + Android KeyStore + Windows Credential Manager
**Rationale**:
- Constitution requires mTLS for all communication
- Self-signed certificates sufficient for home use (per assumption #8)
- Platform-specific secure storage prevents credential leakage
- Certificate pinning prevents MITM attacks

**Alternatives Considered**:
- Pre-shared keys: Rejected - no certificate management or rotation
- JWT tokens: Rejected - insufficient for transport-layer security
- Commercial CA certificates: Rejected - unnecessary complexity for home use

### 5. PC Wake-on-LAN Implementation

**Decision**: WoL magic packet via UDP broadcast with service health check
**Rationale**:
- Feature spec requires PC wake from sleep (FR-001)
- WoL is standard mechanism supported by modern network hardware
- 15-second service timeout accommodates Windows service startup (assumption #10)
- Health check ensures service availability before command processing

**Alternatives Considered**:
- Bluetooth wake: Rejected - not supported by all hardware and out of scope
- Scheduled wake: Rejected - doesn't support on-demand wake
- Manual wake: Rejected - breaks hands-free use case

### 6. Browser Automation Strategy

**Decision**: Chrome DevTools MCP server with WebSocket control
**Rationale**:
- MCP provides standardized browser automation interface
- Chrome DevTools Protocol offers comprehensive page control
- Feature spec requires browser operations (FR-006, user story 2)
- Single browser focus reduces complexity

**Alternatives Considered**:
- Selenium WebDriver: Rejected - heavier dependency, slower startup
- Multiple browser support: Rejected - out of scope for initial version
- Direct HTTP requests: Rejected - insufficient for complex page interactions

### 7. Testing Framework Selection

**Decision**: JUnit/Kotlin Test (Android) + pytest (Python) + Contract tests
**Rationale**:
- Constitution mandates 80% test coverage and TDD workflow
- Platform-native testing tools provide best integration
- Contract testing ensures component independence
- Integration testing validates end-to-end scenarios

**Alternatives Considered**:
- Cross-platform frameworks: Rejected - add complexity without clear benefits
- Manual testing only: Rejected - violates TDD constitution principle
- UI-only testing: Rejected - insufficient for backend validation

### 8. Error Handling Strategy

**Decision**: Turkish error messages + retry queues + graceful degradation
**Rationale**:
- Feature spec requires Turkish error messages (FR-018)
- Queue-and-retry for LLM unavailability (FR-004 edge case)
- Graceful degradation maintains usability during partial failures
- Clear actionable messages reduce user frustration

**Alternatives Considered**:
- English error messages: Rejected - violates Turkish language requirement
- Silent failures: Rejected - violates transparency principle
- Immediate failure: Rejected - poor user experience for temporary issues

## Performance Optimization Strategies

### 1. Latency Reduction
- WebSocket connection reuse (no handshake per command)
- Audio streaming during capture (pipeline processing)
- Local STT processing to avoid cloud round-trip
- Optimized audio buffer sizes (200ms target)

### 2. Network Efficiency
- Opus compression for audio transmission
- Binary WebSocket frames for reduced overhead
- Connection pooling and keep-alive
- Automatic reconnection with exponential backoff

### 3. Resource Management
- In-memory audio processing (no persistent storage per FR-017)
- Command history limited to 5 items (FR-016)
- Background service lifecycle management
- Lazy loading of ML models

## Security Considerations

### 1. Authentication & Authorization
- Device pairing with certificate exchange
- Bearer token authentication (24-hour expiration)
- Single active connection enforcement
- Unauthorized connection attempt logging

### 2. Data Protection
- mTLS encryption for all network traffic
- Encrypted local credential storage
- No persistent voice audio storage
- Security audit logging (FR-012)

### 3. Input Validation
- Audio format validation
- Command sanitization
- File path validation for destructive operations
- System directory protection (FR-011)

## Technology Stack Justification

### Android Component
- **Kotlin**: Modern language with null safety and coroutines
- **Jetpack Compose**: Declarative UI with efficient updates
- **OkHttp**: Reliable WebSocket client with mTLS support
- **Android KeyStore**: Hardware-backed secure storage

### Python Component
- **FastAPI**: Modern async framework with WebSocket support
- **Whisper.cpp**: Local STT processing without cloud dependency
- **Claude API**: Superior natural language understanding
- **MCP Servers**: Standardized tool interface for system operations

### Cross-Cutting Concerns
- **WebSocket Protocol**: Real-time bidirectional communication
- **Opus Audio Codec**: Optimal speech compression
- **mTLS Encryption**: Transport-layer security
- **Structured Logging**: Observability and debugging

## Implementation Risks & Mitigations

### High Risk
- **Wake-on-LAN reliability**: Mitigate with comprehensive testing and user instructions
- **Turkish STT accuracy**: Mitigate with Whisper fine-tuning and fallback mechanisms
- **Network complexity**: Mitigate with clear setup wizard and diagnostics

### Medium Risk
- **PC service startup time**: Mitigate with auto-configuration and timeout handling
- **Audio quality issues**: Mitigate with noise suppression and error recovery
- **LLM API availability**: Mitigate with queuing and retry logic

### Low Risk
- **Android battery drain**: Mitigate with efficient background processing
- **Certificate management**: Mitigate with automated generation and renewal
- **Browser compatibility**: Mitigate with Chrome-specific implementation

## Development Timeline Considerations

### Phase 1: Core Infrastructure (Weeks 1-2)
- WebSocket communication layer
- Audio streaming pipeline
- Basic security implementation
- Project structure setup

### Phase 2: Voice Processing (Weeks 3-4)
- Whisper.cpp integration
- Command interpretation via Claude API
- Basic system operations
- Error handling implementation

### Phase 3: Advanced Features (Weeks 5-6)
- Browser automation
- PC wake-on-LAN
- Setup wizard
- Comprehensive testing

### Phase 4: Polish & Testing (Weeks 7-8)
- Performance optimization
- Security testing
- User acceptance testing
- Documentation completion

## Conclusion

The research confirms the feasibility of the voice-controlled PC assistant within the specified constraints. The technical decisions align with both the feature requirements and constitution principles. The primary challenges are Wake-on-LAN reliability and Turkish speech recognition accuracy, which can be mitigated through careful implementation and testing.

The architecture provides a solid foundation for the core voice control functionality while maintaining the simplicity and security principles required by the constitution.