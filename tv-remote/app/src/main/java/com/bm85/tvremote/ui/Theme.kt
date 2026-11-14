package com.bm85.tvremote.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val Bg = Color(0xFF101318)
val Panel = Color(0xFF1B2028)
val Key = Color(0xFF262C36)
val KeyPressed = Color(0xFF3B4555)
val Accent = Color(0xFF3B82F6)
val PowerRed = Color(0xFFDC2626)
val TextDim = Color(0xFF9AA4B2)

@Composable
fun TvRemoteTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = Accent,
            background = Bg,
            surface = Panel,
            surfaceContainer = Panel,
            surfaceContainerHigh = Key,
            onBackground = Color.White,
            onSurface = Color.White,
        ),
        content = content,
    )
}
