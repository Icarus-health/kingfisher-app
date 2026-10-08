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

## Bau und Installation

Installiert ist die native Apple-Silicon-App **1.0.6-local.a209ba8**. Ihr signiertes Programm und die
verpackte Probe sind durch SHA-256 in `installation.json` belegt. Die alte App und private Konfiguration
liegen als Rückweg außerhalb des Repositorys. Der synchrone Dokumentordner ergänzte nach dem ersten
Signieren Finder-Metadaten; die Prüfung brach vor jedem Austausch ab. Die saubere Signierung erfolgte
anschließend außerhalb dieses Ordners, und die endgültig installierte App besteht die strenge Prüfung.

Der native Docker-Adapter mit unverändertem Produkt-Shellcode prüft das installierte Probe-Paket am echten
Container erfolgreich für beide Phasen (`before=ok`, `after=ok`). Der Container wurde **nicht neu gestartet**:
Kennung, Startzeit, Bild,344 Original-IDs/Digests, Einstellungen und private Env-Datei sind unverändert;
Dienst gesund und persönlicher Import weiterhin explizit pausiert. Der nächste normale App-Start verwendet
das neue Fensterprogramm. Keine Fensterbedienung als bestanden behauptet.

Ein universelles DMG wurde nicht fertiggestellt: Der lokale Intel-Link scheitert wie zuvor an fehlenden
x86_64-Scheiben der Swift-Kompatibilitätsbibliotheken. Intel-Typprüfung besteht; installiert wurde nur der
vollständig gebaute und signierte arm64-Stand für diesen Mac. Der universelle Release-Bau bleibt unverändert
streng und fällt bei diesem Werkzeugfehler aus. `build.json` und das komprimierte Bauprotokoll dokumentieren
die Grenze. Kein neuer öffentlicher Release, kein Docker-Image und keine GitHub-CI-Minuten verbraucht.

Komprimierte Vorher-/Nachher-Protokolle und `log-manifest.json` halten die Nachweise prüfbar. Die gelaufenen
Tests beziehen sich auf den Produktstand `a209ba8`; dieser Nachtrag verändert ausschließlich Dokumentation.

 Native Fensterbedienung bleibt wegen
Mac-/Browserfreigabe ungeprüft. Backend unverändert bei1.0.6-local.3483436, persönlicher Import pausiert,
produktives Ollama aus. Dies ist kein fertiger CoS und keine Abnahme des großen persönlichen Datenbestands.
