#!/bin/bash
set -euo pipefail
BAU=build/mac-app
APP="$BAU/Kingfisher.app"
FASSUNG=1.0.6-preview.6979131
fehler() { echo "build_dmg: $*" >&2; exit 1; }
iconutil -c icns "$BAU/Kingfisher.iconset" -o "$APP/Contents/Resources/Kingfisher.icns"
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
