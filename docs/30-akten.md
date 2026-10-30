# Bezüge und Akten (Etappen D1 und D2)

Stand: 30. September 2026 (Migration 13, nach C2 mit Schema 12). Umsetzung von D1 und D2 aus
[`27-schichten-und-fragen.md`](27-schichten-und-fragen.md). Code:
`sidecar/icarus_memory/bezuege.py`, `akten.py`, `fristen.py`, `akten_routes.py`,
`akten_vorschlaege.py` (Neue Akte?, Oktober 2026), `projekt_automatik.py` (Projekte von selbst, 26.10.2026); Bausteine in `mappe.py`, `time_scope.py`,
`memory_categories.py`, `working_memory_store.py`. Tests: `test_bezuege.py`, `test_akten.py`,
`test_akten_routes.py`, `test_akten_vorschlaege.py`, `test_projekt_automatik.py`, `test_fristen.py`, `messlatte/tests/test_akten.py`.

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
  wieder her. Die Entscheidung trägt den Fingerabdruck der Quelle und gilt für ihren
  **Text**: Nur wenn der Inhaltsdigest am Anfang des gespeicherten Fingerabdrucks nicht
  mehr passt, gilt sie als **veraltet** (wie Themenkorrekturen) und wird als solche
  gezeigt (`NUTZER_GILT`, `nutzer_gilt`). Projektzuordnung, Verdichten, Archivieren,
  nachgetragene Kontakte, Kopfzeilen und Anhangberichte ändern nur Quellenangaben und
  Ablage: Der Nutzer hat über den Inhalt entschieden, die Entscheidung bleibt; neue
  Kontakte kommen beim nächsten Abgleich als eigene Bezüge dazu. Ein anderer Text ist
  in der Praxis eine neue Fassung (neue Episode) und wird neu eingeordnet. Dieselbe
  Regel gilt für den Kreis einer Person (`kreis.py`).
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
`place`, Prompt und JSON-Schema angepasst). Trägt der **erste Teil** der Ortsangabe
(Haus oder Träger: mit Komma dahinter oder aus mindestens zwei Wörtern) den Namen einer
Organisation, die im selben Termin über eine **Adresse** beteiligt ist („Ort: Akademie
Taunus GmbH, Seminarraum 3“ mit jemandem von akademie-taunus), gehört der Termin dieser
Organisation (Rolle `terminort`) statt einem gleichnamigen zweiten Ort. Ein einzelner
Ortsname bleibt Ort, auch wenn eine Domäne so heißt („Ort: Mainz“ mit mainz.de), ebenso
der Ort hinter der Postleitzahl; eine nur vom Modell erwähnte Organisation zählt nicht.
Termine haben dafür eine eigene Regelfassung (4, Mails 3): Nach dem Update werden nur
Termine neu berechnet, nicht der ganze Bestand.

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

Seit Fassung 1.0.26 kommen hinzu:

* **Binnenfristen:** „innerhalb von 14 Tagen“, „binnen zwei Wochen“, „innerhalb eines
  Monats“ zählen ab der Quelle wie „in 14 Tagen“. Werktage und eine Frist ab einem
  anderen Ereignis („nach Erhalt der Ware“, „ab Rechnungsdatum“, „drei Werktage vor
  Ihrem Termin“, „24 Stunden vorher“) bleiben Text ohne Datum.
* **Wochentag mit Datum:** „bis Freitag, den 11. September“ ist eine Angabe; es gilt
  das Datum. Passt der Wochentag nicht zum Datum, bleibt sie ohne Datum. Vorher wurde
  daraus der nächste Freitag.

Welches Datum eine Frist ist, entscheidet `fristangaben_in`: Ein Wort wie „bis“,
„spätestens“, „innerhalb“ braucht eine Handlung im selben Satzteil. Erkannt werden
dafür Antworten, Anmelden, Senden und Einreichen, Zahlen (auch „zahlbar“,
„Zahlungsziel“, „begleichen“), Unterschreiben, Kündigen und Widerrufen, trennbare
Verben („füllen Sie den Bogen bis Freitag aus“, „geben Sie bis Freitag Bescheid“),
Pflichten mit Modalverb („muss bis … beim Finanzamt eingegangen sein“, „können Sie
… kündigen“), benötigte Unterlagen („Wir benötigen die Unterlagen bis …“) und eine
Bitte oder Zusage mit „zu“-Infinitiv („Wir bitten Sie, … bis … nachzureichen“). Nie
eine Frist sind ein Zustand nach dem Datum („bis 18.09. geschlossen“, „die bis
30.09. gültigen Preise“), ein gemeldeter Eingang ohne Modalverb („sind bis 18.09.
eingegangen“), „nicht vor Montag“ und „nicht zu betreten“. Was keine dieser Formen
hat, bleibt Quelle ohne abgeleitete Frist. Die Messung mit zwei unabhängig
geschriebenen Prüfsätzen steht im
[Prüfprotokoll](runs/2026-10-19-fristen-formulierungen/README.md).

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

### Braucht dich, Entscheidungen, Richtung (Akte 11, Migration 23)

Eine Akte vermutet nur. Ein guter Stabschef fragt dort, wo er unsicher ist, einmal nach
und merkt sich die Antwort. Das leistet „Braucht dich“ oben in der Akte (nur auf ihrer
eigenen Seite, `akte(..., ansicht=True)`), dringendes zuerst, höchstens sechs Punkte:

* **Abgesagt, aber noch im Kalender:** ein kommender Termin, den eine Meldung derselben
  Sache mit dem Tag und einem Absagewort absagt. Wahl: „Erledigt“ (Absage bestätigt) oder
  „Findet doch statt“ (die Vermutung entfällt, auch im Zeitstrahl).
* **Gilt das noch?** Eine Absage beendet nur, was sie benennt. Frühere offene Zusagen und
  Bitten **im selben Mailverlauf** (genaue Kopfzeilenbezüge, `episode_mail_headers`) oder
  mit dem **Tag des abgesagten Termins** sind vermutlich hinfällig („Den Ablauf schicken
  wir Ihnen im August“ vor „Wir müssen den Workshop absagen“). Das ist zu unsicher, um es
  selbst zu entscheiden: Die Akte fragt („Gilt nicht mehr“ oder „Gilt weiter“). Ein Punkt
  nach der Absage wird nie gefragt; ohne gemeinsamen Verlauf und ohne den Tag auch nicht.
* **Fristen offener Punkte:** in den nächsten sieben Tagen oder seit höchstens 45 Tagen
  verstrichen, mit demselben Satz wie im Briefing (`fristlage.beschreibung`). Wahl:
  „Erledigt“, bei verstrichenen auch „Gilt nicht mehr“.

**Entscheidungen** (`akten_entscheidungen.py`, Tabelle `akten_entscheidungen`): „erledigt“,
„gilt nicht mehr“, „gilt weiter“, bei Terminen „erledigt“ und „findet doch statt“.
Gespeichert sind nur Verweise (Quelle, Stellen, Inhaltsdigest der Quelle) und der
Zeitpunkt, kein Text, keine Sache, keine Adresse. Eine Entscheidung gilt für die
Textstelle und damit in jeder Akte, in der sie vorkommt. Sie hängt am Text der Quelle,
nicht am Fingerabdruck der Einordnung: Nachgetragene Kontakte, Kopfzeilen oder Anhänge
lassen sie stehen, eine neue Fassung des Textes fragt neu. Ein Termin wird über seine
Quelle angesprochen; ein geänderter Termin ist eine neue Quelle und fragt neu. Die
Entscheidung wirkt nur bei der Anzeige: „Erledigt“ und „gilt nicht mehr“ legen einen
offenen Punkt ab, seine Fristen mahnen weder in der Akte noch im Briefing; „gilt weiter“
hält ihn offen und holt ihn zurück, wenn die Akte ihn nur vermutlich für erledigt hielt;
„findet doch statt“ beendet auch die Frage „gilt das noch?“ zu diesem Termin. Der
Antwortkontext liest dieselben Entscheidungen (`Akten.roh_entschieden`), damit eine
Antwort nichts Abgelegtes als offen nennt. Der Zwischenspeicher der Akte bleibt
unberührt; der Eingabestand der Lage ändert sich (auch bei Termin-Entscheidungen), damit
sie neu geschrieben wird. Jede Entscheidung lässt sich mit einem Klick zurücknehmen;
„Rückgängig“ stellt die vorige Entscheidung wieder her, nicht nur die Vermutung. Sie ist
eine Einordnung durch den Nutzer, kein Fakt im Bestand (Regel des Gedächtnisses
unberührt).

**Richtung.** Jeder offene Punkt sagt, von wem er stammt (`richtung`: `von_mir`,
`an_mich`, `unklar`; bei Mails der Absender gegen die eigenen Adressen, bei Terminen,
Notizen und Mitschriften `unklar`). Die Oberfläche
gruppiert danach: „Du hast zugesagt“, „Du wartest auf“ (Zusagen anderer und deine
Bitten), „Bitten an dich“.

**Zeitstrahl.** Quellen (jüngste 150), Termine und Fristen als Punkte auf drei Spuren,
„heute“ als Linie; Zusagen und Bitten dunkel, abgesagte Termine durchgestrichen, offene
Fristen dunkel. Jeder Punkt ist ein Knopf und öffnet seine Quelle; der Strahl ist ein
einziger Tab-Stopp, die Pfeiltasten (und Pos1/Ende) gehen von Punkt zu Punkt.

### Neue Akte? (Paket B4, Migration 24)

Projekt-Akten entstanden bisher nur über eine Zuordnung des Nutzers (`project_id`) oder als Akte einer
bloßen Erwähnung (`projekt:n:<Name>`). Ein Projekt, das sich erst in den Mails bildet, bemerkte niemand.
`akten_vorschlaege.py` sieht die erwähnten, noch nicht angelegten Projekte durch und schlägt vor, daraus
eine Akte zu machen, ohne Modell, deterministisch und mit Begründung in einem Satz:

* **Schwelle.** Vorgeschlagen wird ein Name, wenn mindestens eines gilt: drei geltende Quellen, zwei
  verschiedene Personen über mindestens zwei Quellen, oder Quellen über 14 Tage verteilt.
* **Nie vorgeschlagen** werden Namen, die ein vorhandenes Projekt tragen (ohne Groß- und Kleinschreibung,
  in Umschrift: „Mueller“ und „Müller“ sind eins), Namen unter drei Zeichen und reine Zahlen. Zwei
  gleichnamige Projekte ordnet `bezuege.projekte_aus` weiterhin bewusst nicht zu.
* **Grund und Textstellen.** „In 4 Mails seit 3. Oktober mit Anna Keller und Ben Braun“: Zahl und Art der
  Quellen, Datum der ältesten, die Beteiligten aus denselben Quellen; dazu bis zu fünf Quellen mit der
  Textstelle der Erwähnung (`quellen_von`, `zitat`). Die Kennung ist ein Hash des normalisierten Namens.
* **Verdichtung schlägt vor, sie schreibt nicht.** Der Vorschlag speichert nichts. Erst „Akte anlegen“
  (`POST /api/v1/akten/vorschlaege/{kennung}/annehmen`) legt das Projekt idempotent an (deterministische
  ID aus der Kennung, ein unterbrochener Versuch ergänzt beim zweiten nur), ordnet die Quellen des
  Vorschlags zu, die noch kein Projekt haben (wie `PUT /api/v1/episodes/projects`), merkt „angenommen“ und
  antwortet mit der Akte (Link) und einem Satz („Akte „Projekt Atlas“ angelegt, 4 Quellen zugeordnet.“).
  Ein Projekt ist Ablage, kein Fakt: Es entsteht keine Aussage und kein Wissensvorschlag. Danach hängen
  alle `n:`-Erwähnungen über das Register am Projekt; die Akte des Projekts ist mit Quellen, Beteiligten
  und Zeitstrahl vollständig.
* **Reversibel.** „Zurücknehmen“ löst die zugeordneten Quellen wieder, entfernt das Projekt, wenn nichts
  anderes daran hängt (andere Quellen, Aufgaben, Notizen, Termine; sonst bleibt es und der Satz sagt
  warum), und vergisst die Entscheidung; der Vorschlag steht wieder. „Nein danke“ (`…/ablehnen`) wird
  gemerkt und nie wiederholt, bis der Nutzer es in der Akte zurücknimmt („Doch vorschlagen“). Zweimal
  annehmen ist 409 und ändert nichts; eine unbekannte Kennung ist 404.
* **Ablage.** Tabelle `akten_vorschlag_entscheidungen` (Migration 24): Kennung, Entscheidung (`angenommen`,
  `abgelehnt`), Zeitpunkt, Sache, Projekt-ID und die zugeordneten Quellen-IDs. Nur Verweise, kein Text.
  Jeder Klick steht im Logbuch (Art `akte_vorschlag`); eine angenommene Akte zählt dort als neue Akte.

**Anzeige.** In der Akte `projekt:n:<Name>` steht oben, vor „Braucht dich“, die Zeile „Neue Akte? Daraus
eine Akte machen? Grund.“ mit den Textstellen und zwei Knöpfen „Akte anlegen“ und „Nein danke“. Annehmen
öffnet die neue Akte mit dem Satz und „Rückgängig“; dort steht dauerhaft „Aus einem Vorschlag angelegt“
mit „Akte wieder auflösen“. Im Briefing und auf Heute steht **jeweils ein** Vorschlag, der mit den
meisten Quellen und bei gleicher Zahl der älteste, als ein Satz mit denselben zwei Knöpfen (`briefing.py`,
Quelle `akte_vorschlag`, leises Gewicht wie das Vorhaben); nie eine Liste. Nach einer Entscheidung steht sofort
der nächste da: einer nach dem anderen, nicht einer am Tag (so stand es bis zum 26.10. irrtümlich hier und in
der Fassung 1.0.27). Die Antwort bleibt auf Heute stehen, auch wenn der Punkt danach verschwindet, mit „Akte
öffnen“. Seit dem 26.10. legt Kingfisher **klare** Vorschläge selbst an (nächster Abschnitt); im Briefing stehen
dann nur noch die unklaren.

### Projekte von selbst (Paket P, Migration 25)

Entscheidung des Nutzers vom 26.10.2026 ([`66-automatik.md`](66-automatik.md)): Ein Projekt, das sich in den Mails
**klar** bildet, legt Kingfisher selbst an und ordnet die Mails zu, mit Rückgängig; unklare bleiben Frage. Das ist
mit der Regel des Gedächtnisses vereinbar, weil ein Projekt Ablage ist, kein Fakt (oben, „Neue Akte?“): Es
entsteht keine Aussage über einen Menschen. `projekt_automatik.py`, ohne Modell und deterministisch:

* **Klar oder unklar** (`einschaetzen`, mit Gründen). Klar ist ein Vorschlag „Neue Akte?“ nur, wenn alles zugleich
  gilt: mindestens drei Quellen **und** zwei verschiedene Personen, die jüngste Quelle höchstens 30 Tage alt, kein
  ähnlicher Name eines vorhandenen Projekts („Umbau“ und „Umbau Praxis“, „Atlas“ und „Atlass“; Vergleich ohne
  „Projekt“, Groß- und Kleinschreibung und Umlaute) und keiner einer anderen Erwähnung (eindeutig), nicht abgelehnt
  und nie zurückgenommen. Sonst bleibt er Frage, mit den Gründen („nur eine Person beteiligt“, „seit über 30 Tagen
  still“, „ähnlich wie das Projekt „Umbau““).
* **Anlegen** (`projekte_anlegen`), vor dem Briefing (`akten_vorschlaege_routes.fuer_briefing`) und nach jedem Takt
  der Mailaufnahme (`server.run_mail_intake`), nur wenn alle Bezüge berechnet sind. Genau wie „Akte anlegen“
  (`annehmen`: deterministische ID, Quellen ohne Projekt zugeordnet), dazu die Herkunft mit Grund als Zahlen und
  Verweise. Höchstens drei am Kalendertag; der Rest bleibt bis morgen Frage. Im Logbuch eine neue Akte (`von`
  `automatisch`).
* **Absenderregel** (`absender_ziel`, `absender_schritt`). Eine neue Mail kommt in das Projekt, in dem **alle**
  früheren Mails desselben Absenders im selben Konto liegen (mindestens zwei, das Projekt offen). Nie bei eigenen
  Mails, Rundmails (mehr als fünf Empfänger), Absendern mit Mails in mehreren Projekten oder mit einer früheren Mail
  ohne Projekt, nie bei einer gesperrten Mail. Jede Mail einmal (Zeilenstand wie bei „Aufgaben folgen der Post“); der
  erste Takt setzt nur den Stand, der Bestand wird nicht neu gedeutet. Die frühere Regel „Vorschlag: … Übernehmen“
  (`project_suggestions.py`) bleibt für ältere Mails.
* **Sichtbar.** Auf Heute unter „Braucht dich“ eine ruhige Zeile „Neues Projekt: Umbau Praxis, aus 4 Mails mit Anna
  Keller und Ben Braun · Ansehen · Rückgängig“ (drei Tage lang; mehrere: „3 neue Projekte: A, B und C · Ansehen“, das
  aufklappt, je mit „Rückgängig“; `NeueProjekte.tsx`). In der Akte des Projekts „Von Kingfisher angelegt. In 4 Mails
  seit … mit … · Rückgängig“. An der Quelle „Zugeordnet nach Absender · Ändern · Rückgängig“ (`SourceProject.tsx`;
  „Ändern“ führt zur Auswahl).
* **Rückgängig, und es kommt nicht wieder.** Das Projekt zurücknehmen (`POST …/vorschlaege/{kennung}/zuruecknehmen`,
  `projekt_automatik.zuruecknehmen`) löst genau Kingfishers eigene Zuordnungen (die des Vorschlags und die der
  Absenderregel), solange der Nutzer sie nicht selbst geändert hat: Jede andere Zuordnung (`EpisodeStore.link_project`
  ohne `automatisch`) ersetzt die automatische. Das Projekt verschwindet, wenn nichts anderes daran hängt, sonst
  bleibt es mit Satz. Danach gilt „abgelehnt“ samt Sperre: weder Projekt noch Frage kommen wieder; „Doch vorschlagen“
  in der Akte macht es wieder zur Frage, aber nie mehr automatisch. Ebenso sperrt das Zurücknehmen einer selbst
  angenommenen Akte die Automatik für diesen Namen. Eine Mail der Absenderregel löst `POST
  /api/v1/projekte/automatik/zuordnung/{episode_id}/zuruecknehmen` und sperrt sie für die Regel (404, wenn Kingfisher
  sie nicht selbst zugeordnet hat; 409, wenn sie inzwischen woanders liegt).
* **Personen ↔ Projekte, nur abgeleitet.** Gespeichert wird über Personen nichts. Wer zum Projekt gehört, ist, wer in
  seinen Quellen vorkommt (wie „Zusammenhänge“): Die Akte eines Projekts nennt unter dem Namen „Beteiligte: Anna
  Keller und Ben Braun“, die Akte einer Person „Projekte: Umbau Praxis“ (nur angelegte, keine bloßen Erwähnungen,
  höchstens drei Namen und „und N weitere“), das Personenprofil wie bisher unter „Wie verbunden?“.
* **Ablage** (Migration 25, nur Verweise und Zahlen): `projekt_automatik_anlagen` (Kennung, Projekt, Zeitpunkt, Grund
  als Anzahl, Tage, Daten, Arten und Sachen-Kennungen der Personen, zurückgenommen), `projekt_automatik_zuordnungen`
  (Quelle, Projekt, Art `akte` oder `absender`), `projekt_automatik_sperren` (`akte:<Kennung>`, `mail:<Quelle>`),
  `projekt_automatik_stand`. Namen liest jede Anzeige neu aus den Quellen.

Grenzen: Die Regel kennt nur, was die Einordnung als Projekt erwähnt; ohne Modell der Einordnung gibt es keine
Erwähnungen und damit keine neuen Projekte (die Absenderregel läuft trotzdem). Die strenge Absenderregel greift bei
Menschen, die über mehreres schreiben, selten; das ist gewollt (lieber keine als eine falsche Zuordnung). Protokoll:
[`runs/2026-10-26-automatik-projekte`](runs/2026-10-26-automatik-projekte/README.md).

### Aufgaben folgen der Post (Oktober 2026)

Stand der Korrektur vom 30.10.2026: `aufgaben_post.py` prüft nach jedem Takt der Mailaufnahme neue
Post deterministisch, ohne Modell und auch in der Pause. Ein Bezug zur Aufgabe beweist keine Erfüllung.

* **Erledigung nur nach Bestätigung.** Eine eigene Mail im genauen Verlauf der Aufgabenquelle oder an deren
  Gegenseite liefert den bestehenden Vorschlag **„Erledigt?“**. Auch tragende Wörter im Betreff, Text oder
  Anhangnamen belegen nur den möglichen Zusammenhang. Verneinungen, Absichten und bloße Antworten bleiben
  offen. Der Vorschlag beschreibt die Mail, ohne Unterlagenversand zu behaupten; auch ältere offene
  Vorschläge werden beim Anzeigen anhand der aktuellen Belege neu beschrieben. Nach Annahme lautet der
  Grund beispielsweise „Erledigt nach deiner Bestätigung zur Mail an Anna Berg vom 21. Oktober.“
* **Warten nur bei bekannter Adresse automatisch auflösen.** Eine eingehende Mail holt eine wartende
  Aufgabe zu „bei dir“ zurück, wenn ihre exakte Absenderadresse als Gegenseite bekannt ist und zusätzlich
  der genaue Verlauf oder tragende Wörter passen. Bekannt heißt: explizite Adresse im Wartestatus oder
  eine dazu passende Person der Aufgabenquelle; bei einer eigenen Quelle muss deren fremder Empfänger
  eindeutig sein. Ein widersprechender bekannter Absender gewinnt gegenüber einem gleichen Vornamen,
  selbst im selben Verlauf: dann kein Treffer und kein Vorschlag für diese Aufgabe. Ohne bekannte
  Adresse liefert ein passender Name höchstens **„Wieder bei dir?“**. Ohne Bezug bleibt auch eine
  bekannte Adresse ein Vorschlag. Fremde Mails erledigen nie eine Aufgabe, die bei dir liegt.
* **Quellen, Fristen und Rückgängig erhalten.** Entzogene oder ersetzte Aufgabenquellen und Mailbelege
  sind unbrauchbar; beim Anzeigen und Annehmen werden aktuelle Fassung und Belegdigest erneut geprüft.
  Fristen werden nicht verändert. Rundmails (mehr als fünf fremde Empfänger), seit über 90 Tagen
  überfällige Aufgaben und gleichrangige Treffer ändern keinen Wartestatus automatisch. Verlauf schlägt
  Person, mehr tragende Wörter schlagen weniger. Eine Mail von vor der Bitte zählt nicht.
  `POST /api/v1/tasks/{id}/rueckgaengig` stellt den vorigen Zustand wieder her, einschließlich Warten und
  Datum, und trennt Aufgabe und Mail dauerhaft (`aufgaben_post_getrennt`). Verwerfen trennt sie ebenfalls.
* **Jede Mail einmal.** Zeilenstand und geprüfte Mail bleiben in `tasks.sqlite3` gespeichert (Migration 4:
  `aufgaben_post_mails`, `aufgaben_post_getrennt`, `aufgaben_post_stand`), auch nach Neustart. Der erste
  Durchlauf setzt nur den Stand; der frühere Bestand wird nicht automatisch neu gedeutet oder korrigiert.

Die bestehenden Vorschlagsarten `ProposalKind.TASK_DONE` und `TASK_WAITING_RESOLVED` und Routen
`GET /api/v1/aufgaben-post/vorschlaege`, `…/{id}/annehmen`, `…/{id}/verwerfen` bleiben erhalten. Jede
Änderung steht im Logbuch (`aufgabe_post`: Kennungen und Zuordnungsart, kein Text) und in der Geschichte
(`post_completed`, `post_returned`, `post_undone`). Aufgabenliste, Akte unter „Braucht dich“ (14 Tage)
und Tageslage zeigen den Grund samt Rückgängig; die Tageslage fasst mehrere Änderungen in einer Zeile
zusammen. Die historische Automatikbeschreibung und ihr damaliger Nachweis stehen unter
[`runs/2026-10-21-aufgaben-post`](runs/2026-10-21-aufgaben-post/README.md); die damalige Zusage, dass
Wortüberschneidung eine automatische Erledigung rechtfertige, gilt seit dieser Korrektur nicht mehr.

### Aufgaben von selbst (26.10.2026)

Die Entscheidung aus [`66-automatik.md`](66-automatik.md): Eindeutige Bitten an dich und eigene Zusagen legt
Kingfisher selbst als Aufgabe an, mit Projekt, Person und Frist; unsichere bleiben Vorschläge, mit „Alle
übernehmen“. Eine Aufgabe ist Ablage, kein Fakt über einen Menschen; deshalb darf sie ohne Annahme entstehen,
aber nur so (`aufgaben_von_selbst.py`, nach jedem Takt der Mailaufnahme und nach jeder Aufgabenerkennung, ohne
Modell):

* **Eindeutig** heißt (`pruefen`, jede Bedingung mit ihrem Satz): eine Mail; die Aufgabenerkennung hat den Auftrag in
  der ganzen Mail geprüft (Bitte an den Empfänger oder eigene Zusage, Titel von der Textstelle getragen,
  `task_review.py`); die Mail ist **neu** nach `neu_eingegangen` (heute bis vorgestern) und kam nicht nur über die
  Bestandsaufnahme eines Postfachs, im Verlauf steht noch keine weitere Mail; eine **Bitte** richtet sich direkt an
  dich (du stehst unter „An“, nicht nur in Kopie) und kommt nicht von einem Sammel- oder Absenderpostfach
  (`people_quality.ist_sammelpostfach`); eine **Zusage** ist deine eigene Mail an jemanden; höchstens drei
  Empfänger, kein Newsletter („abbestellen“); dieselbe Aufgabe gibt es noch nicht (Quelle und Titel oder Textstelle,
  oder ein offener gleichlautender Titel); du hast sie nicht schon einmal zurückgenommen. Höchstens zehn je
  Durchlauf; der Rest bleibt Vorschlag. Jeder Vorschlag wird einmal geprüft (Migration 5:
  `aufgaben_auto_geprueft` mit dem Ergebnis als Kürzel). Das erste Einlesen eines Postfachs erzeugt deshalb keine
  einzige Aufgabe.
* **Zugeordnet.** Person: wer bittet, bei einer Zusage der erste fremde Empfänger unter „An“ (`Task.person`, Adresse
  und Name; die Adresse führt zur Akte). Projekt: das Projekt der Quelle, sonst die Absenderregel, sonst ein
  gemerkter lokaler Hinweis (`task_project_hints.py`), nur vorhandene offene Projekte. Frist: nur, wenn die Textstelle
  genau eine eindeutige Angabe nennt (`fristen.py`, 23:59 Uhr dieses Tages).
* **Sichtbar und zurücknehmbar.** Die Aufgabe trägt `angelegt` (`art: automatisch`, Satz „Von Kingfisher angelegt,
  weil Anna Berg dich am 28. September darum gebeten hat.“, Grundsatz, Mail) und zeigt in Liste und Detail „Von
  Kingfisher angelegt · aus der Mail von Anna Berg vom 28. September · Rückgängig“. Zurücknehmen
  (`POST /api/v1/aufgaben-von-selbst/{id}/rueckgaengig`) entfernt die Aufgabe (die Geschichte behält
  `auto_removed`), legt den Vorschlag als verworfen ab und merkt sich Quelle, Titel und Textstelle
  (`aufgaben_auto_zurueck`): Dieselbe Bitte kommt nicht wieder, auch nicht als neuer Vorschlag aus derselben Mail.
  „Rückgängig“ im Hinweis stellt sie unverändert wieder her (`…/wiederherstellen`).
* **Heute** fasst zusammen: „3 Aufgaben aus der Post angelegt. Ansehen · Rückgängig“ (`GET
  /api/v1/aufgaben-von-selbst/heute`), nicht jede einzeln; das Logbuch sagt es in einem Satz (`aufgabe_post` mit
  `sorte: angelegt`, kein Text). Die Übernahme auf Heute und im Mail-Briefing nimmt den Projekthinweis mit statt
  „ohne Projekt“ (`zuordnung_aus_vorschlag`).
* **Vorschläge** zeigen Projekt, Person und Frist schon vorbefüllt (`person_vorschlag`, `frist_vorschlag`); „Alle N
  übernehmen“ nimmt die sichtbaren in einem Klick (`POST /api/v1/task-candidates/alle-uebernehmen`), der Hinweis
  nimmt die ganze Gruppe mit „Rückgängig“ zurück (`…/gruppe/{gruppe}/rueckgaengig`; die Vorschläge stehen dann
  wieder offen da, nichts gilt als verworfen).
* **Schalter** „Aufgaben aus Mails selbst anlegen“ unter „Was Kingfisher darf“, Vorgabe an
  ([`47-einstellungen.md`](47-einstellungen.md#aufgaben-aus-mails-selbst-anlegen-26102026)). Aus: nichts entsteht.

Protokoll: [`runs/2026-10-26-automatik-aufgaben`](runs/2026-10-26-automatik-aufgaben/README.md).

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
| `PUT /api/v1/akten/entscheidung` | `{sache, ziel, entscheidung: erledigt|gilt_nicht|offen}`; nur Ziele dieser Akte (sonst 404) |
| `DELETE /api/v1/akten/entscheidung?sache=&ziel=` | Entscheidung zurücknehmen (404, wenn keine da ist) |
| `GET /api/v1/akten/vorschlaege` | offene Vorschläge „Neue Akte?“ mit Grund und Textstellen (Prüfung; die Oberfläche zeigt nie eine Liste) |
| `POST /api/v1/akten/vorschlaege/{kennung}/annehmen` | Projekt anlegen, Quellen ohne Projekt zuordnen; Antwort: Akte (Link) und Satz; 404 unbekannt, 409 schon angenommen |
| `POST /api/v1/akten/vorschlaege/{kennung}/ablehnen` | „Nein danke“ merken (409, wenn schon entschieden) |
| `POST /api/v1/akten/vorschlaege/{kennung}/zuruecknehmen` | Entscheidung zurücknehmen: Zuordnungen lösen, Projekt entfernen, wenn nichts anderes daran hängt (404 ohne Entscheidung); bei einer Anlage durch Kingfisher nur dessen eigene Zuordnungen, danach gemerkt |
| `GET /api/v1/projekte/automatik` | was Kingfisher in den letzten drei Tagen selbst angelegt hat: Name, Akte, Zahl, Personen, Grund (für die eine Zeile auf Heute) |
| `POST /api/v1/projekte/automatik/zuordnung/{episode_id}/zuruecknehmen` | eine automatische Zuordnung lösen und die Mail für die Absenderregel sperren (404 nicht automatisch, 409 inzwischen geändert) |
| `POST /api/v1/tasks/{id}/rueckgaengig` | Änderung durch die Post zurücknehmen (404 unbekannt, 409 nichts zurückzunehmen) |
| `GET /api/v1/aufgaben-post/vorschlaege`, `POST …/{id}/annehmen`, `POST …/{id}/verwerfen` | „Erledigt?“ und „Wieder bei dir?“ (404 unbekannt, 409 entschieden oder überholt) |

Jede Anfrage führt die Bezüge kurz nach (höchstens 1,5 s); den Rest rechnet ein
Hintergrundfaden zu Ende. Die Antwort nennt `berechnung.offen`, statt zu tun, als wäre
alles da; die Oberfläche lädt dann still nach.

## Oberfläche

Die Akte beginnt mit **Auf einen Blick** (vermutlich offen, nächste Frist, nächster
Termin, zuletzt), darunter **Braucht dich**, die Lage, der **Zeitstrahl**, dann Offen (nach
Richtung gruppiert, je Punkt „Erledigt“), Fristen, Termine, Stand, Angenommen, Aufgaben,
„Über …“ (Kreis, Geburtstag, Art, Wiederkehrendes) und **Zusammenhänge**; der Verlauf ist
eingeklappt. Jede Entscheidung antwortet unten mit einer Meldung und „Rückgängig“.

**Ein Satz Stand** (Oktober 2026, `akteAnzeige.ts`, `standSatz`) steht unter dem Namen statt der Zeile „Auf einen
Blick“: ohne Modell aus Feldern, die die Akte schon liefert. Die jüngste Zeile unter „Stand“ mit Art, Tag (Quelldatum,
sonst „erfasst am“), Titel der Quelle und Absender („Änderung am 17.9.: Absage Workshop am 28. Oktober (Silke Vogt).“;
in der Akte dieser Person ohne den eigenen Namen), ohne Stand die jüngste Quelle bis heute („Zuletzt am 16.9.: Termin
…“). Dazu höchstens ein Nächstes: „2 Punkte brauchen dich.“, sonst ein vermutlich abgesagter nächster Termin, sonst die
frühere von nächster Frist und nächstem Termin. Der Titel öffnet die Quelle unter dem Kopf. Ohne Datiertes bleibt „Auf
einen Blick“. Was der Satz nennt, wiederholt „Stand“ nicht (nur „Vor dem 17.9.2026 (2)“ aufklappbar; ohne Früheres
fällt der Abschnitt weg), und ein abgesagter Termin, der unter „Braucht dich“ steht, steht unter „Termine“ nur als
leise Zeile ohne Zitat. Zählungen und Logik der Akte ändern sich dadurch nicht. Unter 700 px steht das Bild (56 px)
über dem Namen, der Name hat die volle Breite. Tests: `tests/akte-stand-satz.test.mjs`.

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
| B3 | Zuordnung des Nutzers gilt für den Text; Entscheidung über einen anderen Text ist veraltet | `test_bezuege` |
| B4 | Entzug entfernt den Bezug sofort | `test_bezuege`, `test_akten_routes` |
| B5 | Eigene Adresse ist keine Sache | `test_bezuege` |
| B6 | Änderung der Quelle führt zur Neuberechnung | `test_bezuege` |
| B7 | Neue gleichnamige Adresse macht die Zuordnung wieder offen (Verzeichnis-Kennung) | `test_bezuege` |
| B8 | Projektzuordnung ist ein Ankerbezug | `test_bezuege`, `test_akten_routes` |
| B9 | Terminort ist ein Ortsbezug; trägt sein erster Teil den Namen einer über eine Adresse beteiligten Organisation, gehört er zu ihr; Ortsnamen und Modell-Erwähnungen nicht; nur Termine werden neu berechnet | `test_bezuege` |
| B10 | Entscheidung des Nutzers überlebt Projektzuordnung, Archiv, nachgetragene Kontakte, Kopfzeilen und Anhangberichte (auch ohne Quellenschlüssel, auch im Kreis) | `test_bezuege`, `test_kreis` |
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
