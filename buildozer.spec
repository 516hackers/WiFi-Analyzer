[app]
title = WiFi Analyzer Pro
package.name = wifi_analyzer
package.domain = org.wifianalyzer
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0
requirements = python3,kivy,psutil,speedtest-cli
orientation = portrait
osx.python_version = 3
osx.kivy_version = 2.1.0
fullscreen = 0

# Android
android.permissions = INTERNET,ACCESS_WIFI_STATE,CHANGE_WIFI_STATE,ACCESS_NETWORK_STATE,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION
android.api = 30
android.minapi = 21
android.ndk = 23b
android.sdk = 30
android.arch = arm64-v8a
android.allow_backup = True
android.add_openssl = True

# iOS
ios.kivy_ios_url = https://github.com/kivy/kivy-ios
ios.codesign.allowed = false
