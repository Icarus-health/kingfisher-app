# Projekte als Arbeitsübersicht

Ergänzung auf `feat/memory-feedback-20261010`, ausgehend von `acfa100`.
Diese zweite Verbesserung des Alltagsablaufs erweitert denselben Draft-PR #54.
Nicht auf dem persönlichen Mac installiert.

## Bedienung

Unter Aufgaben ein Projekt wählen. Der neue **Projekt auf einen Blick**-Block
zeigt alle eigenen offenen, wartenden und erledigten Aufgaben des Projekts.
Überfällige eigene Aufgaben, fehlende Fristen und verworfene Aufgaben bleiben
getrennt erkennbar. Eine leere Aufgabenliste bedeutet nicht, dass das Projekt
fertig ist. Projektstatus und Aufgabenstatus sind weiterhin eigene Angaben.

Bis zu drei eigene Aufgaben mit den frühesten Fristen und drei am längsten
wartende Punkte führen direkt in das vorhandene Aufgabendetail. Die Zahlenkarten
öffnen die jeweilige vollständige, paginierte Projektliste und löschen dafür
eine eventuell aktive Listensuche. Alle bestehenden Aktionen und Quellenbelege
bleiben im bisherigen Aufgabendetail. Es entsteht keine zweite Aufgabenverwaltung.

Die Zusammenfassung zählt **alle gespeicherten Projektaufgaben**, unabhängig von
der 50-Aufgaben-Seite oder der Suche. SQLite berechnet die Zahlen und liest
höchstens sechs vollständige Aufgaben in einer gemeinsamen Lesetransaktion.
Wartende Aufgaben sind nicht eigene überfällige Arbeit; verworfen ist nicht
erledigt. Fristen werden nach wirklichem Zeitpunkt sortiert, nicht nach
Zeitzonen-Text. Fehlende Fristen bleiben fehlend.

Lesen verändert weder Aufgaben noch ihre Historie. Das Laden eines anderen
Projekts verwirft späte Antworten. Fehlgeschlagene Abrufe zeigen keine alten
Zahlen. Der Überblick aktualisiert sich nach den bestehenden Aufgabenaktionen
und beim ausdrücklichen Aktualisieren. Der Abrufzeitpunkt bleibt sichtbar;
dieser Schritt behauptet keine automatische Aktualisierung zwischen Fenstern.

## Prüfung

- Vier neue Backendfälle scheiterten vor der Umsetzung an fehlender Methode bzw.
  Route; anschließend bestanden. Sie prüfen 205 eigene Aufgaben plus andere
  Zustände, fremdes Projekt, Zeitzonen, begrenzte Vorschauen, leeres/geschlossenes
  Projekt, fehlende Projektkennung und echten SQLite-Neustart.
- Fünf neue Komponentenfälle scheiterten vor der Umsetzung an der fehlenden
  Übersicht; anschließend bestanden. Geprüft sind Darstellung, direkte Aktionen,
  keine Abrufe ohne Projektauswahl, leeres Projekt, Fehler, Wiederholen und späte
  Antworten. Tests steuern echte Komponentenhandler mit einem Hook-Treiber;
  keine native Fenstertestung oder vollständige React-Browserprüfung.
- 51 betroffene Backendtests und alle 529 UI-Tests bestanden. Typprüfung und
  Web-Produktionsbuild bestanden. Assetvertrag bestanden: 16 Dateien, 16 Icons.
- Unabhängiger Reviewer: kein konkreter Blocker im engen Änderungsumfang,
  eigene fünf UI-Fälle bestanden. Er konnte Backendtests in seiner zuerst
  gefundenen Python-Umgebung nicht ausführen; die 51 Backend-Ergebnisse stammen
  vom Hauptlauf mit der bekannten Review-Umgebung.
- Vorhandene Starlette/httpx-, Node-MockTimers- und große JS-Chunk-Hinweise.
  Kein vollständiger Backend-Gesamtlauf, neuer Anbieteraufruf, Schemawechsel oder
  zusätzliche Bibliothek. Persönliche Daten und laufender Import unberührt.

Protokolle liegen hier komprimiert. Die älteren Memory-Feedback-Nachweise bleiben
in `../2026-10-10-memory-feedback/` erhalten; deren Ergebnis ist separat datiert.
Ein gekoppeltes neues Mac-/Backend-Paket und die echte Bedienprüfung sind offen.

```sh
PYTHONPATH=sidecar /private/tmp/kingfisher-review-20261006-venv/bin/python -m pytest \
  sidecar/tests/test_project_task_overview.py sidecar/tests/test_project_task_flow.py \
  sidecar/tests/test_task_pages.py sidecar/tests/test_task_single.py \
  sidecar/tests/test_task_history.py sidecar/tests/test_task_history_api.py \
  sidecar/tests/test_task_edit.py sidecar/tests/test_workspace.py \
  sidecar/tests/test_task_reminders.py sidecar/tests/test_task_reminder_api.py -q
cd app/kingfisher
npm test
npm run build
```
