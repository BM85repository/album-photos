package com.bm85.tvremote.sony

import android.util.Log
import com.bm85.tvremote.RemoteKey
import com.bm85.tvremote.Status
import com.bm85.tvremote.TvApp
import com.bm85.tvremote.TvController
import com.bm85.tvremote.TvState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors

/**
 * Sony Bravia "IP control" (HTTP + Pre-Shared Key). On the TV:
 * Settings > Network > Home network > IP control > Authentication = "Normal and Pre-Shared Key", set the key,
 * and enable "Remote start" to be able to switch the TV on from standby.
 */
class BraviaRemote(private val host: String, private val psk: String) : TvController {
    private val _state = MutableStateFlow(TvState())
    override val state: StateFlow<TvState> = _state.asStateFlow()
    private val exec = Executors.newSingleThreadExecutor()
    private val codes = ConcurrentHashMap<String, String>(DEFAULT_CODES)
    @Volatile private var closed = false

    override fun connect() {
        if (closed) return
        _state.update { it.copy(status = Status.CONNECTING, message = null) }
        exec.execute {
            try {
                val info = rpc("system", "getRemoteControllerInfo")
                info.optJSONArray("result")?.optJSONArray(1)?.let { arr ->
                    for (i in 0 until arr.length()) {
                        val o = arr.optJSONObject(i) ?: continue
                        codes[o.optString("name")] = o.optString("value")
                    }
                }
                val power = try {
                    rpc("system", "getPowerStatus").optJSONArray("result")?.optJSONObject(0)?.optString("status")
                } catch (_: Exception) { null }
                _state.update { it.copy(status = Status.CONNECTED, message = null, powerOn = power?.let { p -> p == "active" }) }
                refreshVolume()
            } catch (e: Exception) {
                Log.w(TAG, "connect failed", e)
                _state.update { it.copy(status = Status.ERROR, message = "Cannot reach the Sony TV at $host: ${e.message}") }
            }
        }
    }

    override fun press(key: RemoteKey) {
        val code = key.sony.firstNotNullOfOrNull { codes[it] }
        if (code == null) {
            _state.update { it.copy(message = "${key.name} is not supported by this TV") }
            return
        }
        exec.execute {
            try {
                ircc(code)
                if (_state.value.status != Status.CONNECTED) _state.update { it.copy(status = Status.CONNECTED, message = null) }
                if (key == RemoteKey.VOL_UP || key == RemoteKey.VOL_DOWN || key == RemoteKey.MUTE) refreshVolume()
            } catch (e: Exception) {
                if (key == RemoteKey.POWER) {
                    // Standby with "Remote start": try the REST power-on call.
                    try { rpc("system", "setPowerStatus", JSONObject().put("status", true)); return@execute } catch (_: Exception) {}
                }
                _state.update { it.copy(status = Status.ERROR, message = e.message ?: "Command failed") }
            }
        }
    }

    override fun launch(app: TvApp) {
        val code = app.sony.firstNotNullOfOrNull { codes[it] }
        if (code != null) {
            exec.execute { try { ircc(code) } catch (e: Exception) { _state.update { it.copy(message = e.message) } } }
            return
        }
        // Fallback: look the app up in the TV's application list.
        exec.execute {
            try {
                val list = rpc("appControl", "getApplicationList").optJSONArray("result")?.optJSONArray(0)
                    ?: throw IOException("No application list")
                var uri: String? = null
                for (i in 0 until list.length()) {
                    val o = list.optJSONObject(i) ?: continue
                    if (o.optString("title").contains(app.label, ignoreCase = true)) { uri = o.optString("uri"); break }
                }
                if (uri == null) throw IOException("${app.label} not found on the TV")
                rpc("appControl", "setActiveApp", JSONObject().put("uri", uri))
            } catch (e: Exception) {
                _state.update { it.copy(message = e.message) }
            }
        }
    }

    private fun refreshVolume() {
        try {
            val arr = rpc("audio", "getVolumeInformation").optJSONArray("result")?.optJSONArray(0) ?: return
            for (i in 0 until arr.length()) {
                val o = arr.optJSONObject(i) ?: continue
                if (o.optString("target") == "speaker" || arr.length() == 1) {
                    _state.update { it.copy(volume = o.optInt("volume"), volumeMax = o.optInt("maxVolume"), muted = o.optBoolean("mute")) }
                    return
                }
            }
        } catch (_: Exception) {
        }
    }

    private fun rpc(service: String, method: String, param: JSONObject? = null): JSONObject {
        val body = JSONObject()
            .put("method", method)
            .put("id", 1)
            .put("params", if (param == null) JSONArray() else JSONArray().put(param))
            .put("version", "1.0")
        val json = JSONObject(http("/sony/$service", body.toString(), "application/json; charset=UTF-8", null))
        json.optJSONArray("error")?.let { err ->
            val code = err.optInt(0)
            throw IOException(if (code == 403 || code == 401) "Access denied: check the Pre-Shared Key" else "TV error $code ${err.optString(1)}")
        }
        return json
    }

    private fun ircc(code: String) {
        val body = """<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:X_SendIRCC xmlns:u="urn:schemas-sony-com:service:IRCC:1"><IRCCCode>$code</IRCCCode></u:X_SendIRCC></s:Body></s:Envelope>"""
        http("/sony/ircc", body, "text/xml; charset=UTF-8", "\"urn:schemas-sony-com:service:IRCC:1#X_SendIRCC\"")
    }

    private fun http(path: String, body: String, contentType: String, soapAction: String?): String {
        val conn = URL("http://$host$path").openConnection() as HttpURLConnection
        try {
            conn.connectTimeout = 4000
            conn.readTimeout = 6000
            conn.requestMethod = "POST"
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", contentType)
            if (psk.isNotEmpty()) conn.setRequestProperty("X-Auth-PSK", psk)
            if (soapAction != null) conn.setRequestProperty("SOAPACTION", soapAction)
            conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() } ?: ""
            if (code == 403 || code == 401) throw IOException("Access denied: check the Pre-Shared Key on the TV")
            if (code !in 200..299) throw IOException("HTTP $code")
            return text
        } finally {
            conn.disconnect()
        }
    }

    override fun close() {
        closed = true
        exec.shutdownNow()
        _state.update { it.copy(status = Status.DISCONNECTED) }
    }

    companion object {
        private const val TAG = "BraviaRemote"

        /** Standard Bravia IRCC codes, used until the TV's own list is downloaded. */
        val DEFAULT_CODES = mapOf(
            "Power" to "AAAAAQAAAAEAAAAVAw==",
            "PowerOff" to "AAAAAQAAAAEAAAAvAw==",
            "Input" to "AAAAAQAAAAEAAAAlAw==",
            "Home" to "AAAAAQAAAAEAAABgAw==",
            "Return" to "AAAAAgAAAJcAAAAjAw==",
            "Options" to "AAAAAgAAAJcAAAA2Aw==",
            "ActionMenu" to "AAAAAgAAAMQAAABLAw==",
            "Up" to "AAAAAQAAAAEAAAB0Aw==",
            "Down" to "AAAAAQAAAAEAAAB1Aw==",
            "Left" to "AAAAAQAAAAEAAAA0Aw==",
            "Right" to "AAAAAQAAAAEAAAAzAw==",
            "Confirm" to "AAAAAQAAAAEAAABlAw==",
            "VolumeUp" to "AAAAAQAAAAEAAAASAw==",
            "VolumeDown" to "AAAAAQAAAAEAAAATAw==",
            "Mute" to "AAAAAQAAAAEAAAAUAw==",
            "ChannelUp" to "AAAAAQAAAAEAAAAQAw==",
            "ChannelDown" to "AAAAAQAAAAEAAAARAw==",
            "Play" to "AAAAAgAAAJcAAAAaAw==",
            "Pause" to "AAAAAgAAAJcAAAAZAw==",
            "Stop" to "AAAAAgAAAJcAAAAYAw==",
            "Next" to "AAAAAgAAAJcAAAA9Aw==",
            "Prev" to "AAAAAgAAAJcAAAA8Aw==",
            "Rewind" to "AAAAAgAAAJcAAAAbAw==",
            "Forward" to "AAAAAgAAAJcAAAAcAw==",
            "Display" to "AAAAAQAAAAEAAAA6Aw==",
            "GGuide" to "AAAAAQAAAAEAAAAOAw==",
            "SubTitle" to "AAAAAgAAAJcAAAAoAw==",
            "Netflix" to "AAAAAgAAABoAAAB8Aw==",
            "YouTube" to "AAAAAgAAAMQAAABHAw==",
            "Num1" to "AAAAAQAAAAEAAAAAAw==",
            "Num2" to "AAAAAQAAAAEAAAABAw==",
            "Num3" to "AAAAAQAAAAEAAAACAw==",
            "Num4" to "AAAAAQAAAAEAAAADAw==",
            "Num5" to "AAAAAQAAAAEAAAAEAw==",
            "Num6" to "AAAAAQAAAAEAAAAFAw==",
            "Num7" to "AAAAAQAAAAEAAAAGAw==",
            "Num8" to "AAAAAQAAAAEAAAAHAw==",
            "Num9" to "AAAAAQAAAAEAAAAIAw==",
            "Num0" to "AAAAAQAAAAEAAAAJAw==",
        )
    }
}
