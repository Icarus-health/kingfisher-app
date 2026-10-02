# Bezüge und Akten (Etappen D1 und D2)

Stand: 30. September 2026 (Migration 13, nach C2 mit Schema 12). Umsetzung von D1 und D2 aus
[`27-schichten-und-fragen.md`](27-schichten-und-fragen.md). Code:
`sidecar/icarus_memory/bezuege.py`, `akten.py`, `fristen.py`, `akten_routes.py`;
Bausteine in `mappe.py`, `time_scope.py`, `memory_categories.py`,
`working_memory_store.py`. Tests: `test_bezuege.py`, `test_akten.py`,
`test_akten_routes.py`, `test_fristen.py`, `messlatte/tests/test_akten.py`.

## Was sich ändert

Das Gedächtnis kennt jetzt zu jeder **Sache** (Person, Organisation, Projekt, Ort,
Thema) eine **Akte** (Ebene 2 der Schichtablage). Sie entsteht ohne Modell aus den
Auszügen je Quelle (Ebene 1) und den **Bezügen** (D1): Jede Quelle trägt beliebig
viele Verknüpfungen zu Sachen. Alles ist abgeleitet und jederzeit neu berechenbar,
nie Fakt im Bestand, und jede Zeile führt zur Quelle.

## D1: Bezüge

Eine Verknüpfung Quelle → Sache trägt immer ihre Grundlage:

| Grundlage | Woher | Sicherheit |
|---|---|---|
| `anker` | Absender-, Empfänger- oder Gastadresse (Person, dazu die Organisation aus der Domäne), Projektzuordnung der Quelle, Terminort, ein Name ohne Adresse, den genau eine Adresse trägt | sicher, ohne Rückfrage |
| `modell` | Erwähnung aus `memory_categories` mit Textstelle (Person, Organisation, Projekt, **Ort**), Thema mit Belegstelle | vorgeschlagen, korrigierbar |
| `nutzer` | Zuordnung oder Ablehnung per Klick, Themenkorrektur | maßgeblich, überschreibt Modell und Anker |

Kennungen der Sachen: `person:a:<adresse>` (Anker), `person:n:<Name>` (nur ein Name,
so wie C3 ihn führt), `organisation:<Name ohne Rechtsform, nur Buchstaben und
Ziffern>` (Domäne `winter-catering.example` und die Erwähnung „Winter Catering GmbH“
sind dieselbe Sache), `projekt:<id>` oder `projekt:n:<Name>`, `ort:<Name>`,
`thema:<Kategorie>`. Private Anbieter (gmail, gmx …) und die eigene Domäne sind keine
Organisation; automatische Postfächer (`noreply@`) sind eine Organisation, keine Person;
die eigene Adresse ist „ich“ und nie eine Sache.

Regeln:

* **Nur bei Eindeutigkeit.** Ein Name ohne Adresse (Erwähnung im Text, Notiz,
  Transkript) wird einer Person nur zugeordnet, wenn genau eine Adresse ihn als Alias
  trägt (`identitaet.Verzeichnis`). Sonst bleibt er **offen** und nennt seine
  Kandidaten; in der Oberfläche fragt „Wer ist gemeint?“ mit einem Klick zurück. Ein
  zweiter „Alex Winter“ macht eine früher eindeutige Zuordnung wieder offen (die
  betroffenen Quellen werden neu bestimmt, sobald sich das Verzeichnis ändert).
* **Nutzer überschreibt.** `zu` fügt hinzu, `nicht` lehnt eine gefundene Verknüpfung
  ab (Anker wie Modell), Entfernen der Entscheidung stellt den Fund des Programms
  wieder her. Die Entscheidung trägt den Fingerabdruck der Quelle; ändert sich die
  Quelle, gilt sie als **veraltet** (wie Themenkorrekturen) und wird als solche gezeigt.
* **Entzug wirkt sofort.** Jede Lesung verbindet mit den geltenden Quellen
  (nicht ausgeschlossen, aktuelle Fassung, keine Suchfrage des Gesprächs). Der nächste
  Abgleich löscht die Zeilen entzogener Quellen.
* **Kein Quelltext in der Tabelle.** Gespeichert sind Kennungen (normalisierte
  Namen), Zeichenpositionen, Grundlage. Namen und Zitate liest jede Anzeige aus dem
  Original (`Bezuege.beschriftung`, `zitat`).

Orte kommen auf zwei Wegen: als **Terminort** ohne Modell (Feld „Ort:“ einer
Termin-Episode: ohne Komma der ganze Eintrag, mit Komma der erste Teil, der Ort hinter
einer Postleitzahl und ein letzter Teil, der wie ein Ortsname aussieht; „online“ und
„Zoom“ sind kein Ort) und als **Erwähnung** durch `memory_categories` (neue Art
`place`, Prompt und JSON-Schema angepasst).

Speicherung (abgeleitet, neu berechenbar), Migration 13 im Episoden-Store:

| Tabelle | Inhalt |
|---|---|
| `sach_quellen` | je Quelle: Fingerabdruck, Eingabe-Kennung, Verzeichnis-Kennung (nur bei namensabhängigen Bezügen) |
| `sach_bezuege` | Quelle, Sache, Art, Grundlage, Textstelle (Beginn/Ende), Rolle, Kandidaten bei offenen Erwähnungen, `abhaengig` |
| `sach_nutzer` | Entscheidung des Nutzers mit Fingerabdruck (einzige nicht ableitbare Tabelle) |
| `akten_cache` | zwischengespeicherte Akte je Sache (nur Verweise) |

Migration 13 baut `memory_category_entities` neu (SQLite kann eine CHECK-Bedingung
nicht ändern) und behält alle Zeilen. Wo schon Quellen ausgewertet sind, hebt sie die
Taxonomieversion an, damit auch der Bestand nach Orten durchsucht wird; das läuft wie
jede Auswertung im Hintergrund und in Paketen (ein Modellaufruf je Quelle). Bei einer
frischen Installation bleibt die Version bei 1. Die Nummer 12 gehört dem Suchindex (C2).
Der Fingerabdruck einer Quelle ist in SQL berechnet (Digest, Metadaten-Digest,
Bearbeitungszähler, Länge des Dokuments): Ein Nachtrag von Kontakten oder eine neue
Projektzuordnung ändert ihn.

### Fristen

`fristen.py` löst Datumsangaben deterministisch auf, mit dem Zeitpunkt der **Quelle**
als Bezug (nicht heute): „bis Freitag“, „bis zum 12.10.“, „12. November 2026“, „Ende
Oktober“, „in zwei Wochen“, „bis morgen“, „Ende des Monats“. Nur eindeutige
Auflösungen: „nächste Woche“, „Mitte Oktober“, ein Wochentag am selben Wochentag und
ein Datum ohne Jahr, das ebenso vergangen wie künftig sein kann, bleiben Text ohne
Datum und stehen in der Akte als „Zeitangaben ohne festes Datum“. Jede Auflösung nennt
ihre Textstelle. Zahlwörter liest `time_scope.zahl` (dieselbe Stelle wie bei
Zeiträumen in Fragen). Aufgelöst werden Abschnitte der Art Bitte, Zusage, bedingte
Aussage und Änderung.

## D2: Akten

Eine Akte je Sache; `mappe.py` liefert die gemeinsamen Bausteine (`lesen` prüft, ob ein
Abschnitt noch gilt, `eintrag` bildet die Zeile, `_aufgaben` die Aufgaben), die
Kurzansicht der Mappe (Projekt und Person, Route `einzelheiten`, Gesprächsantwort)
bleibt unverändert erreichbar. Abschnitte:

* **Verlauf:** die verknüpften Quellen, jüngste zuerst, je eine Zeile aus Ebene 1
  (sonst der Titel), mit den Grundlagen des Bezugs.
* **Vermutlich offen:** Bitten und Zusagen ohne spätere Erledigung oder Absage. Als
  erledigt oder abgesagt gilt ein Punkt, wenn eine spätere Meldung derselben Sache (Art
  Änderung oder Stand) denselben Gegenstand nennt und ein Erledigt- oder Absagewort
  trägt, oder wenn die zur Quelle gehörende Aufgabe erledigt ist. Nennt sie den
  Gegenstand ohne solches Wort, bleibt der Punkt offen mit dem Hinweis „danach
  geändert“. Die Akte behauptet nie, dass etwas offen ist.
* **Fristen:** kommend und verstrichen, jede mit Quelle. Eine Frist, die eine spätere
  Quelle für denselben Gegenstand verschiebt, steht unter „überholt“ und nennt die neue.
* **Stand:** je Gegenstand die jüngste Änderung oder Statusmeldung, ältere nur als
  „vorher“. Die Reihenfolge entscheidet die Zeit der Quelle: Aktualität schlägt
  Ähnlichkeit.
* **Beteiligte:** Sachen, die in denselben Quellen vorkommen, mit Anzahl.
* **Termine:** vergangene und kommende; nennt eine spätere Meldung den Tag mit einem
  Absagewort, steht dabei „vermutlich abgesagt“ (der Kalendereintrag bleibt oft stehen).
* **Aufgaben:** offene Aufgaben zur Sache.

„Gleicher Gegenstand“ heißt: gemeinsame Wortstämme (mindestens zwei, ohne Monats-,
Wochentags- und Füllwörter), ein gemeinsames langes Wort („Rechnungsanschrift“) und ein
gleiches aufgelöstes Datum zählen doppelt; trägt die spätere Meldung ein Erledigt- oder
Absagewort, genügt ein gemeinsamer Stamm; bei Fristen genügt ein gemeinsames Fristwort.
Das ist bewusst grob und deshalb überall als Vermutung ausgewiesen.

**Zwischenspeicher.** Die Akte wird nur neu berechnet, wenn sich eine Eingabe ändert:
Fingerabdruck über die verknüpften Quellen, ihre Bezugsgrundlagen, ihre Einordnung
(Status, Fassung, Modell, Abschnitte mit Art und Stelle) und den Stand des
Wissensbestands. Gespeichert sind nur Verweise (Quelle, Fassung, Textstellen,
Datumswerte); Zitate liest jede Anzeige aus dem Original. Was von der Uhrzeit abhängt
(kommend/verstrichen, Termine), rechnet die Anzeige.

**Nichts still begrenzen.** Eine Akte wertet die jüngsten 500 Quellen aus und nennt die
Gesamtzahl; jede Liste nennt ihre Gesamtzahl („5 von 12“, „Alle zeigen“).

## Schnittstelle

`akten_routes.py`; die Sachen-ID steht als Abfrageparameter oder im Körper, nie im Pfad.

| Route | Zweck |
|---|---|
| `GET /api/v1/akten/sachen?art=&suche=&limit=&offset=` | Sachen mit Anzahl der Quellen, letzter Aktivität, Gesamtzahl |
| `GET /api/v1/akten/akte?sache=&alle=` | die Akte |
| `GET /api/v1/akten/quellen/{episode_id}` | Bezüge einer Quelle, offene Erwähnungen, Ablehnungen, veraltete Entscheidungen |
| `PUT /api/v1/akten/quellen/{episode_id}/zuordnung` | `{sache, aktion: zu|nicht}` |
| `DELETE /api/v1/akten/quellen/{episode_id}/zuordnung?sache=` | Entscheidung zurücknehmen |
| `POST /api/v1/akten/aktualisieren` | Bezüge neu bestimmen (Prüfung; der Server tut es von selbst) |

Jede Anfrage führt die Bezüge kurz nach (höchstens 1,5 s); den Rest rechnet ein
Hintergrundfaden zu Ende. Die Antwort nennt `berechnung.offen`, statt zu tun, als wäre
alles da; die Oberfläche lädt dann still nach.

## Oberfläche

Kein neuer Menüpunkt. Unter **Gedächtnis** stehen neben Menschen und Projekten die
Listen **Organisationen**, **Orte** und **Themenakten**; jede Zeile öffnet die Akte
(`/memory/akte/<Sache>`). Auf den Profilseiten von Person und Projekt ersetzt die Akte
die Kurzansicht, sobald Bezüge da sind (bis dahin bleibt die Mappe). „Beteiligte“ führen
zur Akte der jeweiligen Sache. Wo eine Quelle geöffnet wird, steht unter den Themen
„Wozu die Quelle gehört“ mit Grundlage, „Gehört nicht dazu“ und, bei offenen
Erwähnungen, „Wer ist gemeint?“ mit den Kandidaten.

## Messung

**Messlatte, Stufe Akten** (`python -m messlatte akten --welt messlatte/welt`, Test
`messlatte/tests/test_akten.py`), ohne Modell, mit der Regel-Einordnung
(`messlatte/akten.py`; sie ersetzt das Modell der Einordnung und ist die Grenze dieser
Messung), gegen die unveränderte Welt (176 Quellen, Bezüge in rund 0,4 s, 97 Sachen).
Fünf Fälle aus `frist-verschoben`, `adresse-geaendert` und `zusage-abgesagt`:

* **5 von 5 Fällen bestanden**, erwartete Quellen im Verlauf **15 von 15**.
* Der neue Stand steht als aktuell da und der überholte Wert dort **nicht**: Einreichfrist
  12.11. statt 15.10. (kommende Frist der Stiftung), Rechnungsanschrift Lindenallee 22
  statt Klinikstraße 5, neue Mailadresse als jüngster Stand unter der alten Adresse, die
  Absage als Stand der Akademie. Die frühere Zusage gilt als durch die Absage erledigt
  und bleibt unter „vermutlich erledigt“ nachvollziehbar; der Kalendereintrag des
  Workshops ist als „vermutlich abgesagt“ gekennzeichnet.
* Die Prüfung selbst fängt Fehler (Tests mit absichtlich falschen Akten: fehlende Quelle,
  alter Wert als Stand oder als kommende Frist, noch offene Zusage, fehlende
  Absagekennzeichnung).

**Leistung, 10.176 Quellen** (Welt plus 10.000 Rauschquellen, `scripts/probe_akten_scale.py`,
Wanduhr in dieser Umgebung mit langsamer Schreibbestätigung; die Aufnahme selbst dauerte
158 s und ist nicht Teil der Zahlen):

| Vorgang | Dauer |
|---|---|
| Bezüge, erster Lauf über alle Quellen (Hintergrund) | 25 s (rund 2,4 ms je Quelle), 12.116 Zeilen, 4.382 Sachen |
| Verzeichnis (Adressen, Namen) neu bauen | 0,65 s |
| Abgleich, nichts geändert | 0,24 s (die Route überspringt ihn bei unverändertem Speicher) |
| Abgleich nach 100 neuen Quellen | 1,1 s |
| Sachenliste (50 Einträge, mit Namen) | 0,25 s |
| Akte mit 100 Quellen, kalt / aus dem Zwischenspeicher | 0,07 s / 0,06 s |
| Abgleich nach Änderung einer Quelle, dann ihre Akte neu | 0,30 s, 0,09 s |
| Akte einer Sache ohne die geänderte Quelle | 0,01 s, aus dem Zwischenspeicher |

Grenze der Messung: Die größte Sache im Rauschen hat nur 21 Quellen (die 100 „Probe“-
Quellen des Skripts sind künstlich); eine Akte mit Tausenden Quellen wertet die jüngsten
500 aus. Mit dem Modell der Einordnung (statt konstanter und Regel-Einordnung) ändern
sich die Inhalte, nicht der Aufwand der Akten.

## Sabotageproben

Jede Zusicherung wurde absichtlich gebrochen (ein Ausdruck im Code ersetzt) und der
zuständige Test geprüft. Alle 25 Proben wurden von mindestens einem Test gefangen; zwei
Proben waren zuerst wirkungslos (`F4`, `A3`) und führten zu je einem neuen Test.

| Probe | Gebrochene Zusicherung | Gefangen von |
|---|---|---|
| F1 | Bezug ist die Quelle, nicht heute | `test_fristen` (bis Freitag) |
| F2 | Wochentag am selben Tag ist uneindeutig | `test_fristen` (uneindeutig) |
| F3 | Datum ohne Jahr nur bei Eindeutigkeit | `test_fristen` (am 25.08.) |
| F4 | Tausenderpunkt und Zahlenfolgen sind kein Datum | `test_fristen` (Belegnummer 112.10.2026; die erste Fassung des Tests fing es nicht) |
| F5 | Uneindeutiges bleibt Text | `test_fristen` (nächste Woche) |
| B1 | Erwähnung nur bei Eindeutigkeit, sonst offen | `test_bezuege` (gleichnamige) |
| B2 | Ablehnung des Nutzers entfernt den Bezug | `test_bezuege`, `test_akten_routes` |
| B3 | Zuordnung des Nutzers veraltet mit der Quelle | `test_bezuege` |
| B4 | Entzug entfernt den Bezug sofort | `test_bezuege`, `test_akten_routes` |
| B5 | Eigene Adresse ist keine Sache | `test_bezuege` |
| B6 | Änderung der Quelle führt zur Neuberechnung | `test_bezuege` |
| B7 | Neue gleichnamige Adresse macht die Zuordnung wieder offen (Verzeichnis-Kennung) | `test_bezuege` |
| B8 | Projektzuordnung ist ein Ankerbezug | `test_bezuege`, `test_akten_routes` |
| B9 | Terminort ist ein Ortsbezug | `test_bezuege` |
| M1 | Orte sind als Erwähnungsart zulässig (Schema) | `test_bezuege` |
| A1 | Stand zeigt den neuen Wert (jüngste zuerst) | `test_akten`, `test_akten_routes`, Messlatte |
| A2 | Erledigtes gilt nicht als offen | `test_akten`, `test_akten_routes`, Messlatte |
| A3 | Zwischenspeicher rechnet bei Änderung einer Quelle neu | `test_akten` (der Test kam durch diese Probe dazu) |
| A4 | Fingerabdruck umfasst die Einordnung | `test_akten` |
| A5 | Verschobene Frist wird ersetzt | `test_akten`, Messlatte |
| A6 | Offen heißt nur „vermutlich“ | `test_akten` |
| A7 | Abgesagter Termin ist gekennzeichnet | Messlatte |
| A8 | Gleiches Datum zählt doppelt (Absage über das Datum) | `test_akten`, Messlatte |
| A9 | Zwischenspeicher hält keine Zitate | `test_akten` |
| A10 | Erledigte Aufgabe erledigt die Bitte | `test_akten`, `test_akten_routes` |

Eine Probe (B7 in der ersten Fassung, Verzeichnis-Kennung nie gleich) ließ den Abgleich
endlos laufen; das ist kein Testerfolg und wurde durch die Probe mit konstanter Kennung
ersetzt. Die Proben liegen nicht im Repository; wer sie wiederholen will, ersetzt die
genannten Ausdrücke in `bezuege.py`, `akten.py`, `fristen.py` oder `memory_categories.py`.

## Offene Punkte

* **Personen über mehrere Adressen** bleiben getrennte Sachen (C3: Zusammenführung ist
  Sache des Nutzers, `person_merges` wirkt nur auf die Graphdarstellung). Ein
  Arbeitgeberwechsel (`adresse-geaendert`) ergibt zwei Personenakten; die neue Anschrift
  steht in der Akte der neuen Organisation.
* **Ebene 1 bestimmt die Akte.** Stand, Offen und Fristen sind so gut wie die Arten,
  die das Modell den Absätzen gibt. Die Messlatte prüft sie mit einer Regel-Einordnung,
  nicht mit einem Modell; die Qualität mit Modell steht aus.
* **Orte ohne Modell** sind grob (Ortsangabe eines Termins). Ohne `place`-Erwähnungen
  des Modells gibt es keine Orte aus Mails und Notizen.
* **Gleicher Gegenstand** ist eine Wortstammheuristik. Sie irrt in beide Richtungen
  (zwei Bitten zum selben Thema, kurze Meldungen ohne gemeinsames langes Wort); die
  Akte weist Offen und Erledigt deshalb als Vermutung aus.
* **Erstberechnung** bei sehr großem Bestand läuft im Hintergrund und braucht Zeit
  (siehe Messung); bis dahin nennen die Listen, wie viele Quellen noch offen sind.
* **Chat und Fragen** lesen die Akten noch nicht (E1 bis E3). Die Lage (Ebene 3, D3) steht seit
  Migration 14 oben in der Akte, siehe [`32-lage.md`](32-lage.md).
* Der Hintergrundfaden für die Bezüge hängt nicht am Zeitplan; nach einem Neustart
  rechnet die erste Anfrage weiter.
