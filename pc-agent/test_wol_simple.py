"""
Simple test script for WoL functionality to verify T045 implementation.
This bypasses the FastAPI setup issues and tests the core service directly.
"""

import asyncio
import sys
from src.services.wol_service import WakeOnLANService

async def test_wol_basic_functionality():
    """Test basic WoL functionality according to T042 test requirements."""

    print("Testing Wake-on-LAN Service...")
    wol_service = WakeOnLANService()

    # Test 1: MAC address validation
    print("\n1. Testing MAC address validation...")
    assert wol_service.validate_mac_address("AA:BB:CC:DD:EE:FF") == True
    assert wol_service.validate_mac_address("aa:bb:cc:dd:ee:ff") == True
    assert wol_service.validate_mac_address("INVALID_MAC") == False
    print("[PASS] MAC address validation works")

    # Test 2: IP address validation
    print("\n2. Testing IP address validation...")
    assert wol_service.validate_ip_address("192.168.1.100") == True
    assert wol_service.validate_ip_address("255.255.255.255") == True
    assert wol_service.validate_ip_address("INVALID_IP") == False
    print("[PASS] IP address validation works")

    # Test 3: Magic packet generation
    print("\n3. Testing magic packet generation...")
    try:
        packet = wol_service.generate_magic_packet("AA:BB:CC:DD:EE:FF")
        assert len(packet) == 102  # Standard WoL packet size
        assert packet.startswith(b'\xff' * 6)  # 6 bytes of FF
        print("[PASS] Magic packet generation works")
    except Exception as e:
        print(f"[FAIL] Magic packet generation failed: {e}")
        return False

    # Test 4: Service health check
    print("\n4. Testing service health check...")
    try:
        health = await wol_service.get_service_health()
        assert health.service_status in ["healthy", "degraded", "unhealthy"]
        assert health.version == "1.0.0"
        assert health.capabilities["wol_enabled"] == True
        print(f"[PASS] Service health: {health.service_status}")
    except Exception as e:
        print(f"[FAIL] Service health check failed: {e}")
        return False

    # Test 5: PC status check (this will fail with network error, which is expected)
    print("\n5. Testing PC status check...")
    try:
        status = await wol_service.check_pc_status("192.168.1.100")
        # Should return offline/unreachable status for non-existent IP
        assert status.pc_status in ["offline", "waking"]
        assert status.ip_address == "192.168.1.100"
        print(f"[PASS] PC status check works: {status.pc_status}")
    except Exception as e:
        print(f"[FAIL] PC status check failed: {e}")
        return False

    # Test 6: WoL packet send validation
    print("\n6. Testing WoL packet send validation...")
    try:
        # This should fail due to validation errors, which is expected
        result = await wol_service.send_wol_packet(
            mac_address="INVALID_MAC",
            ip_address="INVALID_IP"
        )
        assert result.success == False
        assert "MAC" in result.error or "IP" in result.error
        print(f"[PASS] WoL validation works: {result.error}")
    except Exception as e:
        print(f"[FAIL] WoL validation test failed: {e}")
        return False

    print("\nAll WoL service tests passed!")
    return True

async def main():
    """Run the test suite."""
    try:
        success = await test_wol_basic_functionality()
        if success:
            print("\n[SUCCESS] T045 (Wake-on-LAN service) implementation is working correctly!")
            return 0
        else:
            print("\n[ERROR] Some tests failed")
            return 1
    except Exception as e:
        print(f"\n[FATAL] Test suite failed with error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)