"""
Database schema constants for PC Control Agent.

This module provides database schema definitions and constants
for the SQLite database used by the voice control system.
"""

from pathlib import Path

# Get the path to the schema file
SCHEMA_FILE = Path(__file__).parent / "schema.sql"

# Read the schema SQL
with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
    DATABASE_SCHEMA = f.read()

# Schema version for migration tracking
SCHEMA_VERSION = "1.0.0"

# Table names
TABLE_VOICE_COMMANDS = "voice_commands"
TABLE_PC_CONNECTIONS = "pc_connections"
TABLE_DEVICE_PAIRING = "device_pairing"
TABLE_COMMAND_HISTORY = "command_history"
TABLE_ACTIONS = "actions"
TABLE_AUDIT_LOG = "audit_log"

# Schema information
SCHEMA_INFO = {
    "version": SCHEMA_VERSION,
    "file": str(SCHEMA_FILE),
    "tables": [
        TABLE_VOICE_COMMANDS,
        TABLE_PC_CONNECTIONS,
        TABLE_DEVICE_PAIRING,
        TABLE_COMMAND_HISTORY,
        TABLE_ACTIONS,
        TABLE_AUDIT_LOG
    ],
    "created_at": "2025-11-18",
    "description": "PC Voice Control Agent database schema"
}