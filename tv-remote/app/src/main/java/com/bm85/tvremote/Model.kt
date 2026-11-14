package com.bm85.tvremote

import kotlinx.coroutines.flow.StateFlow

enum class TvType { ANDROID_TV, SONY_IP }

data class SavedTv(
    val id: String,
    val name: String,
    val host: String,
    val type: TvType,
    val psk: String = "",
    val mac: String = "",
)

enum class Status { DISCONNECTED, CONNECTING, CONNECTED, NEEDS_PAIRING, ERROR }

data class TvState(
    val status: Status = Status.DISCONNECTED,
    val message: String? = null,
    val powerOn: Boolean? = null,
    val volume: Int? = null,
    val volumeMax: Int? = null,
    val muted: Boolean? = null,
    val currentApp: String? = null,
)

/**
 * One logical button. [atv] = Android KeyEvent code (Android TV Remote protocol),
 * [sony] = candidate IRCC command names (Sony Bravia IP control), first match wins.
 */
enum class RemoteKey(val atv: Int, val sony: List<String>) {
    POWER(26, listOf("Power", "TvPower")),
    INPUT(178, listOf("Input")),
    HOME(3, listOf("Home")),
    BACK(4, listOf("Return", "Back")),
    MENU(82, listOf("Options")),
    SETTINGS(176, listOf("ActionMenu", "SyncMenu")),
    UP(19, listOf("Up")),
    DOWN(20, listOf("Down")),
    LEFT(21, listOf("Left")),
    RIGHT(22, listOf("Right")),
    OK(23, listOf("Confirm")),
    VOL_UP(24, listOf("VolumeUp")),
    VOL_DOWN(25, listOf("VolumeDown")),
    MUTE(164, listOf("Mute")),
    CH_UP(166, listOf("ChannelUp")),
    CH_DOWN(167, listOf("ChannelDown")),
    PLAY(126, listOf("Play")),
    PAUSE(127, listOf("Pause")),
    STOP(86, listOf("Stop")),
    NEXT(87, listOf("Next")),
    PREV(88, listOf("Prev")),
    REWIND(89, listOf("Rewind")),
    FFWD(90, listOf("Forward")),
    INFO(165, listOf("Display")),
    GUIDE(172, listOf("Guide", "GGuide", "EPG")),
    SUBTITLES(175, listOf("SubTitle")),
    N0(7, listOf("Num0")), N1(8, listOf("Num1")), N2(9, listOf("Num2")), N3(10, listOf("Num3")),
    N4(11, listOf("Num4")), N5(12, listOf("Num5")), N6(13, listOf("Num6")), N7(14, listOf("Num7")),
    N8(15, listOf("Num8")), N9(16, listOf("Num9")),
}

enum class TvApp(val label: String, val link: String, val sony: List<String>) {
    NETFLIX("Netflix", "https://www.netflix.com/title", listOf("Netflix")),
    YOUTUBE("YouTube", "https://www.youtube.com", listOf("YouTube")),
    PRIME("Prime Video", "https://app.primevideo.com", emptyList()),
    DISNEY("Disney+", "https://www.disneyplus.com", emptyList()),
}

interface TvController {
    val state: StateFlow<TvState>
    fun connect()
    fun press(key: RemoteKey)
    fun launch(app: TvApp)
    fun close()
}
