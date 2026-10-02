#!/usr/bin/env bash
# Lokaler Ersatz für .github/workflows/ci.yml, solange GitHub Actions nicht
# läuft (zum Beispiel bei aufgebrauchtem Minutenkontingent). Führt dieselben
# Prüfungen aus wie die CI, in derselben Reihenfolge und in UTC wie der Runner.
#
#   scripts/ci_lokal.sh            alle Jobs
#   scripts/ci_lokal.sh sidecar    nur einzelne Jobs: sidecar, ui
#
# Fehlt ein Werkzeug (npm), wird der Job als übersprungen gemeldet,
# nie als bestanden. Am Ende steht eine Zusammenfassung mit Commit.
set -uo pipefail

cd "$(dirname "$0")/.."
export TZ=UTC

PY="${PY:-.venv/bin/python}"
[ -x "$PY" ] || PY=python3
JOBS=("$@")
[ ${#JOBS[@]} -eq 0 ] && JOBS=(sidecar ui)

declare -a ERGEBNIS=()
schritt() {
    local name="$1"; shift
    echo "── $name"
    if "$@"; then ERGEBNIS+=("bestanden     $name"); else ERGEBNIS+=("FEHLGESCHLAGEN $name"); fi
}
fehlt() { ERGEBNIS+=("übersprungen  $1 (fehlt: $2)"); }

sidecar() {
    schritt "Sidecar-Tests" "$PY" -m pytest sidecar/tests -q -p no:cacheprovider
    schritt "Synthetische Gedächtnisdiagnostik" "$PY" -m pytest -q -p no:cacheprovider \
        scripts/test_memory_probe_support.py scripts/test_memory_probe_agent.py \
        scripts/test_probe_memory_pipeline.py scripts/test_probe_hybrid_memory.py \
        scripts/test_memory_probe_catalog.py scripts/test_memory_answer_comparison.py \
        scripts/test_probe_everyday_memory.py scripts/test_probe_working_memory_paraphrase.py \
        scripts/test_probe_working_memory_scale.py scripts/test_probe_working_memory_models.py
    schritt "Messlatte: Rahmenwerk auf der Mini-Welt" "$PY" -m pytest -q -p no:cacheprovider messlatte/tests
    schritt "Mac-App: statische Prüfungen" "$PY" -m pytest -q -p no:cacheprovider macos/test_mac_app.py
    schritt "Beispielprofil gegen das Schema" "$PY" -c '
import json, jsonschema
schema = json.load(open("schema/self-model.schema.json"))
jsonschema.Draft202012Validator.check_schema(schema)
jsonschema.Draft202012Validator(schema).validate(json.load(open("schema/beispiel-profil.json")))'
}

ui() {
    if command -v npm >/dev/null; then
        schritt "Kingfisher UI: npm ci" npm ci --prefix app/kingfisher --no-audit --no-fund
        schritt "Kingfisher UI: Build" npm run build --prefix app/kingfisher
        schritt "Asset-Vertrag" "$PY" scripts/check_asset_manifest.py
    else
        fehlt "Kingfisher UI" npm
    fi
}

for job in "${JOBS[@]}"; do
    case "$job" in
        sidecar|ui) "$job" ;;
        *) echo "Unbekannter Job: $job (sidecar, ui)"; exit 2 ;;
    esac
done

echo
echo "Lokale CI auf $(git rev-parse --short HEAD)$(git diff --quiet HEAD || echo ' mit ungespeicherten Änderungen'):"
printf '  %s\n' "${ERGEBNIS[@]}"
printf '%s\n' "${ERGEBNIS[@]}" | grep -q '^FEHLGESCHLAGEN' && exit 1
exit 0
