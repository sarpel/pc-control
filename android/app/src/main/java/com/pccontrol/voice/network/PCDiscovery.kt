package com.pccontrol.voice.network

import android.content.Context
import android.net.wifi.WifiManager
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import java.io.IOException
import java.net.*
import java.util.concurrent.ConcurrentHashMap
import kotlin.random.Random

/**
 * PC discovery service for finding PC agents on the local network.

 * Features:
 * - Automatic network scanning
 * - UPnP/SSDP discovery
 * - Manual IP entry support
 * - Wake-on-LAN capability
 * - Network analysis and reporting
 */
class PCDiscovery(private val context: Context) {
    companion object {
        private const val TAG = "PCDiscovery"
        private const val PC_AGENT_PORT = 8443
        private const val WOL_BROADCAST_PORT = 9
        private const val DISCOVERY_TIMEOUT_MS = 5000L
        private const val MAX_CONCURRENT_SCANS = 20
    }

    private val wifiManager: WifiManager by lazy {
        context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
    }

    private val discoveredPCs = ConcurrentHashMap<String, DiscoveredPC>()
    private var isScanning = false

    /**
     * Discover PCs on the local network.
     */
    suspend fun discoverPCs(): List<DiscoveredPC> {
        return withContext(Dispatchers.IO) {
            if (isScanning) {
                return@withContext emptyList()
            }

            isScanning = true
            discoveredPCs.clear()

            try {
                Log.i(TAG, "Starting PC discovery")

                // Get current network info
                val localNetworkInfo = getLocalNetworkInfo()
                if (localNetworkInfo == null) {
                    Log.e(TAG, "No network connection available")
                    return@withContext emptyList()
                }

                // Discover using multiple methods
                val discoveryTasks = listOf(
                    async { discoverByNetworkScanning(localNetworkInfo) },
                    async { discoverBySSDP() },
                    async { discoverByMDNS() }
                )

                // Run all discovery methods in parallel
                discoveryTasks.awaitAll()

                // Filter and clean results
                val pcs = discoveredPCs.values.filter { pc ->
                    pc.name.isNotBlank() && pc.ipAddress.isNotBlank()
                }.distinctBy { it.ipAddress }

                Log.i(TAG, "Discovery complete. Found ${pcs.size} PCs")
                pcs.sortedBy { it.name }

            } catch (e: Exception) {
                Log.e(TAG, "Error during PC discovery", e)
                emptyList()
            } finally {
                isScanning = false
            }
        }
    }

    /**
     * Test if a specific IP address has a running PC agent.
     */
    suspend fun testPCConnection(ipAddress: String): Boolean {
        return withContext(Dispatchers.IO) {
            try {
                val url = URL("https://$ipAddress:$PC_AGENT_PORT/api/health")
                val connection = url.openConnection() as HttpURLConnection
                connection.apply {
                    requestMethod = "GET"
                    connectTimeout = 3000
                    readTimeout = 3000
                    setRequestProperty("Accept", "application/json")
                }

                val responseCode = connection.responseCode
                responseCode == HttpURLConnection.HTTP_OK

            } catch (e: IOException) {
                Log.d(TAG, "PC not responding at $ipAddress: ${e.message}")
                false
            }
        }
    }

    /**
     * Send Wake-on-LAN magic packet to wake up a PC.
     */
    suspend fun wakeOnLAN(macAddress: String, ipAddress: String = "255.255.255.255"): Boolean {
        return withContext(Dispatchers.IO) {
            try {
                Log.i(TAG, "Sending WOL packet to $macAddress via $ipAddress")

                // Validate and format MAC address
                val formattedMac = formatMacAddress(macAddress)
                val magicPacket = createMagicPacket(formattedMac)

                // Send broadcast packet
                val socket = DatagramSocket()
                try {
                    val broadcastAddress = InetAddress.getByName(ipAddress)
                    val packet = DatagramPacket(
                        magicPacket,
                        magicPacket.size,
                        broadcastAddress,
                        WOL_BROADCAST_PORT
                    )
                    socket.send(packet)

                    Log.i(TAG, "WOL packet sent successfully to $formattedMac")
                    true

                } finally {
                    socket.close()
                }

            } catch (e: Exception) {
                Log.e(TAG, "Failed to send WOL packet to $macAddress", e)
                false
            }
        }
    }

    /**
     * Get network information for scanning.
     */
    private suspend fun getLocalNetworkInfo(): LocalNetworkInfo? {
        return try {
            val wifiInfo = wifiManager.connectionInfo
            val dhcpInfo = wifiManager.dhcpInfo

            if (dhcpInfo != null && wifiInfo.ipAddress != 0) {
                val ipAddress = formatIpAddress(wifiInfo.ipAddress)
                val netmask = formatIpAddress(dhcpInfo.netmask)

                // Calculate network range
                val networkPrefix = getNetworkPrefix(ipAddress, netmask)

                LocalNetworkInfo(
                    ipAddress = ipAddress,
                    netmask = netmask,
                    networkPrefix = networkPrefix,
                    interfaceName = "wlan0"
                )
            } else {
                // Try to get network info from other interfaces
                getNetworkInfoFromSystem()
            }

        } catch (e: Exception) {
            Log.e(TAG, "Error getting local network info", e)
            getNetworkInfoFromSystem()
        }
    }

    /**
     * Discover PCs by scanning the local network range.
     */
    private suspend fun discoverByNetworkScanning(networkInfo: LocalNetworkInfo): List<DiscoveredPC> {
        return try {
            val scanRange = generateScanRange(networkInfo)
            Log.d(TAG, "Scanning network range: ${scanRange.first()} - ${scanRange.last()}")

            coroutineScope {
                scanRange.chunked(MAX_CONCURRENT_SCANS).map { chunk ->
                    chunk.map { ipAddress ->
                        async {
                            if (isScanning) {
                                val pcInfo = scanIPAddress(ipAddress)
                                pcInfo?.let {
                                    discoveredPCs[it.id] = it
                                }
                            }
                        }
                    }.awaitAll()
                }
            }

            discoveredPCs.values.toList()

        } catch (e: Exception) {
            Log.e(TAG, "Error in network scanning discovery", e)
            emptyList()
        }
    }

    /**
     * Scan a single IP address for PC agent.
     */
    private suspend fun scanIPAddress(ipAddress: String): DiscoveredPC? {
        return try {
            val url = URL("https://$ipAddress:$PC_AGENT_PORT/api/system/info")
            val connection = url.openConnection() as HttpURLConnection
            connection.apply {
                requestMethod = "GET"
                connectTimeout = 2000
                readTimeout = 2000
                setRequestProperty("Accept", "application/json")
            }

            val responseCode = connection.responseCode

            if (responseCode == HttpURLConnection.HTTP_OK) {
                val responseBody = connection.inputStream.bufferedReader().readText()
                parsePCInfo(ipAddress, responseBody)
            } else {
                null
            }

        } catch (e: Exception) {
            // This is normal - most IPs won't have a PC agent
            null
        }
    }

    /**
     * Discover PCs using SSDP (Simple Service Discovery Protocol).
     */
    private suspend fun discoverBySSDP(): List<DiscoveredPC> = withContext(Dispatchers.IO) {
        val discoveredPCs = mutableListOf<DiscoveredPC>()
        try {
            Log.d(TAG, "Starting SSDP discovery")
            DatagramSocket().use { socket ->
                socket.soTimeout = 2000
                
                val ssdpRequest = "M-SEARCH * HTTP/1.1\r\n" +
                        "HOST: 239.255.255.250:1900\r\n" +
                        "MAN: \"ssdp:discover\"\r\n" +
                        "MX: 1\r\n" +
                        "ST: urn:schemas-upnp-org:device:Basic:1\r\n" +
                        "\r\n"
                
                val sendData = ssdpRequest.toByteArray()
                val sendPacket = DatagramPacket(
                    sendData, 
                    sendData.size, 
                    InetAddress.getByName("239.255.255.250"), 
                    1900
                )
                
                socket.send(sendPacket)
                
                val receiveData = ByteArray(1024)
                val receivePacket = DatagramPacket(receiveData, receiveData.size)
                
                val endTime = System.currentTimeMillis() + 2000
                while (System.currentTimeMillis() < endTime) {
                    try {
                        socket.receive(receivePacket)
                        val response = String(receivePacket.data, 0, receivePacket.length)
                        val ip = receivePacket.address.hostAddress
                        
                        // Check if it's our PC agent (simplified check)
                        if (response.contains("PC-Control") && ip != null) {
                             discoveredPCs.add(
                                DiscoveredPC(
                                    id = "pc_${ip.replace(".", "_")}",
                                    name = "PC Agent (SSDP)",
                                    ipAddress = ip,
                                    port = PC_AGENT_PORT,
                                    isOnline = true,
                                    lastSeen = System.currentTimeMillis()
                                )
                             )
                        }
                    } catch (e: SocketTimeoutException) {
                        break
                    }
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error in SSDP discovery", e)
        }
        discoveredPCs
    }

    /**
     * Discover PCs using mDNS (NSD).
     */
    private suspend fun discoverByMDNS(): List<DiscoveredPC> {
        return try {
            Log.d(TAG, "Starting mDNS discovery")
            
            val discoveredServices = mutableListOf<DiscoveredPC>()
            val nsdManager = context.getSystemService(Context.NSD_SERVICE) as android.net.nsd.NsdManager
            val serviceType = "_pc-control._tcp."
            
            val discoveryListener = object : android.net.nsd.NsdManager.DiscoveryListener {
                override fun onDiscoveryStarted(regType: String) {
                    Log.d(TAG, "Service discovery started")
                }

                override fun onServiceFound(service: android.net.nsd.NsdServiceInfo) {
                    Log.d(TAG, "Service discovery success: $service")
                    if (service.serviceType == serviceType) {
                        nsdManager.resolveService(service, object : android.net.nsd.NsdManager.ResolveListener {
                            override fun onResolveFailed(serviceInfo: android.net.nsd.NsdServiceInfo, errorCode: Int) {
                                Log.e(TAG, "Resolve failed: $errorCode")
                            }

                            override fun onServiceResolved(serviceInfo: android.net.nsd.NsdServiceInfo) {
                                Log.d(TAG, "Resolve Succeeded. $serviceInfo")
                                val host = serviceInfo.host
                                val ip = host.hostAddress
                                val name = serviceInfo.serviceName
                                
                                if (ip != null) {
                                    synchronized(discoveredServices) {
                                        discoveredServices.add(
                                            DiscoveredPC(
                                                id = "pc_${ip.replace(".", "_")}",
                                                name = name,
                                                ipAddress = ip
                                            )
                                        )
                                    }
                                }
                            }
                        })
                    }
                }

                override fun onServiceLost(service: android.net.nsd.NsdServiceInfo) {
                    Log.e(TAG, "service lost: $service")
                }

                override fun onDiscoveryStopped(serviceType: String) {
                    Log.i(TAG, "Discovery stopped: $serviceType")
                }

                override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                    Log.e(TAG, "Discovery failed: Error code:$errorCode")
                    nsdManager.stopServiceDiscovery(this)
                }

                override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {
                    Log.e(TAG, "Discovery failed: Error code:$errorCode")
                    nsdManager.stopServiceDiscovery(this)
                }
            }

            nsdManager.discoverServices(serviceType, android.net.nsd.NsdManager.PROTOCOL_DNS_SD, discoveryListener)
            
            // Wait for discovery
            delay(3000)
            
            try {
                nsdManager.stopServiceDiscovery(discoveryListener)
            } catch (e: Exception) {
                // Ignore if already stopped
            }

            discoveredServices
        } catch (e: Exception) {
            Log.e(TAG, "Error in mDNS discovery", e)
            emptyList()
        }
    }

    /**
     * Parse PC information from API response.
     */
    private fun parsePCInfo(ipAddress: String, responseBody: String): DiscoveredPC {
        return try {
            // Simple parsing - in real implementation, use proper JSON parsing
            val pcName = when {
                responseBody.contains("Windows") -> "Windows PC"
                responseBody.contains("hostname") -> extractHostname(responseBody)
                else -> "PC"
            }

            DiscoveredPC(
                id = "pc_${ipAddress.replace(".", "_")}",
                name = pcName,
                ipAddress = ipAddress,
                isAvailable = true,
                lastSeen = System.currentTimeMillis(),
                port = PC_AGENT_PORT,
                macAddress = null // Would be determined via ARP table
            )

        } catch (e: Exception) {
            Log.w(TAG, "Error parsing PC info from $ipAddress", e)
            DiscoveredPC(
                id = "pc_${ipAddress.replace(".", "_")}",
                name = "Bilinmeyen PC",
                ipAddress = ipAddress,
                isAvailable = true,
                lastSeen = System.currentTimeMillis(),
                port = PC_AGENT_PORT
            )
        }
    }

    /**
     * Generate scan range based on network information.
     */
    private fun generateScanRange(networkInfo: LocalNetworkInfo): List<String> {
        val ipParts = networkInfo.ipAddress.split(".")
        val networkParts = networkInfo.networkPrefix.split(".")

        // Generate list of IPs in the local subnet
        val scanRange = mutableListOf<String>()
        for (i in 1..254) {
            val testIp = "${networkParts[0]}.${networkParts[1]}.${networkParts[2]}.$i"
            if (testIp != networkInfo.ipAddress) { // Skip our own IP
                scanRange.add(testIp)
            }
        }

        return scanRange
    }

    /**
     * Get network information from system if WiFi info is not available.
     */
    private suspend fun getNetworkInfoFromSystem(): LocalNetworkInfo? {
        return try {
            // Try to get local IP by connecting to external server
            val socket = Socket()
            socket.connect(InetSocketAddress(InetAddress.getByName("8.8.8.8"), 53))
            val localAddress = socket.localAddress as InetAddress
            socket.close()

            val ipAddress = localAddress.hostAddress
            if (ipAddress != null && ipAddress.startsWith("192.168.")) {
                LocalNetworkInfo(
                    ipAddress = ipAddress,
                    netmask = "255.255.255.0",
                    networkPrefix = ipAddress.substring(0, ipAddress.lastIndexOf('.')),
                    interfaceName = "unknown"
                )
            } else {
                null
            }

        } catch (e: Exception) {
            Log.e(TAG, "Error getting network info from system", e)
            null
        }
    }

    /**
     * Get network prefix from IP and netmask.
     */
    private fun getNetworkPrefix(ipAddress: String, netmask: String): String {
        val ipParts = ipAddress.split(".").map { it.toInt() }
        val maskParts = netmask.split(".").map { it.toInt() }

        val networkParts = ipParts.zip(maskParts).map { (ip, mask) ->
            ip and mask
        }

        return networkParts.joinToString(".")
    }

    /**
     * Format MAC address for WOL packet.
     */
    private fun formatMacAddress(macAddress: String): String {
        return macAddress
            .replace(":", "")
            .replace("-", "")
            .replace(".", "")
            .uppercase()
            .take(12)
            .chunked(2)
            .joinToString(":")
    }

    /**
     * Create WOL magic packet.
     */
    private fun createMagicPacket(macAddress: String): ByteArray {
        val macBytes = macAddress.split(":").map { it.toInt(16).toByte() }.toByteArray()
        val packet = ByteArray(102) // 6 bytes FF + 16 * MAC bytes

        // First 6 bytes are FF
        for (i in 0 until 6) {
            packet[i] = 0xFF.toByte()
        }

        // Repeat MAC address 16 times
        for (i in 0 until 16) {
            System.arraycopy(macBytes, 0, packet, 6 + i * 6, 6)
        }

        return packet
    }

    /**
     * Format IP address from int to string.
     */
    private fun formatIpAddress(ip: Int): String {
        return String.format(
            "%d.%d.%d.%d",
            (ip and 0xff),
            (ip shr 8 and 0xff),
            (ip shr 16 and 0xff),
            (ip shr 24 and 0xff)
        )
    }

    /**
     * Extract hostname from response body.
     */
    private fun extractHostname(responseBody: String): String {
        return try {
            // Simple regex or string parsing
            when {
                responseBody.contains("computername") -> {
                    val start = responseBody.indexOf("computername") + "computername".length
                    responseBody.substring(start).trim().takeWhile { it.isLetterOrDigit() }
                }
                else -> "PC"
            }
        } catch (e: Exception) {
            "PC"
        }
    }
}

// Data classes
data class DiscoveredPC(
    val id: String,
    val name: String,
    val ipAddress: String,
    val isAvailable: Boolean,
    val lastSeen: Long,
    val port: Int = 8443,
    val macAddress: String? = null
)

data class LocalNetworkInfo(
    val ipAddress: String,
    val netmask: String,
    val networkPrefix: String,
    val interfaceName: String
)