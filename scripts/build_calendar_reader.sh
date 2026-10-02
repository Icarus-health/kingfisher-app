#!/bin/bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$root/build/calendar-module-cache"
xcrun swiftc -swift-version 5 -target "$(uname -m)-apple-macosx14.0" \
  -module-cache-path "$root/build/calendar-module-cache" \
  "$root/macos/CalendarReader.swift" \
  -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist \
  -Xlinker "$root/macos/CalendarReader-Info.plist" \
  -o "$root/build/kingfisher-calendar"
codesign --force --sign - --identifier health.kingfisher.calendar-reader "$root/build/kingfisher-calendar"
printf '%s\n' "$root/build/kingfisher-calendar"
