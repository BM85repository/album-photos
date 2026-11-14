package com.bm85.tvremote

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import android.os.Handler
import android.os.Looper
import android.util.Log
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.net.Inet4Address

data class FoundTv(val name: String, val host: String)

/** Finds Google TV / Android TV sets on the Wi-Fi via mDNS (_androidtvremote2._tcp). */
class Discovery(context: Context) {
    private val nsd = context.getSystemService(Context.NSD_SERVICE) as NsdManager
    private val wifi = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
    private val main = Handler(Looper.getMainLooper())
    private var lock: WifiManager.MulticastLock? = null
    private var listener: NsdManager.DiscoveryListener? = null
    private val queue = ArrayDeque<NsdServiceInfo>()
    private var resolving = false

    private val _found = MutableStateFlow<List<FoundTv>>(emptyList())
    val found: StateFlow<List<FoundTv>> = _found.asStateFlow()

    fun start() {
        if (listener != null) return
        lock = wifi.createMulticastLock("tvremote").apply { setReferenceCounted(false); acquire() }
        val l = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(serviceType: String) {}
            override fun onDiscoveryStopped(serviceType: String) {}
            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) { Log.w(TAG, "discovery failed $errorCode") }
            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {}
            override fun onServiceFound(info: NsdServiceInfo) { main.post { queue.addLast(info); next() } }
            override fun onServiceLost(info: NsdServiceInfo) {
                main.post { _found.value = _found.value.filterNot { it.name == info.serviceName } }
            }
        }
        listener = l
        try {
            nsd.discoverServices(SERVICE, NsdManager.PROTOCOL_DNS_SD, l)
        } catch (e: Exception) {
            Log.w(TAG, "discoverServices", e)
            listener = null
        }
    }

    @Suppress("DEPRECATION")
    private fun next() {
        if (resolving) return
        val info = queue.removeFirstOrNull() ?: return
        resolving = true
        try {
            nsd.resolveService(info, object : NsdManager.ResolveListener {
                override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                    main.post { resolving = false; next() }
                }

                override fun onServiceResolved(serviceInfo: NsdServiceInfo) {
                    val addr = serviceInfo.host
                    main.post {
                        resolving = false
                        if (addr != null) {
                            val host = if (addr is Inet4Address) addr.hostAddress else addr.hostAddress?.substringBefore('%')
                            if (host != null) {
                                val tv = FoundTv(serviceInfo.serviceName, host)
                                _found.value = _found.value.filterNot { it.host == host || it.name == tv.name } + tv
                            }
                        }
                        next()
                    }
                }
            })
        } catch (e: Exception) {
            resolving = false
        }
    }

    fun stop() {
        listener?.let { try { nsd.stopServiceDiscovery(it) } catch (_: Exception) {} }
        listener = null
        queue.clear()
        resolving = false
        lock?.let { if (it.isHeld) it.release() }
        lock = null
    }

    companion object {
        private const val TAG = "Discovery"
        private const val SERVICE = "_androidtvremote2._tcp"
    }
}
