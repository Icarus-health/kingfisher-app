# Mac-App zum Herunterladen (Kingfisher.dmg)

`Kingfisher.app` ist das Fenster für alle, die kein Terminal öffnen wollen: von der Download-Seite
(`https://icarus-health.github.io/kingfisher-app/`) laden, in „Programme“ ziehen, öffnen. Die App richtet beim
ersten Start alles ein und bietet später Updates an. Sie enthält keine Fachlogik und keinen Sidecar; sie
startet das fertige Bild `ghcr.io/icarus-health/kingfisher-app:<fassung>` mit Docker. Entscheidung und
Grenzen: [ADR 0008, Nachtrag](../docs/adr/0008-docker-und-mac-fenster.md#nachtrag-download-als-dmg).

Ad hoc signiert, nicht notarisiert: Beim ersten Öffnen meldet macOS, die App sei nicht überprüft. Einmal
Systemeinstellungen → Datenschutz & Sicherheit → „Dennoch öffnen“, danach startet sie normal.

## Was die App tut

Beim Öffnen, Schritt für Schritt (`App/Startup.swift`), jeweils mit einem Satz im Fenster:

1. **Docker finden** an denselben Orten wie `scripts/kingfisher_starten.py`. Fehlt es: „Docker Desktop
   laden“ (öffnet die Downloadseite) und „Nochmal prüfen“.
2. **Docker starten**, wenn es nicht läuft (`open -a Docker`, bei Colima `colima start`), bis zu zwei
   Minuten warten.
3. **Schlüssel bereitstellen** in `~/Library/Application Support/Kingfisher/kingfisher.env` (Ordner 0700,
   Datei 0600), mit denselben Namen wie `.kingfisher.env` (`ICARUS_SIDECAR_TOKEN`,
   `ICARUS_SECRETS_PASSPHRASE`), dazu `KINGFISHER_IMAGE`. Reihenfolge:
   - die eigene Datei, wenn es sie gibt;
   - sonst die einer Installation aus der Arbeitskopie (`make start`, `Kingfisher starten.command`): Die
     App fragt Docker nach dem Container des Projekts `kingfisher` und liest aus dessen Compose-Labels, wo die
     Env-Datei liegt (`com.docker.compose.project.environment_file`, sonst
     `…working_dir/.kingfisher.env`). Die Datei wird vollständig übernommen. Liegt sie dort nicht mehr,
     kommen Token und Passphrase aus der Umgebung des Containers selbst;
   - gibt es keinen Container, aber das Volume `kingfisher_kingfisher-data`, erzeugt die App **nichts**
     neu (sonst wäre die Schlüsseldatei im Volume nicht mehr lesbar), sondern bittet mit einem Klick um die
     Datei `.kingfisher.env` („Datei auswählen“);
   - sonst neu mit `SecRandomCopyBytes` (32 Byte, hex, wie `secrets.token_hex(32)`).
4. **Laden und starten** beim ersten Mal: Bild aus dem Manifest
   `https://icarus-health.github.io/kingfisher-app/latest.json` (nur, wenn es mit
   `ghcr.io/icarus-health/kingfisher-app:` beginnt, sein Tag die Fassung ist und `app_mindestens` erfüllt ist;
   sonst das Bild mit der Fassung der App), `docker compose -p kingfisher -f <Resources/compose.yaml>
   --env-file <Env-Datei> pull`, Bild in die Env-Datei, `up -d`. Später nur `up -d`, wenn `/health` nicht
   ohnehin antwortet. Eine vorhandene Installation aus einer Arbeitskopie wird nicht automatisch umgestellt:
   zusätzliche Ordnerfreigaben und ein Bestand ohne passende Bildkonfiguration brauchen einen gesonderten Umzug.
5. **Prüfen**: Das laufende Bild muss zur Konfiguration passen; `/api/v1/fassung` muss mit dem eigenen Token
   die passende Fassung bestätigen. Nach einer Wiederherstellung ist stattdessen der authentifizierte Prüfmodus
   zulässig. Erst danach die Seite `/today` laden.
6. **Ollama** fehlt (weder erreichbar noch in Programme): ein Satz mit Link unter der Seite, kein Hindernis.

Ein Protokoll der Docker-Aufrufe (ohne Geheimnisse) liegt in `~/Library/Logs/Kingfisher/kingfisher.log`.

### Update über die Brücke

Die App hört unter `window.webkit.messageHandlers.kingfisher` nur auf Nachrichten aus dem Hauptrahmen von
`http://127.0.0.1:8890` und nur auf `{aktion: "aktualisieren", fassung, image}` mit gültigem Bild. Nichts
davon geschieht ohne diese Nachricht, also ohne Klick in der Oberfläche. Ablauf (`App/Updater.swift`,
Zustandsfolge in `App/Logic/UpdateFlow.swift`), währenddessen „Kingfisher wird aktualisiert …“ mit Schritt:

Vorher: laufende Fassung, Bildkennung und Ordnerfreigaben prüfen und das bisherige Bild lokal festhalten.
Eine Installation mit zusätzlichen Freigaben wird durch diesen App-Weg nicht aktualisiert.

1. Sicherung: `POST /backups?vor_update=true` mit Kopf `x-icarus-token` (Antwort 201 und gültiger
   Sicherungsname `vor-update-YYYYMMDDTHHMMSSZ`). Scheitert sie, wird nichts verändert.
2. `compose pull` mit `KINGFISHER_IMAGE=<image>`.
3. `KINGFISHER_IMAGE` dauerhaft in die Env-Datei.
4. `up -d`.
5. Authentifizierte neue Fassung und tatsächlich laufendes Bild prüfen, dann die Seite neu laden.

Scheitert das Laden oder Schreiben der Konfiguration, bleibt der laufende Dienst unverändert. Scheitert der
Neustart oder die Prüfung danach: Dienst stoppen, mit dem **neuen** Bild über `icarus_memory.update_restore`
den gesicherten Datenstand offline wiederherstellen, dann das festgehaltene alte Bild starten. Erfolg wird erst
nach Prüfung seiner unveränderlichen Bildkennung und des authentifizierten Prüfmodus gemeldet. Der Prüfmodus
bleibt aktiv; historische Daten werden nicht automatisch zu aktuellem Arbeitswissen. Scheitert die
Wiederherstellung, bleibt der Dienst angehalten, Sicherung und neueres Bild bleiben erhalten.

## Aufbau

| Datei | Inhalt |
|---|---|
| `Shared/Navigation.swift` | Regeln für Navigation und Downloads (rein, auch vom Fenster des Bestands genutzt) |
| `Shared/WebSurface.swift` | WKWebView mit Dateiauswahl, Hinweisen und Downloads (Bestand und App) |
| `KingfisherApp.swift` | Fenster für eine Installation aus der Arbeitskopie (`scripts/build_mac_window.py`) |
| `App/Logic/*.swift` | reine Logik, nur Foundation: Env-Datei, Fassungen und Bildnamen, Manifest, Brückennachricht, Zustandsfolge des Updates, Erkennen einer vorhandenen Installation, alle Sätze |
| `App/*.swift` | Fenster und Ansicht, Docker, Start, Update, HTTP an 127.0.0.1 |
| `App/Info.plist` | Vorlage; Fassung kommt beim Bauen aus `VERSION` |
| `tests/main.swift` | Prüfprogramm der reinen Logik |
| `test_mac_app.py` | statische Prüfungen ohne Mac |
| `build_dmg.sh` | baut `dist/Kingfisher.dmg` |

## Bauen

Auf einem Mac mit den Xcode Command Line Tools (`xcode-select --install`); `deploy/compose.app.yaml` und
`VERSION` müssen im Repo liegen (fehlt `VERSION`, gilt `0.0.0`):

```sh
bash macos/build_dmg.sh                       # Fassung aus VERSION
KINGFISHER_FASSUNG=1.0.1 bash macos/build_dmg.sh
```

Das Skript übersetzt für arm64 und x86_64, fügt beides mit `lipo` zusammen, schreibt die Info.plist
(Bundle-ID `local.kingfisher.window`, macOS ab 11.3 wie das Fenster des Bestands), legt
`deploy/compose.app.yaml` als `Contents/Resources/compose.yaml` ins Bündel, baut das Icon aus
`design-source/01_Brand/Approved/App_Icon_Exports/`, signiert ad hoc und erzeugt das DMG mit einer
Verknüpfung „Programme“. In CI: `.github/workflows/mac-app.yml` (aus dem Release mit `fassung`, bei Pull
Requests auf `macos/**` nur bauen).

Prüfen ohne Mac und mit Mac:

```sh
.venv/bin/python -m pytest macos/test_mac_app.py -q      # überall; mit swiftc auch die Logik
swiftc macos/App/Logic/*.swift macos/Shared/PowerReporter.swift macos/tests/main.swift -o /tmp/kingfisher-logic && /tmp/kingfisher-logic
```

## Auf dem Mac prüfen

Nur auf einem echten Mac prüfbar; vor einer Veröffentlichung jede Zeile einmal durchgehen, mit
synthetischen Daten. Zum Zurücksetzen: App beenden, `~/Library/Application Support/Kingfisher` löschen
und, nur auf einem Testrechner, `docker compose -p kingfisher down -v`.

- [ ] **Frischer Mac ohne Docker:** DMG öffnen, App nach Programme ziehen, öffnen, Gatekeeper
      („Dennoch öffnen“). Satz und „Docker Desktop laden“ erscheinen; der Knopf öffnet die Downloadseite.
      Docker installieren und einmal öffnen, „Nochmal prüfen“: Laden mit Satz, danach die Einrichtung
      von Kingfisher. Env-Datei hat 0600, Ordner 0700. Ohne Ollama steht der Hinweis unter der Seite.
- [ ] **Docker installiert, aber aus:** App öffnen. Docker Desktop startet von selbst, der Satz dazu
      steht da, danach öffnet sich Kingfisher. Docker in der Zeit nicht anfassen.
- [ ] **Bestehende Starter-Installation mit Daten** (`make start` mit einem API-Schlüssel in den
      Einstellungen): App öffnen. Sie übernimmt `.kingfisher.env` (Vermerk in der ersten Zeile der neuen
      Datei), stellt auf das fertige Bild um, Gedächtnis und Schlüssel sind danach lesbar (Einstellungen →
      Zugänge zeigen den Schlüssel als hinterlegt). Gegenprobe: `.kingfisher.env` vorher verschieben, Container
      entfernen (`docker rm -f kingfisher-kingfisher-1`), App öffnen: Sie bittet um die Datei, „Datei
      auswählen“ mit der verschobenen Datei führt weiter, eine andere Datei wird mit einem Satz abgewiesen.
- [ ] **Update 1.0.0 → 1.0.1:** App mit Fassung 1.0.0 einrichten, Manifest und Bild 1.0.1 bereitstellen,
      in der Oberfläche auf „Aktualisieren“ klicken. Die native Ansicht zeigt die Schritte, danach lädt die
      Seite neu; `docker inspect` zeigt das neue Bild, eine neue Sicherung liegt unter `/data/sicherungen`.
      Ohne Klick passiert nichts (App eine Stunde offen lassen).
- [ ] **Update scheitert beim Ziehen:** wie oben, aber Netz trennen oder ein nicht vorhandenes Bild
      (etwa 9.9.9 per Konsole der Seite: `window.webkit.messageHandlers.kingfisher.postMessage({aktion:
      "aktualisieren", fassung: "9.9.9", image: "ghcr.io/icarus-health/kingfisher-app:9.9.9"})`). Satz „Das
      Update hat nicht geklappt. Deine Daten sind gesichert; Kingfisher läuft weiter mit Fassung 1.0.0.“,
      „Weiter“ lädt die alte Seite, `KINGFISHER_IMAGE` steht unverändert in der Env-Datei.
- [ ] **Fremde Nachrichten:** `postMessage({aktion: "loeschen"})` und ein Bild mit anderem Präfix
      bewirken nichts.
- [ ] Beenden während eines Updates wird mit einem Satz abgelehnt; Download einer Sicherung über die Seite
      landet am gewählten Ort.

# Lokaler Kalenderadapter

Mac-Anbindung mit ausgehender Verbindung zur lokalen Docker-Oberfläche.
Benötigt macOS 14 oder neuer und die Xcode Command Line Tools. Keine weiteren
Pakete, Server oder Konten erforderlich.

```sh
bash scripts/build_calendar_reader.sh
build/kingfisher-calendar status
build/kingfisher-calendar authorize
build/kingfisher-calendar calendars
```

Nur `authorize` fordert die macOS-Freigabe an. Zum Lesen benötigt EventKit
Vollzugriff; der Adapter implementiert ausschließlich Leseoperationen.
Eine Freigabe liest noch keine Termine. `calendars` liefert danach die Namen
und IDs zur ausdrücklichen Auswahl. Entzug über die macOS-Systemeinstellungen,
Datenschutz & Sicherheit, Kalender. Bei lokal signierten Entwicklungsprogrammen
kann macOS den aufrufenden Prozess als verantwortliche Anwendung anzeigen.

`events` erwartet JSON auf stdin mit einer nicht leeren `calendar_ids`-Liste
sowie `start` und `end` im ISO-8601-Format mit Zeitzone. Maximal 31 Tage und
10.000 Termine; fehlende Kalender führen zum Fehler statt zum Lesen aller
Kalender. UID enthält Kalender und Termin-ID; nur bei Serientermin und
abgetrennter Ausnahme kommt der Beginn der konkreten Instanz dazu, damit ein
verschobener Einzeltermin seine Kennung behält (das Gedächtnis legt dann eine
neue Fassung an statt eines zweiten Termins). Teilnehmer erscheinen als
„Name <Adresse>“. Notizen gibt der Adapter nur aus, wenn die Eingabe
`"with_notes": true` enthält (Gedächtnisabgleich, siehe unten); Zugangsdaten
nie. Die Ausgabe enthält persönliche Termine und gehört nicht in Git oder
Testprotokolle.

Prüfung ohne Kalenderzugriff:

```sh
python3 scripts/test_calendar_reader.py
```

Apple: https://developer.apple.com/documentation/eventkit/accessing-the-event-store

## Docker-Anbindung

Nach dem Bauen läuft `python3 scripts/mac_calendar_worker.py --env-file PFAD`
auf dem Mac. Die private Datei enthält den vorhandenen `ICARUS_SIDECAR_TOKEN`
der passenden Containerinstanz. Standardziel ist `http://127.0.0.1:8891`;
`--url` erlaubt eine andere explizite Loopback-Portnummer. Keine Weiterleitungen,
keine Proxy-Nutzung und kein eingehender Host-Port. Der Token wird nie geloggt.

Unter Einstellungen → Kalender auf diesem Mac verbinden und einzelne Kalender
wählen. Nur nach dieser Auswahl werden Termine gelesen. Aktualisierung jede
Minute; nach fünf Minuten ohne erfolgreiche Aktualisierung werden Termine
nicht mehr als aktuelle Daten geliefert. Trennen löscht die lokale Kopie;
eine Generationsnummer verhindert das Zurückschreiben einer laufenden Abfrage.
Die Betriebssystemberechtigung wird separat in macOS entzogen.

Die Kopie liegt ausschließlich in der privaten Container-Datenbank
`mac-calendar.sqlite3` (Dateimodus 0600, SQLite secure_delete). Sie wird nicht
als Gedächtniswissen importiert. Für das Gedächtnis legt der Sidecar jeden Termin
zusätzlich als Rohquelle ab (siehe unten); diese Episoden liegen in der
Episodendatenbank, nicht in `mac-calendar.sqlite3`. Sicherungskopien können
frühere Daten enthalten.
Ein täglicher Autostart ist noch nicht installiert; den lokalen Starter nach
einem Mac-Neustart erneut öffnen. Docker/Colima muss laufen.

Verifiziert: 778 Backendtests bestanden; drei im Sandboxlauf an lokalen
Socketrechten gescheiterte Tests im gezielten erneuten Lauf bestanden
(gesamtes Modelltestmodul: 10 bestanden). Browser: Auswahl → Synchronisation →
Termin im Tagesbriefing → Trennen → Termin entfernt, mit synthetischen Daten.
Echte persönliche Termine bleiben bis zur Kalenderauswahl ungeprüft.

### Jahresansichten

Für die angeforderte Jahresübersicht synchronisiert der Worker jetzt das
laufende Kalenderjahr mit zwei Tagen Randpuffer. Jede einzelne EventKit-Abfrage
bleibt auf 31 Tage begrenzt. Ergebnisse werden anhand der Instanz-UID dedupliziert,
maximal 10.000 Termine insgesamt. Die Jahres-API weist noch unvollständige
Abdeckung ausdrücklich aus. Andere Jahre werden nicht automatisch eingelesen.

### Termine im Gedächtnis

Zusätzlich zur Live-Anzeige liest der Worker das **Gedächtnisfenster** (Vorgabe:
drei Jahre zurück, ein Jahr voraus; die Zahlen stehen nur in
`sidecar/icarus_memory/calendar_memory.py`, der Worker fragt sie über
`memory_window` im Adapterzustand ab). Er liest es in Abschnitten zu 90 Tagen
(je Abschnitt Abfragen zu 31 Tagen, mit Notizen) und sendet jeden Abschnitt an
`POST /api/v1/mac-calendar/memory`. Der Sidecar gleicht ihn mit dem Gedächtnis
ab: geänderte Termine werden neue Fassungen, fehlende Termine des Abschnitts
entzogen, Unverändertes wird nicht angefasst. Das geschieht beim Verbinden und
danach höchstens alle 30 Minuten; ein Fehler dabei meldet die Live-Anzeige nicht
als defekt. Abwählen eines Kalenders oder Trennen entzieht die zugehörigen
Termine im Gedächtnis (die Episoden bleiben als ausgeschlossen erhalten).
Grenzen und Messwerte: `docs/28-termine-im-gedaechtnis.md`.
