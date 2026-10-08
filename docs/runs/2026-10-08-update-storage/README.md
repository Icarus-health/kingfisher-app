# Updates bei knappem Docker-Speicher sicher abbrechen

Der erste lokale Anhangs-Updateversuch (siehe vorheriger Lauf) traf auf ein volles Docker-Dateisystem,
obwohl auf dem Mac noch viel Platz frei war. Eine reine Host-Prüfung kann diesen Fehler nicht verhindern.

## Änderung

Mac-App und Entwickler-Starter prüfen vor Sicherung/Bildmarkierung und erneut nach dem Download,
bevor sie die Bildwahl ändern oder einen Dienst stoppen. Die Messung läuft lesend mit Python im bestehenden
Container. Bei knappem Platz, ausgeschöpften Dateiplätzen, fehlendem Probe-Paket oder unzuverlässiger
Messung wird geschlossen abgebrochen. Reserven und Grenzen stehen in `macos/README.md`. Kein automatisches
Löschen, keine Importfreigabe, kein Modellstart und kein neues Backend-Bild.

## Nachweise

- Native Verhaltens-RED am unveränderten Updater: 14 Sicherheitsfälle aktualisierten fälschlich trotzdem;
  die Erfolgskontrolle zeigte die zwei fehlenden Prüfschritte. Kein bloßer Quelltextvergleich.
- Python-Verhaltens-RED mit ausschließlich entfernten Prüfaufrufen: beide Knappheitsfälle aktualisierten
  fälschlich trotzdem; anschließend unverändert wiederhergestellt.
- 87 gezielte Prüfungen bestanden: 57 kompilierte native Ablauf-/Grenzwert-/Paritätstests und30 Python-Tests
  inklusive echter temporärer Dateien, Symlinks/FIFO, unbekannter Dateiplätze, Größenüberlauf und vollständig
  verpacktem `python -c`-Aufruf. Externe Docker-/HTTP-Grenzen sind simuliert; Updater, Docker-Adapter und
  Konfigurationsdatei verwenden den Produktcode.
- Bestehender Mac-Vertrag:26 bestanden,1 plattformbedingter Skip. Unabhängiges Review ohne offenen Befund;
  der Reviewer führte Python-Tests aus und prüfte Swift separat (sein nativer Teststart kollidierte mit einer
  laufenden Testdatei-Änderung und gilt ausdrücklich nicht als unabhängiger nativer Testlauf).
- Lesende Messung am echten Container:1.020.157.952 freie Bytes,3.018.992 freie Dateiplätze,
  51.750.967 Bytes in26 obersten regulären Datendateien. Keine Inhalte oder Geheimnisse im Bericht.

Bau und Installation werden mit separatem Nachweis ergänzt. Native Fensterbedienung bleibt wegen
Mac-/Browserfreigabe ungeprüft. Backend unverändert bei1.0.6-local.3483436, persönlicher Import pausiert,
produktives Ollama aus. Dies ist kein fertiger CoS und keine Abnahme des großen persönlichen Datenbestands.
