#!/bin/bash
# Baut den Fahrzeit-Adapter (Apple Karten). UNGEPRÜFT: nie auf einem Mac ausgeführt.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$root/build/route-module-cache"
xcrun swiftc -swift-version 5 -target "$(uname -m)-apple-macosx14.0" \
  -module-cache-path "$root/build/route-module-cache" \
  "$root/macos/RouteReader.swift" \
  -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist \
  -Xlinker "$root/macos/RouteReader-Info.plist" \
  -o "$root/build/kingfisher-route"
codesign --force --sign - --identifier health.kingfisher.route-reader "$root/build/kingfisher-route"
printf '%s\n' "$root/build/kingfisher-route"
