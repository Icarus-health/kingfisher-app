#!/bin/bash
# Kingfisher starten: im Finder doppelklicken (Fremdprobe 2, Befund 1). Es öffnet sich ein Fenster, in dem steht, was
# geschieht; tippen muss darin niemand. Fehlt etwas (Docker Desktop, die Entwicklerwerkzeuge von Apple), steht dort
# ein Satz mit Link. Die eigentliche Arbeit macht scripts/kingfisher_starten.py.
cd "$(dirname "$0")" || exit 1
PY="$(command -v python3 || echo /usr/bin/python3)"
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
  echo "Kingfisher braucht die kostenlosen Entwicklerwerkzeuge von Apple. macOS bietet sie gleich in einem Fenster an;"
  echo "installiere sie dort und doppelklicke danach diesen Starter noch einmal."
  xcode-select --install >/dev/null 2>&1
  read -r -p "Zum Schließen die Eingabetaste drücken. " _
  exit 1
fi
"$PY" scripts/kingfisher_starten.py "$@"
status=$?
if [ "$status" -ne 0 ]; then
  read -r -p "Zum Schließen die Eingabetaste drücken. " _
fi
exit "$status"
