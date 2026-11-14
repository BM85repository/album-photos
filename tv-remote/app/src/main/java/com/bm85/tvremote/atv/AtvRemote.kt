package com.bm85.tvremote.atv

import android.os.Build
import android.util.Log
import com.bm85.tvremote.RemoteKey
import com.bm85.tvremote.Status
import com.bm85.tvremote.TvApp
import com.bm85.tvremote.TvController
import com.bm85.tvremote.TvState
import com.bm85.tvremote.proto.Framing
import com.bm85.tvremote.proto.ProtoMessage
import com.bm85.tvremote.proto.ProtoWriter
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import java.io.EOFException
import java.net.InetSocketAddress
import java.net.SocketTimeoutException
import java.util.concurrent.Executors
import javax.net.ssl.SSLException
import javax.net.ssl.SSLSocket
import kotlin.concurrent.thread

/**
 * Android TV Remote v2 (TCP 6466): works with Google TV / Android TV sets
 * (Sony Bravia, ACE, TCL, Philips, Hisense Android models, Chromecast with Google TV...).
 */
class AtvRemote(private val host: String, private val certs: CertManager) : TvController {
    private val _state = MutableStateFlow(TvState())
    override val state: StateFlow<TvState> = _state.asStateFlow()

    private val writer = Executors.newSingleThreadExecutor()
    @Volatile private var socket: SSLSocket? = null
    @Volatile private var closed = false
    @Volatile private var running = false

    override fun connect() {
        synchronized(this) {
            if (closed || running) return
            running = true
        }
        _state.update { it.copy(status = Status.CONNECTING, message = null) }
        thread(name = "atv-remote", isDaemon = true) { loop() }
    }

    private fun loop() {
        var configured = false
        try {
            val s = certs.sslContext().socketFactory.createSocket() as SSLSocket
            socket = s
            s.connect(InetSocketAddress(host, PORT), 5000)
            s.soTimeout = 30000 // the TV pings every few seconds
            s.startHandshake()
            val input = s.inputStream
            while (!closed) {
                val msg = ProtoMessage(Framing.read(input))
                if (msg.has(1)) configured = true
                handle(msg)
            }
        } catch (e: Exception) {
            if (!closed) {
                Log.w(TAG, "connection ended", e)
                val pairing = !configured && (e is SSLException || e is EOFException)
                _state.update {
                    when {
                        pairing -> it.copy(status = Status.NEEDS_PAIRING, message = "Pairing required: the TV does not know this phone yet.")
                        e is SocketTimeoutException && configured -> it.copy(status = Status.ERROR, message = "Connection lost.")
                        else -> it.copy(status = Status.ERROR, message = "Cannot connect to $host: ${e.message ?: e.javaClass.simpleName}")
                    }
                }
            }
        } finally {
            try { socket?.close() } catch (_: Exception) {}
            socket = null
            running = false
        }
    }

    private fun handle(m: ProtoMessage) {
        when {
            m.has(1) -> { // RemoteConfigure from TV -> answer with our features and device info
                val info = ProtoWriter()
                    .string(1, Build.MODEL ?: "Phone")
                    .string(2, Build.MANUFACTURER ?: "Android")
                    .int(3, 1)
                    .string(4, "1")
                    .string(5, "atvremote")
                    .string(6, "1.0.0")
                send(ProtoWriter().message(1, ProtoWriter().int(1, FEATURES).message(2, info)))
                _state.update { it.copy(status = Status.CONNECTED, message = null) }
            }
            m.has(2) -> send(ProtoWriter().message(2, ProtoWriter().int(1, FEATURES))) // RemoteSetActive
            m.has(8) -> { // ping -> pong
                val v = m.message(8)?.int(1) ?: 0
                send(ProtoWriter().message(9, ProtoWriter().int(1, v)))
            }
            m.has(40) -> _state.update { it.copy(powerOn = m.message(40)?.bool(1)) }
            m.has(50) -> {
                val v = m.message(50) ?: return
                _state.update { it.copy(volumeMax = v.int(6), volume = v.int(7), muted = v.bool(8)) }
            }
            m.has(20) -> {
                val pkg = m.message(20)?.message(1)?.string(12)
                if (!pkg.isNullOrEmpty()) _state.update { it.copy(currentApp = pkg) }
            }
            m.has(3) -> Log.w(TAG, "remote error from TV")
        }
    }

    private fun send(w: ProtoWriter): Boolean {
        val s = socket
        if (s == null || _state.value.status != Status.CONNECTED && _state.value.status != Status.CONNECTING) {
            connect()
            return false
        }
        val bytes = w.toByteArray()
        writer.execute {
            try {
                Framing.write(s.outputStream, bytes)
            } catch (e: Exception) {
                Log.w(TAG, "send failed", e)
                try { s.close() } catch (_: Exception) {}
            }
        }
        return true
    }

    override fun press(key: RemoteKey) {
        // RemoteKeyInject(key_code, direction=SHORT)
        send(ProtoWriter().message(10, ProtoWriter().int(1, key.atv).int(2, 3)))
    }

    override fun launch(app: TvApp) {
        // RemoteAppLinkLaunchRequest(app_link)
        send(ProtoWriter().message(90, ProtoWriter().string(1, app.link)))
    }

    override fun close() {
        closed = true
        val s = socket
        socket = null
        writer.execute { try { s?.close() } catch (_: Exception) {} }
        writer.shutdown()
        _state.update { it.copy(status = Status.DISCONNECTED) }
    }

    companion object {
        private const val TAG = "AtvRemote"
        const val PORT = 6466
        // KEY | IME | VOICE | POWER | VOLUME | APP_LINK
        private const val FEATURES = 622
    }
}
