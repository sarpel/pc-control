# Data Model: Voice-Controlled PC Assistant

**Feature**: 001-voice-pc-control
**Date**: 2025-11-18
**Status**: Phase 1 - Design

## Overview

This document defines the core data entities for the voice-controlled PC assistant system. Each entity represents a key concept in the domain model with fields, relationships, validation rules, and state transitions.

## Entity Definitions

### 1. Voice Command

**Purpose**: Represents a user's spoken instruction captured from Android device

**Fields**:
- `id` (UUID): Unique identifier for the command
- `audioData` (bytes, transient): Raw audio buffer in memory only (never persisted per FR-017)
- `transcribedText` (string): Text output from Whisper.cpp STT
- `confidenceScore` (float 0.0-1.0): STT confidence level
- `timestamp` (datetime): When command was captured
- `language` (enum): "tr-TR" (primary) or "en-US" (technical terms)
- `durationMs` (integer): Audio duration in milliseconds
- `status` (enum): listening | processing | executing | completed | error

**Relationships**:
- Has one `Action` (command interpretation result)
- Belongs to one `CommandHistory` (if retained)

**Validation Rules**:
- `audioData` must be 16kHz PCM format
- `transcribedText` maximum length 2500 characters (10 seconds audio)
- `confidenceScore` must be ≥0.60 (below threshold triggers retry prompt)
- `durationMs` must be between 100ms and 30000ms (30 seconds max)
- `status` transitions follow state machine (see below)

**State Transitions**:
```
listening → processing → executing → completed
                ↓             ↓
              error ←——————————┘
```

**Lifecycle**:
- Created when VAD detects voice activity
- `audioData` held in memory during processing only
- Garbage collected immediately after transcription
- Metadata retained in `CommandHistory` for 10 minutes

**Examples**:
```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "transcribedText": "Chrome'u aç",
  "confidenceScore": 0.94,
  "timestamp": "2025-11-18T15:30:45Z",
  "language": "tr-TR",
  "durationMs": 1200,
  "status": "completed"
}
```

---

### 2. PC Connection

**Purpose**: Represents the network connection state between Android phone and Windows PC

**Fields**:
- `connectionId` (UUID): Unique identifier for this connection session
- `pcIpAddress` (string): IPv4 address of PC on local network
- `pcMacAddress` (string): MAC address for Wake-on-LAN
- `pcName` (string): User-friendly PC identifier
- `connectionStatus` (enum): disconnected | connecting | connected | sleeping | error
- `latencyMs` (integer): Current round-trip latency in milliseconds
- `lastHeartbeat` (datetime): Last successful health check
- `authenticationState` (enum): unauthenticated | authenticated | expired
- `certificateFingerprint` (string): SHA-256 hash of PC's TLS certificate
- `establishedAt` (datetime): When connection was established

**Relationships**:
- Has one `DevicePairing` (security configuration)
- Has many `VoiceCommand` (commands sent over this connection)

**Validation Rules**:
- `pcIpAddress` must be valid IPv4 format
- `pcMacAddress` must be valid MAC format
- `latencyMs` thresholds trigger warnings per FR-021
- `lastHeartbeat` must be within 60 seconds
- `authenticationState` must be "authenticated" before accepting commands

---

### 3. Action

**Purpose**: Represents an operation to be performed on the PC, derived from voice command

**Fields**:
- `id` (UUID): Unique identifier for the action
- `commandId` (UUID): Reference to originating `VoiceCommand`
- `actionType` (enum): system | browser | query
- `operation` (string): Specific operation
- `parameters` (JSON): Operation-specific parameters
- `executionStatus` (enum): pending | executing | completed | failed
- `result` (JSON, nullable): Execution result or error details
- `requiresConfirmation` (boolean): True for destructive operations
- `confirmationMessage` (string, nullable): Turkish message for confirmation

**Validation Rules**:
- `requiresConfirmation` set to true for system directory file deletions per FR-011
- Execution timeout: 30 seconds
- `parameters` schema validated against operation type

---

### 4. Command History

**Purpose**: Maintains recent commands for context awareness

**Fields**:
- `id` (UUID): Unique identifier
- `commandText` (string): The transcribed command text
- `actionSummary` (string): Brief description in Turkish
- `executionResult` (enum): success | failed | cancelled
- `timestamp` (datetime): When command was executed
- `retentionExpiresAt` (datetime): 10 minutes from timestamp

**Validation Rules**:
- Maximum 5 entries per FR-016
- Automatic cleanup after 10 minutes
- FIFO queue (oldest evicted when limit reached)

---

### 5. Device Pairing

**Purpose**: One-time security setup between phone and PC

**Fields**:
- `id` (UUID): Unique identifier
- `androidDeviceId` (string): Android device identifier
- `androidDeviceName` (string): User-friendly name
- `pcIdentifier` (string): PC hostname
- `caCertificate` (string, PEM): Self-signed CA certificate
- `clientCertificate` (string, PEM): Client certificate
- `clientPrivateKey` (bytes, encrypted): Stored in Android KeyStore
- `authToken` (string, encrypted): Bearer token
- `tokenExpiresAt` (datetime): 24-hour expiration
- `pairedAt` (datetime): Pairing completion time
- `pairingStatus` (enum): active | expired | revoked

**Security Constraints**:
- Maximum 3 Android devices per PC
- Physical access required (6-digit pairing code)
- RSA 2048-bit minimum certificates
- Automatic token rotation before expiration

---

## Entity Relationships

```
DevicePairing (1) → PCConnection (1) → VoiceCommand (*) → Action (1)
                                    → CommandHistory (1..5)
```

---

## Storage Strategy

### Android
- **SharedPreferences** (encrypted): PC connection details
- **Android KeyStore** (hardware-backed): Private keys, auth tokens
- **In-Memory Only**: Audio buffers, command history

### Python (Windows)
- **SQLite Database**: Device pairings, audit log, command log (7-day retention)
- **Windows Credential Manager**: Auth token encryption key, Claude API key
- **In-Memory Only**: WebSocket connections, voice processing pipelines

---

## Data Privacy

### Voice Audio (FR-017)
- Never persisted to disk
- Memory-only buffers during processing
- Immediately garbage collected after transcription
- No cloud transmission

### Security Audit Log (FR-012)
- Authentication attempts
- Command execution events
- Certificate operations
- 90-day retention