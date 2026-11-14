package com.bm85.tvremote.ui

import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.PressInteraction
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.VolumeOff
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Dialpad
import androidx.compose.material.icons.filled.FastForward
import androidx.compose.material.icons.filled.FastRewind
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Input
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowLeft
import androidx.compose.material.icons.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.PowerSettingsNew
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Remove
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.SkipPrevious
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Subtitles
import androidx.compose.material.icons.filled.ViewList
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.bm85.tvremote.PairingUi
import com.bm85.tvremote.RemoteKey
import com.bm85.tvremote.RemoteViewModel
import com.bm85.tvremote.SavedTv
import com.bm85.tvremote.Status
import com.bm85.tvremote.TvApp
import com.bm85.tvremote.TvState
import com.bm85.tvremote.TvType
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RemoteScreen(vm: RemoteViewModel, tv: SavedTv) {
    val controller by vm.controller.collectAsStateWithLifecycle()
    val fallback = remember { MutableStateFlow(TvState()) }
    val state by (controller?.state ?: fallback).collectAsStateWithLifecycle()
    val pairing by vm.pairing.collectAsStateWithLifecycle()
    val toast by vm.toast.collectAsStateWithLifecycle()
    val context = LocalContext.current
    var showNumbers by remember { mutableStateOf(false) }
    var showApps by remember { mutableStateOf(false) }

    BackHandler { vm.closeRemote() }
    LaunchedEffect(toast) {
        toast?.let { Toast.makeText(context, it, Toast.LENGTH_SHORT).show(); vm.toastShown() }
    }
    val press: (RemoteKey) -> Unit = { vm.press(it) }

    Scaffold(
        containerColor = Bg,
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(tv.name.ifBlank { tv.host }, fontWeight = FontWeight.Bold, maxLines = 1)
                        StatusLine(state)
                    }
                },
                navigationIcon = { IconButton(onClick = { vm.closeRemote() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } },
                actions = { IconButton(onClick = { vm.reconnect() }) { Icon(Icons.Filled.Refresh, "Reconnect") } },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Bg),
            )
        },
    ) { pad ->
        Column(
            Modifier.fillMaxSize().padding(pad).verticalScroll(rememberScrollState()).padding(horizontal = 20.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            if (state.status == Status.NEEDS_PAIRING || state.status == Status.ERROR) {
                ProblemCard(state, tv, onPair = { vm.startPairing() }, onRetry = { vm.reconnect() })
                Spacer(Modifier.height(12.dp))
            }

            // Top row
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                IconKey(Icons.Filled.PowerSettingsNew, "Power", color = PowerRed) { press(RemoteKey.POWER) }
                IconKey(Icons.Filled.Input, "Input") { press(RemoteKey.INPUT) }
                IconKey(Icons.Filled.Settings, "Settings") { press(RemoteKey.SETTINGS) }
                IconKey(Icons.Filled.Dialpad, "Numbers") { showNumbers = true }
            }
            Spacer(Modifier.height(24.dp))

            DPad(press)
            Spacer(Modifier.height(20.dp))

            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                IconKey(Icons.AutoMirrored.Filled.ArrowBack, "Back") { press(RemoteKey.BACK) }
                IconKey(Icons.Filled.Home, "Home") { press(RemoteKey.HOME) }
                IconKey(Icons.Filled.Menu, "Menu") { press(RemoteKey.MENU) }
            }
            Spacer(Modifier.height(20.dp))

            // Volume / mute / channel
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Rocker("VOL", up = { press(RemoteKey.VOL_UP) }, down = { press(RemoteKey.VOL_DOWN) })
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    IconKey(Icons.AutoMirrored.Filled.VolumeOff, "Mute", color = if (state.muted == true) Accent else Key) { press(RemoteKey.MUTE) }
                    Spacer(Modifier.height(8.dp))
                    Text(volumeText(state), color = TextDim, fontSize = 12.sp)
                    Spacer(Modifier.height(16.dp))
                    IconKey(Icons.Filled.Info, "Info") { press(RemoteKey.INFO) }
                    Spacer(Modifier.height(12.dp))
                    Row {
                        IconKey(Icons.Filled.ViewList, "Guide", size = 48.dp) { press(RemoteKey.GUIDE) }
                        Spacer(Modifier.width(8.dp))
                        IconKey(Icons.Filled.Subtitles, "Subtitles", size = 48.dp) { press(RemoteKey.SUBTITLES) }
                    }
                }
                Rocker("CH", up = { press(RemoteKey.CH_UP) }, down = { press(RemoteKey.CH_DOWN) })
            }
            Spacer(Modifier.height(24.dp))

            // Media
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                IconKey(Icons.Filled.SkipPrevious, "Previous", size = 48.dp) { press(RemoteKey.PREV) }
                IconKey(Icons.Filled.FastRewind, "Rewind", size = 48.dp, repeat = true) { press(RemoteKey.REWIND) }
                IconKey(Icons.Filled.PlayArrow, "Play", size = 48.dp) { press(RemoteKey.PLAY) }
                IconKey(Icons.Filled.Pause, "Pause", size = 48.dp) { press(RemoteKey.PAUSE) }
                IconKey(Icons.Filled.Stop, "Stop", size = 48.dp) { press(RemoteKey.STOP) }
                IconKey(Icons.Filled.FastForward, "Forward", size = 48.dp, repeat = true) { press(RemoteKey.FFWD) }
                IconKey(Icons.Filled.SkipNext, "Next", size = 48.dp) { press(RemoteKey.NEXT) }
            }
            Spacer(Modifier.height(24.dp))

            // Apps
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                AppKey("Netflix", Color(0xFFE50914), Modifier.weight(1f)) { vm.launch(TvApp.NETFLIX) }
                AppKey("YouTube", Color(0xFFFF0000), Modifier.weight(1f)) { vm.launch(TvApp.YOUTUBE) }
                AppKey("More…", Key, Modifier.weight(1f)) { showApps = true }
            }
            state.currentApp?.let {
                Spacer(Modifier.height(12.dp))
                Text("On screen: $it", color = TextDim, fontSize = 12.sp)
            }
            Spacer(Modifier.height(12.dp))
            Text("Tip: the phone's volume buttons control the TV volume.", color = TextDim, fontSize = 12.sp, textAlign = TextAlign.Center)
            Spacer(Modifier.height(32.dp))
        }
    }

    if (showNumbers) NumberPad(onDismiss = { showNumbers = false }, press = press)
    if (showApps) {
        AlertDialog(
            onDismissRequest = { showApps = false },
            title = { Text("Open an app") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    TvApp.entries.forEach { app ->
                        Button(onClick = { vm.launch(app); showApps = false }, modifier = Modifier.fillMaxWidth()) {
                            Icon(Icons.Filled.Link, null); Spacer(Modifier.width(8.dp)); Text(app.label)
                        }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { showApps = false }) { Text("Close") } },
        )
    }
    PairingDialog(pairing, onSubmit = { vm.submitCode(it) }, onRetry = { vm.startPairing() }, onCancel = { vm.cancelPairing() })
}

private fun volumeText(s: TvState): String = when {
    s.volume == null -> ""
    s.volumeMax != null && s.volumeMax > 0 -> "Vol ${s.volume}/${s.volumeMax}"
    else -> "Vol ${s.volume}"
}

@Composable
private fun StatusLine(s: TvState) {
    val (text, color) = when (s.status) {
        Status.CONNECTED -> (if (s.powerOn == false) "Connected • TV off" else "Connected") to Color(0xFF22C55E)
        Status.CONNECTING -> "Connecting…" to Color(0xFFF59E0B)
        Status.NEEDS_PAIRING -> "Pairing required" to Color(0xFFF59E0B)
        Status.ERROR -> "Not connected" to PowerRed
        Status.DISCONNECTED -> "Disconnected" to TextDim
    }
    Text(text, color = color, fontSize = 12.sp)
}

@Composable
private fun ProblemCard(state: TvState, tv: SavedTv, onPair: () -> Unit, onRetry: () -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = Panel), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            if (state.status == Status.NEEDS_PAIRING) {
                Text("Pair this phone with the TV", fontWeight = FontWeight.Bold)
                Text("A code will appear on the TV screen. Only needed once.", color = TextDim, fontSize = 13.sp)
                Spacer(Modifier.height(10.dp))
                Button(onClick = onPair) { Text("Start pairing") }
            } else {
                Text(state.message ?: "Not connected", color = Color.White, fontSize = 13.sp)
                Spacer(Modifier.height(6.dp))
                Text(
                    "Check: TV on, same Wi-Fi, IP ${tv.host}" +
                        if (tv.type == TvType.SONY_IP) ", IP control + Pre-Shared Key enabled." else ".",
                    color = TextDim, fontSize = 12.sp,
                )
                Spacer(Modifier.height(10.dp))
                Row {
                    Button(onClick = onRetry) { Text("Retry") }
                    if (tv.type == TvType.ANDROID_TV) {
                        Spacer(Modifier.width(10.dp))
                        TextButton(onClick = onPair) { Text("Pair again") }
                    }
                }
            }
        }
    }
}

@Composable
private fun PairingDialog(p: PairingUi, onSubmit: (String) -> Unit, onRetry: () -> Unit, onCancel: () -> Unit) {
    if (p == PairingUi.Hidden) return
    var code by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onCancel,
        title = { Text("Pairing") },
        text = {
            when (p) {
                PairingUi.Starting -> Row(verticalAlignment = Alignment.CenterVertically) {
                    CircularProgressIndicator(Modifier.size(24.dp)); Spacer(Modifier.width(12.dp)); Text("Contacting the TV…")
                }
                is PairingUi.WaitingCode -> Column {
                    Text("Enter the 6-character code displayed on the TV.")
                    Spacer(Modifier.height(10.dp))
                    OutlinedTextField(
                        value = code,
                        onValueChange = { v -> code = v.uppercase().filter { it in "0123456789ABCDEF" }.take(6) },
                        singleLine = true,
                        label = { Text("Code") },
                        isError = p.error != null,
                        supportingText = { p.error?.let { Text(it) } },
                        keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Characters, autoCorrectEnabled = false),
                    )
                }
                PairingUi.Verifying -> Row(verticalAlignment = Alignment.CenterVertically) {
                    CircularProgressIndicator(Modifier.size(24.dp)); Spacer(Modifier.width(12.dp)); Text("Checking…")
                }
                is PairingUi.Failed -> Text(p.error)
                PairingUi.Hidden -> {}
            }
        },
        confirmButton = {
            when (p) {
                is PairingUi.WaitingCode -> TextButton(enabled = code.length == 6, onClick = { onSubmit(code) }) { Text("Pair") }
                is PairingUi.Failed -> TextButton(onClick = onRetry) { Text("Try again") }
                else -> {}
            }
        },
        dismissButton = { TextButton(onClick = onCancel) { Text("Cancel") } },
    )
}

@Composable
private fun NumberPad(onDismiss: () -> Unit, press: (RemoteKey) -> Unit) {
    val keys = listOf(
        listOf("1" to RemoteKey.N1, "2" to RemoteKey.N2, "3" to RemoteKey.N3),
        listOf("4" to RemoteKey.N4, "5" to RemoteKey.N5, "6" to RemoteKey.N6),
        listOf("7" to RemoteKey.N7, "8" to RemoteKey.N8, "9" to RemoteKey.N9),
        listOf("OK" to RemoteKey.OK, "0" to RemoteKey.N0, "⌫" to RemoteKey.BACK),
    )
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Numbers") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp), horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.fillMaxWidth()) {
                keys.forEach { row ->
                    Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                        row.forEach { (label, key) ->
                            PressBox(onPress = { press(key) }, modifier = Modifier.size(64.dp)) {
                                Text(label, fontSize = 22.sp, fontWeight = FontWeight.SemiBold)
                            }
                        }
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Close") } },
    )
}

@Composable
private fun DPad(press: (RemoteKey) -> Unit) {
    Box(Modifier.size(250.dp).clip(CircleShape).background(Panel), contentAlignment = Alignment.Center) {
        PressBox(onPress = { press(RemoteKey.UP) }, repeat = true, color = Color.Transparent,
            modifier = Modifier.align(Alignment.TopCenter).size(84.dp)) { Icon(Icons.Filled.KeyboardArrowUp, "Up", Modifier.size(40.dp)) }
        PressBox(onPress = { press(RemoteKey.DOWN) }, repeat = true, color = Color.Transparent,
            modifier = Modifier.align(Alignment.BottomCenter).size(84.dp)) { Icon(Icons.Filled.KeyboardArrowDown, "Down", Modifier.size(40.dp)) }
        PressBox(onPress = { press(RemoteKey.LEFT) }, repeat = true, color = Color.Transparent,
            modifier = Modifier.align(Alignment.CenterStart).size(84.dp)) { Icon(Icons.Filled.KeyboardArrowLeft, "Left", Modifier.size(40.dp)) }
        PressBox(onPress = { press(RemoteKey.RIGHT) }, repeat = true, color = Color.Transparent,
            modifier = Modifier.align(Alignment.CenterEnd).size(84.dp)) { Icon(Icons.Filled.KeyboardArrowRight, "Right", Modifier.size(40.dp)) }
        PressBox(onPress = { press(RemoteKey.OK) }, color = Key, modifier = Modifier.size(96.dp)) {
            Text("OK", fontSize = 20.sp, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun Rocker(label: String, up: () -> Unit, down: () -> Unit) {
    Column(
        Modifier.width(72.dp).clip(RoundedCornerShape(36.dp)).background(Panel),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        PressBox(onPress = up, repeat = true, color = Color.Transparent, modifier = Modifier.size(72.dp)) { Icon(Icons.Filled.Add, "$label up") }
        Text(label, color = TextDim, fontSize = 12.sp, fontWeight = FontWeight.Bold)
        PressBox(onPress = down, repeat = true, color = Color.Transparent, modifier = Modifier.size(72.dp)) { Icon(Icons.Filled.Remove, "$label down") }
    }
}

@Composable
private fun IconKey(
    icon: ImageVector,
    description: String,
    size: Dp = 60.dp,
    color: Color = Key,
    repeat: Boolean = false,
    onPress: () -> Unit,
) {
    PressBox(onPress = onPress, repeat = repeat, color = color, modifier = Modifier.size(size)) {
        Icon(icon, description, tint = Color.White)
    }
}

@Composable
private fun AppKey(label: String, color: Color, modifier: Modifier, onPress: () -> Unit) {
    PressBox(onPress = onPress, color = color, shape = RoundedCornerShape(14.dp), modifier = modifier.height(52.dp)) {
        Text(label, fontWeight = FontWeight.Bold, color = Color.White)
    }
}

/** Button that fires on touch-down (like a real remote), with haptics and optional auto-repeat when held. */
@Composable
private fun PressBox(
    onPress: () -> Unit,
    modifier: Modifier = Modifier,
    repeat: Boolean = false,
    color: Color = Key,
    shape: Shape = CircleShape,
    content: @Composable () -> Unit,
) {
    val haptic = LocalHapticFeedback.current
    val scope = rememberCoroutineScope()
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val currentOnPress by rememberUpdatedState(onPress)
    val bg = if (pressed) (if (color == Color.Transparent) KeyPressed.copy(alpha = 0.6f) else KeyPressed) else color
    Box(
        modifier
            .clip(shape)
            .background(bg)
            .pointerInput(repeat) {
                detectTapGestures(onPress = { offset ->
                    val press = PressInteraction.Press(offset)
                    interaction.emit(press)
                    haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                    currentOnPress()
                    val job = if (repeat) scope.launch {
                        delay(450)
                        while (isActive) {
                            currentOnPress()
                            delay(130)
                        }
                    } else null
                    val released = tryAwaitRelease()
                    job?.cancel()
                    interaction.emit(if (released) PressInteraction.Release(press) else PressInteraction.Cancel(press))
                })
            },
        contentAlignment = Alignment.Center,
    ) { content() }
}
