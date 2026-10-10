# Gemeinsames lokales Testpaket für Kalender, RAM und eigene Gesundheitswerte

## Ergebnis und Liefergrenze

Die offenen Drafts #37 (Kalender), #38 (RAM-Reserve) und #40 (Gesundheit) sind in der **separaten Integrationsbranch** `integration/cos-preview-20261009` zusammengeführt und als gepaartes lokales Paket `1.0.6-preview.5f58289` geprüft. Code: `5f5828932c721d06d18137574d092de2f8a40212`. Das ist keine GitHub-PR-Zusammenführung, kein öffentlicher Release und keine Installation.

Die produktive App bleibt `1.0.6-local.3403623`; ihr natives Programm stimmt weiterhin mit der vorher gepinnten Prüfsumme überein. Der laufende Dienst meldet dieselbe ältere Version und ist gesund. Es wurden weder produktive Daten eingebunden noch Mail-/Kalendertexte oder Datenbanken gelesen. Der persönliche Import wurde nicht fortgesetzt. Kein Modell, keine Cloudanfrage und kein Abhängigkeitsdownload waren nötig.

Der Nutzer hat den Fenstertest ausdrücklich auf später verschoben. Deshalb fehlen weiterhin der echte Kalenderdialog, die drei persönlichen Kalender, die gerenderte Darstellung, der vollständige native Bedienweg und die praktische RAM-/Akku-/Modellqualitätsmessung. Ein technisch bestandenes Paket bestätigt diese Abnahmen nicht.

## Eingangsstände

| Draft | Gepinnter Head |
|---|---|
| [#37](https://github.com/Icarus-health/kingfisher-app/pull/37) | `b7a96231e51bccad6529bc53bc38634e7ef31419` |
| [#38](https://github.com/Icarus-health/kingfisher-app/pull/38) | `012800a4fdc339c862d9a94ab3fdb3cf86e2861b` |
| [#40](https://github.com/Icarus-health/kingfisher-app/pull/40) | `63664cde52591d030b1de8d85d61c13edda70b01` |

Die beiden lokalen Integrationsmerges waren konfliktfrei. `server.py` und `api.ts` wurden automatisch zusammengeführt und anschließend eng begrenzt unabhängig gelesen: Setup-Umgebungspriorität vor jeder Mutation, gemeinsame Authentifizierung der Gesundheitsrouten, unverändertes technisches `/health`, UI `/wellbeing` sowie getrennte Kalender-/Gesundheitsquellenschlüssel. Kein konkreter Integrationsblocker wurde gemeldet; der Reviewer führte keine Tests oder Laufzeitzugriffe aus.

## Frische Prüfungen am sauberen Git-Archiv

- 557 betroffene Backendfälle: zunächst **554 bestanden, 1 übersprungen, 2 fehlgeschlagen**. Beide Fehler waren Sandbox-Zugriffe: `test_host_report_measures_the_ollama_model_folder_and_sends_only_a_number` auf die RAM-Auskunft und `test_post_stays_on_loopback_and_does_not_follow_redirect` auf seinen künstlichen lokalen Server. Nur diese zwei Fälle erneut mit den benötigten Systemrechten geprüft: **2 bestanden**. Keine verbleibende Regression in dieser Auswahl; kein vollständiger Backendlauf behauptet. Linux-Fadenpriorität wurde auf macOS übersprungen.
- Vollständige UI-Suite: **451 bestanden**. TypeScript und Vite bestanden; bestehende Warnung über den Haupt-JavaScript-Block größer als 500 kB bleibt sichtbar.
- Native synthetische Tests: zuerst **27 bestanden, 1 übersprungen, 2 Umgebungsfehler** (Compiler-/SDK-Cachezugriff und Loopback-Server). Autorisierter vollständiger Lauf: **29 bestanden, 1 übersprungen**. Der übersprungene Fall prüft den Bauabbruch außerhalb von macOS. Kein EventKit-/Kalenderzugriff und kein Fenster wurden ausgeführt.
- Paketprüfung im kurzlebigen Container: **bestanden**, mit `--network none`, schreibgeschütztem System, eigenen leeren tmpfs-Daten, ohne Ports oder Datenmounts. Sie prüft die tatsächlichen installierten 268 Python-Dateien und 112 UI-Dateien gegen SHA-256-Manifeste, Authentifizierung, Messwertaufnahme/Retry/Korrektur/veralteten Schreibversuch/Verlauf, erneutes Öffnen des gespeicherten Bestands, Entzug, künstliche Kalenderauswahl/Trennung, beide Setup-Aliase mit RAM-Ablehnung sowie statisches `/wellbeing` und technisches `/health`.

Die erste temporäre Dateimount-Variante funktionierte mit Docker Desktop nicht: das Skript erschien als Verzeichnis und konnte nicht starten. Derselbe Test wurde anschließend direkt über Standardeingabe ausgeführt; er enthält dadurch überhaupt keine Host-Datenmounts. Beide Versuche bleiben im Protokoll. HTTP-TestClient ist keine Browserdarstellungsprüfung.

## Pakete und Herkunft

Native App: **ARM64**, ad hoc signiert; `codesign --verify --strict --deep` bestanden, DMG-Prüfsumme mit `hdiutil verify` bestätigt. Nicht notarisiert; Intel/universal ist hier nicht geprüft. App, Backend-Umgebungsfassung und Backend-Versionsdatei tragen exakt `1.0.6-preview.5f58289`.

Backend-ID: `sha256:141071a098dd10c903bf32e4e120581a6f4df5f6a314aa9a41970453cb570430`.

Basis-ID: `sha256:a8d2d89e6c47c5050b779dbc0e595cb187efd9650142416cdb557dfdf8b6cfe9`. Das bereits vorhandene lokale Basisabbild wurde genutzt, ohne Pull. Der vollständige Basisschichten-Präfix wurde danach verglichen. `sidecar/pyproject.toml` ist gegenüber dem Basiscode unverändert. Der komplette alte Python-Paketordner und UI-Ordner wurden im neuen Abbild entfernt und vollständig aus dem Git-Archiv ersetzt; die Dateimanifeste schließen alte Restdateien aus. Das bestehende Basisabbild und der laufende Container wurden nicht ersetzt.

Das dauerhaft abgelegte lokale Paket liegt unter:

`/Users/sorenkube/Documents/Codex/Kingfisher-Pruefpakete/2026-10-09-cos-preview-5f58289/`

Dort liegen App, DMG, Quellarchiv, Manifeste und Prüfskript. Auch die kopierte App wurde nochmals streng signaturgeprüft und byteweise mit ihrem Manifest verglichen. Das Backend liegt nur im lokalen Docker-Speicher; kein großes Imageexport-Duplikat wurde erzeugt. Das Paket **noch nicht als produktive App öffnen oder installieren**: Die spätere Lieferung benötigt den erneuten ruhigen Sicherungs-/Datenprüfungsschritt und die noch offene native Abnahme. Diese Runde prüft keine aktuelle produktive Datenbankkopie.

## Reproduktion ohne private Daten

Das Archiv mit `git archive 5f5828932c721d06d18137574d092de2f8a40212` neu erzeugen; `freeze.json` hält die tatsächlich geprüfte Archivprüfsumme fest. Die vorhandenen Node-Abhängigkeiten wurden lokal geteilt, nicht erneut geladen. In `app/kingfisher` liefen `npm test` und `npm run build`. Für Swift liefen `macos/test_mac_app.py` und `macos/test_native_calendar.py`; native Verpackung:

```sh
KINGFISHER_ARCHITEKTUR=arm64 KINGFISHER_FASSUNG=1.0.6-preview.5f58289 bash macos/build_dmg.sh
```

Der temporäre Compiler-Cache war explizit gesetzt. `package-Dockerfile` beschreibt den Paketbau; **vor** einem Wiederholungsbau die Basis-ID prüfen. In einem eigenen Kontext nur getrackte `sidecar/icarus_memory`-Dateien, die gesamte gebaute `app/dist`-UI und die Versionsdatei aufnehmen. `docker build --network none --pull=false` ausführen und den Basis-Präfix erneut prüfen. `package_probe.py` erwartet das beiliegende Manifest; in dieser Runde wurde dieses in das über Standardeingabe übergebene Skript eingebettet. Aufruf des temporären Containers:

```sh
docker run -i --rm --network none --read-only \
  --tmpfs /data:rw,uid=1000,gid=1000 --tmpfs /tmp:rw,uid=1000,gid=1000 \
  -e PYTHONDONTWRITEBYTECODE=1 --entrypoint python \
  ghcr.io/icarus-health/kingfisher-app:1.0.6-preview.5f58289 - < probe-stdin.py
```

`verification.json`, `package-inputs.json`, `package-verification.json` und die komprimierten Rohprotokolle trennen Erstfehler, Wiederprüfung, Paket- und Installationsstatus. Die [Gesamt-Abnahmematrix](../../64-cos-abnahme-status-2026-10-09.md) behält die noch offenen persönlichen Qualitäts- und Produktgrenzen bei.
