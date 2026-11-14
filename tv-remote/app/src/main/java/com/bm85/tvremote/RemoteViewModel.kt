package com.bm85.tvremote

import android.app.Application
import android.os.Build
import android.view.KeyEvent
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.bm85.tvremote.atv.AtvPairing
import com.bm85.tvremote.atv.AtvRemote
import com.bm85.tvremote.atv.CertManager
import com.bm85.tvremote.atv.PairingException
import com.bm85.tvremote.sony.BraviaRemote
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.UUID

sealed interface PairingUi {
    data object Hidden : PairingUi
    data object Starting : PairingUi
    data class WaitingCode(val error: String? = null) : PairingUi
    data object Verifying : PairingUi
    data class Failed(val error: String) : PairingUi
}

class RemoteViewModel(app: Application) : AndroidViewModel(app) {
    private val store = TvStore(app)
    private val certs = CertManager(app)
    val discovery = Discovery(app)

    private val _saved = MutableStateFlow(store.load())
    val saved: StateFlow<List<SavedTv>> = _saved.asStateFlow()

    private val _current = MutableStateFlow<SavedTv?>(null)
    val current: StateFlow<SavedTv?> = _current.asStateFlow()

    private val _controller = MutableStateFlow<TvController?>(null)
    val controller: StateFlow<TvController?> = _controller.asStateFlow()

    private val _pairing = MutableStateFlow<PairingUi>(PairingUi.Hidden)
    val pairing: StateFlow<PairingUi> = _pairing.asStateFlow()
    private var pairingSession: AtvPairing? = null

    private val _toast = MutableStateFlow<String?>(null)
    val toast: StateFlow<String?> = _toast.asStateFlow()

    fun newId(): String = UUID.randomUUID().toString()

    fun save(tv: SavedTv) {
        val list = _saved.value.filterNot { it.id == tv.id } + tv
        _saved.value = list
        store.save(list)
        if (_current.value?.id == tv.id) {
            _current.value = tv
            connectCurrent()
        }
    }

    fun delete(tv: SavedTv) {
        val list = _saved.value.filterNot { it.id == tv.id }
        _saved.value = list
        store.save(list)
    }

    fun open(tv: SavedTv) {
        _current.value = tv
        connectCurrent()
    }

    fun closeRemote() {
        cancelPairing()
        _controller.value?.close()
        _controller.value = null
        _current.value = null
    }

    fun reconnect() = connectCurrent()

    private fun connectCurrent() {
        val tv = _current.value ?: return
        _controller.value?.close()
        val c: TvController = when (tv.type) {
            TvType.ANDROID_TV -> AtvRemote(tv.host, certs)
            TvType.SONY_IP -> BraviaRemote(tv.host, tv.psk)
        }
        _controller.value = c
        c.connect()
    }

    fun press(key: RemoteKey) {
        val c = _controller.value ?: return
        val tv = _current.value
        if (key == RemoteKey.POWER && tv != null && tv.mac.isNotBlank() && c.state.value.status != Status.CONNECTED) {
            wake(tv.mac)
        }
        c.press(key)
    }

    fun launch(app: TvApp) {
        _controller.value?.launch(app)
    }

    fun wake(mac: String) {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                WakeOnLan.send(mac)
                _toast.value = "Wake-on-LAN sent"
            } catch (e: Exception) {
                _toast.value = "Wake-on-LAN failed: ${e.message}"
            }
        }
    }

    fun toastShown() { _toast.value = null }

    // --- Android TV pairing ---

    fun startPairing() {
        val tv = _current.value ?: return
        cancelPairing()
        _pairing.value = PairingUi.Starting
        viewModelScope.launch(Dispatchers.IO) {
            val session = AtvPairing(tv.host, certs, "${Build.MANUFACTURER} ${Build.MODEL}")
            try {
                session.start()
                pairingSession = session
                _pairing.value = PairingUi.WaitingCode()
            } catch (e: Exception) {
                session.close()
                _pairing.value = PairingUi.Failed(e.message ?: "Pairing failed")
            }
        }
    }

    fun submitCode(code: String) {
        val session = pairingSession ?: return
        _pairing.value = PairingUi.Verifying
        viewModelScope.launch(Dispatchers.IO) {
            try {
                session.finish(code)
                session.close()
                pairingSession = null
                _pairing.value = PairingUi.Hidden
                _toast.value = "Paired!"
                connectCurrent()
            } catch (e: PairingException) {
                if (e.retryable) {
                    _pairing.value = PairingUi.WaitingCode(e.message)
                } else {
                    session.close(); pairingSession = null
                    _pairing.value = PairingUi.Failed(e.message ?: "Pairing failed")
                }
            } catch (e: Exception) {
                session.close(); pairingSession = null
                _pairing.value = PairingUi.Failed(e.message ?: "Pairing failed")
            }
        }
    }

    fun cancelPairing() {
        val s = pairingSession
        pairingSession = null
        if (s != null) viewModelScope.launch(Dispatchers.IO) { s.close() }
        _pairing.value = PairingUi.Hidden
    }

    // --- lifecycle / hardware keys ---

    fun onAppStop() {
        if (pairingSession != null) return // keep the pairing alive while the user looks at the TV
        _controller.value?.close()
        _controller.value = null
    }

    fun onAppStart() {
        if (_current.value != null && _controller.value == null) connectCurrent()
    }

    /** Phone volume buttons drive the TV volume while a remote is open. */
    fun handleHardwareKey(event: KeyEvent): Boolean {
        if (_current.value == null) return false
        val key = when (event.keyCode) {
            KeyEvent.KEYCODE_VOLUME_UP -> RemoteKey.VOL_UP
            KeyEvent.KEYCODE_VOLUME_DOWN -> RemoteKey.VOL_DOWN
            else -> return false
        }
        if (event.action == KeyEvent.ACTION_DOWN) press(key)
        return true
    }

    override fun onCleared() {
        discovery.stop()
        _controller.value?.close()
        pairingSession?.let { s -> Thread { s.close() }.start() }
    }
}
