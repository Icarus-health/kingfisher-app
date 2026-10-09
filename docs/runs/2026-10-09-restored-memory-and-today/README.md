# Wiederhergestellter Modellcache, echte Gedächtnisläufe und nutzbarer Überblick

Am 9. Oktober wurde die konkrete Freigabe zur Wiederherstellung und zur Bedienprüfung am entsperrten Mac erteilt. Drei exakt fehlende BGE-M3-Dateien wurden aus der offiziellen Registry wiederhergestellt (1.157.672.605 Bytes), mit SHA und Größe geprüft. Bestehende Assets und Manifest wurden nicht ersetzt, keine privaten Daten übertragen, kein produktiver Modellserver gestartet. Der frühere Testaufbaufehler bleibt im [Vorfallprotokoll](../2026-10-09-normative-original-binding/model-cache-incident.md) erhalten.

## Produktkorrektur und tatsächliche Mac-Lieferung

Produktcommit `63f707885615f63a502a37f04c5b5ff86e5488fc`, Basis `ec64e00`. Heute schließt nur die exakte Hinweisart `waise/ruhend` vor Sortierung und Fünfergrenze aus. Initialladen, Fokus und Wiederholen benutzen dieselbe Regel; Quelle und Entscheidungsstand bleiben erhalten. Der vollständige Prüfbereich behält die Hinweise. Die Vorschlagszahl kommt aus dem tatsächlichen Pending-Bestand statt aus der auf 20 begrenzten Vorschau.

419 UI-Prüfungen, UI-Build und 62 betroffene Backendprüfungen bestanden; unabhängiges Review ohne Befund. Die neue 23-Vorschläge/20-Vorschau-Kontrolle scheitert mit der alten Zählung, danach wieder grün. Die vom Agenten zuerst ohne benötigte Abhängigkeiten versuchte Backend-Gegenprobe war ein Umgebungsfehler, kein Produktnachweis; sie wird nicht als rote Regression gewertet. Keine neue vollständige Backendwiederholung und keine GitHub-CI-Ausführung.

Das kompakte Paket wurde netzlos mit künstlichem Bestand geprüft: exakt 266 Python- und 112 UI-Dateien. Tatsächlich installierte Version `1.0.6-local.63f7078`, Image `sha256:f35ace06b3940c588d90d25064cc241867a10f14ddbac9326cde38664150840c`. Schema20 unverändert. Vollständige kalte Rohsicherung einschließlich Journalen; WAL-bewusster Datenvergleich vor Veröffentlichung und frische unabhängige Prüfung danach:344 Originalkörper samt Dokumenten,17 Datenbanken, Einstellungen und Pause erhalten, gleicher Datenträger, native Signatur und Programmbytes unverändert. Kein Rückspielen älterer Daten. Privater Rückweg unter `Kingfisher-Rueckweg/2026-10-09-vor-63f7078-schema20`, nicht im Repository.

Native Fensterprüfung: Heute zeigt eine verbliebene handlungsfähige Rückfrage und korrekt49 Gedächtnisvorschläge. Die19 ruhenden Hinweise sind dort ausgeblendet und im vollständigen Prüfbereich weiterhin aufklappbar. Datum/Uhrzeit aktualisieren sich zwischen Seiten. Aufgaben, Kalender und geöffnete Mail wurden zuvor lesend geprüft. Keine Entscheidung, Mailversand, Kalenderänderung oder Importfortsetzung ausgeführt. Persönliche Bildschirmdaten bleiben lokal; `native-window-observations.json` enthält nur sachlich bereinigte Beobachtungen.

## Zwei echte geschlossene Modellläufe

Beide Läufe nutzen tatsächlichen Dokumentupload, Modellaufnahme/Themen-/Personenvorschläge, persistenten BGE-Index, Store-Neustart, echte Gesprächsantworten und jeweils einen Quellenentzug nach Neustart. Nur eingefrorene künstliche Quellen; Qwen3.5:4b/BGE-M3, eigener Port11439, Cloud aus, keine produktiven Einstellungen. Eigenständige Dateiklone mit unterschiedlichen Inodes, keine Cache-Symlinks/Hardlinks; `OLLAMA_NOPRUNE=1`, ursprünglicher Cache und beide Manifeste vor/nach geprüft und unverändert. Notabschaltung bei900 Sekunden/8GiB sampled owned RSS; kein harter GPU-Speicherdeckel. Diagnostisches Entladen alle vier Quellen ist keine produktive Ressourcenabnahme.

| Lauf | Aufnahme/Index | Mechanische Auswahlprüfung | Unabhängige Inhaltsprüfung |
|---|---|---|---|
| Regelabsätze, Produkt d431383 |19/19|11/16|15/16 ausreichend; W04 zitiert richtig, zieht die verlangte Schlussfolgerung nicht ausdrücklich. Zwei Antworten mit sachlich richtigen, aber irrelevanten Ergänzungen.|
| CoS, Produkt63f7078 |18/18|19/23|22/23 ausreichend; RQ06 behauptet fehlende Information trotz abgerufener und ausgewählter Quelle mit ausdrücklich fehlender Versandfreigabe. Alle9 eingefrorenen Personenprüfungen stimmen.|

Die Unterschiede zwischen Auswahlwertung und Inhaltsprüfung bleiben sichtbar. Mechanische Fehler wegen Provider-/Zeitlimit sind keine automatisch falschen Antworten. Umgekehrt ist ein korrekt ausgewählter Beleg kein Beweis für die Antwort. RQ11 fällt nach Zitatnummerierungsfehler auf passende Originalstellen zurück; RQ15 verwirft ein hinzuerfundenes Jahr vor Anzeige. Qwen erzeugt und prüft seine Antwort: das ist kein unabhängiger Wahrheitsbeweis.

Je ein getesteter Quellenentzug: gespeicherter Stand `working_unavailable`, keine Links, kein Modellaufruf, Original erhalten. Der erste Lauf prüft zusätzlich16 gespeicherte Antworten nach erneutem Neustart unverändert. Der zweite prüft Fragen nach geöffneten persistenten Stores, keinen umfassenden erneuten Einzelabruf aller23 Antworten. Normativer Lauf265 Sekunden, RSS-Spitze5,77GiB; CoS-Lauf330 Sekunden,5,75GiB. Keine Garantie für privaten Großbestand, Tagesakku oder die produktiv konfigurierte12B-Modellrolle.

## Nächste konkrete Qualitätsarbeit

1. RQ06 vor Eingriff als feste Regression: Quelle vorhanden und ausgewählt, Antwortstufe verwirft expliziten Negativstatus. Keine pauschale Lockerung für unbekannte Fragen.
2. W04: verlangte Schlussfolgerung sichtbar beantworten, ohne unbelegte neue Regel zu erzeugen.
3. Erst danach begrenzte persönliche Abnahme von Aufnahme, Zuordnung und Antworten; großer Import bleibt pausiert. Native MIME-Namen, metadata-only Belegdarstellung und Ressourcenempfehlung bleiben weitere bekannte Verbesserungen.

Diese Lieferung behebt Cachevorfall und zwei Bedienfehler und stellt erstmals wieder einen vollständigen echten Modellnachweis her. Sie erklärt Kingfisher nicht für fehlerfrei oder den persönlichen CoS für vollständig abgenommen.
