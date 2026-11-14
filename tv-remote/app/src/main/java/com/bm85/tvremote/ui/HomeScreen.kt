package com.bm85.tvremote.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Tv
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.bm85.tvremote.RemoteViewModel
import com.bm85.tvremote.SavedTv
import com.bm85.tvremote.TvType

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(vm: RemoteViewModel) {
    val saved by vm.saved.collectAsStateWithLifecycle()
    val found by vm.discovery.found.collectAsStateWithLifecycle()
    var editing by remember { mutableStateOf<SavedTv?>(null) }

    DisposableEffect(Unit) {
        vm.discovery.start()
        onDispose { vm.discovery.stop() }
    }

    Scaffold(
        containerColor = Bg,
        topBar = {
            TopAppBar(
                title = { Text("TV Remote", fontWeight = FontWeight.Bold) },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Bg),
            )
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = { editing = SavedTv(vm.newId(), "", "", TvType.ANDROID_TV) },
                icon = { Icon(Icons.Filled.Add, null) },
                text = { Text("Add TV") },
            )
        },
    ) { pad ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(pad).padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            item { Section("My TVs") }
            if (saved.isEmpty()) {
                item { Text("No TV yet. Pick one found on your Wi-Fi below, or tap \"Add TV\".", color = TextDim) }
            }
            items(saved, key = { it.id }) { tv ->
                TvCard(
                    title = tv.name.ifBlank { tv.host },
                    subtitle = "${tv.host} • " + if (tv.type == TvType.ANDROID_TV) "Google/Android TV" else "Sony IP control",
                    onClick = { vm.open(tv) },
                    actions = {
                        IconButton(onClick = { editing = tv }) { Icon(Icons.Filled.Edit, "Edit") }
                        IconButton(onClick = { vm.delete(tv) }) { Icon(Icons.Filled.Delete, "Delete") }
                    },
                )
            }
            item { Section("Found on Wi-Fi (Google TV / Android TV)") }
            val newFound = found.filter { f -> saved.none { it.host == f.host } }
            if (newFound.isEmpty()) {
                item {
                    Text(
                        "Searching… The phone must be on the same Wi-Fi as the TV, and the TV switched on. " +
                            "Not found? Add it by IP address (TV: Settings > Network > Status).",
                        color = TextDim,
                    )
                }
            }
            items(newFound, key = { "f" + it.host }) { f ->
                TvCard(
                    title = f.name,
                    subtitle = f.host,
                    icon = { Icon(Icons.Filled.Wifi, null, tint = Accent) },
                    onClick = { editing = SavedTv(vm.newId(), f.name, f.host, TvType.ANDROID_TV) },
                    actions = { IconButton(onClick = { editing = SavedTv(vm.newId(), f.name, f.host, TvType.ANDROID_TV) }) { Icon(Icons.Filled.Add, "Add") } },
                )
            }
            item { Spacer(Modifier.padding(40.dp)) }
        }
    }

    editing?.let { tv ->
        EditTvDialog(
            initial = tv,
            onDismiss = { editing = null },
            onSave = { vm.save(it); editing = null; vm.open(it) },
        )
    }
}

@Composable
private fun Section(text: String) {
    Text(text, style = MaterialTheme.typography.titleSmall, color = Accent, modifier = Modifier.padding(top = 12.dp))
}

@Composable
private fun TvCard(
    title: String,
    subtitle: String,
    onClick: () -> Unit,
    icon: @Composable () -> Unit = { Icon(Icons.Filled.Tv, null, tint = Accent) },
    actions: @Composable () -> Unit = {},
) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = Panel),
    ) {
        Row(Modifier.padding(start = 16.dp, top = 12.dp, bottom = 12.dp, end = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            icon()
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text(title, fontWeight = FontWeight.SemiBold)
                Text(subtitle, color = TextDim, style = MaterialTheme.typography.bodySmall)
            }
            actions()
        }
    }
}

@Composable
private fun EditTvDialog(initial: SavedTv, onDismiss: () -> Unit, onSave: (SavedTv) -> Unit) {
    var name by remember { mutableStateOf(initial.name) }
    var host by remember { mutableStateOf(initial.host) }
    var type by remember { mutableStateOf(initial.type) }
    var psk by remember { mutableStateOf(initial.psk) }
    var mac by remember { mutableStateOf(initial.mac) }
    val valid = host.isNotBlank() && (type == TvType.ANDROID_TV || psk.isNotBlank())

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (initial.host.isEmpty()) "Add TV" else "TV settings") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(name, { name = it }, label = { Text("Name (e.g. Living room)") }, singleLine = true)
                OutlinedTextField(
                    host, { host = it.trim() }, label = { Text("TV IP address (e.g. 192.168.1.40)") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                )
                Text("Connection type", style = MaterialTheme.typography.labelLarge)
                TypeOption(
                    selected = type == TvType.ANDROID_TV,
                    title = "Google TV / Android TV (recommended)",
                    detail = "Sony Bravia (2015+), ACE Android/Google TV and other Android TVs. Pair once with a code shown on the TV.",
                    onClick = { type = TvType.ANDROID_TV },
                )
                TypeOption(
                    selected = type == TvType.SONY_IP,
                    title = "Sony Bravia IP control",
                    detail = "TV: Settings > Network > Home network > IP control > Authentication \"Normal and Pre-Shared Key\".",
                    onClick = { type = TvType.SONY_IP },
                )
                if (type == TvType.SONY_IP) {
                    OutlinedTextField(psk, { psk = it.trim() }, label = { Text("Pre-Shared Key (set on the TV)") }, singleLine = true)
                }
                OutlinedTextField(
                    mac, { mac = it.trim() }, label = { Text("MAC address (optional, power-on)") }, singleLine = true,
                    supportingText = { Text("Used for Wake-on-LAN when the TV is in deep standby.") },
                )
            }
        },
        confirmButton = {
            TextButton(enabled = valid, onClick = {
                onSave(initial.copy(name = name.trim(), host = host.trim(), type = type, psk = psk.trim(), mac = mac.trim()))
            }) { Text("Save & connect") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
private fun TypeOption(selected: Boolean, title: String, detail: String, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().selectable(selected = selected, onClick = onClick).padding(vertical = 4.dp),
        verticalAlignment = Alignment.Top,
    ) {
        RadioButton(selected = selected, onClick = onClick)
        Column(Modifier.padding(top = 12.dp)) {
            Text(title, fontWeight = FontWeight.SemiBold)
            Text(detail, color = TextDim, style = MaterialTheme.typography.bodySmall)
        }
    }
}
