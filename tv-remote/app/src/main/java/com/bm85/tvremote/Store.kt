package com.bm85.tvremote

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress

class TvStore(context: Context) {
    private val prefs = context.getSharedPreferences("tvs", Context.MODE_PRIVATE)

    fun load(): List<SavedTv> = try {
        val arr = JSONArray(prefs.getString("list", "[]"))
        (0 until arr.length()).mapNotNull { i ->
            val o = arr.optJSONObject(i) ?: return@mapNotNull null
            SavedTv(
                id = o.getString("id"),
                name = o.optString("name"),
                host = o.optString("host"),
                type = runCatching { TvType.valueOf(o.optString("type")) }.getOrDefault(TvType.ANDROID_TV),
                psk = o.optString("psk"),
                mac = o.optString("mac"),
            )
        }
    } catch (_: Exception) {
        emptyList()
    }

    fun save(list: List<SavedTv>) {
        val arr = JSONArray()
        list.forEach {
            arr.put(
                JSONObject().put("id", it.id).put("name", it.name).put("host", it.host)
                    .put("type", it.type.name).put("psk", it.psk).put("mac", it.mac)
            )
        }
        prefs.edit().putString("list", arr.toString()).apply()
    }
}

object WakeOnLan {
    /** Sends a magic packet (needs the TV's MAC address and "Wake on LAN"/"Remote start" enabled on the TV). */
    fun send(mac: String) {
        val parts = mac.trim().split(':', '-').filter { it.isNotEmpty() }
        require(parts.size == 6) { "Invalid MAC address" }
        val macBytes = ByteArray(6) { parts[it].toInt(16).toByte() }
        val packet = ByteArray(6 + 16 * 6)
        for (i in 0 until 6) packet[i] = 0xFF.toByte()
        for (i in 0 until 16) System.arraycopy(macBytes, 0, packet, 6 + i * 6, 6)
        DatagramSocket().use { socket ->
            socket.broadcast = true
            val address = InetAddress.getByName("255.255.255.255")
            for (port in intArrayOf(9, 7)) socket.send(DatagramPacket(packet, packet.size, address, port))
        }
    }
}
