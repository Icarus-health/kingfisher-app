# Verständliche Einordnungsfehler im Gedächtnis

Produkt- und Teststand: `5621ec9e1f94ee40ea12485e128950d251211be4`, 9. Oktober 2026.

Fehlgeschlagene Einordnungen erhalten einen geschlossenen, verständlichen Fehlergrund. Alte Fehler ohne gespeicherten Grund bleiben ausdrücklich unbekannt. Interne Anbietertexte und private Inhalte werden weder als Diagnose gespeichert noch in der Anzeige ausgegeben. Eine erfolgreiche erneute Einordnung entfernt den Fehlergrund.

Die Anzeige prüft den aktuellen Quellenfingerabdruck, Generation, Taxonomie, Ausschluss und Entzug. Pro Kontoabruf werden höchstens 16 unterschiedliche fehlgeschlagene Quellen vollständig projiziert. Weitere Fälle erscheinen als ungeprüft und halten den Fortschritt offen. Das ist ein Projektionsbudget, keine feste Obergrenze aller SQL-Abfragen. Bestehendes Wiederholen erreicht auch den verbleibenden Bestand, ohne eine globale Pause aufzuheben. Auch wenn ausschließlich ungeprüfte Fälle übrig sind, bleibt die Aktion „Weitere Einordnungen prüfen“ verfügbar.

## Nachweise

- 398 Oberflächenprüfungen und Produktionsbuild bestanden; die Protokolle liegen daneben.
- Unabhängige Reviews für aktuelle Quellenbindung, begrenzte Statusarbeit und deutsche Anzeigezustände liegen daneben.
- Ein netzloser Pakettest auf künstlichen Daten führt den tatsächlichen Wechsel Schema 19 → 20 aus, erhält Originale, zeigt alte Gründe als unbekannt und prüft neue sichere Gründe sowie deren Entfernung bei Erfolg.
- Das gebaute Paket enthält 264 geprüfte Python-Dateien und exakt 112 UI-Dateien. Image: `sha256:72837cc0356954760e26aa1f9eb99713edc5287f598d7bd1a994f28a4298168f`, Version `1.0.6-local.5621ec9`.
- Breiter lokaler Regressionstest: **6.358 bestanden, 3 übersprungen, 2 Warnungen und 32 Subtests in 852,73 Sekunden**. Derselbe eingefrorene Produkt-/Teststand; gezielte Gruppen sind keine zusätzlichen unabhängigen Gesamtfälle. `full-regression.log` enthält den abschließenden Lauf.
- Der tatsächliche Paketprüfpfad wurde zusätzlich auf genau diesem Image mit leerem flüchtigem `/data` ausgeführt: netzlos, keine persönlichen Daten, 264 Python-/112 UI-Dateien bestätigt. Das explizite tmpfs verhindert das vom Image sonst automatisch angelegte anonyme Datenvolume; `real-tmpfs-package-probe.json`.

## Datenbank und Mac

Schema 20 ergänzt einen nullable Fehlercode. Alte Schema-19-Software darf nicht auf die migrierte Datenbank zurückgeschaltet werden. Der getrennte Offline-Vorlauf wurde mit 22 synthetischen Fällen geprüft und unabhängig gegengelesen; die Root-Gegenprüfung führt dieselben 22 Fälle aus, keine zusätzlichen 22 unterschiedlichen Fälle.

Die eingefrorene erste Mac-Orchestrierung besteht31synthetische Fälle. Ihr erster echter Versuch hielt **vor der Migration** wegen verbliebener SQLite-Journale an; die alte Version startete nach vollständiger Sicherung und WAL-bewusstem Nachweis wieder gesund. Diese historischen Berichte bleiben erhalten.

Der getrennte SQLite-Abschluss erhält vor jedem SQLite-Zugriff eine vollständige Rohsicherung mit Journalen. Er verwendet ausschließlich SQLite-Checkpoint/normalen Abschluss, kein manuelles Entfernen.24synthetische Fälle und ein echter netzloser Linux-Image-Smoke bestehen; die Root-Gegenläufe prüfen dieselben Fälle. Die zweite Orchestrierung besteht38Fälle. Ihr echter Versuch hielt wegen nicht lesbarer600-Metadatendateien unter abweichender Container-UID vor Checkpoint/Migration an; auch dieser alte Schema19-Stand wurde geprüft wieder gestartet. Die dritte Fassung kopiert ausschließlich Code/Hashmetadaten in bytegleiche lesbare temporäre Kopien, erhält die privaten Originalmodi und besteht42Fälle sowie eine echte UID1000-Gegenprobe.

Der dritte echte Versuch finalisierte die Journale und migrierte **Schema19→20 erfolgreich**. Die anschließende streng journalfreie Kontrolle hielt erneut an. Der separate, eng begrenzte Fortsetzungspfad prüft deshalb den tatsächlichen WAL-bewussten Schema20-Bestand gegen die unveränderte kalte Schema19-Sicherung. Alle gespeicherten Zeilen,344Originalkörper mit Dokumenten,17aktive Datenbanken, Einstellungen und Pause stimmen überein. Die neue nullable Fehlercodespalte enthält zunächst ausschließlichNULL. Acht synthetische Fortsetzungsprüfungen und unabhängiges Review bestehen. Keine Wiederholung der Migration, kein alter Serverstart, kein historisches Zurücksetzen.

**Auf dem persönlichen Mac installiert und frisch geprüft:** Backend `1.0.6-local.5621ec9`, Image72837cc0356954760e26aa1f9eb99713edc5287f598d7bd1a994f28a4298168f. Gesundheit, Versionsroute, lesender Endpunkt und Importpause bestehen. Der gesonderte Frischvergleich bestätigt344unveränderte Originalkörper,17Datenbanken, Einstellungen, identisches Datenvolume,264Python-/112UI-Dateien und native Signatur/Bytes. Native Fensterbedienung wurde nicht geprüft.

Die Fortsetzung meldete nach erfolgreichem Start `forward_repair_required`, weil sie von der nativen Speicherprüfung beide Reservestufen als `ok` verlangte. Root prüfte anschließend separat: **vor einer weiteren Sicherung `lowSpace`, nach dem abgeschlossenen Update `ok`**. Der ursprüngliche Fehlerbericht bleibt unverändert erhalten; `mac-root-postpublish.json` dokumentiert den tatsächlich gesunden installierten Stand mit dieser verbleibenden Reservewarnung. Kein Speicher wurde gelöscht. Das ist keine Kapazitätsabnahme für den großen Import.

Persönlicher Import bleibt pausiert, produktives Ollama aus. Kein neuer Modelllauf, Cloudauftrag oder private Neubewertung. Diese Lieferung verbessert Diagnostik und Wiederholung; sie beweist keine höhere Einordnungs- oder Antwortqualität. Native Tages-/Akkuabnahme und der geschlossene Aufnahme-/Such-/Fragenablauf stehen weiterhin aus. Der gesamte CoS bleibt unabgenommen.

Rohprotokolle sind bytegleich erhalten; einige enthalten von pytest/Vite ausgegebene Leerzeichen am Zeilenende. Der Diff-Leerzeichencheck gilt für die übrigen Quell- und Dokumentdateien; die Rohbelege werden dafür nicht verändert.
