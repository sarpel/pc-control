-- PC Control Agent Database Schema
-- SQLite database schema for voice command processing and device management

-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- Voice Commands Table
-- Stores transcribed voice commands from users
CREATE TABLE IF NOT EXISTS voice_commands (
    command_id TEXT PRIMARY KEY,
    audio_data BLOB NOT NULL,           -- Opus-encoded audio data (temporary, may be cleaned up)
    transcription TEXT NOT NULL,        -- Transcribed text in Turkish
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    timestamp DATETIME NOT NULL,
    duration_ms INTEGER NOT NULL CHECK (duration_ms >= 100 AND duration_ms <= 30000),
    language TEXT NOT NULL DEFAULT 'tr',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'processing', 'executing', 'completed', 'failed')
    ),
    device_id TEXT NOT NULL,           -- Foreign key to device_pairing
    session_id TEXT,                    -- WebSocket session identifier
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- PC Connections Table
-- Stores connection information for paired devices
CREATE TABLE IF NOT EXISTS pc_connections (
    connection_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,           -- Foreign key to device_pairing
    pc_ip_address TEXT NOT NULL,
    pc_mac_address TEXT NOT NULL,
    pc_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'disconnected' CHECK (
        status IN ('disconnected', 'connecting', 'connected', 'authenticated', 'error')
    ),
    latency_ms INTEGER CHECK (latency_ms >= 1 AND latency_ms <= 10000),
    last_heartbeat DATETIME,
    authentication_token TEXT,         -- JWT token for the session
    certificate_fingerprint TEXT,     -- Device certificate fingerprint
    connection_count INTEGER DEFAULT 0, -- Number of times connected
    total_connection_time_ms INTEGER DEFAULT 0, -- Total connection time
    last_connected_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Actions Table
-- Stores actions executed for voice commands
CREATE TABLE IF NOT EXISTS actions (
    action_id TEXT PRIMARY KEY,
    command_id TEXT NOT NULL,
    action_type TEXT NOT NULL CHECK (
        action_type IN (
            'system_launch', 'system_volume', 'system_file_find',
            'system_info', 'system_file_delete', 'browser_navigate',
            'browser_search', 'browser_extract', 'browser_interact'
        )
    ),
    parameters TEXT NOT NULL,          -- JSON string of action parameters
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'executing', 'completed', 'failed', 'requires_confirmation')
    ),
    result TEXT,                       -- JSON string of action result
    error_message TEXT,
    execution_time_ms INTEGER CHECK (execution_time_ms >= 1 AND execution_time_ms <= 60000),
    started_at DATETIME,
    completed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (command_id) REFERENCES voice_commands (command_id) ON DELETE CASCADE
);

-- Device Pairing Table
-- Stores pairing information for security setup
CREATE TABLE IF NOT EXISTS device_pairing (
    pairing_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,           -- Renamed from android_device_id for consistency
    android_fingerprint TEXT,          -- Made optional
    pc_fingerprint TEXT,               -- Made optional
    pairing_code TEXT NOT NULL CHECK (
        pairing_code GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]'
    ),
    status TEXT NOT NULL DEFAULT 'initiated' CHECK (
        status IN ('initiated', 'awaiting_confirmation', 'completed', 'failed', 'expired', 'active', 'revoked')
    ),
    created_at DATETIME NOT NULL,
    completed_at DATETIME,
    pc_name TEXT,
    pc_ip_address TEXT,
    expires_at DATETIME NOT NULL,      -- 10 minutes from creation
    authentication_token TEXT,         -- Generated JWT token for device
    device_name TEXT,
    device_model TEXT,
    os_version TEXT,
    pairing_method TEXT DEFAULT 'manual', -- 'manual', 'qr', 'nfc'
    created_by TEXT DEFAULT 'pc_agent',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Additional fields used by PairingService
    ca_certificate TEXT,
    client_certificate TEXT,
    auth_token_hash TEXT,
    token_expires_at DATETIME,
    paired_at DATETIME
);

-- Command History Table
-- Stores recent command history for context (retained for 10 minutes or 5 commands)
CREATE TABLE IF NOT EXISTS command_history (
    history_id TEXT PRIMARY KEY,
    command_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    transcription TEXT NOT NULL,
    action_summary TEXT NOT NULL,
    success BOOLEAN NOT NULL,
    execution_time_ms INTEGER,
    timestamp DATETIME NOT NULL,
    expires_at DATETIME NOT NULL,       -- 10 minutes from creation
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (command_id) REFERENCES voice_commands (command_id) ON DELETE CASCADE
);

-- Connection Sessions Table
-- Tracks individual WebSocket connection sessions
CREATE TABLE IF NOT EXISTS connection_sessions (
    session_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    connection_id TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (
        status IN ('active', 'closed', 'error', 'timeout')
    ),
    started_at DATETIME NOT NULL,
    ended_at DATETIME,
    duration_ms INTEGER,
    messages_sent INTEGER DEFAULT 0,
    messages_received INTEGER DEFAULT 0,
    audio_bytes_received INTEGER DEFAULT 0,
    last_activity DATETIME,
    client_info TEXT,                   -- JSON with client information
    error_details TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (device_id) REFERENCES device_pairing (device_id)
);

-- System Audit Log Table
-- Tracks all security-relevant events
CREATE TABLE IF NOT EXISTS audit_log (
    log_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL CHECK (
        event_type IN (
            'device_pairing', 'connection_established', 'connection_lost',
            'authentication_success', 'authentication_failure',
            'command_executed', 'command_failed', 'security_violation',
            'certificate_revoked', 'configuration_changed'
        )
    ),
    device_id TEXT,
    user_id TEXT,                       -- May be null for system events
    event_data TEXT,                     -- JSON with event details
    ip_address TEXT,
    user_agent TEXT,
    timestamp DATETIME NOT NULL,
    severity TEXT DEFAULT 'info' CHECK (
        severity IN ('debug', 'info', 'warning', 'error', 'critical')
    ),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Audit Logs Table
-- Stores security audit logs
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    event_type TEXT NOT NULL,
    device_id TEXT NOT NULL,
    user_id TEXT,
    ip_address TEXT,
    user_agent TEXT,
    details TEXT,                      -- JSON string of event details
    severity TEXT NOT NULL DEFAULT 'info',
    security_related BOOLEAN DEFAULT 0,
    session_id TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Performance Metrics Table
-- Stores performance and usage metrics
CREATE TABLE IF NOT EXISTS performance_metrics (
    metric_id TEXT PRIMARY KEY,
    metric_type TEXT NOT NULL CHECK (
        metric_type IN (
            'command_latency', 'audio_processing_time', 'llm_response_time',
            'database_query_time', 'websocket_message_time', 'system_resource_usage'
        )
    ),
    device_id TEXT,
    value REAL NOT NULL,
    unit TEXT,                          -- 'ms', 'percentage', 'count', etc.
    metadata TEXT,                       -- JSON with additional context
    timestamp DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Error Log Table
-- Stores application errors and exceptions
CREATE TABLE IF NOT EXISTS error_log (
    error_id TEXT PRIMARY KEY,
    error_type TEXT NOT NULL CHECK (
        error_type IN (
            'authentication_error', 'connection_error', 'processing_error',
            'system_error', 'user_error', 'network_error', 'timeout_error'
        )
    ),
    error_code TEXT,
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    device_id TEXT,
    session_id TEXT,
    user_data TEXT,                      -- JSON with relevant user context
    timestamp DATETIME NOT NULL,
    resolved BOOLEAN DEFAULT FALSE,
    resolution_notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Configuration Table
-- Stores application configuration settings
CREATE TABLE IF NOT EXISTS configuration (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    category TEXT DEFAULT 'general',
    is_sensitive BOOLEAN DEFAULT FALSE,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT DEFAULT 'system'
);

-- Indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_voice_commands_timestamp ON voice_commands (timestamp);
CREATE INDEX IF NOT EXISTS idx_voice_commands_device_id ON voice_commands (device_id);
CREATE INDEX IF NOT EXISTS idx_voice_commands_status ON voice_commands (status);

CREATE INDEX IF NOT EXISTS idx_pc_connections_device_id ON pc_connections (device_id);
CREATE INDEX IF NOT EXISTS idx_pc_connections_status ON pc_connections (status);
CREATE INDEX IF NOT EXISTS idx_pc_connections_last_heartbeat ON pc_connections (last_heartbeat);

CREATE INDEX IF NOT EXISTS idx_actions_command_id ON actions (command_id);
CREATE INDEX IF NOT EXISTS idx_actions_status ON actions (status);
CREATE INDEX IF NOT EXISTS idx_actions_action_type ON actions (action_type);
CREATE INDEX IF NOT EXISTS idx_actions_created_at ON actions (created_at);

CREATE INDEX IF NOT EXISTS idx_device_pairing_device_id ON device_pairing (device_id);
CREATE INDEX IF NOT EXISTS idx_device_pairing_status ON device_pairing (status);
CREATE INDEX IF NOT EXISTS idx_device_pairing_expires_at ON device_pairing (expires_at);

CREATE INDEX IF NOT EXISTS idx_command_history_device_id ON command_history (device_id);
CREATE INDEX IF NOT EXISTS idx_command_history_timestamp ON command_history (timestamp);
CREATE INDEX IF NOT EXISTS idx_command_history_expires_at ON command_history (expires_at);

CREATE INDEX IF NOT EXISTS idx_connection_sessions_device_id ON connection_sessions (device_id);
CREATE INDEX IF NOT EXISTS idx_connection_sessions_status ON connection_sessions (status);
CREATE INDEX IF NOT EXISTS idx_connection_sessions_started_at ON connection_sessions (started_at);

CREATE INDEX IF NOT EXISTS idx_audit_log_device_id ON audit_log (device_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_event_type ON audit_log (event_type);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log (timestamp);

CREATE INDEX IF NOT EXISTS idx_performance_metrics_timestamp ON performance_metrics (timestamp);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_device_id ON performance_metrics (device_id);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_type ON performance_metrics (metric_type);

CREATE INDEX IF NOT EXISTS idx_error_log_device_id ON error_log (device_id);
CREATE INDEX IF NOT EXISTS idx_error_log_timestamp ON error_log (timestamp);
CREATE INDEX IF NOT EXISTS idx_error_log_error_type ON error_log (error_type);

-- Triggers for automatic timestamp updates
CREATE TRIGGER IF NOT EXISTS update_voice_commands_timestamp
    AFTER UPDATE ON voice_commands
BEGIN
    UPDATE voice_commands SET updated_at = CURRENT_TIMESTAMP WHERE command_id = NEW.command_id;
END;

CREATE TRIGGER IF NOT EXISTS update_pc_connections_timestamp
    AFTER UPDATE ON pc_connections
BEGIN
    UPDATE pc_connections SET updated_at = CURRENT_TIMESTAMP WHERE connection_id = NEW.connection_id;
END;

CREATE TRIGGER IF NOT EXISTS update_actions_timestamp
    AFTER UPDATE ON actions
BEGIN
    UPDATE actions SET updated_at = CURRENT_TIMESTAMP WHERE action_id = NEW.action_id;
END;

CREATE TRIGGER IF NOT EXISTS update_device_pairing_timestamp
    AFTER UPDATE ON device_pairing
BEGIN
    UPDATE device_pairing SET updated_at = CURRENT_TIMESTAMP WHERE pairing_id = NEW.pairing_id;
END;

CREATE TRIGGER IF NOT EXISTS update_error_log_timestamp
    AFTER UPDATE ON error_log
BEGIN
    UPDATE error_log SET updated_at = CURRENT_TIMESTAMP WHERE error_id = NEW.error_id;
END;

-- Views for common queries
CREATE VIEW IF NOT EXISTS active_connections AS
SELECT
    pc.*,
    dp.device_id,
    dp.android_fingerprint,
    dp.device_name as android_device_name
FROM pc_connections pc
JOIN device_pairing dp ON pc.device_id = dp.device_id
WHERE pc.status = 'authenticated'
  AND pc.last_heartbeat > datetime('now', '-5 minutes');

CREATE VIEW IF NOT EXISTS recent_commands AS
SELECT
    vc.*,
    pc.pc_name,
    dp.device_name as android_device_name,
    COUNT(a.action_id) as action_count
FROM voice_commands vc
LEFT JOIN pc_connections pc ON vc.device_id = pc.device_id
LEFT JOIN device_pairing dp ON vc.device_id = dp.device_id
LEFT JOIN actions a ON vc.command_id = a.command_id
WHERE vc.timestamp > datetime('now', '-1 hour')
GROUP BY vc.command_id
ORDER BY vc.timestamp DESC;

CREATE VIEW IF NOT EXISTS error_summary AS
SELECT
    error_type,
    COUNT(*) as error_count,
    MAX(timestamp) as last_occurrence,
    COUNT(CASE WHEN resolved = TRUE THEN 1 END) as resolved_count
FROM error_log
WHERE timestamp > datetime('now', '-24 hours')
GROUP BY error_type
ORDER BY error_count DESC;

-- Insert initial configuration values
INSERT OR IGNORE INTO configuration (key, value, description, category) VALUES
('max_audio_size_mb', '10', 'Maximum audio file size in megabytes', 'audio'),
('command_timeout_seconds', '30', 'Default command execution timeout', 'system'),
('max_queue_length', '5', 'Maximum connection queue length', 'system'),
('session_timeout_hours', '24', 'Default session timeout duration', 'security'),
('audit_log_retention_days', '90', 'Days to retain audit logs', 'system'),
('performance_metrics_retention_days', '30', 'Days to retain performance metrics', 'system'),
('error_log_retention_days', '30', 'Days to retain error logs', 'system'),
('certificate_validation_enabled', 'true', 'Enable certificate validation', 'security'),
('rate_limit_enabled', 'true', 'Enable rate limiting', 'security'),
('debug_mode_enabled', 'false', 'Enable debug logging', 'system');