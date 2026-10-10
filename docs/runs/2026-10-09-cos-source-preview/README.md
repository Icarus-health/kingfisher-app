# Gemeinsames CoS-Paket mit Quellen- und Fortschrittsanzeige

## Ergebnis

Version **1.0.6-preview.173cef8**, Code `173cef8adb39d7a5d68a6c81f3acc3c16850733b`. Die bestehende gemeinsame Kalender-/RAM-/Gesundheitsvorschau wurde um PR [#41](https://github.com/Icarus-health/kingfisher-app/pull/41) und [#42](https://github.com/Icarus-health/kingfisher-app/pull/42) ergänzt. Ein gemeinsames lokal geprüftes App-/Backendpaket liegt bereit; es ist **nicht installiert**, kein öffentlicher Release und keine Zusammenführung der GitHub-Drafts in main.

Die Quellenübersicht unterscheidet Verbindung, Aufnahme/Wiedererkennung und Einordnung. Gedächtnisfortschritt berücksichtigt die tatsächliche Pause-/Energiefreigabe; fehlgeschlagene Aktualisierungen behalten den letzten bekannten Stand ohne aktuelle ETA-/Fertigbehauptung. Kompakte Ordnerabfragen senden Zähler statt Dateinamen und Fehlerlisten. Kalenderkorrektur, RAM-Vorauswahl und eigene datierte Gesundheitsmessungen bleiben enthalten.

Die automatische Git-Zusammenführung war konfliktfrei. Die unabhängige statische Prüfung fand dennoch einen wichtigen Sichtbarkeitsfehler des älteren Coverage-Pollers. Die Korrektur verwirft überholte Antworten auch bei schnellem Verbergen/Zurückkehren und bei Nachlesen nach einem Automatikwechsel. Keine Modellanfrage oder neue Freigabe ist dafür nötig.

## Frische Nachweise und ihre Reichweite

- 195 betroffene Backendfälle bestanden, 1 Linux-spezifischer Fall auf macOS übersprungen. Der Lauf stammt aus dem anfänglichen Integrationsarchiv `26e2bda`; sämtliche getrackten Backenddateien sind bytegleich zum finalen Archiv `173cef8`. Kein vollständiger Backendlauf behauptet.
- Vollständige UI-Suite am finalen Code: 485 bestanden. Ein zwischenzeitlicher Lauf hatte 482 bestandene Fälle und einen Quelltext-Regextest, der den früheren Ausdruck verlangte. Er wurde durch eine echte Effekt-/Handlerprüfung ersetzt. Das Protokoll bleibt erhalten.
- Nachgewiesenes RED→GREEN: drei Sichtbarkeitsfälle und zwei Automatik-Nachlesefälle. Finale sieben Komponenten-Grenzfälle bestanden. Die deterministische Hook-Steuerung prüft die echten Effekte/Handler, ersetzt jedoch keinen React-Runtime-, DOM- oder nativen Fenstertest.
- Aus sauberem finalem Git-Archiv: 28 fokussierte UI-Fälle, TypeScript/Vite und ARM-App-Bau bestanden. Vorhandene Node-Abhängigkeiten wurden geteilt; keine Downloads. Native Swift-Dateien wurden in dieser Runde nicht geändert; die früheren nativen Testläufe bleiben im [vorherigen Paketbericht](../2026-10-09-cos-preview-integration/README.md), sie werden hier nicht als neue Prüfung ausgegeben.
- Ad-hoc-Signatur streng/tief verifiziert, ARM64 und Appversion geprüft, DMG-Prüfsumme bestätigt. Nicht notarisiert; keine Intel-/Universalabnahme.
- Tatsächliches neues Backend-Abbild im kurzlebigen Container mit `--network none`, schreibgeschütztem System, leeren tmpfs-Daten, ohne Ports oder Host-/Produktivdatenmounts geprüft. Alle 268 Python- und 112 UI-Dateien stimmen exakt mit dem Inhaltsmanifest überein. App-/Backend-Versionskennung und unveränderte Basisschichten bestätigt.
- Paketfluss: Gesundheitsaufnahme, idempotentes Retry, Korrektur, Ablehnung veralteter Änderung, Verlauf, erneutes Öffnen und Entzug; künstliche Kalenderauswahl/Trennung; RAM-Ablehnung vor Modell-I/O; geschützte Metadatenrouten, Live-Pause im Coverage-Status, kompakte Ordnerzählung mit Alias-/fehlenden Referenzen und 10.000 künstlichen Fehlern ohne Fehlerliste/Originaländerung. UI-Routen werden nur statisch ausgeliefert, nicht gerendert.
- Der erste Paketversuch behielt nach dem UI-Aufruf einen gültigen synthetischen Browsercookie und erwartete fälschlich 401. Das Testskript leert jetzt Header **und** Cookies vor der anonymen Prüfung. Der endgültige Paketfluss besteht; kein Produkt-Authfehler verschwiegen oder daraus behauptet.

## Pakete und Reproduktion

Dauerhafte lokale Ablage:

`/Users/sorenkube/Documents/Codex/Kingfisher-Pruefpakete/2026-10-09-cos-preview-173cef8/`

Sie enthält App, DMG, Quellarchiv, Versions-/Inhaltsmanifeste und das endgültige Paketprüfskript. Das vorige Paket bleibt erhalten. Backend-ID: `sha256:21678699de7673650fc8be2ea40ea99268aab29680b7661f241dd593a4cd4a8d`. Verwendete vorhandene Basis-ID: `sha256:a8d2d89e6c47c5050b779dbc0e595cb187efd9650142416cdb557dfdf8b6cfe9`; keine Abhängigkeitsänderung und kein Pull. Der vollständige alte Python-/UI-Ordner wird vor Übernahme entfernt, um veraltete Restdateien auszuschließen.

`freeze.json` pinnt das Git-Archiv, `package-inputs.json` die eingebauten Inhalte, `package-verification.json` Version/Signatur/DMG/Image. `verification.json` trennt frische Tests von historischem Nachweis und hält Rohlog-Prüfsummen fest. Der Bauweg und das no-network-Probeschema stehen im vorherigen Paketbericht; neuer Versionswert ist `1.0.6-preview.173cef8`. `package-Dockerfile` und `package_probe.py` sind die tatsächlich verwendeten Paketinputs. Vor Wiederholung immer die Basis-ID verifizieren.

## Unveränderte produktive App und offene Abnahmen

Die installierte App ist per Info.plist und nativer Prüfsumme erneut bestätigt: `1.0.6-local.3403623`, unverändertes natives Programm. Kein laufender Dienst wurde ersetzt, keine persönlichen Inhalte gelesen, kein produktives Volume eingebunden, kein Import fortgesetzt und keine Cloud-/Modellinferenz ausgeführt. Die aktuelle Kalenderfreigabe oder Kalenderinhalte wurden nicht erneut gelesen.

Der echte Fenstertest bleibt auf ausdrücklichen Nutzerwunsch verschoben. Das betrifft die drei persönlichen Kalender, tatsächliche Darstellung, Rückkehrpositionen und den kompletten Alltag mit Mail/Aufgaben/Terminen. Das Paket ist nicht als produktive App zu öffnen oder zu installieren, bevor der ruhige Sicherungs-/Datenprüfungsschritt und die native Abnahme stattfinden. Persönliche Gedächtnisqualität, Vollständigkeit, Ressourcen-/Akkuverhalten und Qualität der kleineren Modellvorauswahl sind weiterhin unbewiesen. Allgemeines Atlas-Inventar und vollständiger Voice-Dialog bleiben eigene offene Ausbaustufen. Der volle Produktauftrag bleibt erhalten.

Bestehende Warnungen: Starlette/httpx, Vite-Bündelgröße; zusätzlich macOS-Werkzeughinweis zur künftigen hdiutil-create-Ablösung. Keine CI-Wiederholung, kein Agenten-Check-in und kein Abonnement angelegt.
