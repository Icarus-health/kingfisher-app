# Gemeinsame geprüfte CoS-Vorschau

Code **8ad7828c7664f6cd277f6bfeb2b06407591e4075**, Version **1.0.6-preview.8ad7828**. Die bisherigen getrennten Vorschauen sind in einem Stand zusammengeführt: Kalender-Duplikate mit Quellenbezügen (#37), RAM-Vorauswahl (#38), eigene datierte Gesundheitswerte (#40), Fortschritt und Quellenübersicht (#41/#42), lokaler Sprachdialog (#43), quellengebundene Wiederholung manueller Mailaufgaben (#44), korrigierter Grafikprüfer (#45). Keine zusätzlichen Funktionsentwürfe und keine Neuordnung persönlicher Daten.

## Frische gemeinsame Prüfung

- Sauberes Git-Archiv des obigen Codecommits, keine Synchronisationskopien. **515 UI-Fälle bestanden**, TypeScript/Vite-Build bestanden, bestehende Bündelgrößenwarnung erhalten.
- **234 betroffene Backendfälle und 26 Unterfälle bestanden**: Aufgabenaufnahme/Wiederholung/Migration/Bearbeitung/Verlauf, Gesundheitswerte, RAM, künstliche Kalender, Mail-Terminvorbereitung/-bindung, Arbeitsansichten, Quellenentzug und Kernablauf. Der Kernablauf benutzt künstliche Modellvorschläge; er belegt keine echte Erkennungsqualität.
- Echte Grafikprüfung grün: 16 Dateiverweise, 16 Icons. Die früheren falschen `expired`-Fehler bleiben in den historischen Einzelprotokollen erhalten.
- Enges unabhängiges Integrationsreview ohne konkrete Regression. Kein neuer vollständiger Backend-Gesamtlauf; vorherige Teil-/Gesamtnachweise werden nicht als heutiger Vollnachweis ausgegeben.
- Native Quellen bytegleich zum Voice-Stand `2e672637`; dessen 34 Tests und ein Plattformskip sind historisch, kein neuer Lauf. ARM-App/DMG frisch gebaut, tiefe strenge Ad-hoc-Signatur, ARM64, Version und DMG-Integrität geprüft. Nicht notarisiert, Intel nicht geprüft.
- Neues tatsächliches Backend-/UI-Abbild aus verifizierter vorhandener Basis, ohne Pull oder Netzwerk gebaut. Basisschichten erhalten; alle 268 Python- und 112 UI-Dateien im Abbild gegen SHA-256-Manifest geprüft.
- Getrennter Container: kein Netzwerk, keine Ports oder Hostmounts, schreibgeschützt mit leerem tmpfs. Gesundheitsaufnahme/Wiederholung/Korrektur/Verlauf/Entzug, künstliche Kalenderauswahl/Trennung, RAM-Ablehnung vor Modell-I/O, Quellenmetadaten/Auth/Pause sowie Mailaufgabe nach verlorener Antwort und Neustart bestehen. Bearbeitete/erledigte Aufgaben bleiben erhalten; geänderte Felder/Quellen und Entzug lehnen alte Speicheranfragen ab. UI wird statisch ausgeliefert, nicht gerendert.

## Fehler im Prüfaufbau bleiben sichtbar

Der erste native Paketbau scheiterte am System-Iconwerkzeug in der eingeschränkten Umgebung. Die identischen Originalgrafiken wurden mit erlaubtem Systemzugriff erfolgreich verarbeitet, der vollständige Build danach bestanden. Kein neues Icon oder Workaround in Produktcode.

Der erste Container-Prüfaufruf hatte falsche tmpfs-Besitzrechte (10001 statt vorhandener 1000) und keinen ausdrücklichen Python-Einstieg; der Dienststart scheiterte sofort an seinem leeren Testverzeichnis. Der korrigierte Prüfer startet ausdrücklich Python und nutzt UID/GID 1000. Es wurden keine produktiven Daten gemountet oder Modelle aufgerufen. Beide Fehlprotokolle erhalten.

Nach Kopieren in die dauerhafte Paketablage beanstandete codesign Finder-/Resource-Metadaten. Ausschließlich beim neu erstellten Vorschau-App-Bündel wurden diese Metadaten entfernt (`xattr -cr`); danach bestand die strenge tiefe Signaturprüfung auch dort. Programm, DMG und Quellarchiv wurden gegen ihre gespeicherten Prüfsummen verglichen und sind unverändert. Keine produktive App verändert.

## Pakete und Grenzen

Dauerhafte lokale Ablage: `/Users/sorenkube/Documents/Codex/Kingfisher-Pruefpakete/2026-10-09-cos-reviewed-8ad7828/` mit App, DMG, Original-Gitarchiv, Manifesten und ausführbarem stdin-Prüfer. Ältere Pakete erhalten. Docker-ID `sha256:c9b13d19f1873968a4da1e8c559e8653388d20d8b5b408a47580334c6bd68cd8`, Basis `sha256:a8d2d89e6c47c5050b779dbc0e595cb187efd9650142416cdb557dfdf8b6cfe9`. Lokaler kompatibler Tag `ghcr.io/icarus-health/kingfisher-app:1.0.6-preview.8ad7828`; **nicht veröffentlicht**.

Produktive Installation und pausierter Import bleiben unverändert. Kein Fenster, Mikrofon, persönliche Kalender-/Mailinhalte, Cloudmodell oder Ollama benutzt. Fenstertest ausdrücklich später: erst dort tatsächliche Darstellung, Entwurf/Abbruch/Senden, Kalenderbestand, Quellenabdeckung und RAM/Akku prüfen. Nicht als fertiges CoS oder fehlerfreies persönliches Gedächtnis bezeichnet. Keine Installation/Öffnung vor sicherer Übergabe und nativer Abnahme.

`freeze.json` pinnt den Code, `package-inputs.json` die Inhalte, `package-verification.json` das Paket, `verification.json` Ergebnisse und Rohlog-Prüfsummen. Reproduktion: vorhandene Basis-ID prüfen, sauberes Archiv entpacken, bestehende Node-Abhängigkeiten nutzen, UI bauen; Python-Paket/UI/VERSION über den dokumentierten isolierten Docker-Overlay ersetzen. Paketprüfung exakt:

```sh
docker run --rm --network none --read-only \
  --tmpfs /data:rw,uid=1000,gid=1000 --tmpfs /tmp:rw,uid=1000,gid=1000 \
  -e ICARUS_DATA_DIR=/data --entrypoint python -i \
  ghcr.io/icarus-health/kingfisher-app:1.0.6-preview.8ad7828 - < probe-stdin.py
```

Keine CI-Wiederholung, Abonnements oder Check-ins. Vorhandene Starlette/httpx-, Vite- und hdiutil-Werkzeughinweise sind sichtbar.
