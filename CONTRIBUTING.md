# Kingfisher: Beitrag und Abnahme

Kingfisher ist eine lokale Docker-App mit SQLite. Die aktuelle gemeinsame
Arbeitsbasis ist der Branch `main`. Änderungen gehören als
kleine, überprüfbare Commits auf einen eigenen Branch mit PR nach `main`; bestehende Icarus-Funktionen werden nur
additiv erweitert.

Für den aktuellen Stand, Einrichtung und nächste Aufgaben zuerst
[`docs/DEVELOPER-START.md`](docs/DEVELOPER-START.md) lesen. Historische
Branchangaben und Abnahmeprozentwerte sind keine aktuellen Arbeitsaufträge.

## Verbindliche Produktgrenzen

- Kein Supabase, keine Cloud-Datenbank und kein zusätzlicher Datenbankdienst.
- Persönliche Laufzeitdaten, Backups, SQLite-Dateien und `.kingfisher.env`
  gehören niemals in Git oder in ein Ticket.
- Lokale Quellen bleiben opt-in und lesend. Externe Modellanbieter erhalten
  bestätigtes persönliches Entitätswissen nicht automatisch.
- Ein Gespräch oder eine importierte Quelle ist kein Fakt. Dauerhafte
  Entitätsaussagen entstehen nur als belegter Kandidat und nach sichtbarer
  Nutzerbestätigung.

## Oberfläche und Designquellen

Die Reihenfolge ist verbindlich:

1. `design-source/06_Screens/Approved` (die Bildvorlagen wurden vor der Veröffentlichung entfernt, die Indexdateien bleiben)
2. `design-source/07_Coding_Package/KINGFISHER-ASSET-MANIFEST-v1.json`
3. übrige freigegebene Dateien in `design-source/`
4. ältere Dokumentation

`design-source/` ist die reproduzierbare Build-Kopie. Google Drive bleibt die
Quellenablage; die genaue Doppelablage steht in
`docs/design-source-provenance.md`.

Keine Bilder, Icons, Schriften, Avatare, Placeholder oder UI-Komponenten
erfinden. Wenn eine sichtbare Entscheidung von keiner Referenz gedeckt ist,
nicht improvisieren, sondern exakt anhalten:

```
SCREEN-DEVIATION-REQUEST
Screen: …
Reference: …
Missing decision: …
Why no reference covers it: …
Smallest safe option: …
```

## Pflichtprüfungen

Für einen Sidecar-/Gedächtnis-Change mindestens:

```sh
env PYTHONPYCACHEPREFIX=/private/tmp/kingfisher-pycache \
  ICARUS_DATA_DIR=/private/tmp/kingfisher-tests \
  .venv/bin/pytest -q sidecar/tests/test_context.py sidecar/tests/test_egress.py \
  sidecar/tests/test_agent.py sidecar/tests/test_kingfisher.py \
  sidecar/tests/test_claims.py sidecar/tests/test_graph.py
```

Für jede Änderung am Frontend oder an Assets zusätzlich:

```sh
cd app/kingfisher && npm run build
cd ../..
python3 scripts/check_asset_manifest.py
```

Vor einer Produktbehauptung den betreffenden Flow im lokal gebauten Docker-
Container testen. Ein Healthcheck oder ein Screenshot ersetzt keinen echten
Gesprächs-, Speicher- oder Wiederanlaufnachweis. Sichtbare Screens werden im
Browser am Referenzviewport geprüft und unter `docs/visual-checks/`
dokumentiert.
