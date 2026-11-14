# TV Remote (Android)

Wi-Fi remote control for a Samsung Galaxy (or any Android 8+ phone) driving:

| TV | Connection | Setup on the TV |
|---|---|---|
| **Sony Bravia** Google TV / Android TV (2015+) | Android TV Remote protocol (recommended) | Nothing — pair once with the code shown on screen |
| **ACE** (or any) Google TV / Android TV | Android TV Remote protocol | Nothing — pair once |
| **Sony Bravia** (fallback / older) | Sony IP control (HTTP + Pre-Shared Key) | Settings > Network > Home network > IP control: Authentication "Normal and Pre-Shared Key", set a key, enable "Remote start" |

The Galaxy S25 has **no infrared emitter**: the TV must be on the same Wi-Fi. A TV that is not Android/Google TV
(e.g. Linux/VIDAA-based budget models) cannot be controlled by this app.

## Download

Direct APK (always the latest build):
**https://github.com/BM85repository/album-photos/releases/download/tv-remote-latest/TVRemote.apk**

Open the link on the phone, tap the file, allow "Install unknown apps" for the browser when asked.

## Features

Power, input, settings, D-pad/OK, back/home/menu, volume/mute, channels, media keys, number pad, Netflix/YouTube/
Prime Video/Disney+ launch, auto-discovery of Android TVs on the Wi-Fi, phone volume buttons → TV volume,
optional Wake-on-LAN (MAC address) for deep standby.

## Build

GitHub Actions (`.github/workflows/tv-remote.yml`) builds and publishes on every push touching `tv-remote/`.
Locally: `./gradlew assembleRelease` (Android SDK required).

Note: the signing keystore is committed for simplicity (so each update installs over the previous one).
For a public repository, move it to a GitHub secret before distributing the app beyond personal use.
