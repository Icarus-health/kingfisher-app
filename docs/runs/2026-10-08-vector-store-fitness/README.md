# Lokaler Vektorspeicher: Eignungsmessung, 8. Oktober 2026

Nur erzeugte normalisierte Float32-Vektoren, keine persönlichen Quellen, Modellstarts oder Cloudanfragen. Geprüft: sqlite-vec **0.1.9**, exakte Cosinus-Top-12, 1024 Dimensionen. Vier Fragen gegen eine unabhängig vollständig berechnete 256-Vektor-Referenz stimmen überein; größte Distanzabweichung < 0,0000002. Neustart der Verbindung, Modellpartition, dauerhaftes Löschen und quick_check bestehen. Erweiterungsladen ist nach Initialisierung wieder abgeschaltet.

| Umgebung | Vektoren | Einfügen | längste von sechs Fragen | maximaler Prozessspeicher | Datenbank |
|---|---:|---:|---:|---:|---:|
| Mac arm64, SQLite 3.53.4 | 20.000 | 2,90 s | 0,0335 s | 38,2 MB | 97,1 MB |
| Mac arm64, SQLite 3.53.4 | 100.000 | 14,03 s | 0,1623 s | 39,5 MB | 426,4 MB |
| Linux arm64, SQLite 3.46.1 | 100.000 | 52,92 s | 0,2862 s | 34,8 MB | 426,4 MB |

Linux: vorhandenes python:3.12-slim, kein Netzwerk/Pull, zwei CPUs, 512 MiB, lesendes Root-Dateisystem, eigener synthetischer Arbeitsordner. Prozessgrenzen zusätzlich CPU 180 s, Datei 700 MiB. Keine globalen Docker-Ressourcen geändert. Mac-Betriebssystemcache wurde **nicht geleert**; Wiederöffnung ist kein Nachweis kalter Disk-Latenz. RSS ist Prozessspeicher, kein Gesamtverbrauch des Macs oder der Docker-VM. Größere Bestände und reale Embeddings sind hier nicht gemessen. Das beweist weder relevante Antworten noch vollständige Produktintegration.

`probe.py` und die drei JSON-Dateien sind die ausgeführten Messartefakte. Die großen synthetischen Datenbanken und nativen Binärdateien werden nicht eingecheckt.

## Herkunft und Entscheidung

[PyPI sqlite-vec](https://pypi.org/project/sqlite-vec/) und [Python-Anbindung](https://alexgarcia.xyz/sqlite-vec/python.html). Nur die tatsächlich getestete API verwenden; die laufende Website dokumentiert teilweise neuere Vorabfassungen. Wheels über explizites offizielles PyPI, ohne Abhängigkeiten geladen, SHA-256 vor Entpacken verglichen:

- macosx_11_0_arm64: `1d52e30513bae4cc9778ddbf6145610434081be4c3afe57cd877893bad9f6b6c`
- manylinux_2_17_aarch64: `4e921e592f24a5f9a18f590b6ddd530eb637e2d474e3b1972f9bbeb773aa3cb9`

Upstream [MIT](https://github.com/asg017/sqlite-vec/blob/v0.1.9/LICENSE-MIT) / [Apache-2.0](https://github.com/asg017/sqlite-vec/blob/v0.1.9/LICENSE-APACHE), Copyright 2024 Alex Garcia. MIT-Hinweis bei Aufnahme/Redistribution beilegen; die Wheels enthalten keinen vollständigen Lizenztext. Version exakt pinnen, kein automatisches Upgrade auf Vorabfassungen. Die Messung rechtfertigt einen getrennten, löschbaren Vektorcache; Originaldatenbanken bleiben erweiterungsfrei. Die Produktverkabelung braucht eigene Quellenentzug-, Neustart-, Hintergrundbudget- und Sicherungsprüfungen.

## Implementierter Speicherbaustein (noch ohne Produktverkabelung)

`DurableSemanticIndex` speichert nur Vektoren und gebundene Quellenverweise in `.search-cache/<Originaldateiname>.vectors.sqlite3`. Die Originaldatei wird nur lesend angebunden. Ein vollständiger Modellname samt Digest und eine Cache-Epoche verhindern Vermischung und verspätete Pakete anderer Modellstände. Vektoren, Paketfortschritt und Fehler werden transaktional gespeichert. Quellen werden vor Speicherung und Rückgabe erneut aufgelöst. Die bestehende Wortsuche und der bisherige opt-in-Fragepfad sind unverändert; dies allein behebt deren bisherige Laufzeitgrenze noch nicht.

Eine gezielte RED/GREEN-Gegenprobe zeigte, dass ein eingefrorener maximaler SHA-Schlüssel keinen festen Bestand bildet: neue Hashes können davor liegen und alte Arbeit weiter verdrängen. Deshalb nutzt der Cache einen dauerhaften SQLite-Einfügepositions-Cursor mit eingefrorener Obergrenze; SHA-Schlüssel bleiben die Identität. Gelöschte/wiederverwendete Positionen werden vor Commit geprüft. Ein weiterer RED/GREEN-Fall verhindert, dass ein ansonsten lesbarer Cache mit fehlendem Vektor nach Wiederöffnung als vollständig gilt.

128 betroffene Speicher-, Bedeutungs-, Lebenszyklus-, Flow-, Sicherungs-, Wiederherstellungs- und gemeinsame Quellenregeln-Tests bestanden in 22,93 s. Enthalten: 21 neue Cache-Tests, Neustart, echte Sicherung/Wiederherstellung ohne Cache, Quellenwechsel/Entzug, Modell-/Dimensionswechsel, Transaktionsabbruch, Fehlerpause, konkurrierende Pakete, 2251 Abschnitte und neue Ankünfte. Eine bereits vorhandene Starlette/httpx-Deprecation-Warnung blieb sichtbar. Kein neuer vollständiger Backend-Lauf. Die Tests verwenden die isoliert entpackte geprüfte Mac-Erweiterung; sie ändern keine Modellkonfiguration.

`storage_smoke.py` bestand zusätzlich in einem kurzlebigen Container des vorhandenen Linux-arm64-App-Abbilds, mit dem neuen Paketquelltext und dem geprüften Linux-Wheel lesend eingebunden: Neustart, reine SQLite-Integrität der Originale, Abruf, sofortiger Quellenentzug und Bereinigung. Kein Netzwerk, keine Modellaufrufe, keine Änderungen an der installierten App. Ergebnis: `linux-storage-smoke.json`.

Noch erforderlich: Hintergrundarbeiter mit allen Modell-/Energie-/Pausengrenzen, Einbettungsrollen-Verkabelung, vollständige Bestandskennung, ehrlicher API-/UI-Fortschritt, Restore-Lebenszyklus und Prüfung des vollständigen Fragewegs. Erst danach den geprüften Stand auf dem Mac aktivieren. Strukturelle Cache-Zahlen sind weder eine Aussage über vollständige Mailaufnahme noch über die Richtigkeit einer Antwort.

Das lokale Python-Wheel wurde isoliert ohne Abhängigkeiten gebaut. `package-check.json` bestätigt den exakten sqlite-vec-Pin, den vollständigen MIT-Hinweis im ausgelieferten Paket und den bytegleichen neuen Modulquelltext. Das Build-Werkzeug wurde nur in der isolierten Build-Umgebung geladen; keine globale Installation oder bestehende virtuelle Umgebung verändert.

## Unabhängiges Review und Entscheidungen

Ein frischer Reviewer prüfte den ganzen Speicherbaustein. Sein wichtiger Befund: Originaldatei-Austausch während einer bereits begonnenen Operation konnte alte Referenzen liefern bzw. Fortschritt am alten Handle speichern. Zwei Regressionen für Suche und Commit scheiterten vor der Korrektur. Nun wird die Dateikennung vor Transaktionsabschluss nochmals geprüft; Lesen bricht ab, Schreiben rollt zurück. Die oben genannten128 Tests, Linux-Probe und Paketprüfung gelten für diese endgültige Korrektur. Kein verbleibender wichtiger Reviewbefund.

Kleiner zurückgestellter Befund: Fehler-Hashes entzogener/neu eingeordneter Abschnitte bleiben bisher im Cache; sie beeinflussen weder aktuelle Abdeckung noch Treffer, sammeln aber unnötige Metadaten an. Die nächste Hintergrundintegration bekommt eine begrenzte Bereinigung dieser Fehlerzeilen. Originale bleiben unberührt.

Bewusste Entscheidungen: Speicher separat fertigstellen und noch nicht im Produkt aktivieren (Kosten: zusätzlicher Integrationsschritt, dafür keine halbfertige Mac-Suche); Einfügeposition statt SHA-Reihenfolge für den endlichen Aufbaudurchlauf (Kosten bei falscher Annahme: Aufbauverzögerung nach Ersetzungen, keine Änderung der Originale). Der vollständige Integrationsplan liegt unter `docs/superpowers/plans/2026-10-08-durable-search-integration.md`.
