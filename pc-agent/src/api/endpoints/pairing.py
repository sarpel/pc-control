"""
Device pairing API endpoints.

This module provides REST API endpoints for secure device pairing between
Android clients and the PC backend. Implements the complete pairing flow
including QR code generation, authentication, and certificate exchange.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
import hashlib
import secrets
import json

from api.middleware import get_current_device, rate_limiter
from services.certificate_service import CertificateService
from services.connection_manager import ConnectionManager
from database.connection import get_database_connection

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/pairing", tags=["pairing"])

# Dependencies
certificate_service = CertificateService()
connection_manager = ConnectionManager()

# Constants
PAIRING_CODE_LENGTH = 6
PAIRING_EXPIRE_MINUTES = 10
MAX_PAIRING_ATTEMPTS = 3
PAIRING_ATTEMPT_WINDOW_MINUTES = 5


class PairingRequest(BaseModel):
    """Request model for initiating device pairing."""
    android_device_id: str = Field(..., min_length=1, description="Android device identifier")
    android_fingerprint: str = Field(..., min_length=1, description="Android certificate fingerprint")
    device_name: Optional[str] = Field(None, description="Human-readable device name")
    device_model: Optional[str] = Field(None, description="Device model")
    os_version: Optional[str] = Field(None, description="Android OS version")
    pairing_method: str = Field("manual", description="Pairing method: manual, qr, nfc")

    @field_validator('pairing_method')
    @classmethod
    def validate_pairing_method(cls, v):
        allowed_methods = ['manual', 'qr', 'nfc', 'network_discovery']
        if v not in allowed_methods:
            raise ValueError(f"Pairing method must be one of: {allowed_methods}")
        return v


class PairingConfirmation(BaseModel):
    """Request model for confirming device pairing."""
    pairing_id: str = Field(..., description="Pairing session identifier")
    pairing_code: str = Field(..., min_length=PAIRING_CODE_LENGTH, max_length=PAIRING_CODE_LENGTH)
    android_fingerprint: str = Field(..., description="Android certificate fingerprint")


class PairingResponse(BaseModel):
    """Response model for pairing requests."""
    success: bool
    pairing_id: Optional[str] = None
    pairing_code: Optional[str] = None
    pc_fingerprint: Optional[str] = None
    pc_name: Optional[str] = None
    pc_ip_address: Optional[str] = None
    status: Optional[str] = None
    expires_at: Optional[datetime] = None
    error_message: Optional[str] = None
    requires_qr_code: bool = False
    qr_code_data: Optional[str] = None


class AuthenticationResponse(BaseModel):
    """Response model for device authentication."""
    success: bool
    device_id: Optional[str] = None
    authentication_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    error_message: Optional[str] = None


class DeviceInfoResponse(BaseModel):
    """Response model for device information."""
    device_id: str
    device_name: str
    device_model: str
    os_version: str
    paired_at: datetime
    last_connected_at: Optional[datetime]
    connection_count: int


@router.post("/initiate", response_model=PairingResponse)
@rate_limiter(max_requests=5, window_seconds=60)
async def initiate_pairing(
    request: PairingRequest,
    http_request: Request,
    db=Depends(get_database_connection)
) -> PairingResponse:
    """
    Initiate device pairing process.

    Creates a new pairing session with unique pairing code and returns
    the necessary information for the Android client to complete pairing.
    """
    try:
        logger.info(f"Initiating pairing for device: {request.android_device_id}")

        # Check if device is already paired
        existing_pairing = await db.execute_query(
            """
            SELECT * FROM device_pairing
            WHERE android_device_id = ? AND status = 'completed'
            ORDER BY completed_at DESC LIMIT 1
            """,
            (request.android_device_id,),
            fetch_one=True
        )

        if existing_pairing:
            logger.warning(f"Device {request.android_device_id} already paired")
            return PairingResponse(
                success=False,
                error_message="Device already paired. Please remove existing pairing first."
            )

        # Generate pairing session
        pairing_id = str(uuid.uuid4())
        pairing_code = generate_pairing_code()

        # Get PC certificate fingerprint
        pc_fingerprint = certificate_service.get_server_certificate_fingerprint()
        if not pc_fingerprint:
            logger.error("Failed to get PC certificate fingerprint")
            return PairingResponse(
                success=False,
                error_message="Server certificate not available"
            )

        # Get PC information
        pc_name = await get_pc_name()
        pc_ip_address = get_client_ip(http_request)

        # Calculate expiration time
        expires_at = datetime.utcnow() + timedelta(minutes=PAIRING_EXPIRE_MINUTES)

        # Store pairing session in database
        await db.execute_query(
            """
            INSERT INTO device_pairing (
                pairing_id, android_device_id, android_fingerprint, pc_fingerprint,
                pairing_code, status, created_at, expires_at, pc_name, pc_ip_address,
                device_name, device_model, os_version, pairing_method
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pairing_id, request.android_device_id, request.android_fingerprint,
                pc_fingerprint, pairing_code, 'initiated', datetime.utcnow(), expires_at,
                pc_name, pc_ip_address, request.device_name, request.device_model,
                request.os_version, request.pairing_method
            )
        )

        # Generate QR code data if needed
        qr_code_data = None
        if request.pairing_method == 'qr':
            qr_code_data = generate_qr_code_data(pairing_id, pairing_code, pc_fingerprint)

        logger.info(f"Pairing initiated successfully: {pairing_id}")

        return PairingResponse(
            success=True,
            pairing_id=pairing_id,
            pairing_code=pairing_code,
            pc_fingerprint=pc_fingerprint,
            pc_name=pc_name,
            pc_ip_address=pc_ip_address,
            status="initiated",
            expires_at=expires_at,
            requires_qr_code=request.pairing_method == 'qr',
            qr_code_data=qr_code_data
        )

    except Exception as e:
        logger.error(f"Error initiating pairing: {e}")
        return PairingResponse(
            success=False,
            error_message=f"Failed to initiate pairing: {str(e)}"
        )


@router.post("/confirm", response_model=PairingResponse)
@rate_limiter(max_requests=10, window_seconds=60)
async def confirm_pairing(
    request: PairingConfirmation,
    db=Depends(get_database_connection)
) -> PairingResponse:
    """
    Confirm device pairing with pairing code.

    Validates the pairing code and completes the secure pairing process
    by exchanging certificates and generating authentication tokens.
    """
    try:
        logger.info(f"Confirming pairing: {request.pairing_id}")

        # Get pairing session
        pairing = await db.execute_query(
            """
            SELECT * FROM device_pairing
            WHERE pairing_id = ? AND status IN ('initiated', 'awaiting_confirmation')
            """,
            (request.pairing_id,),
            fetch_one=True
        )

        if not pairing:
            logger.warning(f"Invalid pairing session: {request.pairing_id}")
            return PairingResponse(
                success=False,
                error_message="Invalid or expired pairing session"
            )

        # Check if pairing has expired
        if datetime.utcnow() > pairing['expires_at']:
            await db.execute_query(
                "UPDATE device_pairing SET status = 'expired' WHERE pairing_id = ?",
                (request.pairing_id,)
            )
            return PairingResponse(
                success=False,
                error_message="Pairing session has expired"
            )

        # Validate pairing code
        if pairing['pairing_code'] != request.pairing_code:
            logger.warning(f"Invalid pairing code for {request.pairing_id}")
            # Increment attempt count
            await db.execute_query(
                "UPDATE device_pairing SET status = 'failed' WHERE pairing_id = ?",
                (request.pairing_id,)
            )
            return PairingResponse(
                success=False,
                error_message="Invalid pairing code"
            )

        # Validate Android fingerprint
        if pairing['android_fingerprint'] != request.android_fingerprint:
            logger.warning(f"Fingerprint mismatch for {request.pairing_id}")
            return PairingResponse(
                success=False,
                error_message="Device fingerprint mismatch"
            )

        # Generate authentication token
        auth_token = generate_authentication_token(pairing['android_device_id'])

        # Update pairing session
        await db.execute_query(
            """
            UPDATE device_pairing
            SET status = 'completed', authentication_token = ?, completed_at = ?
            WHERE pairing_id = ?
            """,
            (auth_token, datetime.utcnow(), request.pairing_id)
        )

        # Create device connection record
        connection_id = str(uuid.uuid4())
        await db.execute_query(
            """
            INSERT INTO pc_connections (
                connection_id, device_id, pc_name, pc_ip_address, pc_mac_address,
                status, last_connected_at, connection_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                connection_id, pairing['android_device_id'], pairing['pc_name'],
                pairing['pc_ip_address'], get_pc_mac_address(),
                'authenticated', datetime.utcnow(), 1
            )
        )

        logger.info(f"Pairing completed successfully: {request.pairing_id}")

        return PairingResponse(
            success=True,
            pairing_id=request.pairing_id,
            pc_fingerprint=pairing['pc_fingerprint'],
            pc_name=pairing['pc_name'],
            pc_ip_address=pairing['pc_ip_address'],
            status="completed",
            authentication_token=auth_token
        )

    except Exception as e:
        logger.error(f"Error confirming pairing: {e}")
        return PairingResponse(
            success=False,
            error_message=f"Failed to confirm pairing: {str(e)}"
        )


@router.post("/authenticate", response_model=AuthenticationResponse)
@rate_limiter(max_requests=20, window_seconds=60)
async def authenticate_device(
    request: Request,
    db=Depends(get_database_connection)
) -> AuthenticationResponse:
    """
    Authenticate device using certificate-based mutual TLS.

    This endpoint validates the client certificate from mTLS and
    provides an authentication token for subsequent API calls.
    """
    try:
        # Extract client certificate from mTLS
        client_cert = request.client.ssl_object.get_peer_certificate()
        if not client_cert:
            return AuthenticationResponse(
                success=False,
                error_message="Client certificate required"
            )

        # Get certificate fingerprint
        cert_fingerprint = get_certificate_fingerprint(client_cert)

        # Find paired device
        pairing = await db.execute_query(
            """
            SELECT * FROM device_pairing
            WHERE android_fingerprint = ? AND status = 'completed'
            ORDER BY completed_at DESC LIMIT 1
            """,
            (cert_fingerprint,),
            fetch_one=True
        )

        if not pairing:
            return AuthenticationResponse(
                success=False,
                error_message="Device not paired or invalid certificate"
            )

        # Generate new authentication token
        auth_token = generate_authentication_token(pairing['android_device_id'])

        # Update last authentication
        await db.execute_query(
            """
            UPDATE device_pairing
            SET authentication_token = ?, updated_at = ?
            WHERE pairing_id = ?
            """,
            (auth_token, datetime.utcnow(), pairing['pairing_id'])
        )

        # Calculate token expiration
        expires_at = datetime.utcnow() + timedelta(hours=24)

        logger.info(f"Device authenticated: {pairing['android_device_id']}")

        return AuthenticationResponse(
            success=True,
            device_id=pairing['android_device_id'],
            authentication_token=auth_token,
            expires_at=expires_at
        )

    except Exception as e:
        logger.error(f"Error authenticating device: {e}")
        return AuthenticationResponse(
            success=False,
            error_message=f"Authentication failed: {str(e)}"
        )


@router.get("/status/{pairing_id}")
async def get_pairing_status(
    pairing_id: str,
    db=Depends(get_database_connection)
) -> Dict[str, Any]:
    """Get status of a pairing session."""
    try:
        pairing = await db.execute_query(
            "SELECT * FROM device_pairing WHERE pairing_id = ?",
            (pairing_id,),
            fetch_one=True
        )

        if not pairing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pairing session not found"
            )

        return {
            "pairing_id": pairing_id,
            "status": pairing['status'],
            "created_at": pairing['created_at'],
            "expires_at": pairing['expires_at'],
            "completed_at": pairing['completed_at'],
            "device_name": pairing['device_name'],
            "is_expired": datetime.utcnow() > pairing['expires_at']
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pairing status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get pairing status"
        )


@router.get("/devices", response_model=List[DeviceInfoResponse])
async def get_paired_devices(
    current_device: Dict = Depends(get_current_device),
    db=Depends(get_database_connection)
) -> List[DeviceInfoResponse]:
    """Get list of paired devices."""
    try:
        devices = await db.execute_query(
            """
            SELECT
                dp.android_device_id,
                dp.device_name,
                dp.device_model,
                dp.os_version,
                dp.created_at as paired_at,
                pc.last_connected_at,
                pc.connection_count
            FROM device_pairing dp
            LEFT JOIN pc_connections pc ON dp.android_device_id = pc.device_id
            WHERE dp.status = 'completed'
            ORDER BY dp.completed_at DESC
            """,
            fetch_all=True
        )

        return [
            DeviceInfoResponse(
                device_id=device['android_device_id'],
                device_name=device['device_name'] or "Unknown Device",
                device_model=device['device_model'] or "Unknown Model",
                os_version=device['os_version'] or "Unknown",
                paired_at=device['paired_at'],
                last_connected_at=device['last_connected_at'],
                connection_count=device['connection_count'] or 0
            )
            for device in devices
        ]

    except Exception as e:
        logger.error(f"Error getting paired devices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get paired devices"
        )


@router.delete("/devices/{device_id}")
async def remove_paired_device(
    device_id: str,
    current_device: Dict = Depends(get_current_device),
    db=Depends(get_database_connection)
) -> Dict[str, Any]:
    """Remove a paired device."""
    try:
        # Check if device exists
        pairing = await db.execute_query(
            "SELECT * FROM device_pairing WHERE android_device_id = ? AND status = 'completed'",
            (device_id,),
            fetch_one=True
        )

        if not pairing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found"
            )

        # Remove device connections
        await db.execute_query(
            "DELETE FROM pc_connections WHERE device_id = ?",
            (device_id,)
        )

        # Mark pairing as cancelled
        await db.execute_query(
            "UPDATE device_pairing SET status = 'cancelled' WHERE android_device_id = ?",
            (device_id,)
        )

        logger.info(f"Device removed: {device_id}")

        return {"success": True, "message": "Device removed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing device: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove device"
        )


# Helper functions

def generate_pairing_code() -> str:
    """Generate a 6-digit numeric pairing code."""
    return f"{secrets.randbelow(1000000):06d}"


def generate_authentication_token(device_id: str) -> str:
    """Generate a JWT authentication token for the device."""
    # This would use a proper JWT library in production
    payload = {
        "device_id": device_id,
        "exp": datetime.utcnow() + timedelta(hours=24),
        "iat": datetime.utcnow(),
        "type": "device_auth"
    }
    # For now, return a simple token (implement proper JWT in production)
    token_data = f"{device_id}:{datetime.utcnow().timestamp()}:{secrets.token_urlsafe(32)}"
    return hashlib.sha256(token_data.encode()).hexdigest()


def generate_qr_code_data(pairing_id: str, pairing_code: str, pc_fingerprint: str) -> str:
    """Generate QR code data for pairing."""
    qr_data = {
        "type": "pc_control_pairing",
        "pairing_id": pairing_id,
        "pairing_code": pairing_code,
        "pc_fingerprint": pc_fingerprint,
        "version": "1.0"
    }
    return json.dumps(qr_data)


async def get_pc_name() -> str:
    """Get the PC name."""
    try:
        import platform
        return platform.node()
    except Exception:
        return "PC Controller"


def get_client_ip(request: Request) -> str:
    """Get client IP address."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host


def get_pc_mac_address() -> str:
    """Get PC MAC address."""
    try:
        import uuid
        mac = uuid.getnode()
        return ':'.join([f'{(mac >> 8*i) & 0xff:02x}' for i in range(6)][::-1])
    except Exception:
        return "00:00:00:00:00:00"


def get_certificate_fingerprint(certificate) -> str:
    """Get SHA-256 fingerprint of certificate."""
    try:
        # This would use proper certificate parsing
        # For now, return a placeholder
        cert_data = str(certificate)
        return hashlib.sha256(cert_data.encode()).hexdigest()
    except Exception:
        return ""