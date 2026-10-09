# Read-only Review: alter Snapshot-Archivierer

Geprüfte Skriptfassung: SHA-256 `8d2f3e7b9fc18238e3e6d9b3d51e1f22098c212fe5b0042eb9f015a7efeb58a3`.

Kein konkreter Pfadausbruch oder einzigartiger Datenverlust im statisch geprüften Werkzeug gefunden. Es akzeptiert nur drei fest kodierte Namen, prüft Root/Targets und alle rekursiven Einträge auf Symlinks bzw. reguläre Dateien, vergleicht den vollständigen Dateiinhalt (Länge + SHA-256) zwischen Host- und Live-Kopie und verlangt beim Apply sowohl den Plan-SHA als auch eine erneute Live-Inhaltsprüfung. Die aktuelle Live-Aufbewahrungsmappe `vor-update-20261009T022544Z` bleibt zwingend vorhanden und wird nicht gelöscht.

Die neue Trennung ist passend: `make_plan()` vergleicht nur die drei alten Ziel-Snapshots und verlangt vom früher erstellten Hostarchiv keinen späteren `KEEP`-Snapshot. `scan()` und `apply()` verwenden weiterhin `tree(..., require_keep=True)`, sodass ein Live-Bestand ohne den aktuellen Snapshot blockiert wird. Die sichtbaren Tests decken diese beiden Fälle zusätzlich ab (sieben synthetische Fälle insgesamt; nicht in dieser Nachprüfung ausgeführt).

Begrenzte Betriebsgrenze: Das Apply ist nicht atomar. Ändert sich ein späteres Ziel zwischen der initialen Gesamtprüfung und dessen Einzelprüfung, können frühere Ziele bereits entfernt sein, bevor das Werkzeug abbricht. Eine Unterbrechung nach einzelnen Löschungen kann ebenfalls einen Teilstand hinterlassen. Laut vorgegebenem Ablauf bleiben die vollständigen Bytes im verifizierten Host-Rückweg vorhanden; dies ist daher kein Verlust der einzigen Kopie, aber kein Alles-oder-nichts-Löschvorgang.

Keine Ausführung, keine Liveaktionen und keine Datenänderungen.
