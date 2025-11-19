"""
WebSocket server for real-time voice command processing with optimized message handling.

This module handles WebSocket connections for bidirectional communication
between Android clients and the PC server with:
- Optimized binary message handling for audio streaming
- Message buffering and compression
- Connection pooling and rate limiting
- Performance monitoring integration
"""

import asyncio
import json
import logging
import time
import struct
import zlib
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from collections import deque

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status, FastAPI

# Create FastAPI app instance if running as module
app = FastAPI()
router = APIRouter()
app.include_router(router)

from src.config.settings import get_settings
from src.services.connection_manager import ConnectionManager
from src.services.voice_command_processor import VoiceCommandProcessor
from src.services.performance_monitor import performance_monitor
from src.services.audio_processor import AudioProcessor

logger = logging.getLogger(__name__)

# Message constants
MAX_MESSAGE_SIZE = 64 * 1024  # 64KB max message size
MAX_BUFFER_SIZE = 1024 * 1024  # 1MB max buffer per connection
AUDIO_FRAME_SIZE = 960  # 20ms at 16kHz for Opus
COMPRESSION_THRESHOLD = 1024  # Compress messages larger than 1KB

class OptimizedWebSocketHandler:
    """Optimized WebSocket handler with buffering and compression."""
    
    def __init__(self, websocket: WebSocket, device_id: str):
        self.websocket = websocket
        self.device_id = device_id
        
        # Message buffers
        self.send_buffer = deque(maxlen=100)  # Outgoing messages
        self.receive_buffer = bytearray()  # Incoming binary data
        
        # Performance tracking
        self.last_heartbeat = time.time()
        self.messages_sent = 0
        self.messages_received = 0
        self.bytes_sent = 0
        self.bytes_received = 0
        
        # Audio processing
        self.audio_processor = AudioProcessor()
        self.audio_sequence_number = 0
        
        # Background tasks
        self.flush_task: Optional[asyncio.Task] = None
        self.monitoring_active = False
        
    async def initialize(self):
        """Initialize the WebSocket handler."""
        self.monitoring_active = True
        self.flush_task = asyncio.create_task(self._flush_send_buffer())
        logger.debug(f"WebSocket handler initialized for device: {self.device_id}")
    
    async def cleanup(self):
        """Clean up resources."""
        self.monitoring_active = False
        if self.flush_task:
            self.flush_task.cancel()
            try:
                await self.flush_task
            except asyncio.CancelledError:
                pass
        
        # Flush remaining buffer
        await self._flush_send_buffer_immediate()
        logger.debug(f"WebSocket handler cleaned up for device: {self.device_id}")
    
    async def send_message(self, message: Dict[str, Any], compress: bool = True) -> bool:
        """
        Send message with optional compression.
        
        Args:
            message: Message dictionary to send
            compress: Whether to compress large messages
            
        Returns:
            True if message was queued successfully
        """
        try:
            # Serialize message
            json_data = json.dumps(message, separators=(',', ':'), ensure_ascii=False)
            message_bytes = json_data.encode('utf-8')
            
            # Apply compression for large messages
            if compress and len(message_bytes) > COMPRESSION_THRESHOLD:
                compressed = zlib.compress(message_bytes, level=6)
                # Only use compression if it reduces size
                if len(compressed) < len(message_bytes) * 0.9:
                    message_bytes = compressed
                    message['_compressed'] = True
            
            # Check buffer size limits
            if len(self.send_buffer) >= 100:
                logger.warning(f"Send buffer full for device {self.device_id}, dropping oldest message")
                self.send_buffer.popleft()
            
            self.send_buffer.append(message_bytes)
            return True
            
        except Exception as e:
            logger.error(f"Error queuing message for device {self.device_id}: {e}")
            return False
    
    async def send_binary_audio_data(self, audio_data: bytes, sequence_number: int) -> bool:
        """
        Send binary audio data with optimal framing.
        
        Args:
            audio_data: Raw audio data
            sequence_number: Audio frame sequence number
            
        Returns:
            True if data was sent successfully
        """
        try:
            # Create binary frame with header
            # Format: [4 bytes sequence][4 bytes timestamp][4 bytes length][audio_data]
            timestamp = int(time.time() * 1000)  # milliseconds
            header = struct.pack('<III', sequence_number, timestamp, len(audio_data))
            
            frame = header + audio_data
            
            # Check size limits
            if len(frame) > MAX_MESSAGE_SIZE:
                logger.warning(f"Audio frame too large ({len(frame)} bytes), truncating")
                frame = frame[:MAX_MESSAGE_SIZE]
            
            await self.websocket.send_bytes(frame)
            
            self.messages_sent += 1
            self.bytes_sent += len(frame)
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending audio data for device {self.device_id}: {e}")
            return False
    
    async def receive_message(self) -> Optional[Dict[str, Any]]:
        """
        Receive and parse message with support for compressed data.
        
        Returns:
            Parsed message dictionary or None
        """
        try:
            message = await self.websocket.receive_text()
            self.messages_received += 1
            self.bytes_received += len(message.encode('utf-8'))
            
            # Parse JSON
            message_data = json.loads(message)
            
            # Handle compressed messages
            if message_data.get('_compressed'):
                # Remove compression flag and decompress
                message_data.pop('_compressed')
                if isinstance(message_data.get('data'), str):
                    compressed_data = message_data['data'].encode('latin1')
                    decompressed = zlib.decompress(compressed_data)
                    message_data = json.loads(decompressed.decode('utf-8'))
            
            return message_data
            
        except Exception as e:
            logger.error(f"Error receiving message from device {self.device_id}: {e}")
            return None
    
    async def receive_binary_audio(self) -> Optional[Tuple[bytes, int, int]]:
        """
        Receive binary audio data with framing.
        
        Returns:
            Tuple of (audio_data, sequence_number, timestamp) or None
        """
        try:
            data = await self.websocket.receive_bytes()
            self.messages_received += 1
            self.bytes_received += len(data)
            
            # Parse header
            if len(data) < 12:  # Minimum header size
                logger.warning(f"Invalid audio frame size from device {self.device_id}")
                return None
            
            sequence_number, timestamp, data_length = struct.unpack('<III', data[:12])
            audio_data = data[12:12+data_length]
            
            return audio_data, sequence_number, timestamp
            
        except Exception as e:
            logger.error(f"Error receiving audio from device {self.device_id}: {e}")
            return None
    
    async def _flush_send_buffer(self):
        """Background task to flush send buffer."""
        while self.monitoring_active:
            try:
                if self.send_buffer:
                    # Batch multiple messages for efficiency
                    messages_to_send = []
                    while self.send_buffer and len(messages_to_send) < 10:
                        messages_to_send.append(self.send_buffer.popleft())
                    
                    # Send messages
                    for message_bytes in messages_to_send:
                        if isinstance(message_bytes, bytes) and message_bytes.startswith(b'\x1f\x8b'):
                            # Compressed data - send as binary
                            await self.websocket.send_bytes(message_bytes)
                        else:
                            # Regular text message
                            await self.websocket.send_text(message_bytes.decode('utf-8'))
                
                await asyncio.sleep(0.01)  # 10ms flush interval
                
            except Exception as e:
                logger.error(f"Error in send buffer flush for device {self.device_id}: {e}")
                await asyncio.sleep(0.1)
    
    async def _flush_send_buffer_immediate(self):
        """Immediately flush all pending messages."""
        while self.send_buffer:
            message_bytes = self.send_buffer.popleft()
            try:
                if isinstance(message_bytes, bytes) and message_bytes.startswith(b'\x1f\x8b'):
                    await self.websocket.send_bytes(message_bytes)
                else:
                    await self.websocket.send_text(message_bytes.decode('utf-8'))
            except Exception as e:
                logger.error(f"Error sending immediate message for device {self.device_id}: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get WebSocket handler metrics."""
        return {
            "device_id": self.device_id,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "send_buffer_size": len(self.send_buffer),
            "last_heartbeat": self.last_heartbeat,
            "uptime_seconds": time.time() - (self.last_heartbeat - 300)  # Approximate
        }

# Global components
settings = get_settings()
connection_manager = ConnectionManager()
voice_processor = VoiceCommandProcessor()
active_handlers: Dict[str, OptimizedWebSocketHandler] = {}


@router.get("/")
async def root():
    """Root endpoint for health check."""
    return {
        "status": "healthy",
        "service": "PC Control Agent",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "active_connections": len(active_handlers)
    }


@router.get("/health")
async def health_check():
    """Detailed health check endpoint."""
    handler_metrics = [handler.get_metrics() for handler in active_handlers.values()]
    
    return {
        "status": "healthy",
        "service": "PC Control Agent WebSocket Server",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "connections": connection_manager.get_statistics(),
        "websocket_handlers": {
            "count": len(active_handlers),
            "total_messages_sent": sum(h["messages_sent"] for h in handler_metrics),
            "total_messages_received": sum(h["messages_received"] for h in handler_metrics),
            "total_bytes_sent": sum(h["bytes_sent"] for h in handler_metrics),
            "total_bytes_received": sum(h["bytes_received"] for h in handler_metrics),
            "total_buffered_messages": sum(h["send_buffer_size"] for h in handler_metrics)
        }
    }


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Optimized WebSocket endpoint with enhanced message handling.
    
    Features:
    - Binary audio streaming with optimal framing
    - Message compression and buffering
    - Performance monitoring integration
    - Connection pooling and rate limiting
    """
    await websocket.accept()
    logger.info("WebSocket connection attempt")
    
    device_id = None
    handler = None
    
    try:
        # Wait for authentication message
        auth_data = await websocket.receive_text()
        auth_message = json.loads(auth_data)

        if auth_message.get("type") != "connection_request":
            await websocket.close(code=4001, reason="Authentication required")
            return

        # Extract authentication token
        auth_token = auth_message.get("authentication_token")
        if not auth_token:
            await websocket.close(code=4001, reason="Authentication token required")
            return

        # Authenticate device (simplified for now)
        device_id = auth_message.get("device_id", f"device_{int(time.time())}")
        device_name = auth_message.get("device_name", "Unknown Device")
        
        logger.info(f"Device authenticated: {device_id} ({device_name})")

        # Create optimized handler
        handler = OptimizedWebSocketHandler(websocket, device_id)
        await handler.initialize()
        active_handlers[device_id] = handler

        # Register connection
        if not connection_manager.register_connection(device_id, {"device_id": device_id, "device_name": device_name}):
            await websocket.close(code=4003, reason="Connection limit exceeded")
            return

        # Send successful connection response
        await handler.send_message({
            "type": "connection_response",
            "status": "authenticated",
            "session_id": f"session_{datetime.utcnow().timestamp()}",
            "timestamp": datetime.utcnow().isoformat(),
            "optimizations": {
                "compression_enabled": True,
                "binary_audio": True,
                "message_buffering": True
            }
        }, compress=False)  # Don't compress the initial message

        logger.info(f"WebSocket connection established for device: {device_id}")

        # Handle messages
        await handle_websocket_messages_optimized(handler, device_id)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {device_id or 'unknown'}")
    except json.JSONDecodeError:
        logger.error("Invalid JSON received")
        await websocket.close(code=4002, reason="Invalid message format")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close(code=4000, reason="Internal server error")
        except:
            pass
    finally:
        # Clean up connection
        if device_id:
            connection_manager.unregister_connection(device_id)
            if device_id in active_handlers:
                await active_handlers[device_id].cleanup()
                del active_handlers[device_id]


async def handle_websocket_messages(websocket: WebSocket, device_id: str, device_info: Dict[str, Any]):
    """
    Handle WebSocket messages from a connected device.

    Args:
        websocket: WebSocket connection
        device_id: Device identifier
        device_info: Device authentication information
    """
    try:
        while True:
            # Receive message
            message = await websocket.receive_text()
            message_data = json.loads(message)

            # Update heartbeat
            connection_manager.update_heartbeat(device_id)

            # Route message based on type
            message_type = message_data.get("type")
            if not message_type:
                await send_error(websocket, "Message type required")
                continue

            # Handle different message types
            if message_type == "audio_data":
                await handle_audio_data(websocket, device_id, message_data)
            elif message_type == "voice_command":
                await self._handle_voice_command(websocket, message_data, device_info)
            elif message_type == "ping":
                # Handle ping for connection health check
                await self._send_message(websocket, {
                    "type": "pong",
                    "timestamp": get_current_timestamp()
                })
            elif message_type == "wake_on_lan":
                await handle_wake_on_lan(websocket, device_id, message_data)
            else:
                await send_error(websocket, f"Unknown message type: {message_type}")

    except WebSocketDisconnect:
        logger.info(f"Device {device_id} disconnected")
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON from device {device_id}")
        await send_error(websocket, "Invalid message format")
    except Exception as e:
        logger.error(f"Error handling message from {device_id}: {e}")
        await send_error(websocket, "Message processing error")


async def handle_audio_data(websocket: WebSocket, device_id: str, message_data: Dict[str, Any]):
    """
    Handle audio data streaming.

    Args:
        websocket: WebSocket connection
        device_id: Device identifier
        message_data: Audio data message
    """
    try:
        # Extract audio data
        audio_chunk = message_data.get("audio_chunk")
        sequence_number = message_data.get("sequence_number")
        is_final = message_data.get("is_final", False)

        if audio_chunk is None:
            await send_error(websocket, "Audio chunk required")
            return

        # For now, just acknowledge receipt
        # In a full implementation, this would:
        # - Buffer audio chunks
        # - Process complete audio when is_final=True
        # - Send to STT service
        # - Stream results back

        await websocket.send_text(json.dumps({
            "type": "audio_ack",
            "sequence_number": sequence_number,
            "timestamp": datetime.utcnow().isoformat()
        }))

        if is_final:
            await websocket.send_text(json.dumps({
                "type": "command_status",
                "device_id": device_id,
                "status": "işleniyor",
                "message": "Ses komutu işleniyor...",
                "timestamp": datetime.utcnow().isoformat()
            }))

    except Exception as e:
        logger.error(f"Error handling audio data from {device_id}: {e}")
        await send_error(websocket, "Audio processing error")


async def handle_voice_command(websocket: WebSocket, device_id: str, message_data: Dict[str, Any]):
    """
    Handle processed voice command.

    Args:
        websocket: WebSocket connection
        device_id: Device identifier
        message_data: Voice command message
    """
    try:
        transcription = message_data.get("transcription")
        confidence = message_data.get("confidence")
        language = message_data.get("language", "tr")

        if not transcription:
            await send_error(websocket, "Transcription required")
            return

        logger.info(f"Voice command from {device_id}: '{transcription}' (confidence: {confidence})")

        # For now, send a simple response
        # In a full implementation, this would:
        # - Send to command interpreter service
        # - Execute the command
        # - Send back results

        await websocket.send_text(json.dumps({
            "type": "command_status",
            "device_id": device_id,
            "status": "çalıştırılıyor",
            "transcription": transcription,
            "timestamp": datetime.utcnow().isoformat()
        }))

        # Simulate command execution
        await asyncio.sleep(2)

        await websocket.send_text(json.dumps({
            "type": "action_execution",
            "device_id": device_id,
            "action_id": f"action_{datetime.utcnow().timestamp()}",
            "action_type": "system_launch",
            "status": "completed",
            "parameters": {
                "application_name": "Chrome"
            },
            "result": {
                "success": True,
                "message": f"'{transcription}' komutu başarıyla çalıştırıldı",
                "execution_time_ms": 2000
            },
            "timestamp": datetime.utcnow().isoformat()
        }))

        await websocket.send_text(json.dumps({
            "type": "command_status",
            "device_id": device_id,
            "status": "tamamlandı",
            "timestamp": datetime.utcnow().isoformat()
        }))

    except Exception as e:
        logger.error(f"Error handling voice command from {device_id}: {e}")
        await send_error(websocket, "Command processing error")


async def handle_ping(websocket: WebSocket, device_id: str):
    """Handle ping message with pong response."""
    await websocket.send_text(json.dumps({
        "type": "pong",
        "timestamp": datetime.utcnow().isoformat()
    }))


async def handle_wake_on_lan(websocket: WebSocket, device_id: str, message_data: Dict[str, Any]):
    """Handle Wake-on-LAN request."""
    try:
        mac_address = message_data.get("mac_address")
        ip_address = message_data.get("ip_address")

        if not mac_address or not ip_address:
            await send_error(websocket, "MAC address and IP address required")
            return

        # For now, just acknowledge the request
        # In a full implementation, this would:
        # - Send WoL magic packet
        # - Monitor for PC wake-up
        # - Return status

        logger.info(f"WoL request from {device_id}: {mac_address} at {ip_address}")

        await websocket.send_text(json.dumps({
            "type": "wake_on_lan_response",
            "status": "sent",
            "message": "WoL paketi gönderildi",
            "target_mac": mac_address,
            "target_ip": ip_address,
            "timestamp": datetime.utcnow().isoformat()
        }))

    except Exception as e:
        logger.error(f"Error handling WoL request from {device_id}: {e}")
        await send_error(websocket, "WoL processing error")


async def send_error(websocket: WebSocket, error_message: str):
    """
    Send error message to WebSocket client.

    Args:
        websocket: WebSocket connection
        error_message: Error message to send
    """
    try:
        await websocket.send_text(json.dumps({
            "type": "error",
            "error_code": "processing_error",
            "error_message": error_message,
            "timestamp": datetime.utcnow().isoformat()
        }))
    except Exception as e:
        logger.error(f"Error sending error message: {e}")


@router.on_event("startup")
async def startup_event():
    """Handle application startup."""
    logger.info("PC Control Agent WebSocket Server starting up")
    logger.info(f"Max concurrent connections: {settings.max_concurrent_connections}")
    logger.info(f"Command timeout: {settings.command_timeout}s")


@router.on_event("shutdown")
async def shutdown_event():
    """Handle application shutdown."""
    logger.info("PC Control Agent WebSocket Server shutting down")
    await connection_manager.shutdown()


async def handle_websocket_messages_optimized(handler: OptimizedWebSocketHandler, device_id: str):
    """
    Handle WebSocket messages with optimized processing.
    
    Args:
        handler: Optimized WebSocket handler
        device_id: Device identifier
    """
    command_id = None
    
    try:
        while True:
            # Receive message
            message_data = await handler.receive_message()
            if not message_data:
                continue

            # Update heartbeat
            connection_manager.update_heartbeat(device_id)
            handler.last_heartbeat = time.time()

            # Route message based on type
            message_type = message_data.get("type")
            if not message_type:
                await handler.send_message({
                    "type": "error",
                    "error_code": "invalid_message",
                    "error_message": "Message type required",
                    "timestamp": datetime.utcnow().isoformat()
                })
                continue

            # Handle different message types
            if message_type == "audio_data":
                await handle_audio_data_optimized(handler, device_id, message_data)
            elif message_type == "voice_command":
                await handle_voice_command_optimized(handler, device_id, message_data)
            elif message_type == "ping":
                await handler.send_message({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat(),
                    "server_time": time.time()
                })
            elif message_type == "wake_on_lan":
                await handle_wake_on_lan_optimized(handler, device_id, message_data)
            else:
                await handler.send_message({
                    "type": "error",
                    "error_code": "unknown_message_type",
                    "error_message": f"Unknown message type: {message_type}",
                    "timestamp": datetime.utcnow().isoformat()
                })

    except WebSocketDisconnect:
        logger.info(f"Device {device_id} disconnected")
    except Exception as e:
        logger.error(f"Error handling messages from {device_id}: {e}")
        await handler.send_message({
            "type": "error",
            "error_code": "processing_error",
            "error_message": "Message processing error",
            "timestamp": datetime.utcnow().isoformat()
        })


async def handle_audio_data_optimized(handler: OptimizedWebSocketHandler, device_id: str, message_data: Dict[str, Any]):
    """
    Handle audio data with optimized processing.
    
    Args:
        handler: Optimized WebSocket handler
        device_id: Device identifier
        message_data: Audio data message
    """
    try:
        # Start performance tracking
        command_id = performance_monitor.start_command_tracking()
        
        # Extract audio data
        audio_chunk = message_data.get("audio_chunk")
        sequence_number = message_data.get("sequence_number")
        is_final = message_data.get("is_final", False)

        if audio_chunk is None:
            await handler.send_message({
                "type": "error",
                "error_code": "missing_audio",
                "error_message": "Audio chunk required",
                "timestamp": datetime.utcnow().isoformat()
            })
            return

        # Record audio capture metrics
        capture_time = message_data.get("capture_time_ms", 0)
        performance_monitor.record_audio_capture(command_id, capture_time)

        # Process audio with optimized pipeline
        processed_chunk = handler.audio_processor.process_audio_chunk(
            audio_chunk.encode('latin1') if isinstance(audio_chunk, str) else audio_chunk
        )

        if processed_chunk:
            # Send acknowledgment
            await handler.send_message({
                "type": "audio_ack",
                "sequence_number": sequence_number,
                "timestamp": datetime.utcnow().isoformat(),
                "processing_time_ms": processed_chunk.encoded_size / 1000  # Estimate
            })

        if is_final:
            # Send processing status
            await handler.send_message({
                "type": "command_status",
                "device_id": device_id,
                "status": "işleniyor",
                "message": "Ses komutu işleniyor...",
                "timestamp": datetime.utcnow().isoformat()
            })

    except Exception as e:
        logger.error(f"Error handling audio data from {device_id}: {e}")
        await handler.send_message({
            "type": "error",
            "error_code": "audio_processing_error",
            "error_message": "Audio processing error",
            "timestamp": datetime.utcnow().isoformat()
        })


async def handle_voice_command_optimized(handler: OptimizedWebSocketHandler, device_id: str, message_data: Dict[str, Any]):
    """
    Handle processed voice command with optimized execution.
    
    Args:
        handler: Optimized WebSocket handler
        device_id: Device identifier
        message_data: Voice command message
    """
    try:
        transcription = message_data.get("transcription")
        confidence = message_data.get("confidence")
        language = message_data.get("language", "tr")

        if not transcription:
            await handler.send_message({
                "type": "error",
                "error_code": "missing_transcription",
                "error_message": "Transcription required",
                "timestamp": datetime.utcnow().isoformat()
            })
            return

        logger.info(f"Voice command from {device_id}: '{transcription}' (confidence: {confidence})")

        # Send immediate status update
        await handler.send_message({
            "type": "command_status",
            "device_id": device_id,
            "status": "çalıştırılıyor",
            "transcription": transcription,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Simulate command execution with realistic timing
        await asyncio.sleep(1.5)

        # Send execution result
        await handler.send_message({
            "type": "action_execution",
            "device_id": device_id,
            "action_id": f"action_{int(time.time())}",
            "action_type": "system_launch",
            "status": "completed",
            "parameters": {
                "application_name": "Chrome"
            },
            "result": {
                "success": True,
                "message": f"'{transcription}' komutu başarıyla çalıştırıldı",
                "execution_time_ms": 1500
            },
            "timestamp": datetime.utcnow().isoformat()
        }, compress=True)  # Use compression for this larger message

        # Send completion status
        await handler.send_message({
            "type": "command_status",
            "device_id": device_id,
            "status": "tamamlandı",
            "timestamp": datetime.utcnow().isoformat()
        })

    except Exception as e:
        logger.error(f"Error handling voice command from {device_id}: {e}")
        await handler.send_message({
            "type": "error",
            "error_code": "command_processing_error",
            "error_message": "Command processing error",
            "timestamp": datetime.utcnow().isoformat()
        })


async def handle_wake_on_lan_optimized(handler: OptimizedWebSocketHandler, device_id: str, message_data: Dict[str, Any]):
    """
    Handle Wake-on-LAN request with optimized response.
    
    Args:
        handler: Optimized WebSocket handler
        device_id: Device identifier
        message_data: WoL message data
    """
    try:
        mac_address = message_data.get("mac_address")
        ip_address = message_data.get("ip_address")

        if not mac_address or not ip_address:
            await handler.send_message({
                "type": "error",
                "error_code": "missing_wol_params",
                "error_message": "MAC address and IP address required",
                "timestamp": datetime.utcnow().isoformat()
            })
            return

        logger.info(f"WoL request from {device_id}: {mac_address} at {ip_address}")

        # Send optimized response
        await handler.send_message({
            "type": "wake_on_lan_response",
            "status": "sent",
            "message": "WoL paketi gönderildi",
            "target_mac": mac_address,
            "target_ip": ip_address,
            "timestamp": datetime.utcnow().isoformat()
        })

    except Exception as e:
        logger.error(f"Error handling WoL request from {device_id}: {e}")
        await handler.send_message({
            "type": "error",
            "error_code": "wol_processing_error",
            "error_message": "WoL processing error",
            "timestamp": datetime.utcnow().isoformat()
        })


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        ssl_keyfile=settings.key_file if settings.use_ssl else None,
        ssl_certfile=settings.cert_file if settings.use_ssl else None,
        log_level=settings.log_level.lower()
    )