# Dauerhafte Bedeutungssuche im Produkt — 8. Oktober 2026

Code: `44a9fb559bf48e449bf53d633a1a0666c748ea1c`, Draft-PR9. Lokaler App-Baustein: `1.0.6-local.44a9fb5`; dies ist keine öffentliche Stable-Veröffentlichung.

## Verhalten

Die App bindet einen Suchdienst je Originalbestand. Bereits eingeordnete Abschnitte werden über den vorhandenen Hintergrundprozess in Paketen von höchstens8 Abschnitten und16384 UTF-8-Bytes vorbereitet. Prompt-/Upload-Arbeit nimmt ebenfalls ein globales Paket mit, damit ältere Quellen Fortschritt erzielen. Netzteil-, Pause-, Generation-, Modellrollen- und Wiederherstellungsgrenzen bleiben bestehen.

Gesprächsrouting und Antwortvorbereitung nutzen denselben dauerhaften Suchbestand. Nur der Fragevektor wird innerhalb einer HTTP-Nachricht wiederverwendet; Treffer und Quellenprüfung werden jedes Mal frisch berechnet. Geänderte Suchtexte bekommen eigene Vektoren. Produktive Arbeitsgedächtnissuche fällt nie auf den alten Diagnoseadapter zurück, der Quellen während einer Frage einbettet. Dieser bleibt für explizite Standalone-Diagnosen kompatibel. Bestätigtes Wissen besitzt daneben weiterhin seinen bisherigen separaten Suchweg; dieser Baustein ersetzt nicht automatisch jede andere Modellverwendung.

Der Status unterscheidet Quellen-Einordnung von vorbereiteten Suchabschnitten. Regelmäßige Coverage-Abfragen starten weder Modell noch Tags-Abfrage. Ungeprüfte Hintergrundbereitschaft wird als `unverified` statt frisch bestätigt angezeigt; frühere ausdrückliche Prüfungen gelten nur bei unveränderter Konfiguration. Vorbereitete Abschnitte und noch nicht sortierte Quellen bleiben getrennt sichtbar. Keine erfundene Restzeit oder Zusage perfekter Treffer.

## Gegenprüfungen

- Breiter betroffener Backend-Lauf:403 bestanden,1 übersprungen;1 Wiederherstellungs-Test scheiterte zunächst allein an der Sandbox-Portbindung. Derselbe einzelne Test mit lokaler Portfreigabe:1 bestanden. Keine CI-Wiederholung.
- Nach Reviewkorrekturen:50 fokussierte Tests bestanden (Suchdienst, Rollenbindung, echter HTTP-/Verlaufsweg, lokale Gewichtsprüfung). Vorherige Bestands-/Signaturprüfung:83 bestanden. Diese Läufe überschneiden sich und sind keine addierbare Gesamtsumme.
- Gesamte vorhandene UI-Tests:382 bestanden. TypeScript/Produktionsbau erfolgreich; bestehende Warnung zum großen JavaScript-Bündel bleibt.
- Vollständige Signatur über alle aktuellen zugelassenen Quellen und Einordnungen statt2048er Fenster. Test mit2049 neueren Ablenkern findet eine alte Quelle im tatsächlichen Auswahlweg; eine Änderung an einer alten, nicht ausgewählten Quelle macht die gespeicherte Antwort ohne Einbettung ungültig.
- Paralleltests mit dem tatsächlich verwendeten nicht wiedereintrittsfähigen Gesprächs-Lock. Hintergrund gibt den Modellplatz vor dem Commit frei; so kann eine Frage, die bereits den Gesprächs-Lock hält, keinen gegenseitigen Stillstand verursachen. Die bestehende Serialisierung der Vordergrundgespräche wurde bewusst beibehalten; Quellensperren werden während Transport nie gehalten.
- Echte gebaute Oberfläche im getrennten lokalen Browser-Test mit ausschließlich künstlichen Daten: pausierter/teilweiser Stand, getrennte Fortschritte, unbekannte bzw. veraltete Werte über echte Komponenten-Render-Tests. Wechsel von1/2 auf2/2 sortierte Quellen und1/1 auf2/2 Suchabschnitte erschien ohne erneuten Klick durch vorhandene15-Sekunden-Aktualisierung. Doppelte Pausenformulierung und Singularbeschriftungen korrigiert.

## Unabhängiges Review und Korrekturen

Review des vollständigen Integrations-Diffs `8417445..00dcb03` fand zwei wichtige Fehler:

1. Ein lokaler Ollama-Endpunkt beweist keine lokalen Gewichte. Produktadapter prüft jetzt frisch den exakten Einbettungsnamen/Digest, positive GGUF-/Größen-/Architektur-/Parameter-Metadaten und Einbettungsfähigkeit; Remote-Metadaten werden vor Quellenübergabe verworfen. Wiederholt bei Eintritt, vor und nach Einbettung. Freigabe wird unmittelbar vor der Quellenübergabe erneut geprüft. Ursprüngliche unabhängige Remote-Standardmodell-Reproduktion:kein `/api/embed`, Original erhalten.
2. Abfragen während einer Fehlersperre verlängerten deren Frist. Eigener Wartezustand verhindert dies; deterministischer Test zeigt Wiederanlauf bei ursprünglicher Frist130 statt unendlicher Verlängerung.

Beide Befunde unabhängig nachgeprüft,45 Tests bestanden; keine weiteren wichtigen Befunde im begrenzten Review. Nach zusätzlichem Freigabe-Test50 fokussierte Tests bestanden. Keine privaten Inhalte oder echten Cloudaufrufe in diesen Prüfungen.

## Fertiges Paket / Linux-Arm64

Das Python-Paket, vollständige Lizenz, sqlite-vec0.1.9 und112 Oberflächen-Dateien wurden im fertigen Abbild gegen Prüfsummen geprüft.264 Paket-Dateien stimmen bytegenau. Native Linux-Wheel-Prüfsumme entspricht der zuvor isoliert geprüften Fassung. `package-check.json` und `image-check.json` enthalten den Nachweis.

`product_smoke.py` läuft im fertigen Abbild ohne Netzwerk, mit2CPU/512MiB/64Prozessen und64MiB temporärem Platz. Echter FastAPI-Gesprächsweg, lokale Modell-Metadatenprüfung per Attrappe, native SQLite-Vektorerweiterung, Hintergrundaufbau, eine Frage-Einbettung, Wiederöffnung und Quellenentzug bestanden. Originaldatenbank bleibt ohne Erweiterung lesbar. Ergebnis:`linux-product-smoke.json`.

## Grenzen

Synthetische Vektoren/Modellantworten prüfen Verdrahtung und Quellenschutz, keine echte LLM-Trefferqualität. Vorherige100000-Vektoren-Messung ist kein vollständiger Ende-zu-Ende-Benchmark. Die vollständige Signatur streamt Metadaten, liest aber alle aktuellen Quellen strukturell; ihre Laufzeit bei sehr großen echten Mailbeständen ist noch zu messen. Normale Inhaltsänderungen müssen den Inhaltsdigest/Quellenstand aktualisieren; eine absichtliche direkte SQL-Fälschung beider Textkopien bei unverändert falschem Digest liegt außerhalb dieses Vertrags und wird beim Auflösen verworfen.

Native Mac-Bedienprüfung bleibt offen:Computersteuerung meldete gesperrten Mac. Der Browser-Test ersetzt diesen Nachweis nicht. Mac-Installation und Datenprüfung werden gesondert dokumentiert, sobald tatsächlich durchgeführt.
