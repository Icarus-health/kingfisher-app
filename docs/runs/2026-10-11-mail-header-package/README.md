# Mailheader-Index: Paket und persönliche Installation

11.10.2026, Quellcode `f858681bb5afa0d7fe0482f87ce208c10793c38f`. App-Dateien und gesundes Backend installiert als `1.0.6-preview.f858681`, Image `sha256:48b1bd538de8eb14eca5f217dcefeac28f042630533310cb7cc7916ed40e0102`.

## Paketbindung

272 Backenddateien aus festgehaltenem Git-Archiv; 112 UI-Dateien bytegleich zum vorher geprüften und installierten a578-Paket. UI, native Quellen, Modellrollen unverändert. Archiv-SHA und alle Dateien stehen in `package-freeze.json`. `VERSION` wird ausschließlich für das lokale Preview-Artefakt gesetzt; `staging-overrides.json` hält beide Hashes fest. Kein Download, kein Registry-Publish, kein CI-Neustart.

ARM64-App mit sechs Dateien, streng/tief ad hoc signiert. DMG schreibgeschützt eingehängt, vollständig verglichen und wieder ausgehängt; SHA `be5a39b67c7bb28682c8dacc214c3cba4bcd2aded5a1d0d3b9225fc6324222ea`. Nicht notarisiert. Kanonisches DMG unter `Documents/Codex/Kingfisher-Pruefpakete/2026-10-11-mail-header-f858681/Kingfisher.dmg`, nicht in Git.

Tatsächlich ausgeführte künstliche Paketabläufe in netzlosem Container mit frischen tmpfs, ohne persönlichen Datenträger: Gesundheitsbeobachtungen, Quellen-/Aufgabenbindung, Kalenderzeiträume, weitere vorhandene Kernabläufe und vier eingefrorene neue Indexfälle einschließlich 50.000 fremder Mails, v21-Backfill, atomare Headeränderung und Nicht-Mail-Kontrolle. `package-runtime-proof.json` bindet Image, Treiber und fertiges Log. Kein reales Modell oder persönliche Gedächtnisqualität geprüft.

Erster Paketlauf scheiterte an zwei historischen Probe-Erwartungen „neueste Version = 21“. Diese wurden auf tatsächliche v22 aktualisiert; ursprüngliche v20-/Backup-/Originalerhaltserwartungen bleiben. Die alte Fehlermeldung bleibt gespeichert. Der erste sandboxed DMG-Attach scheiterte vor dem Einhängen; derselbe Prüfer mit Gerätezugriff bestand, ebenfalls getrennte Logs.

## Installationsprüfung und Review

Migrationserhalt schützt alle bestehenden EpisodeStore-Tabellen, alle bisherigen Schemaobjekte und die Schemas/Versionen der übrigen Datenbanken. Nur die bekannten v22-Erweiterungen sind erlaubt; die Produktionsmigration verifiziert zusätzlich exaktes DDL/Trigger-SQL. Sechs künstliche Installationswächterfälle (gültig, unerwartete Tabelle, fehlender Trigger, geändertes Original, anderes Schema, falsche Version) bestanden. Der erste Testlauf war rot, weil der neue Wächter noch fehlte.

Unabhängiger enger statischer Review fand eine echte Konfigurationslücke: Compose konnte Shellwerte vor der env-Datei bevorzugen. Gegenprobe auf tatsächlichen Installerfunktionen zunächst rot. Jetzt werden ICARUS_*, KINGFISHER_*, COMPOSE_* und LLM_API_KEY aus der geerbten Compose-Umgebung entfernt; nach Start werden tatsächliche Runtimewerte gegen den alten Stand verglichen, ausgenommen allein die separat exakt geprüfte neue Fassung. AST-Gegenfälle und echte `docker compose config`-Auflösung mit ausschließlich künstlicher Konfiguration bestanden. Finaler Review ohne konkreten Blocker; Hashes entsprechen dem ausgeführten Installer.

Vier Staging- und drei Fehlerbehandlungsfälle am tatsächlichen Installer-AST bestanden: Unterbrechung/Signatur/Hashfehler entfernen nur eigene Staging-Dateien; nach fehlgeschlagenem Update bleibt der neue Dienst gestoppt. Es wird kein alter Dienst auf möglicherweise migrierten Daten gestartet und keine neue Nutzereingabe durch automatische Wiederherstellung überschrieben.

## Persönlich ausgeführt

Frische kalte Vollsicherung: 148 Dateien, neun Verzeichnisse, 281.322.188 Bytes. Wiederherstellung byteweise und mit Eigentümer, Rechten, Änderungszeit und xattrs verglichen; Integrität aller 17 SQLite-Datenbanken bestätigt. Sicherungsarchiv, persönliche Dateimanifeste, env und Datenbanken bleiben ausschließlich im geschützten lokalen Sicherungsverzeichnis außerhalb Git.

Noch vor dem Appwechsel: Archiv schreibgeschützt in netzlosem Container mit maximal 1 GiB RAM und zwei CPUs eingebunden, in geschützten temporären Bereich wiederhergestellt, tatsächliche v21→v22-Migration ausgeführt. Alle 42 alten EpisodeStore-Tabellen erhalten; 17 Schemas geprüft; sämtliche 74 abgeleiteten Header stimmen mit den Originalen überein. Das ist ein Migrations-/Integritätsnachweis, keine Aussage über Vollständigkeit aller historischen Mailheader oder inhaltliche Qualität.

Nach Wechsel: sieben persönliche Kerntabellen einschließlich Originalen, Aufgaben, Projekten und Gesprächshistorie identisch; zusätzlich alle 42 alten EpisodeStore-Tabellen identisch. Nur erwartete v22-Schemaerweiterung, übrige Schemas und Datenvolume gleich. Neue Appdateien entsprechen kanonischem DMG und gültiger Signatur. Nur Imageauswahl in env geändert, Anbieter-/Modellkonfiguration einschließlich Runtimevergleich erhalten. Hintergrundaufnahme pausiert, keine Cloudkosten oder Modellstarts.

Frische lokale API-Prüfung: neue Fassung, Kalenderfreigabe erteilt, drei Kalender ausgewählt, online, sechs Einträge im angefragten Siebentagefenster, keine Fehler/Warnungen. Kalender-Gedächtnisfreigabe bleibt aus. Keine Termintexte gespeichert.

## Noch offen

Der native Prozess wurde nicht neu gestartet und das neue native Fenster nicht geprüft, da der Mac zuletzt gesperrt war. Oberfläche ist gegenüber vorher unverändert. Persönlicher Alltags-/Gedächtnisqualitätsnachweis, Modellwahl und Qualifikation vor großer Mailaufnahme bleiben offen. Kein Main-Merge, öffentlicher Release oder allgemeiner Perfektionsnachweis.

Die Treiber sind datierte lokale Prüf-/Installationsartefakte mit absoluten Pfaden und strikten Alt-/Neu-Pins. Nicht als allgemeiner Updater direkt wiederverwenden. Für eine Wiederholung neue eigene Pfade, passenden eingefrorenen Stand und neue Sicherung prüfen. Die frühere breite Testbasis ist ausdrücklich historisch, getrennt von den frischen betroffenen Tests dieses Indexpatches (siehe benachbarten Runordner).
