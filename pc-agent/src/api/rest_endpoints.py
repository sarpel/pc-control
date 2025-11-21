"""
REST API endpoints for device pairing and Wake-on-LAN functionality.

Pairing Endpoints:
- POST /api/pairing/initiate - Start pairing process
- POST /api/pairing/verify - Verify pairing code and get certificates
- GET /api/pairing/status - Check pairing status
- DELETE /api/pairing/{device_id} - Revoke pairing

Wake-on-LAN Endpoints:
- POST /api/wol/send - Send Wake-on-LAN magic packet
- GET /api/wol/status - Check PC wake status
- POST /api/wol/health - Health check for PC service

All endpoints require mTLS authentication for security.
"""

from datetime import datetime
from fastapi import HTTPException, status, APIRouter, Depends
from pydantic import BaseModel, field_validator
from typing import Optional, Dict, Any
import logging

from src.services.pairing_service import PairingService
from src.services.audit_log_service import AuditLogService
from src.services.wol_service import WakeOnLANService
from src.database.connection import Database

logger = logging.getLogger(__name__)

# Create routers
pairing_router = APIRouter(prefix="/api/pairing", tags=["pairing"])
wol_router = APIRouter(prefix="/api/wol", tags=["wake-on-lan"])

# Global service instances
from src.database.connection import get_database_connection
from src.services.certificate_service import CertificateService

_db = get_database_connection()
_cert_service = CertificateService()
wol_service = WakeOnLANService()
pairing_service_instance = PairingService(_db, _cert_service)
audit_service_instance = AuditLogService(_db)


# Request/Response Models
class PairingInitiateRequest(BaseModel):
    """Request model for pairing initiation."""
    device_name: str
    device_id: str

    @field_validator('device_name')
    @classmethod
    def validate_device_name(cls, v):
        if not v or len(v.strip()) < 1:
            raise ValueError('device_name cannot be empty')
        if len(v) > 100:
            raise ValueError('device_name too long (max 100 characters)')
        return v.strip()

    @field_validator('device_id')
    @classmethod
    def validate_device_id(cls, v):
        if not v or len(v.strip()) < 1:
            raise ValueError('device_id cannot be empty')
        if len(v) > 200:
            raise ValueError('device_id too long (max 200 characters)')
        return v.strip()


class PairingInitiateResponse(BaseModel):
    """Response model for pairing initiation."""
    pairing_id: str
    pairing_code: str
    expires_in_seconds: int


class PairingVerifyRequest(BaseModel):
    """Request model for pairing verification."""
    pairing_id: str
    pairing_code: str
    device_id: str

    @field_validator('pairing_code')
    @classmethod
    def validate_pairing_code(cls, v):
        if not v or len(v) != 6 or not v.isdigit():
            raise ValueError('pairing_code must be 6 digits')
        return v


class PairingVerifyResponse(BaseModel):
    """Response model for pairing verification."""
    ca_certificate: str
    client_certificate: str
    client_private_key: str
    auth_token: str
    token_expires_at: str


class PairingStatusResponse(BaseModel):
    """Response model for pairing status."""
    status: str
    device_name: str
    device_id: str
    paired_at: Optional[str]
    token_expires_at: Optional[str]


# WoL Request/Response Models
class WoLSendRequest(BaseModel):
    """Request model for Wake-on-LAN packet sending."""
    mac_address: str
    ip_address: str
    broadcast_address: Optional[str] = None

    @field_validator('mac_address')
    @classmethod
    def validate_mac_address(cls, v):
        # Basic MAC address format validation
        import re
        mac_pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
        if not re.match(mac_pattern, v):
            raise ValueError('Invalid MAC address format')
        return v.upper()

    @field_validator('ip_address')
    @classmethod
    def validate_ip_address(cls, v):
        import socket
        try:
            socket.inet_aton(v)
        except socket.error:
            raise ValueError('Invalid IP address format')
        return v


class WoLSendResponse(BaseModel):
    """Response model for Wake-on-LAN packet sending."""
    success: bool
    message: str
    sent_at: float
    retry_count: int
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None


class WoLStatusResponse(BaseModel):
    """Response model for PC status check."""
    pc_status: str  # "online", "offline", "waking"
    ip_address: str
    last_checked: float
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class WoLHealthResponse(BaseModel):
    """Response model for WoL service health check."""
    service_status: str  # "healthy", "degraded", "unhealthy"
    timestamp: float
    version: str
    capabilities: Dict[str, Any]


# Dependency injection
async def get_pairing_service(db: Database) -> PairingService:
    """Get pairing service instance."""
    from services.certificate_service import CertificateService
    cert_service = CertificateService()
    return PairingService(db, cert_service)


async def get_audit_service(db: Database) -> AuditLogService:
    """Get audit log service instance."""
    return AuditLogService(db)


# Endpoint implementations
@pairing_router.post(
    "/initiate",
    response_model=PairingInitiateResponse,
    status_code=status.HTTP_200_OK,
    summary="Initiate device pairing",
    description="Start the pairing process and return a 6-digit verification code valid for 5 minutes."
)
async def initiate_pairing(
    request: PairingInitiateRequest,
    # Removed unused param - using pairing_service_instance
    # Removed unused param - using audit_service_instance
):
    """
    Initiate pairing process for an Android device.

    Returns:
        6-digit pairing code and session details
    """
    try:
        # Initiate pairing
        result = await pairing_service_instance.initiate_pairing(
            device_name=request.device_name,
            device_id=request.device_id
        )

        # Log audit event
        await audit_service_instance.log_event(
            event_type="pairing_initiated",
            device_id=request.device_id,
            details={
                "device_name": request.device_name,
                "pairing_id": result["pairing_id"],
                "ip_address": "client_ip",  # Would be populated by middleware
                "user_agent": "client_ua"  # Would be populated by middleware
            }
        )

        logger.info(f"Pairing initiated: {request.device_id} -> {result['pairing_id']}")

        return PairingInitiateResponse(**result)

    except ValueError as e:
        # Log failed attempt
        await audit_service_instance.log_event(
            event_type="pairing_initiate_failed",
            device_id=request.device_id,
            details={
                "device_name": request.device_name,
                "error": str(e),
                "reason": "validation_failed"
            }
        )

        if "already paired" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e)
            )
        elif "Maximum" in str(e):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

    except Exception as e:
        logger.error(f"Unexpected error in initiate_pairing: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@pairing_router.post(
    "/verify",
    response_model=PairingVerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify pairing code",
    description="Verify the 6-digit pairing code and exchange certificates."
)
async def verify_pairing(
    request: PairingVerifyRequest,
    # Removed unused param - using pairing_service_instance
    # Removed unused param - using audit_service_instance
):
    """
    Verify pairing code and complete device pairing.

    Returns:
        Certificates and auth token for secure communication
    """
    try:
        # Verify pairing
        result = await pairing_service_instance.verify_pairing(
            pairing_id=request.pairing_id,
            pairing_code=request.pairing_code,
            device_id=request.device_id
        )

        # Log successful verification
        await audit_service_instance.log_event(
            event_type="pairing_verified",
            device_id=request.device_id,
            details={
                "pairing_id": request.pairing_id,
                "success": True,
                "ip_address": "client_ip"
            }
        )

        logger.info(f"Pairing verified: {request.device_id} -> {request.pairing_id}")

        return PairingVerifyResponse(**result)

    except ValueError as e:
        # Log failed verification
        await audit_service_instance.log_event(
            event_type="pairing_verification_failed",
            device_id=request.device_id,
            details={
                "pairing_id": request.pairing_id,
                "error": str(e),
                "reason": "session_not_found_or_expired"
            }
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

    except PermissionError as e:
        # Log invalid code attempt
        await audit_service_instance.log_event(
            event_type="pairing_verification_failed",
            device_id=request.device_id,
            details={
                "pairing_id": request.pairing_id,
                "error": str(e),
                "reason": "invalid_pairing_code",
                "security": True  # Flag for security monitoring
            }
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid pairing code"
        )

    except Exception as e:
        logger.error(f"Unexpected error in verify_pairing: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@pairing_router.get(
    "/status",
    response_model=PairingStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get pairing status",
    description="Check the pairing status of a device."
)
async def get_pairing_status(
    device_id: str,
    # Removed unused param - using pairing_service_instance
    # Removed unused param - using audit_service_instance
):
    """
    Get pairing status for a specific device.

    Returns:
        Current pairing status and device information
    """
    try:
        result = await pairing_service_instance.get_pairing_status(device_id)

        # Log status check (lower severity)
        await audit_service_instance.log_event(
            event_type="pairing_status_checked",
            device_id=device_id,
            details={
                "status": result["status"],
                "ip_address": "client_ip"
            },
            severity="info"
        )

        return PairingStatusResponse(**result)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except Exception as e:
        logger.error(f"Unexpected error in get_pairing_status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@pairing_router.delete(
    "/{device_id}",
    status_code=status.HTTP_200_OK,
    summary="Revoke device pairing",
    description="Revoke pairing for a specific device."
)
async def revoke_pairing(
    device_id: str,
    # Removed unused param - using pairing_service_instance
    # Removed unused param - using audit_service_instance
):
    """
    Revoke pairing for a device.

    Args:
        device_id: Device identifier to revoke

    Returns:
        Success message
    """
    try:
        # Get device info before revoking for logging
        device_info = await pairing_service_instance.get_pairing_status(device_id)

        # Revoke pairing
        await pairing_service_instance.revoke_pairing(device_id)

        # Log revocation
        await audit_service_instance.log_event(
            event_type="pairing_revoked",
            device_id=device_id,
            details={
                "device_name": device_info.get("device_name", "unknown"),
                "status_before": device_info.get("status", "unknown"),
                "ip_address": "client_ip",
                "security": True
            }
        )

        logger.info(f"Pairing revoked: {device_id}")

        return {"message": f"Pairing revoked for device {device_id}"}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except Exception as e:
        logger.error(f"Unexpected error in revoke_pairing: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@pairing_router.post(
    "/rotate-token/{device_id}",
    status_code=status.HTTP_200_OK,
    summary="Rotate auth token",
    description="Rotate auth token before expiration."
)
async def rotate_auth_token(
    device_id: str,
    # Removed unused param - using pairing_service_instance
    # Removed unused param - using audit_service_instance
):
    """
    Rotate authentication token for a device.

    Returns:
        New auth token and expiration
    """
    try:
        result = await pairing_service_instance.rotate_auth_token(device_id)

        # Log token rotation
        await audit_service_instance.log_event(
            event_type="auth_token_rotated",
            device_id=device_id,
            details={
                "token_expires_at": result["token_expires_at"],
                "ip_address": "client_ip"
            }
        )

        logger.info(f"Auth token rotated: {device_id}")

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except Exception as e:
        logger.error(f"Unexpected error in rotate_auth_token: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# Wake-on-LAN Endpoints
@wol_router.post(
    "/send",
    response_model=WoLSendResponse,
    status_code=status.HTTP_200_OK,
    summary="Send Wake-on-LAN magic packet",
    description="Send Wake-on-LAN magic packet to wake a sleeping PC."
)
async def send_wol_packet(
    request: WoLSendRequest
):
    """
    Send Wake-on-LAN magic packet to specified MAC and IP addresses.

    Args:
        request: WoL send request with MAC, IP, and optional broadcast address

    Returns:
        WoL send result with success status and details
    """
    try:
        # Send WoL packet
        result = await wol_service.send_wol_packet(
            mac_address=request.mac_address,
            ip_address=request.ip_address,
            broadcast_address=request.broadcast_address
        )

        # Log WoL attempt
        await audit_service_instance.log_event(
            event_type="wol_packet_sent",
            device_id="unknown",  # WoL doesn't require device authentication
            details={
                "mac_address": request.mac_address,
                "ip_address": request.ip_address,
                "broadcast_address": request.broadcast_address,
                "success": result.success,
                "retry_count": result.retry_count,
                "ip_address_client": "client_ip"
            },
            severity="info" if result.success else "warning"
        )

        if result.success:
            logger.info(f"WoL packet sent successfully: {request.mac_address} -> {request.ip_address}")
        else:
            logger.warning(f"WoL packet failed: {request.mac_address} -> {request.ip_address}, error: {result.error}")

        return WoLSendResponse(
            success=result.success,
            message=result.message,
            sent_at=result.sent_at,
            retry_count=result.retry_count,
            error=result.error,
            execution_time_ms=result.execution_time_ms
        )

    except ValueError as e:
        # Log validation error
        await audit_service_instance.log_event(
            event_type="wol_validation_failed",
            device_id="unknown",
            details={
                "mac_address": request.mac_address,
                "ip_address": request.ip_address,
                "error": str(e),
                "ip_address_client": "client_ip"
            },
            severity="warning"
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except OSError as e:
        # Log permission or network error
        await audit_service_instance.log_event(
            event_type="wol_permission_error",
            device_id="unknown",
            details={
                "mac_address": request.mac_address,
                "ip_address": request.ip_address,
                "error": str(e),
                "security": True,
                "ip_address_client": "client_ip"
            },
            severity="error"
        )

        raise HTTPException(
            status_code=status.HTTP_200_OK,  # Don't expose permission issues via HTTP status
            detail="WoL paketi gönderilemedi. PC'nin ağ ayarlarını kontrol edin."
        )

    except Exception as e:
        logger.error(f"Unexpected error in send_wol_packet: {e}", exc_info=True)

        # Log unexpected error
        await audit_service_instance.log_event(
            event_type="wol_unexpected_error",
            device_id="unknown",
            details={
                "mac_address": request.mac_address,
                "ip_address": request.ip_address,
                "error": str(e),
                "ip_address_client": "client_ip"
            },
            severity="error"
        )

        raise HTTPException(
            status_code=status.HTTP_200_OK,  # Graceful handling
            detail="WoL paketi gönderilemedi. Daha sonra tekrar deneyin."
        )


@wol_router.get(
    "/status",
    response_model=WoLStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Check PC wake status",
    description="Check if a PC is online, offline, or waking up."
)
async def check_pc_wake_status(
    ip: str,
    # Removed unused param - using audit_service_instance
):
    """
    Check the wake status of a PC.

    Args:
        ip: IP address of the PC to check

    Returns:
        PC status information with latency details
    """
    try:
        if not ip or not ip.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="IP address parameter is required"
            )

        # Check PC status
        result = await wol_service.check_pc_status(ip.strip())

        # Log status check
        await audit_service_instance.log_event(
            event_type="pc_status_checked",
            device_id="unknown",
            details={
                "ip_address": ip,
                "pc_status": result.pc_status,
                "latency_ms": result.latency_ms,
                "ip_address_client": "client_ip"
            },
            severity="info"
        )

        logger.info(f"PC status checked: {ip} -> {result.pc_status}")

        return WoLStatusResponse(
            pc_status=result.pc_status,
            ip_address=result.ip_address,
            last_checked=result.last_checked,
            latency_ms=result.latency_ms,
            error=result.error
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise

    except Exception as e:
        logger.error(f"Unexpected error in check_pc_wake_status: {e}", exc_info=True)

        # Log unexpected error
        await audit_service_instance.log_event(
            event_type="pc_status_check_error",
            device_id="unknown",
            details={
                "ip_address": ip,
                "error": str(e),
                "ip_address_client": "client_ip"
            },
            severity="warning"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PC durumu kontrol edilemedi"
        )


@wol_router.post(
    "/health",
    response_model=WoLHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="WoL service health check",
    description="Check if Wake-on-LAN service is healthy and has required capabilities."
)
async def wol_health_check(
    # Removed unused param - using audit_service_instance
):
    """
    Check the health and capabilities of the Wake-on-LAN service.

    Returns:
        Service health status and capability information
    """
    try:
        # Get service health
        result = await wol_service.get_service_health()

        # Log health check (lower severity to avoid noise)
        await audit_service_instance.log_event(
            event_type="wol_health_checked",
            device_id="system",
            details={
                "service_status": result.service_status,
                "version": result.version,
                "ip_address_client": "system"
            },
            severity="debug"
        )

        logger.debug(f"WoL health check: {result.service_status}")

        return WoLHealthResponse(
            service_status=result.service_status,
            timestamp=result.timestamp,
            version=result.version,
            capabilities=result.capabilities
        )

    except Exception as e:
        logger.error(f"Unexpected error in wol_health_check: {e}", exc_info=True)

        # Log health check failure
        await audit_service_instance.log_event(
            event_type="wol_health_check_error",
            device_id="system",
            details={
                "error": str(e),
                "severity": "error"
            }
        )

        # Return degraded status on health check failure
        return WoLHealthResponse(
            service_status="unhealthy",
            timestamp=datetime.utcnow().timestamp(),
            version="1.0.0",
            capabilities={
                "wol_enabled": False,
                "error": "Health check failed"
            }
        )


# Health check endpoint
@pairing_router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Pairing service health check",
    description="Check if pairing service is healthy."
)
async def health_check():
    """Simple health check for pairing service."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "pairing"
    }