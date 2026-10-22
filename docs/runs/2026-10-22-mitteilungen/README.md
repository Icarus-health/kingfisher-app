# Paket B3: Mitteilungen auf dem Mac (Etappe 5)

Stand 22.10.2026, Branch `feat/mac-mitteilungen-20261022` auf `main` 1.0.26, Fassung nicht angehoben. Nur synthetische
Daten (Attrappen für Kalender, Briefing, Fristen, Wegezeit; gestellte Uhr). Ziel aus
[`24-weg-zum-jarvis.md`](../../24-weg-zum-jarvis.md#5-von-sich-aus-melden): Kingfisher meldet sich von sich aus, wenige
Dinge, zu passenden Zeiten; „Fertig heißt“: keine Mitteilung, die der Nutzer im Nachhinein für überflüssig hält, eine
Woche lang gezählt. **Die Woche im Alltag und die Abnahme am Mac stehen aus** (unten).

## Was gebaut wurde

| Bereich | Dateien |
|---|---|
| Sidecar | `mitteilungen.py` (Regeln, Merkliste `mitteilungen.sqlite3` ohne Inhalt), `mitteilungen_routes.py` (`GET …/faellig`, `POST …/{id}/zugestellt`, `POST …/{id}/rueckmeldung`, `GET …/woche`, `GET/PUT …/einstellung`, `POST …/erlaubnis`), `config.Settings.mitteilungen` (Vorgaben `an=False`, `morgens="07:30"`), `logbuch.ARTEN` + `mitteilung`, `mitteilung_ueberfluessig`, `wegezeit.auskunft(nur_lesen=…)`, Registrierung in `server.py` |
| Mac-App | `macos/Shared/Mitteilungen.swift` (reine Logik, nur Foundation: Pfade, Grenzen, strenge Prüfung der Antwort), `macos/Shared/NotificationReporter.swift` (alle 5 Minuten, `UNUserNotificationCenter`, Kategorie `KINGFISHER_MITTEILUNG`, Aktionen „Öffnen“ und „War überflüssig“, Antwort ≤ 4 KB, keine Weiterleitungen, Erlaubnis erst mit Schalter), `AppDelegate.swift` (Start, `openPage`, Stopp), `WebSurface.open(pfad:)`, `build_dmg.sh` (`-framework UserNotifications`), `tests/main.swift` (Prüfungen der Logik) |
| Oberfläche | `Einstellungen/Mitteilungen.tsx` (Schalter, Uhrzeit, Wochen-Satz, Erlaubnis-Hinweis), `mitteilungenSchalter.ts` (reine Logik), `SCHALTER.mitteilungen` in `gliederung.ts`, `Darf.tsx`, `api.ts`, `CalmUI.css` |
| Doku | `docs/24-weg-zum-jarvis.md` (Stand Etappe 5), `docs/47-einstellungen.md` (Abschnitt), `docs/44-logbuch.md` (Arten), `docs/53-download-und-updates.md`, `docs/DEVELOPER-START.md` (Codekarte), `macos/README.md` (Abschnitt und Checkliste) |

Regeln, die gelten: Vorgabe aus; nichts verlässt den Rechner (die App spricht nur mit 127.0.0.1); je Abruf höchstens
drei Mitteilungen, je Art eine, Dringendes zuerst; nichts doppelt, auch nicht nach einem Neustart (Merkliste in der
Datei); Ruhezeit 21:00 bis Morgenzeit nur mit „Termin gleich“; Wegezeit nur aus dem Zwischenspeicher, nie eine Anfrage
an einen Kartendienst wegen einer Mitteilung; nichts Inhaltliches ins Protokoll (Fehler nur mit ihrer Art, Logbuch nur
mit `sorte`); jede Mitteilung mit „War überflüssig“.

Angepasst gegenüber dem Bauplan, dem Bestand zuliebe: Der Schaltertitel heißt „Mitteilungen auf dem {Rechner}“ und geht
durch `fuerSystem` (kein fester Mac-Satz in der Oberfläche, `tests/system.test.mjs`); ohne Mac-App ist der Schalter
gesperrt und sagt es ehrlich (`nurAufDemMac`). Die reine Swift-Logik liegt unter `macos/Shared/` statt `App/Logic/`,
weil `scripts/build_mac_window.py` alle Shared-Quellen übersetzt und der Reporter dort liegt. „Verstrichene eigene
Zusage“ heißt: `richtung von_mir`, `art Zusage`, `status verstrichen`, `tage == -1` (der Tag der Zusage war gestern).

## Tests: erst rot, dann grün

| Lauf | Vorher | Nachher |
|---|---|---|
| `sidecar/tests/test_mitteilungen.py` (43 Tests) | Sammelfehler (`ImportError: cannot import name 'mitteilungen'`) | 43 bestanden |
| `macos/test_mac_app.py` (5 neue Tests) | 4 rot im gezielten Lauf (`-k mitteilung`; der fünfte, `test_bauskript_bindet_user_notifications…`, war dort nicht ausgewählt und wäre ohne das Framework ebenso rot gewesen) | 32 bestanden, 1 übersprungen (`swiftc` fehlt) |
| UI `mitteilungen.test.mjs`, `einstellungen-gliederung.test.mjs` | 2 Dateien rot (Modul fehlt; „fünf Schalter“) | 18 bestanden (mit `system.test.mjs`) |

Volle Läufe auf dem Endstand (Python 3.13, `-n auto`, 4 Kerne, 22:02 min):

* Sidecar: **7.773 bestanden, 1 fehlgeschlagen, 3 übersprungen**, 26 Unterfälle. Der eine Fehlschlag:
  `test_cloud_memory.py::test_bulk_accepts_101_sources_after_pilot_and_uses_larger_budget` (`_threads[job_id].is_alive()`
  unter Last noch wahr); allein wiederholt: 1 bestanden. Ohne Bezug zu diesem Paket.
* UI: `npm test` **768 bestanden, 0 fehlgeschlagen**; `npx tsc --noEmit` ohne Befund; `npm run build` erfolgreich.
* Mac-App statisch: 32 bestanden, 1 übersprungen.
* `scripts/pruefe_anfuehrungszeichen.py` über alle neuen und geänderten Dateien: sauber.

## Sabotageproben (13, alle gefangen)

Zusicherung absichtlich gebrochen, gezielter Lauf, Datei wiederhergestellt (`git status` danach unverändert).

| Probe | Datei | rote Tests | Gefangen von |
|---|---|---|---|
| Morgenmitteilung zweimal (Merkliste vergisst alles) | `mitteilungen.py` | 5 | `…genau_einmal_je_tag…`, `…einmal_je_termin`, `…zusage_einmal…` |
| Termin außerhalb des Fensters (0 bis 120 Minuten) | `mitteilungen.py` | 4 | `…nur_im_fenster_von_30_bis_60_minuten[20, 29, 61, 90]` |
| `an=False` liefert trotzdem | `mitteilungen.py` | 2 | `…ausgeschaltet_liefert_nichts…`, Routen-Test |
| Rückmeldung ohne Logbuch | `mitteilungen.py` | 2 | `…landen_im_logbuch_ohne_inhalt`, `…ueber_die_routen…` |
| Inhalt im Protokoll (Fehlertext geloggt) | `mitteilungen.py` | 1 | `test_nichts_inhaltliches_im_protokoll` |
| Antwort zu groß (Satz ungekürzt) | `mitteilungen.py` | 1 | `test_antwort_bleibt_klein…` |
| Ruhezeit entfernt | `mitteilungen.py` | 1 | `test_in_der_ruhezeit…` |
| Wegezeit fragt trotz `nur_lesen` den Kartendienst | `wegezeit.py` | 1 | `…wegezeit_nur_aus_dem_zwischenspeicher` |
| Framework `UserNotifications` fehlt im Bauskript | `build_dmg.sh` | 1 | `test_bauskript_bindet_user_notifications…` |
| `print(` im Reporter (Inhalt ins Protokoll) | `NotificationReporter.swift` | 1 | `…nie_inhalt_im_protokoll` |
| Schaltertext ohne „nichts verlässt den Rechner“ | `gliederung.ts` | 2 | Gliederungs- und Mitteilungstest |
| „Mac“ fest im Titel statt `{Rechner}` | `gliederung.ts` | 1 | `mitteilungen.test.mjs` |
| Erlaubnis-Hinweis fehlt | `mitteilungenSchalter.ts` | 1 | `mitteilungen.test.mjs` |

## Browserprobe (`scripts/probe_mitteilungen_ui.py`, Chromium 1194, echter Sidecar, Ollama-Attrappe)

Der Sidecar gibt sich als Mac-App aus (Attrappe `laufumgebung.system_art`), ein zweiter Lauf als Docker im Browser.
Ergebnis `ok: true`, **Konsole leer** (keine Fehler, keine Warnungen). Geprüft und als Bild festgehalten
(`paket_b3_browser/`, 1280 und 390 px): Schalter an der richtigen Stelle, Vorgabe aus, „Es verlässt nichts den
Rechner“, kein Uhrzeitfeld ohne Schalter; Einschalten speichert `an` und zeigt 07:30 und den Wochen-Satz; 08:15
speichern (im Sidecar 08:15), 21:30 lässt sich nicht speichern („vor 21:00 Uhr“); Erlaubnis „abgelehnt“ per Attrappe
ergibt den Hinweis mit den Systemeinstellungen, auch bei 390 px ohne waagerechtes Scrollen; Ausschalten lässt die
Uhrzeit stehen und nimmt den Hinweis weg; ohne Mac ist der Schalter gesperrt mit dem Satz „Mitteilungen gibt es nur in
der Kingfisher-App auf dem Mac, nicht im Browser mit Docker.“ Bilder: `mitteilungen-aus-1280`, `-an-1280`,
`-uhrzeit-1280`, `-erlaubnis-1280`, `-erlaubnis-390`, `-aus-390`, `-docker-1280` (nicht im Repository).

## Offen und Grenzen

* **Swift nicht gebaut.** Kein Swift-Übersetzer in diesem Container; `macos/tests/main.swift` (Prüfungen der neuen
  Logik) läuft erst in `mac-app.yml`. Der Code ist durch Lesen und die Struktur-Tests in `macos/test_mac_app.py`
  geprüft, nicht übersetzt.
* **Mitteilungen nicht am Mac gesehen.** Banner, „Öffnen“ und „War überflüssig“, das Öffnen der Seite bei geschlossenem
  Fenster: Checkliste in [`macos/README.md`](../../../macos/README.md#auf-dem-mac-prüfen).
* **Erlaubnis bei Ad-hoc-Signatur ungeprüft.** Ob macOS der ad hoc signierten App den Dialog zeigt und Mitteilungen
  zustellt, ist nur am Mac zu klären; `UNUserNotificationCenter.current()` setzt ein App-Bündel voraus (gegeben in
  `Kingfisher.app`, nicht beim rohen Programm).
* Die Zahl für „Fertig heißt“ (eine Woche ohne überflüssige Mitteilung) braucht die Woche im Alltag.
* Die Merkliste `mitteilungen.sqlite3` gehört nicht zur Sicherung: Nach einer Wiederherstellung könnte eine heutige
  Mitteilung ein zweites Mal kommen.
* Die Zeitangabe im Uhrzeitfeld folgt der Browsersprache (im Chromium der Probe „08:15 AM“); gespeichert wird `HH:MM`.
