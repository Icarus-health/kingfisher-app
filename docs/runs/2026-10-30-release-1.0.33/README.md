# Gedächtnis und geprüfte Abläufe: Fassung 1.0.33

## Stand

**Vorbereitet, noch nicht veröffentlicht oder auf dem persönlichen Mac installiert.**
Diese Fassung bündelt PR #103 und den direkten Prüfweg aus PR #104. Sie ergänzt keine Modellrolle, neue Quelle oder andere Produktfunktion.

## Release-Vorbereitung

- Vorgänger öffentlich geprüft: GitHub-Release `v1.0.32`, veröffentlicht am 30.10.2026.
- `VERSION` ist `1.0.33`; fünf kurze Neuerungen einschließlich der offenen Modell-/Realmail-/Mac-Abnahme. `App mindestens: 1.0.18` unverändert; kein Swift-/Brückenvertrag geändert.
- `python3 scripts/release_seite.py pruefen --tag v1.0.33` bestanden.
- Download-Seite und Manifest lokal gebaut: genaue Imagekennung `ghcr.io/icarus-health/kingfisher-app:1.0.33`, DMG unter dem gleichen Tag, keine unbekannten Vorlagenplatzhalter. Dies veröffentlicht noch nichts.
- Gezielte Release-/Fassungs-/Updaterprüfungen: **99 bestanden**, eine bekannte Starlette/httpx-Abkündigungswarnung. Versionsanzeige der Oberfläche: **12/12 bestanden**. Keine neue Vollprüfung unveränderter Backendlogik außerhalb der regulären GitHub-Prüfungen.
- Der unveränderte Release-Workflow baut arm64/amd64-Bild und Mac-DMG auf GitHub; erst nach beiden Artefakten veröffentlicht er Release, Download-Seite und Updateangebot. Lokaler Mac-Paketbau wird bei der aktuellen Speicherlast nicht begonnen.

## Noch vor der Veröffentlichung / Installation

1. PR #104 und Release-Metadaten nur nach bestandenen Prüfungen integrieren.
2. Tag/Workflow, beide Containerarchitekturen, tatsächliches DMG und öffentliches Manifest prüfen.
3. Vor Mac-Update Sicherung und Datenstand festhalten; normalen Updateweg verwenden und globale Importpause anschließend erneut lesen.
4. Native Mac-Bedienprüfung getrennt durchführen. Die vollständige echte Modellprobe und eine gemischte Realmail-Stichprobe bleiben Qualitätsgates; der Großimport wird durch das Update nicht fortgesetzt.

Keine neue Qualitätsfreigabe aus Versionsprüfung oder Paketbau ableiten. Aktuelle Speichergrenze und Nutzerabwesenheit bleiben bestehen.
