# Download und Updates

Stand: 2. Oktober 2026. Wie Kingfisher von einer Download-Seite auf einen Mac kommt, wie eine neue Fassung mit einem
Tag veröffentlicht wird und wie sie beim Menschen ankommt: als Angebot, das er mit einem Klick annimmt.

## Der Weg für den Nutzer

1. Download-Seite öffnen (`https://icarus-health.github.io/kingfisher-app/`), „Für Mac laden“.
2. Docker Desktop installieren und einmal öffnen; `Kingfisher.dmg` öffnen, App in „Programme“ ziehen, beim ersten
   Öffnen an Gatekeeper vorbei (macOS 15+: Systemeinstellungen → Datenschutz & Sicherheit → „Dennoch öffnen“;
   älter: Rechtsklick → Öffnen); Ollama installieren für Antworten in eigenen Worten.
3. Später: Auf Heute erscheint ein ruhiger Hinweis „Neue Fassung 1.2.0 ist da: …“ mit „Jetzt aktualisieren“. Die
   App prüft Speicher, sichert, lädt das neue Bild, prüft Speicher erneut, startet neu und lädt die Seite; danach steht einmal „Kingfisher ist jetzt auf
   Fassung 1.2.0.“ oder „Das Update hat nicht geklappt; deine Daten sind gesichert.“

Die Starter-Datei (`Kingfisher starten.command`) und `make start` bleiben der Weg für Entwickler, die aus dem
Quelltext bauen.

## Aufbau

| Teil | Wo | Was es tut |
|---|---|---|
| Fassungsnummer | `VERSION` | SemVer ohne „v“. Das Bild bekommt sie als Build-Arg und Umgebungsvariable `KINGFISHER_FASSUNG`; ein lokal gebautes Bild liest `/opt/kingfisher/VERSION`, eine Arbeitskopie die Datei selbst. |
| Neuerungen | `docs/fassungen/<fassung>.md` | Ein Satz je Spiegelstrich; der erste steht im Hinweis auf Heute. Optional eine Zeile `App mindestens: 1.1.0`. |
| Fertiges Bild | `ghcr.io/icarus-health/kingfisher-app:<fassung>` und `:latest` | arm64 und amd64, gebaut von `release.yml`. `container.yml` veröffentlicht für `main` nur `:main` und den Commit. |
| Compose | `compose.yaml`, `deploy/compose.app.yaml` | `image: ${KINGFISHER_IMAGE:-…}`; die zweite Datei ohne `build:` für die Mac-App. Projekt `kingfisher`, Volume `kingfisher-data`, Port `127.0.0.1:8890` bleiben, sonst startet eine Installation leer (`sidecar/tests/test_compose_vertrag.py`). |
| Manifest | `latest.json` auf der Download-Seite | `{fassung, datum, image, dmg, hinweise, app_mindestens}`; gebaut von `scripts/release_seite.py`. |
| Prüfung im Sidecar | `fassung.py`, `fassung_routes.py` | Einmal am Tag eine GET-Anfrage an `KINGFISHER_UPDATE_URL` (Vorgabe `https://icarus-health.github.io/kingfisher-app/latest.json`; leer = nie). |
| Oberfläche | `Fassung.tsx`, `fassungsAngebot.ts` | Hinweis auf Heute, Zeile unter „Kingfisher und du“, „Updates ohne App“ unter „Für Techniker“. |
| Update ohne App | `make aktualisieren`, `scripts/kingfisher_aktualisieren.py` | Sichern, Bild laden, `KINGFISHER_IMAGE` setzen, neu starten, bei Fehler zurück. |
| Veröffentlichen | `.github/workflows/release.yml` | Tag prüfen, Bild, Mac-App (`mac-app.yml`), Release mit DMG, Seite über Pages. |
| Download-Seite | `site/index.html` | Vorlage; der Workflow setzt Fassung, Datum, Neuerungen und Links ein. |

### Die Prüfung im Sidecar

* **Was hinausgeht:** genau eine GET-Anfrage je Tag an die Manifest-Adresse. Kein Keks (der Öffner hat keinen
  Keksspeicher), keine Kennung (User-Agent ist fest `Kingfisher`, ohne Fassung und ohne Rechnernamen), keine
  Anmeldung. Zeitgrenze 5 s, höchstens 64 KB. Nur HTTPS (unverschlüsselt nur an `127.0.0.1`, für Attrappen).
  Weiterleitungen nur auf HTTPS. GitHub sieht dabei, wie bei jedem Seitenaufruf, die IP-Adresse.
* **Fehler sind still.** Kein Netz, Zeitgrenze, kaputtes JSON: nichts ändert sich, nur `geprueft_um` bleibt alt.
  Nächster Versuch nach einer Stunde, nicht im Takt.
* **Strenge Prüfung.** Jede Angabe mit dem richtigen Typ, Fassungen als `X.Y.Z`, Datum als ISO-Tag, `dmg` als
  HTTPS-Adresse, ein bis zwanzig Hinweise. `image` muss `ghcr.io/icarus-health/kingfisher-app:<fassung>` sein.
  Sonst wird das Manifest verworfen, auch wenn es aus der richtigen Quelle kommt.
* **Im Zeitplan.** Die Prüfung hängt als leichte Aufgabe (`Scheduler.nebenbei_setzen`) im Faden des Zeitplans. Der
  Faden läuft auch, wenn der Zeitplan selbst aus ist, solange die Prüfung an ist; `running` im Zeitplan meldet weiter
  nur den Plan. Erste Prüfung frühestens eine Minute nach dem Start.
* **Zustand** in `fassung.json` im Datenordner: Schalter, letzte Prüfung, letztes gültiges Manifest.

**Schnittstelle** (mit Token wie alle anderen):

* `GET /api/v1/fassung` → `{fassung, neueste, update_verfuegbar, app_update_noetig, geprueft_um, pruefen,
  download_seite}`. Fragt nie nach außen.
* `POST /api/v1/fassung/pruefen` sieht sofort nach (auch bei ausgeschalteter täglicher Prüfung, weil ein Mensch
  geklickt hat); zusätzlich `erreicht`.
* `PUT /api/v1/fassung {"pruefen": bool}` schaltet die tägliche Prüfung.

`app_update_noetig` ist wahr, wenn ein Update da ist und `app_mindestens` neuer ist als die laufende Fassung. Die App
meldet ihre eigene Fassung nicht; sicher ist nur: Sie ist nie neuer als die Fassung, mit der sie kam. Eine App, die
älter ist als die laufende Fassung, erkennt diese Regel nicht (offen, siehe unten).

### Die Brücke zur Mac-App

Im Fenster der App gibt es `window.webkit.messageHandlers.kingfisher`. „Jetzt aktualisieren“ schickt
`{aktion: "aktualisieren", fassung: "1.2.0", image: "ghcr.io/icarus-health/kingfisher-app:1.2.0"}` und merkt sich im
`localStorage` (`kingfisher.update`, in try/catch) Ziel- und Ausgangsfassung. Nach dem Neuladen vergleicht die Seite
mit der laufenden Fassung, sagt es einmal und löscht den Merker. Ohne Brücke (Browser) steht statt des Knopfs „Öffne
Kingfisher über die App, um zu aktualisieren.“; braucht die Fassung eine neue App, ein Satz mit dem Weg zur
Download-Seite.

Die [Speicherregeln der Mac-App](../macos/README.md#speicherprüfung-vor-updates) gelten ebenso für den Entwickler-Starter. Es wird nichts automatisch aufgeräumt.

### Update ohne App: `make aktualisieren`

1. Ziel: `FASSUNG=1.2.0` oder die Antwort von `POST /api/v1/fassung/pruefen` des laufenden Kingfisher.
2. Speicher im laufenden Container prüfen; bei unklarer oder zu geringer Reserve vor Sicherung und Bildmarkierung abbrechen. Danach Sicherung im Container wie `make backup`, aber mit dem Präfix `vor-update-` (3 werden aufbewahrt), damit
   `make zurueck-vor-update` sie findet. Scheitert sie, ändert sich nichts.
3. `docker pull` des Bildes und erneute Speicherprüfung. Scheitert eines, bleiben Bildwahl und laufender Dienst unverändert; Sicherung und Download können bereits vorliegen.
4. `KINGFISHER_IMAGE=<bild>` in `.kingfisher.env`, dann `make start` (mit dem freigegebenen Notizordner wie bisher;
   mit fertigem Bild ohne `--build`).
5. Antwortet danach nicht die neue Fassung, wird zuerst der Dienst gestoppt. Mit dem neuen Bild wird die
   Update-Sicherung offline zurückgespielt; erst danach startet das zuvor festgehaltene alte Bild ohne Neubau.
   Seine unveränderliche Bildkennung und der authentifizierte Prüfmodus müssen bestätigt sein. Die Sicherung
   bleibt erhalten. Scheitert Stoppen oder Wiederherstellen, wird alter Code nicht auf neueren Daten gestartet.
   Nach erfolgreichem Rückweg bleiben historische Daten im Prüfmodus, bis der Bestand geprüft wurde.

Wer danach wieder aus dem Quelltext bauen will, löscht die Zeile `KINGFISHER_IMAGE` aus `.kingfisher.env`. `make
start` und der Doppelklick-Starter sagen das, solange ein fertiges Bild eingetragen ist.

## Eine Fassung veröffentlichen

1. `VERSION` erhöhen (etwa `1.2.0`).
2. `docs/fassungen/1.2.0.md` schreiben: ein Satz je Spiegelstrich, Alltagssprache, der wichtigste zuerst. Braucht
   die Fassung eine neuere App, die Zeile `App mindestens: 1.2.0`.
3. Beides auf `main` bringen, dann den Tag setzen und schieben: `git tag v1.2.0 && git push origin v1.2.0`. Ohne
   Terminal: Actions → „Release“ → „Run workflow“ auf `main` mit dem Tag `v1.2.0`; fehlt der Tag, legt der Lauf ihn
   nach der Prüfung von `VERSION` selbst an.

`release.yml` prüft Tag gegen `VERSION` und die Notiz, baut das Bild (beide Architekturen, `:1.2.0` und `:latest`),
ruft `mac-app.yml` mit `fassung` auf und erwartet das Artefakt `Kingfisher.dmg`, legt den Release `v1.2.0` mit der
Datei an (Text aus der Notiz) und veröffentlicht zuletzt Seite und `latest.json`. Erst dann sieht ein laufender
Kingfisher das Angebot. Ein abgebrochener Lauf lässt sich von Hand neu starten (Actions → Release → Run workflow,
Tag eingeben); ein bestehender Release bekommt die DMG dann ersetzt.

Die Seite geht über GitHub Pages mit Actions (`configure-pages`, `upload-pages-artifact`, `deploy-pages`), nicht über
einen Branch `gh-pages`: kein zweiter Branch, kein Token, nichts, was von Hand auseinanderlaufen kann. Ein eigenes
Download-Repository ist nicht nötig, solange das Haupt-Repository öffentlich ist.

## Was der Eigentümer einmal einrichtet

1. **Öffentliches Repository** `Icarus-health/kingfisher-app` (seit Oktober 2026 der öffentliche Ort von Kingfisher;
   die frühere, private Entwicklungsgeschichte bleibt in einem eigenen privaten Repository). Ohne öffentliches
   Repository sind Release, DMG und Seite für Fremde nicht erreichbar.
2. **Pages:** Settings → Pages → Build and deployment → Source „GitHub Actions“.
3. **Umgebung `github-pages`:** Settings → Environments → `github-pages` → Deployment branches and tags: eine Regel
   für Tags `v*` ergänzen. Sonst lehnt GitHub die Veröffentlichung aus einem Tag ab (Vorgabe: nur der Standardbranch).
4. **Paket öffentlich:** Nach dem ersten Release unter Packages → `kingfisher-app` → Package settings → Change visibility
   → Public, und unter „Manage Actions access“ dieses Repository mit Schreibrecht. Sonst kann die App das Bild nicht
   ohne Anmeldung laden.
5. **Mac-Workflow:** `mac-app.yml` muss als wiederverwendbarer Workflow (`workflow_call`, Eingabe `fassung`) das
   Artefakt `Kingfisher.dmg` hochladen; Geheimnisse dafür reicht `release.yml` mit `secrets: inherit` durch.

**Datenschutz:** Das Bild enthält den Programmcode. Mit einem öffentlichen Bild ist er für jeden lesbar, wie bei
einem öffentlichen Repository ohnehin. Persönliche Daten stecken nie im Bild; sie liegen im Volume auf dem Rechner.

## Was nur auf dem Mac prüfbar ist

* Die App selbst: Brücke, Sichern, Ziehen des Bildes, Neustart und Neuladen (anderer Arbeitsbereich: `macos/`).
* Gatekeeper beim ersten Öffnen der DMG und der App (macOS 15 und älter).
* Docker Desktop auf Apple-Chip mit dem arm64-Bild; `docker compose -p kingfisher -f deploy/compose.app.yaml` mit
  einer bestehenden Installation (dieselben Daten).
* Ein echter Lauf von `release.yml` (Pages, GHCR, Release); hier nur mit `actionlint` und Tests geprüft.

Geprüft in diesem Container: Sidecar-Tests (`test_fassung.py` mit HTTP-Attrappe, `test_compose_vertrag.py` auch mit
`docker compose config`, `test_kingfisher_aktualisieren.py`, `test_release_seite.py`), UI-Tests (`fassung.test.mjs`),
Browserproben `scripts/probe_fassung_ui.py` und `scripts/probe_download_seite.py`.

## Offen

* `app_update_noetig` erkennt eine zu alte App nur, wenn sie älter ist als jede bisher gelaufene Fassung. Genauer
  ginge es, wenn die App ihre Fassung meldet (etwa in der Brücke); das ist mit der Mac-App abzustimmen.
* Vorabfassungen (`1.2.0-rc1`) gibt es nicht; die Prüfung nimmt nur `X.Y.Z`.
