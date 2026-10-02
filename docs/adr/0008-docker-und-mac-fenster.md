# ADR 0008: Docker und natives Mac-Fenster statt Tauri

**Status:** akzeptiert · **Datum:** 2026-09-29 · **Löst ab:** [ADR 0006](0006-tauri-desktop.md) · **Schärft:** [ADR 0007](0007-docker-als-zweiter-weg.md)

## Kontext

[ADR 0006](0006-tauri-desktop.md) wählte eine eigene Tauri-App mit gebündeltem Python-Sidecar, [ADR 0007](0007-docker-als-zweiter-weg.md) ergänzte Docker als zweiten Weg für alle, die keine signierte App bekommen können. In der Praxis ist die Reihenfolge umgekehrt gelaufen: Der Sidecar wird als Container betrieben (`make start`), die Oberfläche ist die React-Anwendung unter `app/kingfisher/`, und auf dem Mac öffnet ein kleines natives Fenster (`macos/`, `scripts/build_mac_window.py`) die lokale Adresse. Die Tauri-Hülle und die ältere Oberfläche `app/src/` wurden dabei nicht mehr benutzt, aber weiter mitgeführt: ein Rust-Zweig in der CI, ein PyInstaller-Bündel von rund einem Gigabyte, ein macOS-Workflow für ein signiertes Bündel, das es nie gab, und ein stiller Rückgriff des Sidecars auf die Altoberfläche.

Zwei Wege und zwei Oberflächen kosten Pflege und erzeugen Fehler, die niemand bemerkt, weil niemand sie benutzt.

## Entscheidung

- **Auslieferung ist Docker.** Ein Image mit Sidecar und gebauter React-Oberfläche (`ICARUS_UI_DIR=/opt/kingfisher/ui`), Port ausschließlich an `127.0.0.1`.
- **Die Hülle auf dem Mac ist ein natives Fenster** (Swift/WebKit, `macos/KingfisherApp.swift`), das die lokale Adresse öffnet und die vorhandene Docker-Umgebung bei Bedarf startet. Es enthält keine Fachlogik und keinen Sidecar.
- **Entfernt:** `app/src-tauri/`, `app/package.json` (enthielt nur die Tauri-CLI), `packaging/` (PyInstaller), `.github/workflows/build-macos.yml`, die Make-Ziele `app-dev`, `app-build`, `sidecar-binary`, `icon`, der Rust-Job der CI und die ältere Oberfläche `app/src/`.
- **Ohne `ICARUS_UI_DIR`** liefert der Sidecar in einer Arbeitskopie die gebaute React-Oberfläche aus `app/dist`; gibt es sie nicht, ist er nur die API.

## Begründung

Der Grundsatz „immer die für den Nutzer einfachste Lösung“ spricht für den Weg, der ohne Apple-Entwicklerkonto, Signierung und Notarisierung auskommt. Docker gibt dem Sidecar eine feste, reproduzierbare Laufzeit (kein PyInstaller mit nativen Erweiterungen von lancedb und pylance), und das Fenster erspart dem Nutzer, eine Adresse im Browser zu kennen. Eine einzige Oberfläche bedeutet: Was getestet und im Browser geprüft wurde, ist auch das, was ausgeliefert wird.

## Folgen

- Kein signiertes und notarisiertes Bündel. Das Mac-Fenster ist ad hoc signiert und für die Weitergabe nicht notarisiert (siehe README).
- Docker wird auf dem Mac vorausgesetzt. Die Ersteinrichtung und der erste Start laufen per Terminal (`make start`); ein bereits eingerichtetes Fenster startet die vorhandene Docker-Laufzeit bei Bedarf selbst.
- Computer-Use und der Schlüsselbund des Betriebssystems bleiben im Container ausgeschlossen (siehe ADR 0007); Geheimnisse liegen verschlüsselt im Datenvolumen.
- Kein nativer Ordnerdialog aus dem Container heraus; Ordner werden über Bind-Mounts und Auswahllisten freigegeben.
- Die Entscheidung gegen Tauri ist umkehrbar, aber nicht kostenlos: Ein späteres Bündel müsste Sidecar, Signierung und CI neu aufbauen.
- ADR 0006 bleibt als Begründung dafür erhalten, dass keine fremde Oberfläche (Open WebUI) den Freigabe-Layer tragen darf. Dieser Teil gilt unverändert.

## Offene Punkte

- Ersteinrichtung ohne Terminal: gelöst durch die ladbare App (siehe Nachtrag) mit Download-Seite, fertigem Bild aus GHCR und Updates mit einem Klick ([Download und Updates](../53-download-und-updates.md)).
- Signiertes, notarisiertes Mac-Fenster, sobald ein Apple-Developer-Konto vorliegt.
- Windows und Linux: kein Fenster; Browser auf `http://127.0.0.1:8890` genügt.

## Nachtrag: Download als DMG

**Datum:** 2026-10-02

Der erste Start braucht kein Terminal mehr: `Kingfisher.dmg` mit `Kingfisher.app` (`macos/App`, gebaut von
`macos/build_dmg.sh`, in CI `.github/workflows/mac-app.yml`). Auf dem Mac sind weder Git noch Python noch
Entwicklerwerkzeuge nötig, nur Docker Desktop, das die App selbst findet, startet oder zum Laden anbietet.

- Die App startet das **fertige Bild** `ghcr.io/icarus-health/kingfisher-app:<fassung>` über
  `deploy/compose.app.yaml` (im Bündel als `compose.yaml`), mit demselben Projektnamen `kingfisher` und
  Volume wie `make start`. Eine Installation aus der Arbeitskopie wird übernommen: Token und Passphrase kommen
  aus deren `.kingfisher.env`, deren Ort Docker Compose selbst am Container vermerkt. Gibt es Daten, aber
  keinen Schlüssel, erzeugt die App keinen neuen, sondern bittet um die Datei.
- **Updates** nur nach einer Nachricht der Oberfläche über die Brücke `kingfisher` (Aktion `aktualisieren`),
  also nach einem Klick: erst Sicherung, dann Bild laden, umstellen, starten, warten. Scheitert etwas nach der
  Sicherung, läuft die alte Fassung weiter.
- Weiterhin **ad hoc signiert, nicht notarisiert**: einmal „Dennoch öffnen“. Die Bundle-ID bleibt
  `local.kingfisher.window`, damit Sitzung und Ansicht des bisherigen Fensters erhalten bleiben.
- Das Fenster für die Arbeitskopie (`macos/KingfisherApp.swift`) bleibt; beide teilen `macos/Shared/`.

Grenzen: Die Mac-Helfer aus `scripts/start_mac_app.py` (Kalender, Karten, Audio, Ordner, Autostart) brauchen
Python und laufen mit der geladenen App noch nicht. Ein über `make start NOTIZEN=…` eingebundener Notizordner
wird von der App nicht eingebunden. Prüfliste für den Mac: [`macos/README.md`](../../macos/README.md).
