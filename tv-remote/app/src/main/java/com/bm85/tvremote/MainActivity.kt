package com.bm85.tvremote

import android.os.Bundle
import android.view.KeyEvent
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.bm85.tvremote.ui.HomeScreen
import com.bm85.tvremote.ui.RemoteScreen
import com.bm85.tvremote.ui.TvRemoteTheme

class MainActivity : ComponentActivity() {
    private val vm: RemoteViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            TvRemoteTheme {
                val current by vm.current.collectAsStateWithLifecycle()
                val tv = current
                if (tv == null) HomeScreen(vm) else RemoteScreen(vm, tv)
            }
        }
    }

    override fun onStart() {
        super.onStart()
        vm.onAppStart()
    }

    override fun onStop() {
        super.onStop()
        if (!isChangingConfigurations) vm.onAppStop()
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (vm.handleHardwareKey(event)) return true
        return super.dispatchKeyEvent(event)
    }
}
