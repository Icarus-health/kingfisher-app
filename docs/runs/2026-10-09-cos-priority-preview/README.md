# Gemeinsame CoS-Vorschau mit vorrangiger Quellen-Wiederprüfung

Code **83cfaa0664f73b0d95d2535c582427814f2d24ba**, Version **1.0.6-preview.83cfaa0**. Diese Lieferung ergänzt die [vorherige gemeinsame Vorschau](../2026-10-09-cos-context-preview/README.md) um [Draft #48](https://github.com/Icarus-health/kingfisher-app/pull/48). Nach Korrektur von Beteiligten/Quellen oder ausdrücklicher Wiederöffnung wartet die Aufgabenprüfung nicht bis zum Ende eines großen Erstimports. Eine dauerhafte, textfreie Wiedervorlage reserviert einen begrenzten Anteil des erlaubten Prüfbudgets; der normale Import läuft weiterhin im übrigen Anteil. Das aktiviert kein Modell und bestätigt keine Aufgabe automatisch.

## Frische Nachweise des gemeinsamen Pakets

- Sauberes Gitarchiv: **507 betroffene Backendtests bestanden**, kein frischer Gesamtlauf behauptet. UI und native Quellen gegenüber `262cfc3` unverändert. TypeScript/Vite und Grafikprüfung (16 Dateien, 16 Icons) frisch bestanden. Die **515 UI-Fälle und 34 nativen Fälle mit einem Plattformskip** sind frühere Nachweise auf unveränderten Quellen.
- ARM64-App und DMG frisch gebaut; strenge tiefe Ad-hoc-Signatur und DMG-Integrität bestanden. Nicht notarisiert, Intel nicht geprüft. Die neue dauerhafte Vorschaukopie ist nach Entfernen ihrer Finder-/Resource-Metadaten erneut signatur- und prüfsummengeprüft. Bestehende Bündelgrößen-, Starlette/httpx- und hdiutil-Hinweise bleiben sichtbar.
- Tatsächliches lokales Backend-/UI-Abbild ohne Pull oder Netzwerk aus vorhandener Basis gebaut: Basisschichten erhalten, 269 Python-/112 UI-Dateien im Prüfprozess gegen Manifest verglichen. 109 Designquellen separat gegen Manifest geprüft.
- Isolierter fertiger Paketablauf ohne Netzwerk, Ports, Hostmounts, Schlüssel oder Modelle: bisherige Gesundheits-, künstliche Kalender-, RAM-, Quellenübersichts-, Mailaufgaben-Wiederholungs- und Kontaktkorrekturabläufe bestanden. Zusätzlich: Quelle hinter 30 künstlichen Mails wird nach Kontaktkorrektur im nächsten begrenzten Lauf erneut geprüft; Ausschluss wird abgearbeitet, ausdrückliche Wiederöffnung erneut vorgemerkt und geprüft. Original bleibt gleich; keine automatisch übernommene Aufgabe.
- Echte SQLite-Umstellung **v20 → v21 mit künstlichem Bestand**, geprüfte Sicherung vor der Umstellung und Wiederherstellung dieser Sicherung im leeren Prüfcontainer bestanden. Alle ursprünglichen Episode-Zeilen bleiben unverändert; die v20-Sicherung bleibt v20, wiederhergestellter Bestand wird korrekt nach v21 umgestellt. Kein Zugriff auf persönliche Datenbanken.
- [Unabhängiges enges Integrationsreview](independent-integration-review.md) ohne konkrete Kollision. Ein Testkonflikt wurde so aufgelöst, dass EpisodeStore v21 und TaskStore v3 samt manueller Mailauftrags-Wiederholung erhalten bleiben. Laufzeitcode der neuen Wiedervorlage ist gegenüber #48 unverändert.

## Frühere Nachweise und offene Grenzen

Die [Einzelkorrektur #48](../2026-10-09-task-source-rechecks/README.md) enthält Red-/Mutations- und Skalierungsnachweise sowie den vorherigen Backend-Gesamtlauf: 5913 bestanden, 13 zunächst fehlgeschlagene alte Testverträge, 1 Plattformskip und 26 Unterfälle. Die betroffenen Testverträge wurden anschließend korrigiert und ihre vollständigen Dateien erneut geprüft (112 Fälle). Kein vollständig grüner damaliger Gesamtlauf oder erneuter heutiger Gesamtlauf wird daraus abgeleitet.

Die automatische Wiedervorlage betrifft korrigierte Quellen für die Aufgabenprüfung; neu eingehende Quellen und Modellwechsel nutzen weiterhin den vorhandenen Scanweg. Sie ist kein vollständiger Gedächtnis-Neuaufbau. Der alte Scan-Verzögerungshinweis im früheren Vorschauprotokoll ist historisch und durch diese begrenzte Priorisierung ergänzt.

**Nicht installiert, nicht veröffentlicht.** Die persönliche App bleibt unverändert, großer Import pausiert. Nutzerantwort: **Fenstertest später**. Kein Fenster, EventKit, Mikrofon, persönliche Mail-/Kalendertexte, Ollama oder Cloudmodell benutzt. Native Darstellung, echte Kalender, persönliche Erkennungs-/Abrufqualität, Quellenabdeckung und RAM/Akku bleiben offen. Alle Modellantworten im Pakettest sind fest vorgegebene künstliche Prüfurteile; kein Beleg für echte Modellqualität oder einen fertigen CoS.

**Vor einer späteren Installation ist eine geprüfte vollständige Sicherung des tatsächlichen Bestands nötig.** v21 kann von der älteren App nicht einfach geöffnet werden; für Rückkehr zur alten App muss die geprüfte Sicherung von vor der Umstellung wiederhergestellt werden. Die synthetische Sicherungsprobe ersetzt keine Sicherung deiner Daten.

Dauerhafte Ablage: `/Users/sorenkube/Documents/Codex/Kingfisher-Pruefpakete/2026-10-09-cos-priority-83cfaa0/`. Ältere Pakete bleiben erhalten. Lokales Abbild `sha256:4b50fb4a18b36f86c2d60de5d7eb9952a580f02baf9c67cc67791e7d935f4f62`, nur lokaler Tag `ghcr.io/icarus-health/kingfisher-app:1.0.6-preview.83cfaa0`.

`freeze.json`, `package-inputs.json`, `package-verification.json`, `verification.json`, `Dockerfile` und `probe-stdin.py` halten den Stand fest. Rohlogs verlustfrei komprimiert. Reproduktion nur mit lokal vorhandenem Abbild:

```sh
docker run --rm --network none --read-only \
  --tmpfs /data:rw,uid=1000,gid=1000 --tmpfs /tmp:rw,uid=1000,gid=1000 \
  -e ICARUS_DATA_DIR=/data --entrypoint python -i \
  ghcr.io/icarus-health/kingfisher-app:1.0.6-preview.83cfaa0 - < probe-stdin.py
```

Diese Lieferung aktualisiert den bestehenden gemeinsamen Draft #46, erstellt keinen weiteren kombinierten PR und löst keine CI-Wiederholung oder Überwachung aus.
