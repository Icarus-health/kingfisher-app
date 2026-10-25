# Viel Bestand: die Oberfläche mit einer großen synthetischen Welt (25.10.2026)

Bisher war jede Seite mit 181 synthetischen Mails geprüft. Ein echtes Postfach hat Tausende, dazu lange Namen mit
Titeln und Umlauten, viele Akten und lange Betreffzeilen. Paket V6 des Verbesserungsdurchgangs nach #94 hat die
Oberfläche mit einer solchen Welt durchgesehen, gemessen und behoben, was klar in der Oberfläche oder eng und eindeutig
im Sidecar lag. Nur synthetische Daten; die Welt liegt nicht im Repository.

## Die Welt

Zur Welt der Messlatte (Lea Hartmann, Stichtag 29.09.2026, Europe/Berlin) kommen aus einem Generator (deterministisch,
`seed=6`, im Scratchpad der Sitzung, nicht im Repository):

| Art | Anzahl | Besonderheiten |
|---|---|---|
| Mails | 8.000 (zusammen 8.181) | drei Jahre, dichter zur Gegenwart, 60 in den letzten drei Tagen; 22 % Rundschreiben, 22 % gesendet, Verläufe mit `Re:`/`AW:`, 10 % Betreff über 150 Zeichen, 3 % mit sehr langem Wort (Verweis) |
| Kontakte | 600 in 120 Organisationen | Titel („Prof. Dr. Dr. h. c. mult.“, „Dr. rer. nat.“, „Dipl.-Ing.“), Umlaute und Fremdzeichen (Æ, ø, ł, ı, ş), Doppelnamen bis über 40 Zeichen; wenige schreiben sehr viel |
| Projekte | 80 | Namen bis 150 Zeichen, 2.195 Mails zugeordnet |
| Termine | 1.500 (zusammen 1.528) | 500 in sechs Wochen um den Stichtag, Rest 2025/2026; lange Titel und Orte, bis zu zwölf Teilnehmende |
| Aufgaben | 300 | lange Titel, 75 % mit Fälligkeit (−40 bis +90 Tage), 40 % mit Projekt |

Aufgenommen über dieselben Wege wie die Messlatte (`messlatte/aufnahme.py`: Mail über `Intake.step` mit dem echten
`MailConnector`, Termine über den Mac-Kalender-Adapter und `/api/v1/mac-calendar/memory`; Projekte, Zuordnung und
Aufgaben über die Routen der Oberfläche; danach `akten_routes.nachfuehren`). Alle 9.737 Quellen kamen an, keine
fehlte. Dauer in dieser Umgebung: Aufnahme 322 s, Projekte und Zuordnung 29 s, Aufgaben 4 s, Bezüge und Akten 84 s;
Datenbank 205 MB. Größte Akten: eine Person mit 665 Quellen, eine Organisation mit 3.924.

## Wie gemessen wurde

Echter Sidecar (`create_app` wie die Messlatte, eingefrorene Uhr des Stichtags) unter uvicorn, gebaute Oberfläche,
Chromium über Playwright, de-DE, 1280 und 390 px. Je Seite ein frischer Seitenaufruf; **sichtbar** heißt: `main` trägt
Text, kein Ladezeichen mehr (`aria-busy`, Skelette, `data-memory-loading`), und der Text bleibt 0,5 s gleich. Dazu die
langsamste API-Anfrage der Seite, Überstand und Abschneiden wie `scripts/probe_seiten_ui.py`, gekürzte Texte ohne
Titel, die größte Liste mit oder ohne Seitenwahl, Konsolenfehler.

**Vorher** ist der Stand von `feat/oberflaeche-20261023` (Sidecar und gebaute Oberfläche aus `HEAD` vor dem Paket),
**nachher** dieser Branch auf einer neu aufgenommenen, gleich erzeugten Welt. Beide liefen abwechselnd je zweimal; die
Tabelle nennt die Spanne. Die Maschine war während der Messung von parallelen Testläufen anderer Pakete ausgelastet
(Last um 11 auf 4 Kernen): Wanduhrzeiten sind deshalb höher und streuen; der Vergleich gilt nur innerhalb der Tabelle.
Für den Graphen zusätzlich CPU-Zeit im selben Prozess (unten).

## Messtabelle

| Seite | Breite | sichtbar vorher (s) | sichtbar nachher (s) | langsamste Anfrage vorher | nachher | Auffälliges vorher | nachher | Höhe nachher (px) |
|---|---|---|---|---|---|---|---|---|
| Heute | 1280 | 3,5–7,0 | 4,2–6,0 | morning-briefing 6,7 s | morning-briefing 5,4 s | – | – | 1875 |
| Aufgaben | 1280 | 0,5–1,0 | 0,8 | tasks 0,1 s | tasks 0,0 s | – | – | 3875 |
| Nachrichten | 1280 | 0,7 | 0,7–0,8 | local-mail 0,5 s | local-mail 0,5 s | 58× gekürzt ohne Titel | 40× gekürzt ohne Titel | 900 |
| Kalender, Monat | 1280 | 0,2–0,4 | 0,3 | calendar 0,2 s | calendar 0,1 s | – | – | 1512 |
| Kalender, Woche | 1280 | 0,2 | 0,2 | calendar 0,1 s | integrations 0,1 s | – | – | 932 |
| Kalender, Liste | 1280 | 0,2 | 0,2 | integrations 0,1 s | calendar 0,1 s | – | – | 8102 |
| Gedächtnis, Menschen | 1280 | 5,0 | 2,8–3,3 | memory/graph 4,5 s | memory/graph 2,9 s | – | – | 900 |
| Gedächtnis, Organisationen | 1280 | 7,3–10,4 | 1,4 | memory/graph 9,9 s | akten/sachen 1,2 s | – | – | 900 |
| Gedächtnis, Projekte | 1280 | 4,3–5,3 | 3,0–3,8 | memory/graph 4,6 s | memory/graph 3,5 s | – | – | 900 |
| Gedächtnis, Suche | 1280 | 3,7–5,8 | 2,7–9,7 | memory/graph 5,3 s | memory/graph 9,2 s | – | – | 900 |
| Akte Person (665 Quellen) | 1280 | 1,0–1,2 | 1,2 | akten/akte 0,9 s | memory/people/… 1,3 s | – | – | 1842 |
| Akte Organisation (3.924 Quellen) | 1280 | 1,2 | 1,1 | akten/akte 0,8 s | akten/akte 0,8 s | – | – | 2212 |
| Einstellungen | 1280 | 0,2–0,3 | 0,4–0,7 | einrichtung/lernt 1,0 s | einrichtung/lernt 0,7 s | – | – | 1276 |
| Heute | 390 | 3,7–3,9 | 3,2–3,5 | morning-briefing 3,5 s | morning-briefing 3,8 s | – | – | 2536 |
| Aufgaben | 390 | 0,3 | 0,6 | status 0,1 s | aufgaben-post/vorschlaege 0,4 s | – | – | 8321 |
| Nachrichten | 390 | 0,6–0,8 | 0,5–0,6 | local-mail 0,7 s | local-mail 0,5 s | 59× gekürzt ohne Titel | 40× gekürzt ohne Titel | 844 |
| Kalender, Monat | 390 | 0,2 | 0,2–0,3 | conversations/latest 0,1 s | conversations/latest 0,1 s | – | – | 4799 |
| Kalender, Woche | 390 | 0,2 | 0,2 | calendar 0,1 s | calendar 0,1 s | 6× über den Rand | 6× über den Rand | 5078 |
| Kalender, Liste | 390 | 0,1–0,2 | 0,2–0,3 | mac-calendar 0,1 s | calendar 0,1 s | – | – | 15883 |
| Gedächtnis, Menschen | 390 | 4,3–5,4 | 2,5 | memory/graph 4,9 s | memory/graph 2,2 s | – | – | 844 |
| Gedächtnis, Organisationen | 390 | 7,4–9,9 | 1,2–1,3 | memory/graph 9,4 s | akten/sachen 1,1 s | – | – | 844 |
| Gedächtnis, Projekte | 390 | 4,2–5,0 | 2,9–3,2 | memory/graph 4,4 s | memory/graph 2,9 s | – | – | 844 |
| Gedächtnis, Suche | 390 | 4,9–5,0 | 2,7–3,1 | memory/graph 4,5 s | memory/graph 2,8 s | 4× über den Rand | – | 844 |
| Akte Person (665 Quellen) | 390 | 1,1–1,4 | 1,1–1,5 | akten/akte 0,9 s | memory/people/… 1,4 s | – | – | 2225 |
| Akte Organisation (3.924 Quellen) | 390 | 0,9–1,0 | 0,9–1,2 | akten/akte 0,5 s | akten/akte 0,6 s | 1× über den Rand | 1× über den Rand | 2618 |
| Einstellungen | 390 | 0,5 | 0,3 | einrichtung/lernt 0,9 s | einrichtung/lernt 0,7 s | – | – | 1742 |

Die 9,7 s der Suche bei 1280 px nachher sind eine Lastspitze im ersten Lauf (zweiter Lauf 2,7 s, Graph dabei 9,2 s
statt rund 3 s). „Gekürzt ohne Titel“ nachher in Nachrichten sind nur noch die Vorschauzeilen (bewusst, siehe unten). „Über den Rand“
in Kalender-Woche bei 390 px und in der Akte der Organisation siehe „Nicht behoben“.

**Gedächtnisgraph** (`GET /api/v1/memory/graph`, gleiche Datenbank, drei Aufrufe je Fassung im selben Prozess):

| | vorher | nachher |
|---|---|---|
| Antwort | 19,5 MB | 10,2 MB |
| Themenknoten / Kanten | 9.233 / 57.349 | 1 / 22.499 |
| CPU je Aufruf | 2,6–3,0 s | 1,6–1,9 s |
| Wanduhr je Aufruf (unter Last) | 3,9–4,6 s | 2,7–3,1 s |

## Befunde und was behoben ist

1. **Leerzeichen fehlten in langen Betreffzeilen mit Umlauten** („Landesamt fürGesundheit“, „Rüdesheimam Rhein“,
   „nächsterSchritt“). Ursache: Ein Absender faltet lange Köpfe und mischt kodierte (`=?utf-8?q?…?=`) und unkodierte
   Wörter; `connectors/mail.py::_decode` hängte die Teile von `decode_header` bloß aneinander und verlor dabei das
   Leerzeichen hinter jedem kodierten Wort. Jetzt `make_header`, das die Leerzeichen setzt; ein unbekannter
   Zeichensatz bricht die Mail nicht mehr ab, sondern bleibt lesbar. Gleiche Ursache und gleiche Abhilfe für
   Anzeigenamen in `kontakte.anzeigename`. Gilt für neu eingelesene Mails; schon gespeicherte Betreffzeilen bleiben,
   wie sie sind.
2. **Kodierte Namen im Briefing**: „Um 7:30 Uhr ist „Telefonat“ mit =?utf-8?q?Dr=2E_rer=2E_nat=2E_Kai_K=C3=B6rner?= und
   Xaver Zimmermann.“ Kennt der Kalender nur die Adresse, kommt der Name aus den Mails, und die Beteiligten stehen dort
   in Kopfzeilenform. `EpisodeStore.participants_for_addresses` legt jetzt zu jeder gespeicherten Schreibweise ihre
   lesbare Form ab (`anzeige`, nur bei Mailquellen dekodiert, wie `anzeigenamen=True` es schon tat); angezeigt wird sie
   in `vorbereitung.teilnehmer` und damit in Terminvorbereitung, Termin-Zuordnung, Briefing und „Was brauche ich
   morgen?“. Die gespeicherte Schreibweise (`person`) bleibt unverändert. Wirkt auch auf schon gespeicherte Mails.
   Nachher: „… mit Dr. rer. nat. Kai Körner und Xaver Zimmermann.“
3. **Der Gedächtnisgraph trug jede technische Markierung als Thema.** `mail:message:<Prüfsumme>`, der Anhangsbericht
   `mail:attachments:{…}`, `mail-parent:…`, `source:truncated` wurden je Mail eigene Themenknoten: 9.233 Knoten und mehr
   als die Hälfte der 19,5 MB, die jede Gedächtnisseite lädt. Markierungen mit kleingeschriebenem Namensraum vor einem
   Doppelpunkt sind jetzt keine Themen (`graph.ist_thema`); Schlagwörter aus Ordnern und Kopfzeilen bleiben.
4. **Die Route des Graphen** gibt das schon fertige JSON direkt zurück statt durch die allgemeine Umwandlung von FastAPI
   (bei 10.000 Quellen eine halbe Sekunde je Aufruf); `kontakte.anzeigename` merkt sich seine Ergebnisse (der Graph
   fragt dieselben paar hundert Namen zehntausendfach). Mit 3. zusammen: CPU je Aufruf −36 %.
5. **Organisationen, Bereiche, Dokumente, Orte und Themen warteten auf den ganzen Graphen**, obwohl sie ihn nicht
   brauchen (eigene, seitenweise Abfragen). Organisationen: 7–10 s bis sichtbar, nachher 1,2–1,4 s. Der Graph wird nur
   noch für Suchen, Menschen, Projekte und Entscheidungen geladen, einmal (`MemoryBrowseModel.brauchtGraph`); ein
   Fehler des Graphen sperrt die anderen Ansichten nicht mehr.
6. **„50 Aufgaben brauchen dich heute.“** bei 300 Aufgaben: gezählt wurde die geladene Seite (50 Zeilen, alle
   überfällig). Ist die erste Seite bis zum Ende fällig und gibt es weitere, steht jetzt „Mehr als 50 Aufgaben brauchen
   dich heute.“; auf späteren Seiten entfällt die Zeile, statt eine falsche Zahl zu nennen
   (`taskWorkspaceModel.heuteKopfZeile`).
7. **Fundstellen der Suche ragten bei 390 px 200 px über den Rand** (Verweis ohne Umbruchstelle im Zitat): `break-word`
   verkleinert die Mindestbreite im Raster nicht, `overflow-wrap: anywhere` schon.
8. **Gekürzte Betreffzeilen in der Mailliste** tragen den ganzen Betreff als Titel (der Absender hatte ihn schon).

## Nicht behoben (mit Messung und Vorschlag)

- **Heute braucht 3–7 s.** Das Morgenbriefing allein: 2 s je Aufruf am laufenden Server, 0,5 s warm im Testclient,
  beim ersten Aufruf nach dem Start 5,8 s (Bezüge-Verzeichnis neu bauen, 4,5 s, einmal je Prozess). Heute ruft es
  zweimal gleichzeitig (`post=false` für den schnellen Gruß und das volle); beide kosten gleich viel, weil der teure Teil
  (`akten_vorschlaege.fuer_briefing` mit `bezuege.sachen`, `working_memory_context.reports`) in beiden läuft, und sie
  bremsen sich gegenseitig samt `einrichtung/lernt` (0,5–0,9 s je Aufruf). Vorschlag: `post=false` ohne „Neue Akte?“ und
  ohne Arbeitsgedächtnis, das Verzeichnis beim Start im Hintergrund bauen. Liegt im Briefing (Paket V1), deshalb hier
  nicht angefasst.
- **Menschen, Projekte, Suche laden weiter den ganzen Graphen** (10 MB, rund 3 s): Die Listen zeigen 25 Zeilen, filtern
  aber im Browser über alle Knoten, darunter je Quelle ein Knoten. Vorschlag: seitenweise Personen- und Projektliste
  und Suche im Sidecar wie bei den Organisationen (`akten/sachen`), der Graph nur noch für die Graphansicht.
- **Organisationsliste je Aufruf 1,2–1,6 s** (`akten/sachen?art=organisation`) und **Gruppenvorschläge 2,2–2,5 s**
  (`organisation-group-suggestions`), ohne Zwischenspeicher. Vorschlag: am Stand der Bezüge zwischenspeichern.
- **Kalender, Woche bei 390 px**: sieben Spalten zu je mindestens 76 px rollen in ihrer Fläche seitlich. Gewollt oder
  nicht, ist eine Gestaltungsfrage (drei Tage auf dem Handy?); die Seite selbst rollt nicht.
- **Akte der Organisation bei 390 px**: Die Messung meldet ein Dateifeld des Logo-Wählers über dem Rand; es steckt in
  einem zugeklappten Aufklapper (Fehlmeldung der Messung). Der Akte-Kopf ist Paket V2.
- **„Wie war das Gespräch mit agidius-zimmermann@privat-18.example und 11 weiteren?“**: Die Nachfrage nach einem
  Termin nennt die Adresse, wenn der Kalender nur sie kennt. Vorschlag: denselben Namensindex wie die
  Terminvorbereitung (`nachbereitung.frage_zu`).
- **„zuletzt“ in der Organisationsliste liegt in der Zukunft** (31.12.2026), weil künftige Termine mitzählen.
- **Vorschauzeilen in der Mailliste** bleiben ohne Titel: Sie sind ein Ausschnitt, der ganze Text öffnet mit einem Klick.
- **Kalender, Liste bei 390 px** ist bei 175 Terminen in sieben Tagen 15.900 px hoch; begrenzt durch den Zeitraum,
  mit Vor/Zurück.

Gut skaliert haben: Nachrichten (Seiten zu 40, „1–40 von 8181“), Aufgaben (Seiten zu 50), Kalender Monat („16
weitere“), Akten (Zeitstrahl „die jüngsten 150 von 500 Quellen“, Zusammenhänge „10 von 372“, Verlauf aufklappbar mit
„Alle zeigen“, Termine „Vergangen (16)“), Menschen und Projekte (Seiten zu 25). Lange Namen und Titel brechen überall
um; kein Konsolenfehler auf keiner Seite.

## Tests und Sabotageproben

Neu: `sidecar/tests/test_mail_header_name_decoding.py` (vier Fälle: gefalteter Betreff, unbekannter Zeichensatz,
gefalteter Name mit Titel, Name in der Terminvorbereitung), `sidecar/tests/test_graph.py::test_technische_markierungen_werden_keine_themen`,
`app/kingfisher/tests/viel-bestand.test.mjs` (vier Fälle).

| Sabotage | gefangen von |
|---|---|
| Betreff: Teile wieder bloß aneinanderhängen | `test_mail_betreff_behaelt_leerzeichen_…` |
| Betreff: unbekannter Zeichensatz bricht wieder ab | `test_mail_betreff_mit_unbekanntem_zeichensatz_bleibt_lesbar` |
| Anzeigename: Teile wieder bloß aneinanderhängen | `test_gefalteter_anzeigename_mit_titel_behaelt_das_leerzeichen` |
| Anzeigename: Zwischenspeicher ohne Kopfzeilen-Merkmal | `test_gefalteter_anzeigename_mit_titel_behaelt_das_leerzeichen` |
| Terminvorbereitung: Namen roh aus dem Bestand | `test_terminvorbereitung_nennt_mailnamen_mit_umlaut_dekodiert` |
| Graph: technische Markierungen wieder als Themen | `test_technische_markierungen_werden_keine_themen` |
| Gedächtnis: Organisationen laden wieder den Graphen | `viel-bestand.test.mjs` |
| Gedächtnis: Seite wartet wieder immer auf den Graphen | `viel-bestand.test.mjs` |
| Aufgaben: Seitengröße wieder als Zahl | `viel-bestand.test.mjs` |
| Nachrichten: Betreff ohne Titel | `viel-bestand.test.mjs` |
| Suche: Fundstelle bricht nicht um | `viel-bestand.test.mjs` |

Alle elf gefangen. Oberfläche: 878 Tests grün, `tsc --noEmit` und Build grün; `scripts/probe_seiten_ui.py`: 75
Breiten geprüft, 0 nicht in Ordnung. Backend: volle Suite 7.972 bestanden, 3 ausgelassen, 0 fehlgeschlagen.
