# Lokales Einordnungsupdate installiert, 11.10.2026

**1.0.6-preview.2d6467b** ist auf dem persönlichen Mac installiert; das neue Backend läuft und antwortet gesund. Das native Bundle ist ersetzt und geprüft, der native Prozess wurde ausdrücklich nicht beendet oder neu gestartet. Der Mac ist weiter gesperrt: neuer App-Prozess, Fenster, Diktat und Dateidialog sind noch nicht abgenommen. Kein öffentliches Release, kein Registry-Upload.

## Eingefrorenes Paket

- Code `2d6467b888fc150eb2f118e272ba8ac2f2bfbeda`. Gegenüber dem zuvor installierten `6979131` genau eine geänderte Laufzeitdatei: `memory_categories.py`. [Gemessene lokale Verbesserung und bekannte Abweichungen](../2026-10-11-category-guidance/README.md): 6/8 Entwicklungsfälle und 5/6 unabhängige Gegenfälle, keine vollständige Qualitätsfreigabe.
- Vorhandenes Elternimage `sha256:066cf82ddc4a8217b9d8c4f660f84cdacf0ca9315da287cb9384710bfaccd458`, Build ohne Netz oder Pull. Nur geprüfte Python-Datei und Versionsmetadaten ersetzt. Neues Image `sha256:a3f6dc20a9b9115c0479b11fc174d4eb19ff80ab79320237efc8c99c7761d812`.
- Sämtliche 269 Python-Dateien und 112 unveränderten UI-Dateien im neuen Image gegen Manifest verglichen. Zehn integrierte synthetische Paketblöcke für Gedächtnis, Quellenentzug, Mail-Aufgaben, Health, Kategorienkorrektur, Projekte, Transkriptvorschau, Learning und World Facts bestanden. Flüchtiger Container, frisches tmpfs, schreibgeschützte Laufzeit, kein Netz, produktives Volume, Modell oder Cloudschlüssel. Kein neuer vollständiger UI-/Backend-Testlauf.
- Native ARM64-App aus eingefrorenem Git-Archiv neu übersetzt, ad hoc signiert; nicht notarisiert, kein Intel-Build. Compose und Update-Speicherprüfer bytegleich zum Elternpaket.
- Dauerhaftes DMG unter `Documents/Codex/Kingfisher-Pruefpakete/2026-10-11-category-guidance-2d6467b/Kingfisher.dmg`, SHA-256 `ec7784a9991882b7b81d5db396b7f1cd6181accd6eb86f90ac12df45c5790a74`. Schreibgeschützt eingebunden, alle sechs App-Dateien und strenge tiefe Signatur gegen Buildmanifest geprüft, anschließend ausgeworfen. Auch das installierte Bundle stimmt vollständig damit überein. `hdiutil` meldet eine Werkzeug-Abkündigung, nicht ein fehlgeschlagenes Einbinden.

## Frische Sicherung und tatsächlicher Wechsel

Private Sicherung mit Zeitkennung `20261011T114110Z` im vorhandenen Kingfisher-Sicherungsbereich; Originalkonfiguration und alte native `Contents` erhalten. Kein privates Archiv, Schlüssel oder Quellentext im Repository.

- 148 Dateien, neun Verzeichnisse, 281.322.188 Bytes des Datenvolumes kalt gesichert.
- Archiv auf eine eigene temporäre Kopie extrahiert; Inhalte, Verzeichnisse, Rechte, UID/GID, Nanosekunden-mtime und xattrs stimmen exakt. Alle 17 wiederhergestellten SQLite-Datenbanken bestehen die Integritätsprüfung. Das ist eine Datei-/Verzeichnis-Wiederherstellung, kein Starttest einer restaurierten App und kein Blockabbild.
- Host-Konfiguration atomar geschrieben, nur die eine Bildselektor-Zeile geändert, weiterhin 0600. Bestehender App-Pfad und Bundle-Wurzel erhalten; alte `Contents` in den privaten Sicherungsordner verschoben. Dieser Zwei-Rename-Swap ist nicht stromausfallatomar; der normale Ausnahmeweg stellt Code und Config zurück.
- Compose ohne Build/Pull gewechselt, dasselbe `kingfisher_kingfisher-data:/data`. Vor/nach Wechsel Inhalte aller sieben ausgewählten Kerntabellen identisch: 344 Episoden, 333 Quellenverweise, drei Gespräche/14 Nachrichten, leere Aufgaben-/Projekt-/Notizbestände.
- `sqlite_master`-Schemas und `PRAGMA user_version` aller 17 Root-Datenbanken vor/nach Wechsel identisch. Das beweist diese Schemas/Versionen und die sieben Tabelleninhalte, nicht jede Zeile aller übrigen Tabellen oder abstrakt jede mögliche Migration.
- Tatsächlicher laufender Einordnungscode hat SHA-256 `7fa1b14b9e3724800ac77d41e2fd22b5ecd3818347fd3ac48b5ca5f0b91985ed`, identisch mit den lokalen Modellproben. Frische authentifizierte Versionsantwort bestätigt die neue Fassung.
- Hintergrundpause bleibt aktiv. Kalenderstatus erneut `granted`, aktiviert, Helfer online, kein Fehler, genau drei ausgewählte Kalender; `memory_allowed:false` bleibt wirksam. Keine Termine geschrieben, Modelle gestartet oder großen privaten Mailmengen nachbearbeitet.

## Unabhängige Prüfung und noch offene Nutzung

Der Installationsreview fand vor Ausführung eine Tempdatei-Lücke im Config-Rückfallweg. Mit eindeutiger temporärer Datei und `finally`-Cleanup behoben: erzwungener Replace-Fehler lässt das Original und keinen Temprest zurück; unmittelbare Rücksetzung gelingt mit 0600. Der ursprüngliche Fehlerpfad fällt im Regressionstest durch. Der Test verwendet die tatsächlichen Imports und Funktion aus dem Installskript, kein eingespeistes `tempfile`. Ein zunächst gemeldeter fehlender Import wurde anhand des frisch gelesenen Dateistands und SHA überprüft und verworfen. Schemaabgleich auf Reviewhinweis ergänzt.

`install.py`, `backup.py` und `test_atomic_env.py` sind konkrete Run-Treiber mit damaligen Pfaden und Elternfassungen, keine universellen Installer. Nicht blind auf einem anderen oder bereits aktualisierten Bestand ausführen. Logs und Manifeste erhalten die synthetischen Prüfungen, `verification.json` trennt Installation vom ausstehenden nativen Neustart.

Bestehende abgeschlossene Quellen bekommen durch das Update keine automatische neue Einordnung; gezielte Wiederprüfung bleibt ein ausdrücklicher Schritt, eigene Korrekturen bleiben erhalten. Vor dem großen Import bleiben die gemessenen zusätzlichen Kategorien und der echte persönliche Mail→Gedächtnis→Aufgabe→Kalender-Ablauf zu prüfen. Gemma12B-Gewichte fehlen weiterhin; keine allgemeine Antwort-, Namen-, Akku- oder Gedächtnisfehlerfreiheit behauptet.
