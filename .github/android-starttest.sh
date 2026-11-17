#!/bin/bash
# Installiert die App, startet sie zweimal und sammelt Absturzmeldungen + Bildschirmfotos.
mkdir -p starttest
APK=android/app/build/outputs/apk/release/app-release.apk
adb install -r "$APK" || exit 1
adb logcat -c
adb shell am start -W -n de.rh.pctools/.MainActivity
sleep 12
adb exec-out screencap -p > starttest/start1.png
adb logcat -d > starttest/logcat1.txt
adb shell am start -W -n de.rh.pctools/.MainActivity
sleep 8
adb exec-out screencap -p > starttest/start2.png
adb logcat -d > starttest/logcat2.txt
adb shell am force-stop de.rh.pctools
adb shell am start -W -n de.rh.pctools/.MainActivity --ez demo_test true
sleep 8
adb exec-out screencap -p > starttest/demo.png
adb logcat -d > starttest/logcat3.txt
adb shell dumpsys activity activities | grep -E "mResumedActivity|topResumedActivity" > starttest/activity.txt || true
CRASH=$(grep -h -A40 -E "FATAL EXCEPTION|AndroidRuntime: " starttest/logcat*.txt | grep -E "AndroidRuntime" | head -60)
if [ -n "$CRASH" ]; then
  echo "$CRASH" > starttest/crash.txt
  echo "$CRASH" | head -30 | while IFS= read -r l; do echo "::error::$l"; done
  exit 1
fi
echo "::notice::Kein Absturz. Aktiv: $(cat starttest/activity.txt | head -2 | tr '\n' ' ')"
