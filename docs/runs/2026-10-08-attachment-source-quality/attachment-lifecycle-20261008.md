# Anhangquellen: Lifecycle-Prüfung und begrenzter Fix

Stand: 08.10.2026, `work/memory-activation-20260923`, Baseline `66b11a8` und aktueller gemeinsamer Arbeitsstand. Nur synthetische Quellen, echte lokale Episode-/Claim-/Proposal-Stores; keine persönlichen Inhalte, kein Modell, kein Netz. Keine Commits.

## Bestätigte Ausgangsfehler (before-only)

`attachment-audit-before-20261008.json` zeigt: Entzug oder Ersetzung der Mail ließ ihren Anhang aktuell, dessen bestätigte Aussage aktiv und den Claim-Kontext abrufbar. Derselbe Vorher-Lauf dokumentiert gemischte Text-/Scan-PDFs als scheinbar gelesen, stillen Anhangüberlauf und fehlerhafte Zeichenbegrenzung. Die Parser-/MIME-/Anzeigeänderungen dazu liegen beim Hauptagenten und sind nicht Inhalt dieses Lifecycle-Fixes.

`attachment-lifecycle-red-20261008.log` enthält die zunächst fehlenden Lifecycle-Sperren. `attachment-lifecycle-followup-red-20261008.log` bestätigt zusätzlich den inkonsistenten Metadatendigest beim Ausschluss mit Begründung sowie das irreführend erfolgreiche Wiederöffnen einer ungültigen Berichtigung.

## Implementierter Vertrag

- `episodes.py:202`: Neue Anhänge werden durch `mail-parent:<episode-id>` an genau eine Mailfassung gebunden. Ein alter Anhang ohne Tag ist nur bei genau einer gespeicherten Mailfassung eindeutig. Mehrdeutige/fehlende Beziehungen bleiben ausgeschlossen; kein Raten anhand des aktuellen Heads.
- `episodes.py` (`_sql_direct_mail_parent_valid`, `sql_mail_parent_valid`, `sql_nicht_ausgeblendet`): Geteilte SQL-Prüfung sperrt ungültige Anhänge in geltenden und sichtbaren Quellen. Wie der Snapshot erlaubt sie höchstens acht Quellenleseschritte einschließlich Startquelle; bei einem Anhang zählt auch seine Mail dazu. Fehlende Ziele, Zyklen ohne Ende und ungültige Elternbeziehungen werden verworfen. Ignorierte Berichtigungsoriginale bleiben zulässige Kettenziele, da eine Berichtigung ihr Original absichtlich ausschließt. Der finale Snapshot bleibt zusätzlich Pflicht.
- `source_snapshot.py:67`: Snapshot prüft den Eltern-Snapshot einschließlich Integrität und `current()`. Nur Anhänge ergänzen ihren Fingerabdruck um Elternidentität, Textdigest, Schlüssel, Head und Ausschlussstatus. Beratende Header-/Abrufberichte verändern einen unveränderten Anhangbeleg nicht. Unabhängige Quellen behalten ihren bisherigen Fingerabdruck.
- `episodes.py:1214` und `source_versions.py:10`: Mailentzug sperrt vorhandene Anhänge und deren Berichtigungen; der bestehende Claim-Invalidierungspfad erfasst diese Nachfahren ebenfalls. Text und Historie bleiben erhalten. Mail-Wiederöffnung öffnet Kinder nicht automatisch.
- `episodes.py:1247`: Direkte Wiederöffnung scheitert bei gesperrtem/mehrdeutigem Elternbezug oder ungültiger Berichtigung.
- `source_corrections.py:55`: Die Berichtigung einer Mail entzieht vorher auch Aussagen aus ihren Anhängen.
- `episodes.py:1059,1094`: Beratender Anhangbericht wird idempotent als ein JSON-Tag gespeichert, ohne Text/Digest/Zustand zu ändern; ignorierte Quellen bleiben unangetastet. Die öffentliche Kinderliste gibt nur aktuelle Kindfassungen mit eindeutiger Bindung zurück. Sie behauptet keinen vollständigen MIME-Abruf.
- `episodes.py:1948`: Zustandsgründe können Tags verändern. `_put` führt deshalb den Metadatendigest anhand des gespeicherten Schlüssels nach; der Schlüssel selbst wird nicht überschrieben. Ausschluss mit Grund und anschließendes ausdrückliches Öffnen liefern wieder konsistente Snapshots.

## Zusätzliche Altbestandslücke und Nachweis

Vor dem zweiten Fix konnte eine schon verwaiste Legacy-Anhangberichtigung trotz `current() == False` weiter in direkter Quellensuche, FTS-Treffern und sichtbarer SQL-Inventur vorkommen. Das wurde ohne heutigen Kaskadenpfad durch einen historischen Head-Wechsel reproduziert.

- Repro: `attachment-orphan-correction-20261008.py`
- Vorher: `attachment-orphan-correction-before-20261008.json` → alle drei Suchwege `true`.
- Regression zunächst rot: `attachment-orphan-correction-red-20261008.log` (1 fehlgeschlagen, 14 grün).
- Nachher: `attachment-orphan-correction-after-20261008.json` → `current=false`, alle drei Suchwege `false`.

## Prüfungen

Zunächst 15 Lifecycle-Regressionen grün. Darin: exakte/alte Elternbindung, Entzug, Ersetzung, keine automatische Wiederöffnung, SQL-/FTS-/Sichtbarkeitsgate, Nachfahren-Claims und Kontext, Kind- und Elternberichtigung, beratende Elternänderungen erhalten akzeptierte Kindbelege, idempotenter Bericht sowie begründeter Entzug mit konsistentem Wiederöffnen.

Der gezielte Nachlauf über Lifecycle, Quellenkorrekturen, Teilkorrekturen, Quellenversionen, Suchindex, Ausschluss und geltende Quellen: **125 bestanden**, eine bestehende Starlette/httpx-Abkündigungswarnung, 20,70 Sekunden. Protokoll: `attachment-lifecycle-regression-green-20261008.log`.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts /tmp/kingfisher-review-20261006-venv/bin/python -m pytest sidecar/tests/test_attachment_lifecycle.py sidecar/tests/test_source_correction_flow.py sidecar/tests/test_source_partial_correction.py sidecar/tests/test_source_versions.py sidecar/tests/test_source_index.py sidecar/tests/test_source_exclusion.py sidecar/tests/test_geltende_quelle.py -q -p no:cacheprovider
```

Letzter Grenzfix nach Produktcommit `7061e30`: Die SQL-Rekursion erlaubte eine Quelle mehr als der Snapshot und rechnete den zusätzlichen Mail-Leseschritt eines Anhangs nicht mit. Fünf parametrische Tests vergleichen Snapshot, direkte Suche, FTS und sichtbare Inventur: Anhang mit 6/7/8 Korrekturkanten sowie normale Quelle mit 7/8 Kanten. Vorher 3 rot, 2 grün (`attachment-depth-red-20261008.log.gz`). Die gemeinsame Anhangserkennung ist nun als `_sql_is_mail_attachment` herausgezogen; der CTE endet bei Tiefe 7 und lässt dort keinen Anhang zu, dessen Mail einen weiteren Schritt benötigen würde.

Nach diesem letzten Produktdiff: **93 gezielte Tests grün**, darunter sämtliche **20 Lifecycle-Fälle**, Quellen-/Teilkorrekturen und Suchindex. Eine bestehende Starlette/httpx-Warnung, 16,25 Sekunden; `attachment-depth-green-20261008.log.gz`. `git diff --check` sauber. Der umfangreichere 125-Test-Lauf oben liegt vor dieser letzten Tiefengrenzenänderung; ein dritter Gesamtlauf wurde gemäß Koordination nicht gestartet.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts /tmp/kingfisher-review-20261006-venv/bin/python -m pytest sidecar/tests/test_attachment_lifecycle.py sidecar/tests/test_source_correction_flow.py sidecar/tests/test_source_partial_correction.py sidecar/tests/test_source_index.py -q -p no:cacheprovider
```

## Grenzen

Der Hauptagent prüft Parser, MIME-Abrufstatus, UI, übergreifende Tests und Build. Diese lokalen Tests beweisen keine erfolgreiche Aufnahme persönlicher Mails und keine OCR-/Modellqualität.

Eine vor diesem Patch gespeicherte Berichtigung eines Anhangs enthält den alten Ziel-Fingerabdruck ohne Elternanteil. Der neue Snapshot verwirft diese Berichtigung vorsichtig; Original und Berichtigung bleiben gespeichert. Eine automatische Fingerabdruckmigration oder Wiederzulassung wurde bewusst nicht eingebaut. Mehrdeutige Legacy-Anhänge benötigen ebenfalls eine ausdrückliche neue, eindeutige Aufnahme.
