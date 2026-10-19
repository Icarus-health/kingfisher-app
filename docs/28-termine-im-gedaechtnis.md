# Termine im Gedächtnis (Etappe C1)

Stand: 29. September 2026, ergänzt am 19. Oktober 2026 um Zeit, Serie und Absage aus
CalDAV und Abo ([Abschnitt unten](#zeit-serie-und-absage-aus-caldav-und-abo-oktober-2026)).
Umsetzung von C1 aus [`26-plan-stabschef.md`](26-plan-stabschef.md). Code:
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
  gelesen; die Obergrenze `MAX_TERMINE_JE_ABSCHNITT` gilt trotzdem je 90 Tage, nicht
  für alle Jahre zusammen). Google liefert Notiz und Teilnehmernamen (`description`,
  `displayName`), CalDAV und Abo `DESCRIPTION` und `CN`. CalDAV und Abo klappen
  Serien im gelesenen Zeitraum aus (siehe unten).
* **Einordnung:** Termine laufen durch dieselbe Einordnung wie jede Quelle
  (`working_memory_*`). Dazu steht `event` jetzt überall, wo Rohquellenarten
  aufgezählt werden: `episodes.ROHQUELLEN` und alle SQL-Bedingungen
  `kind IN ('message','document','event')` in Einordnung, Suche, Kategorien,
  Abdeckung, Erwähnungen und Projektzuordnung. `test_keine_abfrage_laesst_termine_still_aus`
  fängt eine neue Stelle ab, die die Art vergisst. Personen: Ein bevorstehender
  Termin zählt nicht als Kontakt.

## Grenzen (offen)

* **CalDAV und Abo:** Eine Zeitzone, die nur als VTIMEZONE in der Datei beschrieben
  ist (weder IANA-Name noch in der Outlook-Tabelle), bleibt unbekannt; die Uhrzeit gilt
  dann wie bisher als UTC. `RANGE=THISANDFUTURE` gilt nur für den einen geänderten
  Termin. Siehe unten.
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

## Zeit, Serie und Absage aus CalDAV und Abo (Oktober 2026)

Über CalDAV und die geheime iCal-Adresse (der Weg für Google ohne Cloud-Projekt) las
ein kleiner eigener Parser die Termine. `DTSTART;TZID=Europe/Berlin` galt als UTC
(Termine um ein bis zwei Stunden verschoben), `STATUS:CANCELLED` als normaler Termin,
und von einer Serie kam nur der erste Termin an. Code: `connectors/calendar.py`
(`parse_events`), `connectors/zeitzonen.py`, `connectors/collections.py`
(`ICalendarSubscription`, `ABO_GROESSE`), Zählgrenze je Abschnitt in
`calendar_memory.kalender_job`. Tests: `sidecar/tests/test_ical_termine.py`.

* **Zeitzonen.** `TZID` gilt über `zoneinfo`; Outlook-Namen („W. Europe Standard
  Time“) über eine Tabelle der 51 häufigsten Zonen nach CLDR `windowsZones.xml`
  (Gebiet „001“). Ein unbekannter Name wird nicht geraten: Die Uhrzeit gilt wie bisher
  als UTC. Eine Uhrzeit ohne Zone („floating“) ist nach RFC 5545 die Ortszeit des
  Lesers, also `KINGFISHER_TIMEZONE` (bisher UTC). Ganztägige Termine und `…Z` bleiben
  wie bisher. Parameter in Anführungszeichen (`TZID="(UTC+01:00) …"`) zerbrechen die
  Zeile nicht mehr.
* **Ende.** DTEND, sonst DTSTART plus DURATION, sonst ein Tag (Datum) oder kein
  Zeitraum (Uhrzeit), wie RFC 5545 es vorgibt. Termine ohne DTEND fehlten bisher still
  im Gedächtnis.
* **Absagen und Erinnerungen.** Abgesagte Termine fehlen (wie bei Google und
  Microsoft); das Gedächtnis entzieht sie wie gelöschte. Zeilen einer Erinnerung
  (VALARM) überschreiben Titel und Notiz nicht mehr (Google: „This is an event
  reminder“).
* **Serien.** Im gelesenen Zeitraum ausgeklappt, mit RDATE, EXDATE und geänderten
  oder abgesagten Einzelterminen (RECURRENCE-ID); DTSTART ist immer ein Termin. Die
  Regeln rechnet `python-dateutil`. Ohne Zeitraum bleibt eine Serie ein Termin (so
  zählt `kalender_abo.pruefe`). Eine Serie, die mehr als 100.000 Wiederholungen bis
  zum Fenster braucht, wird mit einem Satz abgelehnt statt still gekürzt.
* **Kennung eines Einzeltermins:** `UID#<ursprünglicher Beginn>` (UTC, bei
  ganztägigen das Datum, ohne Zone die Ortszeit), gleich bei jedem Abruf und in jedem
  Fenster. Ein verschobener Termin behält sie und ist eine neue Fassung; ein per
  EXDATE oder Absage herausgenommener wird entzogen. Ein Termin ohne UID bekommt eine
  feste Ersatzkennung aus seinem Inhalt (ohne DTSTAMP) statt einer zufälligen.
* **CalDAV** klappt ebenfalls lokal aus, nicht mit `<C:expand>`: Server setzen das
  uneinheitlich um, und RFC 4791 (9.6.5) lässt dem ersten Termin die RECURRENCE-ID
  offen; die Kennung soll nicht vom Server abhängen. Die Antwort wird als XML gelesen
  (vorher als Rohtext: `&amp;` im Titel, `&#13;` an jedem Wert).
* **Abo-Größe:** höchstens 25 MB statt 5 MB, beim Einrichten und beim Lesen dieselbe
  Grenze und derselbe Satz; gelesen wird nur bis zur Grenze.

**Einmalig nach dem Update.** Beim ersten Abgleich wird die bisherige einzige
Episode jeder CalDAV- oder Abo-Serie entzogen (ihre Kennung war die blanke UID), die
Einzeltermine kommen neu hinzu; eine Zuordnung oder Nachbereitung am ersten Termin
einer solchen Serie hängt an der alten Kennung. Termine mit TZID oder ohne Zone und
Termine, deren Notiz bisher „This is an event reminder“ war, werden einmal neue
Fassungen; Termine ohne DTEND kommen neu hinzu; abgesagte werden entzogen.

**Gemessen** (synthetische Datei nach Googles Aufbau, rund 1,8 KB je Termin mit fünf
Teilnehmern, Meet-Text und Erinnerung; jede 200. ist eine offene Wochenserie seit
2016; in dieser Umgebung, nicht auf einem Mac):

| Datei | Termine | Anzeige (30 Tage) | Gedächtnisfenster (4 Jahre) |
|---|---|---|---|
| 5 MB | 2.812, davon 14 Serien | 0,5 s | 0,6 s (5.932 Termine) |
| 25 MB | 14.053, davon 70 Serien | 2,6 s | 2,9 s (28.821 Termine), rund 110 MB Speicher zusätzlich |
| 5 MB, jede 20. eine Serie | 2.810, davon 140 Serien | 0,9 s | 1,3 s (32.138 Termine) |

**Sabotageprobe.** Je Zusicherung absichtlich gebrochen, `test_ical_termine.py` lief,
danach zurückgespielt; in jedem Fall wurde der genannte Test rot.

| Gebrochene Zusicherung | Rot wurde |
|---|---|
| TZID wird übergangen | `…tzid_wird_in_die_richtige_zeit…`, `…outlook_zeitzonennamen…`, `…ende_in_einer_anderen_zone…` |
| Outlook-Tabelle fehlt | `…outlook_zeitzonennamen…`, `…zuordnung_der_windows_zonen…` |
| unbekannte Zone wird geraten (Zone des Nutzers) | `…unbekannte_zeitzone_behaelt_die_bisherige_rueckfallregel` |
| Uhrzeit ohne Zone gilt als UTC | `…termin_ohne_zeitzone…` |
| Anführungszeichen in Parametern übergangen | `…doppelpunkt_und_semikolon…`, `…unbekannte_zeitzone…` |
| Absage wird übernommen | `…abgesagter_termin_wird_nicht_uebernommen`, `…im_gedaechtnis_entzogen` |
| VALARM-Zeilen zählen zum Termin | `…erinnerung_ueberschreibt…` |
| DURATION übergangen; kein Ende ohne DTEND | `…ende_aus_dauer…` |
| RRULE nicht ausgeklappt | 14 Tests |
| EXDATE übergangen | `…exdate…`, `…kennungen_sind_stabil…`, `…serie_im_gedaechtnis…` |
| geänderter Einzeltermin ersetzt den ursprünglichen nicht | `…verschobener_einzeltermin…`, `…abgesagter_einzeltermin…`, `…caldav_klappt…`, `…serie_im_gedaechtnis…` |
| Kennung am tatsächlichen statt am ursprünglichen Beginn | `…verschobener_einzeltermin…`, `…serie_im_gedaechtnis…` |
| Kennung in Ortszeit statt UTC | `…serie_wird_im_fenster…`, `…exdate…`, `…abgesagter_einzeltermin…` |
| Ausklappen in UTC statt in der Ortszeit | 7 Tests, u. a. `…bleibt_ueber_die_zeitumstellung_um_neun` |
| Fenster übergangen; Fensterbeginn ohne Spielraum | `…vor_dem_fenster_beginnt…` |
| DTSTART nicht als erster Termin | `…beginn_ist_immer_ein_termin…` |
| ohne Fenster ausgeklappt | `…ohne_fenster_bleibt_eine_serie_ein_termin` |
| zu dichte Serie still gekürzt | `…zu_dichte_serie_wird_ehrlich_abgelehnt` |
| UNTIL in anderer Form (Datum, Ortszeit, ganztägig mit UTC) | `…until_in_anderer_form…` |
| Ortszeit ohne Zone nicht in der Zone der Serie | `…exdate…` |
| unlesbare Regel oder Zusatz `X-…` kippt die Datei | `…kaputte_oder_fremde_regel…` |
| zufällige Ersatzkennung ohne UID | `…termin_ohne_uid…` |
| Obergrenze für die ganze Abo-Datei | `…obergrenze_gilt_beim_abo_je_abschnitt` |
| CalDAV aus dem Rohtext statt aus dem XML | `…caldav_liest_den_kalender_aus_dem_xml…` (beide Fälle) |
| Abo-Grenze wieder 5 MB (Lesen oder Einrichten) | `…abo_ueber_fuenf_mb…` |
| erst alles laden, dann prüfen | `…zu_grosses_abo_bricht_frueh_ab…` |

**Nicht geprüft:** gegen echte Server (Google, iCloud, Nextcloud, Outlook); die
Attrappen bilden deren Antworten nach. Die Zeiten oben sind keine Messung auf einem
Mac.
