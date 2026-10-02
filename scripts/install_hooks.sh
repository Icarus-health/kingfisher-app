#!/usr/bin/env bash
# Legt den Hook `pre-push` (Schnellprüfung, siehe scripts/hooks/pre-push) für dieses Repository an.
#
#   scripts/install_hooks.sh               anlegen (Symlink auf scripts/hooks/pre-push)
#   scripts/install_hooks.sh --ersetzen    einen fremden pre-push-Hook nach pre-push.alt sichern und ersetzen
#   scripts/install_hooks.sh --entfernen   den angelegten Hook wieder entfernen
#
# Ein bereits vorhandener, fremder Hook wird nie ungefragt überschrieben. Gilt für das Repository und alle seine
# Worktrees (sie teilen das Hook-Verzeichnis); wird nirgends global eingestellt.
set -euo pipefail

WURZEL="$(cd "$(dirname "$0")/.." && pwd)"
QUELLE="$WURZEL/scripts/hooks/pre-push"
HOOKS="$(cd "$WURZEL" && git rev-parse --git-path hooks)"
case "$HOOKS" in /*) ;; *) HOOKS="$WURZEL/$HOOKS" ;; esac
ZIEL="$HOOKS/pre-push"

[ -f "$QUELLE" ] || { echo "Fehlt: $QUELLE" >&2; exit 1; }
chmod +x "$QUELLE"

unser_hook() { [ -L "$ZIEL" ] && [ "$(readlink "$ZIEL")" = "$QUELLE" ]; }

case "${1:-}" in
    --entfernen)
        if unser_hook; then
            rm "$ZIEL"
            echo "Entfernt: $ZIEL"
        elif [ -e "$ZIEL" ] || [ -L "$ZIEL" ]; then
            echo "Nicht angerührt: $ZIEL ist nicht der Hook dieses Repositorys."
        else
            echo "Kein pre-push-Hook angelegt."
        fi
        exit 0
        ;;
    --ersetzen) ersetzen=1 ;;
    "") ersetzen=0 ;;
    *) echo "Unbekannte Angabe: $1 (--ersetzen oder --entfernen)" >&2; exit 2 ;;
esac

mkdir -p "$HOOKS"
if unser_hook; then
    echo "Schon angelegt: $ZIEL"
    exit 0
fi
if [ -e "$ZIEL" ] || [ -L "$ZIEL" ]; then
    if [ "$ersetzen" -ne 1 ]; then
        echo "Es gibt schon einen pre-push-Hook: $ZIEL" >&2
        echo "Nicht überschrieben. Mit --ersetzen wird er nach pre-push.alt gesichert und ersetzt." >&2
        exit 1
    fi
    mv "$ZIEL" "$ZIEL.alt"
    echo "Gesichert: $ZIEL.alt"
fi
ln -s "$QUELLE" "$ZIEL"
echo "Angelegt: $ZIEL -> $QUELLE"
echo "Vor jedem Push läuft jetzt die Schnellprüfung; die volle Prüfung bleibt scripts/ci_lokal.sh."
