[app]
title = LiveAzaan
package.name = liveazaan
package.domain = org.liveazaan
source.dir = .
source.include_exts = py,kv,mp3,pem,rules
version = 1.1.0

requirements = python3==3.11.0,kivy==2.2.1,requests,pyaudio
orientation = portrait
fullscreen = 0

android.permissions = RECORD_AUDIO,INTERNET,WAKE_LOCK,POST_NOTIFICATIONS
android.api = 33
android.minapi = 24
android.sdk = 33
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a,armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1
