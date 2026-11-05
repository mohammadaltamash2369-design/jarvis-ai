[app]
title = Jarvis AI
package.name = jarvisai
package.domain = org.jarvis
source.dir = .
source.include_exts = py,png,gif,ttf,otf,json
source.exclude_dirs = __pycache__,bin,venv,.git,.github,.buildozer,sample-packs,custom
version = 1.0
requirements = python3==3.11.5,hostpython3==3.11.5,kivy==2.3.0,pyjnius,android,certifi
orientation = portrait
fullscreen = 1
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
presplash.color = #000000
android.permissions = INTERNET,RECORD_AUDIO,QUERY_ALL_PACKAGES,com.android.alarm.permission.SET_ALARM
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True

p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
