# Termine im Gedächtnis (Etappe C1)

Stand: 29. September 2026. Umsetzung von C1 aus
[`26-plan-stabschef.md`](26-plan-stabschef.md). Code:
`sidecar/icarus_memory/calendar_memory.py` (Regeln),
`calendar_memory_routes.py` (Verdrahtung, Auskunft), `mac_calendar.py`
(Route für den Mac-Arbeiter), `scripts/mac_calendar_worker.py` und
`macos/CalendarReader.swift` (Lesen des Zeitraums). Tests:
`sidecar/tests/test_kalendergedaechtnis.py`.

## Was sich ändert

Bisher las das Produkt Termine bei jeder Frage live aus dem Kalender (±30 Tage,
der Mac-Adapter nur das laufende Jahr). Vergangene Treffen waren für Rückblicke
unsichtbar, Terminnotizen gingen verloren, die Suche fand keinen Termin. Jetzt
wird **jeder Termin einer freigegebenen Kalenderquelle** als Rohquelle abgelegt:
Episode der Art `event` (die Art gab es im Modell, war aber nie benutzt) mit

| Feld der Episode | Inhalt |
|---|---|
| `title` | Titel des Termins |
| `occurred_at` | Beginn |
| `body` | Titel, Zeit (Wochentag, Datum in Wort und Zahl, Uhrzeit von–bis in der Zeitzone des Nutzers), Ort, Teilnehmer, Kalender, Notiz |
| `participants` | Teilnehmer als „Name <Adresse>“ (wie bei Mail) |
| `provenance` | Quellenart `calendar`, `source_ref` = `calendar:<Quelle>:<UID des Termins>` |

Der Text enthält alles Erhebliche. Damit ist der Digest des Textes zugleich der
Fingerabdruck einer Fassung.

## Regeln

* **Rohmaterial, keine Fakten** (`10-verdichtung.md`). Termine gehen nicht in die
  Verdichtung (`EpisodeStore.pending` überspringt die Art); was daraus Wissen
  werden soll, braucht wie immer Vorschlag und Annahme.
* **Kein zweites Versionssystem.** Ein Termin ist eine Quelle mit `source_key`
  (`cal:<Quelle>:<Hash der UID>`). Verschiebung oder Änderung = neue Fassung
  derselben Quelle über `source_versions.track_source` (Wissen aus der alten
  Fassung wird gesperrt, die alte Fassung ausgeschlossen, der Zeiger umgestellt).
  Gelöscht oder abgesagt = entzogene Quelle (`invalidate_with_corrections` und
  `ignore`), die Episode bleibt als Nachweis. Ein selbst gesetzter Ausschluss trägt
  die Marke `entzogen:kalender` (`EpisodeStore.ignore(grund=…)`); nur daran erkennt
  das Programm, dass ein wiederkehrender Termin (Kalender neu verbunden, Termin
  wieder eingetragen) wieder gelten darf. Ein Ausschluss durch den Nutzer trägt sie
  nicht und bleibt bestehen.
* **Zurückgesetzter Termin.** Wird ein Termin auf eine frühere Fassung
  zurückgesetzt (A → B → A), öffnet der Abgleich die Episode von A wieder. Wissen,
  das aus A bestätigt war, bleibt gesperrt; nur die Rohquelle ist wieder auffindbar.
  Bei Dokumenten gilt weiterhin die bestehende, strengere Regel
  (`test_source_versions`).
* **Nur mit Freigabe.** Mac: Verbinden und Kalenderauswahl (wie bisher). Andere
  Quellen (CalDAV, Google, iCalendar-Abo): sie müssen eingerichtet sein; gelesen
  werden sie im Zeitplanlauf, der wie bei Mail und Ordnern der Zeitplan-Freigabe
  folgt, oder auf Knopfdruck (`POST /api/v1/calendar-memory/sync`). Vor jedem
  Schreibpaket wird die Freigabe erneut geprüft.
* **Trennen entzieht.** Kalender abwählen, Mac-Kalender trennen oder eine Quelle
  unter Einstellungen entfernen entzieht ihre Termine im Gedächtnis
  (`KalenderGedaechtnis.entziehen_ohne_freigabe`). Der Zeitplanlauf holt einen
  übersehenen Fall nach.
* **Fehlende Termine nur aus vollständigem Abschnitt.** Ein Abschnitt darf Termine
  entziehen, die in ihm fehlen. Ein Lesefehler ist kein Löschbeweis (die Quelle
  bleibt unberührt); ein **leerer** Abschnitt entzieht nichts, weil er ebenso von
  einem stillen Fehler stammen kann.

## Zeitraum und Ablauf

`calendar_memory.py` hält die Zahlen an einer einzigen Stelle:
`VERGANGENHEIT_TAGE = 3 * 365`, `ZUKUNFT_TAGE = 365`, `ABSCHNITT_TAGE = 90`,
`MAX_TERMINE_JE_ABSCHNITT = 20000`. Die Live-Anzeige (Kalenderseite, Briefing ±30
Tage, Jahresansicht des Mac-Adapters) bleibt unverändert.

* **Mac:** Der Arbeiter erfährt das Fenster aus `memory_window` im Adapterzustand,
  liest es in Abschnitten zu 90 Tagen (Abfragen zu je 31 Tagen, mit Notizen über
  `with_notes`) und sendet jeden Abschnitt an `POST /api/v1/mac-calendar/memory`.
  Beim Verbinden, bei neuer Generation und danach höchstens alle 30 Minuten. Ein
  Fehler im Gedächtnisabgleich meldet die Live-Anzeige nicht als defekt. Der
  Adapter gibt einem Einzeltermin eine stabile UID (Kalender und Termin-ID); erst
  Serientermine und abgetrennte Ausnahmen bekommen den Beginn dazu. Sonst wäre jede
  Verschiebung ein neuer Termin statt einer neuen Fassung.
* **Google, CalDAV, iCalendar-Abo:** der Zeitplanlauf liest dasselbe Fenster in
  Abschnitten zu 90 Tagen (das Abo liefert immer die ganze Datei und wird einmal
  gelesen). Google liefert Notiz und Teilnehmernamen (`description`,
  `displayName`), CalDAV `DESCRIPTION` und `CN`.
* **Einordnung:** Termine laufen durch dieselbe Einordnung wie jede Quelle
  (`working_memory_*`). Dazu steht `event` jetzt überall, wo Rohquellenarten
  aufgezählt werden: `episodes.ROHQUELLEN` und alle SQL-Bedingungen
  `kind IN ('message','document','event')` in Einordnung, Suche, Kategorien,
  Abdeckung, Erwähnungen und Projektzuordnung. `test_keine_abfrage_laesst_termine_still_aus`
  fängt eine neue Stelle ab, die die Art vergisst. Personen: Ein bevorstehender
  Termin zählt nicht als Kontakt.

## Grenzen (offen)

* **Serientermine** über CalDAV und Abo erscheinen nur einmal (der Parser klappt
  Wiederholungen nicht aus, siehe `connectors/calendar.py`). Mac und Google liefern
  jede Instanz.
* **Zeitzone:** Der Text nennt Zeiten in `KINGFISHER_TIMEZONE` (Vorgabe
  Europe/Berlin). Ändert sich die Einstellung, ändern sich die Texte, und jeder
  Termin wird einmal als neue Fassung abgelegt.
* **Erstübernahme** ist langsam, weil jede Episode mit eigener Schreibbestätigung
  abgelegt wird (siehe Messung unten); danach ist ein Abgleich unveränderter Termine
  ein reiner Lesevorgang.
* **Ein leerer Kalender** entzieht nichts (siehe oben); wer wirklich alle Termine
  löscht, muss die Quelle trennen.
* **Termine erzeugen keine Aufgabenvorschläge** (`task_candidates` bleibt bei Mail
  und Dokumenten) und keine Verdichtungsvorschläge.
* Der Nutzer sieht bisher nur die Zähler von `GET /api/v1/calendar-memory`; eine
  Oberflächenanzeige fehlt.

## Leistungsgrenzen (gemessen)

Synthetisch, 10.000 Termine über das ganze Fenster (Notiz je rund 300 Zeichen, zwei
Teilnehmer), eine Umgebung mit langsamer Schreibbestätigung (rund 14 ms je
Commit), 17 Abschnitte:

| Vorgang | Dauer |
|---|---|
| Erstübernahme aller 10.000 Termine | 245 s (rund 25 ms je Episode, bestimmt von der Schreibbestätigung) |
| Abgleich, nichts geändert | 2,5 s |
| Abgleich, 1 % (100 Termine) geändert | 6,5 s |
| größte Sendung (ein 90-Tage-Abschnitt, rund 1.100 Termine) | 354 KB JSON |
| Episodendatei danach | 25 MB |

Der Adapterzustand des Mac-Kalenders (`mac-calendar.sqlite3`) wächst nicht: Er hält
weiter nur die Live-Anzeige; die Gedächtnisabschnitte werden nicht gespeichert,
sondern durchgereicht. Grenzen: höchstens 20.000 Termine je Abschnitt (darüber
Ablehnung statt stiller Kürzung), höchstens 10.000 je 31-Tage-Abfrage des
Mac-Adapters (unverändert), Notizen auf 20.000 Zeichen gekürzt. Ein
Kalender mit deutlich mehr als rund 100 Terminen am Tag über drei Jahre ist damit
nicht belegt.

## Messung mit der Messlatte

Ohne Modell (Stufe „Abruf“), Welt v1, 77 Fragen; „vorher“ ist die Basis vom
29. September (Commit `4fb80b8`), „nachher“ der Stand dieses Arbeitspakets.

| Kennzahl | ohne Rauschen vorher | nachher | mit 10.000 Rauschquellen vorher | nachher |
|---|---|---|---|---|
| Erwartete Belege gefunden | 95 von 136 | 101 von 136 | 85 von 136 | 91 von 136 |
| Fragen mit allen Belegen | 42 von 71 | 47 von 71 | 37 von 71 | 41 von 71 |
| Erwartete Belege auf Rang 1 | 29 von 136 | 26 von 136 | 29 von 136 | 26 von 136 |
| bis Rang 5 | 82 | 85 | 75 | 80 |
| bis Rang 12 | 93 | 99 | 83 | 89 |
| Fragen mit verbotenen Belegen | 15 von 77 | 15 von 77 | 15 von 77 | 14 von 77 |
| Termine außerhalb des Fensters | 4 | 0 | 744 | 0 |
| Dauer der Aufnahme | 1,5 s | 4,4 s | 91 s | 200 s |

Die 19 Termine der Welt sind Beleg in 9 (Frage, Beleg)-Paaren; vorher fehlten alle 9,
nachher fehlt 1 (ohne Rauschen) bzw. 2 (mit Rauschen).

* **Gewonnen** (ohne Rauschen): fremde-anweisung-04 (`fremde-anweisung-008`),
  mainz-03 und mainz-07 (`mainz-009`), meeting-protokoll-04 (`meeting-protokoll-011`),
  namensgleich-03 (`namensgleich-005`), terminvorbereitung-01
  (`terminvorbereitung-008`). Mit Rauschen zusätzlich verbessert: zeitraum-06 findet
  `mainz-009`.
* **Verdrängt:** In terminvorbereitung-02 findet die Suche jetzt `terminvorbereitung-008`
  statt `terminvorbereitung-007`, in zeitraum-06 `mainz-009` statt `zeitraum-009`. Die
  Kandidatenliste ist begrenzt, ein Termin steht davor. Netto null je Frage.
* **Noch fehlend:** `terminvorbereitung-008` bei „Was steht morgen bei mir an?“
  (terminvorbereitung-06) und bei -02 mit Rauschen. Das ist die Auflösung von „morgen“
  und die Reihenfolge der Kandidaten, nicht die Aufnahme.
* **Rang 1 sinkt von 29 auf 26.** Termine rücken vor gleich gute Mails; in
  frist-verschoben-05 fällt `frist-verschoben-008` von Rang 3 auf 12. Das ist eine Frage
  der Rangfolge (Etappe D, „Aktualität schlägt Ähnlichkeit“), keine der Ablage.
* **Verbotene Belege:** Ein abgesagter Workshop steht als Termin weiter im Kalender und
  kommt jetzt in zusage-abgesagt-01 (`zusage-abgesagt-003`) und namensgleich-02
  (`namensgleich-005`) als verbotener Beleg in den Kontext; dafür entfallen
  namensgleich-01 (`namensgleich-010`) und mit Rauschen falle-04. Die Zahl bleibt 15
  (mit Rauschen 14). Die Antwortqualität ist nicht gemessen (kein Modell).

## Sabotageprobe

Je Zusicherung absichtlich gebrochen, `test_kalendergedaechtnis.py` lief, danach
zurückgespielt (Skript in der Sitzung; wiederholbar mit den Ersetzungen aus der
Tabelle). In jedem Fall wurde der genannte Test rot; nach dem Zurückspielen 28 von 28
grün.

| Gebrochene Zusicherung | Rot wurde |
|---|---|
| Verschiebung = neue Fassung (`track_source` entfernt) | `…verschobener_termin_ist_neue_fassung…`, `…zurueckgesetzter_termin…` |
| gelöschter Termin wird entzogen | `…geloeschter_termin_wird_entzogen…` |
| leerer Abschnitt entzieht nichts | `…leerer_abschnitt_entzieht_nichts…` |
| Inkrementalität (Fingerabdruckvergleich entfernt) | `…zweiter_abgleich_fasst_unveraenderte_termine_nicht_an` |
| Zeitfenster (Vergangenheit 1 Jahr statt 3) | vier Tests, u. a. Ablage und Verschiebung |
| Fensterfilter des Abgleichs entfernt | `…termine_ausserhalb_des_fensters…` |
| Freigabe vor dem Schreiben geprüft | `…ohne_freigabe_wird_nichts_geschrieben` |
| Nutzerausschluss bleibt | `…vom_nutzer_ausgeschlossener_termin…` |
| Trennen des Mac-Kalenders entzieht | `…mac_abwaehlen_und_trennen…` |
| Abwählen eines Mac-Kalenders entzieht | `…mac_abwaehlen_und_trennen…` |
| Mac-Route prüft Kalenderauswahl | `…mac_route_lehnt_veraltete_generation_und_fremde_kalender_ab` |
| Mac-Route verwirft veraltete Generation | derselbe Test |
| Entfernen einer Quelle entzieht (Server) | `…trennen_einer_kalenderquelle_entzieht_ihre_termine` |
| Rohquellenart `event` in `ROHQUELLEN` | `…suche_findet_einen_termin_von_vor_zwei_jahren` |
| Abfrage vergisst `event` (SQL) | `…keine_abfrage_laesst_termine_still_aus` |
| Verdichtung überspringt Termine | `…termine_sind_keine_vorlage_fuer_die_verdichtung` |
| bevorstehender Termin ist kein Kontakt | `…bevorstehender_termin_zaehlt_nicht_als_kontakt…` |
| wiederkehrender Termin wird wiederhergestellt | `…zurueckgesetzter_termin…`, `…trennen_entzieht_nur_die_getrennte_quelle…` |

**Nicht geprüft:** Der Swift-Adapter (`macos/CalendarReader.swift`) und der neue Teil
des Arbeiters (`scripts/mac_calendar_worker.py`) wurden in dieser Umgebung weder
gebaut noch gegen einen echten Kalender gestartet (kein macOS); die Route, gegen die
der Arbeiter sendet, ist getestet. Das Bauen und ein Lauf auf dem Mac stehen aus.
