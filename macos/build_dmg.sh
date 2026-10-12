#!/usr/bin/env bash
# Baut dist/Kingfisher.dmg mit Kingfisher.app: universell (arm64 und x86_64), ad hoc signiert, nicht
# notarisiert. Läuft nur auf macOS mit den Xcode Command Line Tools (lokal oder in .github/workflows/mac-app.yml).
#
#   bash macos/build_dmg.sh                 Fassung aus der Datei VERSION (fehlt sie: 0.0.0)
#   KINGFISHER_FASSUNG=1.0.1 bash macos/build_dmg.sh
#   bash macos/build_dmg.sh --nur-fassung   gibt nur die Fassung aus (auch ohne Mac, für Tests)
#
# Ins Bündel kommt deploy/compose.app.yaml als Contents/Resources/compose.yaml: Damit startet die App das
# fertige Bild (ghcr.io/icarus-health/kingfisher-app:<fassung>) unter demselben Projektnamen und Volume wie
# `make start`. Geheimnisse kommen nie ins Bündel; die App erzeugt oder übernimmt sie beim ersten Start.
set -euo pipefail

WURZEL="$(cd "$(dirname "$0")/.." && pwd)"
cd "$WURZEL"

COMPOSE_APP="deploy/compose.app.yaml"
ICON_QUELLE="design-source/01_Brand/Approved/App_Icon_Exports/kingfisher-app-icon-1024.png"
ICON_RUECKFALL="design-source/01_Brand/Approved/kingfisher-logo-dark-approved-v1.png"
MINDEST_MACOS="11.3"   # wie scripts/build_mac_window.py und LSMinimumSystemVersion in macos/App/Info.plist

fehler() { echo "build_dmg: $*" >&2; exit 1; }

# Öffentliche Releases bleiben universal; lokale Abnahme kann ausdrücklich nur einen Mac-Typ bauen.
case "${KINGFISHER_ARCHITEKTUR:-universal}" in
    universal) ARCHITEKTUREN=(arm64 x86_64) ;;
    arm64) ARCHITEKTUREN=(arm64) ;;
    x86_64) ARCHITEKTUREN=(x86_64) ;;
    *) fehler "Unbekannte Architektur. Erlaubt sind universal, arm64 und x86_64." ;;
esac

# -- Fassung -----------------------------------------------------------------
FASSUNG="${KINGFISHER_FASSUNG:-}"
if [ -z "$FASSUNG" ] && [ -f VERSION ]; then
    FASSUNG="$(tr -d '[:space:]' < VERSION)"
fi
FASSUNG="${FASSUNG:-0.0.0}"
# SemVer ohne Build-Angabe: Die Fassung ist zugleich der Tag des Bildes, und Docker-Tags erlauben kein „+“.
SEMVER='^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?$'
[[ "$FASSUNG" =~ $SEMVER ]] || fehler "Die Fassung „${FASSUNG}“ ist keine gültige SemVer-Fassung wie 1.0.0."
BUNDLE_VERSION="${FASSUNG%%-*}"   # CFBundleVersion erlaubt nur Zahlen und Punkte

if [ "${1:-}" = "--nur-fassung" ]; then
    echo "$FASSUNG"
    exit 0
fi

# -- Voraussetzungen ---------------------------------------------------------
[ -f "$COMPOSE_APP" ] || fehler "Es fehlt $COMPOSE_APP (Compose-Datei für das fertige Bild). Ohne sie kann die App Kingfisher nicht starten; sie wird nicht hier erzeugt."
[ "$(uname -s)" = "Darwin" ] || fehler "Die Mac-App lässt sich nur auf macOS bauen."
command -v xcrun >/dev/null || fehler "Es fehlen die Xcode Command Line Tools (xcode-select --install)."

[ -f scripts/kingfisher_update_storage.py ] || fehler "Es fehlt scripts/kingfisher_update_storage.py (Speicherprüfung für Updates)."

BAU="build/mac-app"
APP="$BAU/Kingfisher.app"
rm -rf "$BAU"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" dist

# -- Übersetzen: beide Architekturen, dann ein universelles Programm ---------
QUELLEN=(macos/Shared/*.swift macos/App/Logic/*.swift macos/App/*.swift)
for ARCH in "${ARCHITEKTUREN[@]}"; do
    echo "Übersetze für $ARCH …"
    xcrun swiftc -parse-as-library -O -target "$ARCH-apple-macosx$MINDEST_MACOS" \
        -framework AppKit -framework WebKit -framework Security -framework EventKit \
        "${QUELLEN[@]}" -o "$BAU/Kingfisher-$ARCH"
done
if [ "${#ARCHITEKTUREN[@]}" -eq 2 ]; then
    xcrun lipo -create -output "$APP/Contents/MacOS/Kingfisher" "$BAU/Kingfisher-arm64" "$BAU/Kingfisher-x86_64"
else
    cp "$BAU/Kingfisher-${ARCHITEKTUREN[0]}" "$APP/Contents/MacOS/Kingfisher"
fi
chmod 755 "$APP/Contents/MacOS/Kingfisher"

# -- Info.plist, Compose-Datei, Icon -----------------------------------------
sed -e "s/__FASSUNG__/$FASSUNG/g" -e "s/__BUNDLE_VERSION__/$BUNDLE_VERSION/g" \
    macos/App/Info.plist > "$APP/Contents/Info.plist"
plutil -lint "$APP/Contents/Info.plist" >/dev/null
cp "$COMPOSE_APP" "$APP/Contents/Resources/compose.yaml"
cp scripts/kingfisher_update_storage.py "$APP/Contents/Resources/update-storage-probe.py"

ICON="$ICON_QUELLE"
[ -f "$ICON" ] || ICON="$ICON_RUECKFALL"
if [ -f "$ICON" ]; then
    ICONSET="$BAU/Kingfisher.iconset"
    mkdir -p "$ICONSET"
    for GROESSE in 16 32 128 256 512; do
        sips -z "$GROESSE" "$GROESSE" "$ICON" --out "$ICONSET/icon_${GROESSE}x${GROESSE}.png" >/dev/null
        DOPPELT=$((GROESSE * 2))
        sips -z "$DOPPELT" "$DOPPELT" "$ICON" --out "$ICONSET/icon_${GROESSE}x${GROESSE}@2x.png" >/dev/null
    done
    iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/Kingfisher.icns"
else
    echo "Hinweis: kein freigegebenes Icon gefunden; die App bekommt das Standardsymbol."
fi

# -- Ad hoc signieren --------------------------------------------------------
# Metadaten aus den Bildwerkzeugen würden die Signatur ungültig machen.
xattr -cr "$APP"
codesign --force --deep --sign - "$APP"
codesign --verify --strict --deep "$APP"

# -- DMG mit Verknüpfung zu „Programme“ --------------------------------------
INHALT="$BAU/dmg"
mkdir -p "$INHALT"
cp -R "$APP" "$INHALT/"
ln -s /Applications "$INHALT/Programme"
rm -f dist/Kingfisher.dmg
# hdiutil scheitert auf CI-Rechnern gelegentlich mit „Resource busy“; zwei weitere Versuche.
for VERSUCH in 1 2 3; do
    if hdiutil create -volname "Kingfisher" -srcfolder "$INHALT" -ov -format UDZO dist/Kingfisher.dmg; then
        break
    fi
    [ "$VERSUCH" -lt 3 ] || fehler "hdiutil konnte das DMG nicht anlegen."
    sleep 5
done
echo "Fertig: dist/Kingfisher.dmg (Fassung $FASSUNG)"
