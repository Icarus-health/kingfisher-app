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

Die Mac-Orchestrierung besteht 31 synthetische Fälle sowie dieselben 31 Root-Gegenproben; unabhängiges Review und rote Kontrollen liegen unter `installer/` bzw. daneben. Die separate Frischprüfung wurde statisch gegengelesen; sie ist auf dem neuen persönlichen Mac-Stand noch nicht gelaufen. Die Orchestrierung stoppt den App-Dienst, verlangt ein ruhiges Wartungsfenster ohne weitere erkannte Schreiber, prüft Speicherreserve und erzwingt eindeutige Migrationsergebnisse ohne Veröffentlichung. Nach Veröffentlichung erfolgt keine automatische historische Rücksetzung.

Der tatsächliche Installationsversuch stoppte **vor der Migration**: Der kalt gestoppte Bestand enthält noch genau `regeln.sqlite3-wal` mit 0 Bytes und `regeln.sqlite3-shm` mit 32.768 Bytes. Der unveränderte Vorlauf lehnt Begleitdateien ab, statt sie zu löschen oder mit `immutable=1` auszublenden. Dieser Befund ist kein Datenbankschaden.

Root prüfte danach WAL-bewusst mit `mode=ro` ohne `immutable`, sicherte den vollständigen Bestand einschließlich Journaldateien unter dem privaten lokalen Rückweg, verglich alle logischen Daten und bestätigte Schema19, 344 Originalkörper, 17 aktive Datenbanken, Pause und fehlenden Prüfmodus. Image und env-Datei waren unverändert. Die bisherige Version `1.0.6-local.e8cfc26` startete wieder gesund; Version, lesender Endpunkt und globale Pause wurden geprüft. `mac-installation-stopped.json` und `mac-safe-resume.json` trennen Versuch und tatsächlich geprüften Wiederanlauf.

Noch notwendig ist ein separat geprüfter SQLite-Abschluss unter gestoppten Schreibern sowie dessen bewusste Einbindung vor dem unveränderten Migrationsvorlauf. Kein manuelles Löschen der Journaldateien; kein erneuter alter Serverstart zwischen Abschluss und Migration.

**Noch nicht auf dem persönlichen Mac installiert.** Persönlicher Import bleibt pausiert, produktives Ollama aus. Kein neuer Modelllauf, Cloudauftrag oder private Neubewertung. Diese Lieferung verbessert Diagnostik und Wiederholung; sie beweist keine höhere Einordnungs- oder Antwortqualität. Native Bedienung und Tages-/Akkuabnahme stehen weiterhin aus.

Rohprotokolle sind bytegleich erhalten; einige enthalten von pytest/Vite ausgegebene Leerzeichen am Zeilenende. Der Diff-Leerzeichencheck gilt für die übrigen Quell- und Dokumentdateien; die Rohbelege werden dafür nicht verändert.
