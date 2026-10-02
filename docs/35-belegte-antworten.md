# Suchen von oben und unten, belegte Antworten in Sätzen (Etappen E2 und E3)

Stand: 30. September 2026. Umsetzung von E2 und E3 aus
[`27-schichten-und-fragen.md`](27-schichten-und-fragen.md). Code: `akten_kontext.py`
(E2), `satzantwort.py` und `relative_zeit.py` (E3), gezielte Haken in
`working_memory_answers.py`, `source_candidates.py`, `akten.py`, `akten_routes.py`,
`agent.py`; Oberfläche `SatzAntwort.tsx`. Tests: `test_akten_kontext.py`,
`test_satzantwort.py`, `test_relative_zeit.py`, `messlatte/tests/test_antwort_saetze.py`,
`messlatte/tests/test_ungekennzeichnet.py`. Browserprobe: `scripts/probe_satzantwort_ui.py`.

## E2: Suchen von oben und unten

**Von unten** bleibt, was es war: Wortsuche, Volltextindex (C2), Umschreibungen (E1).
**Von oben** kommt dazu: Nennt die Frage Sachen, die sich **eindeutig** auflösen lassen
(`akten_kontext.sachen_finden`: eine Person mit genau einer Adresse für den Namen; eine
Organisation, ein Projekt oder ein Ort, dessen Kennung der Name ist), liefert ihre Akte
bevorzugte Quellen: aktuellen Stand, kommende Fristen und Termine, vermutlich Offenes.
Sie sind eine **dritte Liste der Rangfusion** (`source_candidates.zusammenfuehren`, Gewicht
1), kein Vorspann. Zwei Namensvettern lösen nichts auf (sonst kämen die Quellen des falschen
Alex Winter als „bevorzugt“ in den Kontext). Themen sind zu breit und zählen nicht.

**Überholtes wird gekennzeichnet, nie still entfernt.** Für die gefundenen Quellen fragt
`akten_kontext.aufbauen` die Akten aller Sachen, zu denen sie gehören. Führt eine Akte eine
Angabe der Quelle als überholt (Frist ersetzt, Stand „vorher“, durch Absage oder Erledigung
abgelöst, Termin abgesagt), trägt die Zeile der Quelle im Kontext des Modells das Feld
`ueberholt` (überholte Angabe, neue Angabe, neue Quelle mit ihrer Kennung) und steht **hinter**
den unmarkierten (die Kennungen S1… bleiben, das Modell wählt weiter über sie). Die Anweisung
nennt, was das Feld heißt. Auch der Zitatmodus zeigt solche Quellen hinten und mit „überholt“,
mit dem neuen Wert und der neueren Quelle.

Dazu musste die Akte (D2) etwas lernen: Eine Ausschreibung nennt ihre Frist als **Angabe**
(`fact`/`status`), nicht als Bitte, und stand deshalb nie unter „ersetzt“. Jetzt zählt eine
Angabe mit **Fristwort** („Einreichfrist“, „Anmeldeschluss“), wenn eine spätere Zusage, Bitte
oder Änderung denselben Gegenstand (dieselben Wortstämme wie bei jeder Frist, ohne das bloße Wort „Frist“) mit anderem Datum nennt; sonst wäre jedes Datum in jeder
Angabe eine Frist. Sie erscheint nur unter „ersetzt“ (`AKTEN_VERSION` 2, der Zwischenspeicher
rechnet neu).

**Reproduzierbar.** Alles hängt nur von Bestand, Akten und dem Tag ab (nicht von der Uhrzeit).
Der Fingerabdruck (`Kontext.signatur`: bevorzugte Quellen, Kennzeichnungen, Sachen) steht in
der Antwort (`answer['akten']`, `answer['akten_sachen']`); die Frischeprüfung rechnet ihn
neu (`_akten_frisch`). Eine fremde neue Mail ändert die Akten dieser Sache nicht, eine neue
Frist zur Sache schon (beides Tests). Ohne Zugang zu den Akten gilt eine Antwort mit Akten als
veraltet (fail-closed). Der Zugang hängt am Speicher (`episodes.akten_zugang`, gesetzt in
`akten_routes.verbinden`); ohne ihn verhält sich alles wie vor E2. Die Bezüge werden vor einer
neuen Antwort höchstens alle 3 Sekunden nachgeführt (sonst kostete jede Frage rund 60 ms für
die Prüfung, ob etwas Neues da ist).

### Frische und „Ranking-Drift“: nicht gelockert, begründet

Geprüft wurde, `_fresh` an die genutzten Belege statt an die ganze Kandidatenliste zu binden.
Die Liste wird verglichen, weil sie mehr sichert als die Belege: neue Mitglieder eines
genannten Projekts (`_project_members`), neue Treffer des Volltextindex, die die Wortsignatur
nicht sieht (Wortteile, Zerlegung), und Quellen, die durch die Rangfusion neu hineinrutschen.
Ersetzte man den Listenvergleich durch „jeder genutzte Beleg unverändert“, müssten
Projektmitglieder, Indexmenge und Personenquellen je eine eigene Signatur bekommen; ohne sie
bliebe „Was gibt es Neues zu Mainz?“ nach einer neuen Projektmail „frisch“. Das senkt die
Sicherheit, und ein gebrochener Vergleich fällt nicht auf. **Nicht umgesetzt.** Neu ist nur,
dass der Akten-Anteil (Kennzeichnung, bevorzugte Quellen) rangunabhängig gesichert ist
(Fingerabdruck über Inhalte, nicht Ränge) und deshalb selbst nicht kippt. Die Drift bleibt ein
Ärgernis der Bestandsgröße (siehe `29-suchindex.md`), kein Sicherheitsproblem.

### Die Zwölfergrenze: Entscheidung nach Messung

Messlatte, Regel-Einordnung, ohne Modell, Abruf. „Plätze“ sind Abschnitte im Kontext der
Auswahl, das Budget die Zeichen des Kontexts.

| Plätze / Budget | 0 Rauschen: Belege (von 136) | Fragen komplett (von 71) | Kontext Zeichen (Mittel) | Quellen im Kontext | 10.000 Rauschen: Belege | komplett | Kontext | Abruf je Frage, Median |
|---|---|---|---|---|---|---|---|---|
| 12 / 24.000 | 121 | 62 | 16.183 | 11,8 | 105 | 54 | 14.633 | 0,92 s |
| **16 / 32.000** | **124** | **64** | **20.021** | 15,5 | **109** | **57** | **17.628** | 0,91 s |
| 20 / 40.000 | 127 | 66 | 23.697 | 19,3 | 111 | 57 | 20.592 | 0,93 s |
| 16 / 24.000, 20 / 24.000 | 124, 127 | 64, 66 | wie oben | | | | | |

**Entscheidung: 16 Plätze und 32.000 Zeichen** (`MAX_REFS`, `MAX_CONTEXT`). Gegenüber 12
kommen 3 bis 4 Belege und 3 Fragen mehr vollständig an, bei rund 20 % mehr Kontext; 20 Plätze
bringen nur 2 weitere bei nochmals 20 % mehr. Die Suchzeit ändert sich nicht messbar. Was die
Messlatte **nicht** zeigt: Ihre Quellen sind kurz (im Mittel rund 600 Zeichen), das Budget
greift dort nie (16/24.000 und 16/32.000 ergeben dasselbe). Echte Mails haben 2 bis 4 KB, und
jede Zeile trägt die ganze Quelle als Kontext: Mit dem alten Budget passten dann nur 6 bis 8
Quellen, gleich wie viele Plätze es gibt. Die Modellzeit wächst mit dem Kontext (rund 1,2× für
16/32.000); sie ist mit einem echten Modell auf dem Zielgerät zu messen, nicht hier.

### Messung E2

Welt v1, 77 Fragen, ohne Modell. „vorher“ ist derselbe Code mit `--ohne-akten` und 12 Plätzen
(Stand von D3), „nachher“ der Stand dieses Pakets. Die Regel-Einordnung
(`--einordnung regel`, Schlüsselwörter der Stufe Akten) gibt den Absätzen Arten wie Änderung
und Zusage; ohne sie kennen die Akten nichts Überholtes (bei konstanter Einordnung bleibt alles
ungekennzeichnet). **Grenze:** Gemessen wird bei gegebener Einordnung, nicht die Qualität der
Modelleinordnung.

| Kennzahl | 0: vorher (regel) | nachher | 10.000: vorher | nachher |
|---|---|---|---|---|
| Erwartete Belege gefunden (von 136) | 120 | 124 | 105 | 109 |
| Fragen mit allen Belegen (von 71) | 61 | 64 | 54 | 57 |
| Belege bis Rang 12 | 105 | 106 | 90 | 90 |
| Fragen mit verbotenen Belegen im Kontext (von 77) | 21 | 21 | 18 | 18 |
| verbotene Belege, gezählt je Beleg | 36 | 37 | 29 | 32 |
| **Fragen mit verbotenen Belegen ungekennzeichnet** | 21 | **15** | 18 | **13** |
| **verbotene Belege ungekennzeichnet** | 36 | **27** | 29 | **23** |
| Rückfragen mit allen Bedeutungen (von 7) | 7 | 7 | 7 | 7 |
| Unnötige Rückfragen | 0 von 70 | 0 von 70 | 0 von 70 | 0 von 70 |
| Fragen im freien Chat | 1 | 1 | 1 | 1 |
| Kontext der Auswahl, Zeichen (Mittel) | 15.718 | 20.021 | 14.275 | 17.628 |
| Abruf je Frage, Median / P95 | 0,07 / 0,12 s | 0,10 / 0,16 s | 0,81 / 1,57 s | 0,83 / 1,62 s |

Mit konstanter Einordnung (die Messlatte-Vorgabe, keine Arten): 123 statt 121 Belege und 63 statt
62 komplette Fragen ohne Rauschen, 106 statt 103 und 55 statt 53 mit 10.000 (Plätze und Akten),
verbotene Belege unverändert (21 und 18 Fragen), Kennzeichnung erwartungsgemäß null.

Die Zahl **verbotener Belege im Kontext bleibt gleich oder wächst leicht** (mehr Plätze,
nichts wird entfernt). Die gefährliche Größe ist die **ungekennzeichnete**: sie sinkt von 21
auf 15 Fragen (36 auf 27 Belege), mit Rauschen von 18 auf 13 (29 auf 23). Was bleibt, ist nicht
„überholt“ im Sinne der Akte: Namensvettern (`namensgleich-*`), Quellen außerhalb des
gefragten Zeitraums (`zeitraum-*`), ältere Fassungen ohne gemeinsamen Gegenstand
(`meeting-protokoll-*`, `terminvorbereitung-04`), Fallen (`falle-*`). Und `frist-verschoben-01`:
Die Notiz zum Förderantrag hat ohne Modell keinen Bezug zur Stiftung, also keine Akte, in der
ihre Frist als ersetzt stünde. Ein Modell der Einordnung mit Erwähnungen würde sie verbinden;
das ist hier nicht messbar.

Ein Aufschlag von rund 0,03 s je Frage ohne und praktisch keiner mit Rauschen (Median) kommt
aus den Akten; ein Profil bei 3.000 Rauschquellen zeigte rund 25 % Mehrzeit, davon die Hälfte
Nachführen der Bezüge (jetzt gedrosselt) und der Rest das Lesen der Akten.

## E3: Belegte Antwort in Sätzen

Das Modell der Rolle `antwort` (der Standardanbieter der Gedächtnisfrage) bekommt **nach**
der Auswahl der Quellen einen zweiten Auftrag: höchstens fünf Sätze aus den gewählten Quellen
und den Zeilen der Akte, als JSON `{"saetze":[{"text","belege":[…]}],"status":
"antwort|nichts_vorliegend|unklar"}`. Jeder Satz läuft durch `satzpruefung.py` (Zahlen, Daten,
Uhrzeiten, Namen, Kennungen, Zusagen, Verneinung gegen die genannten Belege). Verworfene Sätze
entfallen, ihre Zahl steht in der Antwort. Der Zitatmodus bleibt der Rückfall, nie eine
unbelegte oder leere Antwort:

| Lage | Ergebnis |
|---|---|
| mindestens ein Satz besteht | Sätze mit Belegnummern; darunter Belege, „Aus der Akte“, Zahl der verworfenen Sätze |
| kein Satz besteht, Modell fällt aus, ungültiges JSON, Werkzeugaufruf, Status `unklar`, Widerspruch, nicht lokales Modell | Zitatmodus (Originalwortlaut), der Grund steht in `answer['satzantwort']` |
| Status `nichts_vorliegend` ohne Sätze | „Dazu liegt in den bisher eingeordneten Quellen keine Information vor.“ plus die geprüften Titel, Status `working_unknown` (Kategorie falle) |
| Auswahl unklar (Rückfrage), bestätigte Einträge, Klick auf eine Auswahl | wie bisher (keine Sätze) |

**Aktualität.** Eine überholte Angabe wird nie als Stand genannt: Ein Satz, der einen Beleg
mit Kennzeichnung nennt (bei Fristen: der die überholte Angabe nennt), besteht nur, wenn er
zugleich die neuere Quelle nennt und den Wandel benennt („verschoben“, „vorher“, „bisher“ …).
Ist eine gewählte Quelle überholt und erzählt kein Satz den Wandel, ergänzt das Programm ihn
wörtlich aus der Akte („Die Frist gilt jetzt für 12. November 2026; vorher hieß es 15. Oktober
2026.“), durch dieselbe Prüfung; besteht auch das nicht, gilt der Zitatmodus. Beispiel aus der
Welt (Browserprobe): „Die Einreichfrist wurde von 15. Oktober 2026 auf 12. November 2026
verlängert. [1][2]“ mit Beleg 2 als „überholt durch [1]: 15. Oktober 2026 → 12. November 2026“.

**Relative Zeit.** „morgen“, „nächste Woche“ und Verwandte (geschlossene Liste in
`relative_zeit.py`) gelten nur, wenn sie gegen den Stichtag aufgelöst sind und der Beleg den
Tag trägt. Ein einzelner Tag steht danach in Klammern im Satz („Morgen (30.09.2026) um 14 Uhr
…“) und läuft als Datum durch die Prüfung; ein Zeitraum besteht, wenn der Beleg einen Tag darin
trägt. Das Datum in Klammern bleibt, damit die gespeicherte Antwort morgen nicht falsch wird.
Am nächsten Tag besteht derselbe Modellsatz nicht mehr (Test). „demnächst“ und Ähnliches
bleiben unaufgelöst.

**Datensparsamkeit.** Das Modell sieht nur die gewählten Quellen und die Zeilen der Akte, nie
die übrigen Kandidaten (Test). Absätze, die sich an ein Modell wenden („Hinweis an
KI-Assistenten …“), werden bereinigt und stehen weder im Aufruf noch in der Prüfung. Nur lokale
Anbieter: `prepare` gibt für ein Cloudmodell in der Rolle `antwort` weiterhin nichts heraus
(Gedächtnisantworten sind `local_only`), und `formulieren` fragt nur lokale Anbieter. Es gibt
keinen neuen Weg für Daten an eine Cloud; die Egress-Kennzeichnung der Gesprächsnachricht
(`history_egress: local_only`) bleibt unverändert, gespeichert sind Sätze und Verweise, nie
Quelltext.

**Gespeichert und beim Anzeigen erneut geprüft.** `answer['satzantwort']` hält Sätze, Verweise,
Zählungen. Beim Anzeigen liest `wiederherstellen` jeden Beleg neu und prüft jeden Satz mit dem
gespeicherten Stichtag erneut; fehlt eine Quelle, ist ein Satz verändert oder besteht nicht
mehr, gilt der Zitatmodus.

**Oberfläche.** Die Gesprächsansicht zeigt Sätze ruhig mit kleinen Belegnummern. Eine Nummer
öffnet „Weg nach unten: Akte und Quellen“: Aus der Akte (Stand, Frist, wörtlich), die Belege im
Wortlaut mit dem Hinweis „überholt durch [n]“, je Beleg die Quelle. Angezeigt werden nur Belege,
auf die ein Satz sich stützt (fortlaufend nummeriert). Geprüft im echten Chromium (Fake-Modell,
Welt der Messlatte): Sätze, Nummern, Aufklappen per Klick, ehrliches „nichts liegt vor“,
Zitat-Rückfall; die Konsole blieb leer. Die Bilder liegen nicht im Repository
(`scripts/probe_satzantwort_ui.py --ausgabe DIR` erzeugt sie neu).

### Messung E3, was ohne Modell messbar ist

Die Stufe „Antwort“ (`--modell`) misst mit einem echten Modell Sätze, Vollständigkeit und
falsche Aussagen. Ohne Modell ist die **Mechanik** prüfbar, mit dem Skriptmodell der Tests
(`messlatte/tests/test_antwort_saetze.py`, echter Antwortpfad über die Konversations-API):

* sorgfältiges Skript: ein Satz mit Beleg, Klasse „richtig“, keine falsche Aussage;
* unaufmerksames Skript, das die alte Frist nennt: die Satzprüfung verwirft den Satz (die
  Quelle ist überholt), es gilt der Zitatmodus; bestünde er, erkennt die Bewertung die falsche
  Aussage (beide Zweige im Test);
* erfundene Zahl: verworfen, Zitatmodus;
* nichts liegt vor: `working_unknown`, erkannt als `nicht_bekannt`.

Die Bewertung liest bei einer Satzantwort die Belege aus dem, worauf die Sätze sich stützen,
nicht aus allem, was das Modell sah. **Nicht messbar ohne Modell:** ob echte Modelle brauchbare
Sätze schreiben, wie oft sie `nichts_vorliegend` zu Unrecht sagen (dann fehlt eine Antwort, die
der Zitatmodus geliefert hätte), und die Antwortzeit des zweiten Aufrufs. Die Messlatte führt
dazu `kontext_zeichen` (Auswahl) und `satz_zeichen` (Sätze).

## Antwortzeit

Auf dem Zielgerät (M2 Max) wusste niemand, ob der zweite Modellaufruf 2 oder 20 Sekunden kostet. Jetzt misst
jede Gedächtnisantwort sich selbst (`zeitmessung.py`, ein kleiner Sammler je Antwort, weitergereicht, kein
gemeinsamer Zustand). Abschnitte in Sekunden: `frage` (Frage verstehen; die Dauer reist als `dauer_s` an der
`Anfrage` vom Server in die Antwort), `suche` (Kandidaten, Akten, Kontext), `antwort_modell` (erster Aufruf, Quellen
wählen), `saetze_modell` (zweiter Aufruf), `satzpruefung` und `gesamt`. Ein Abschnitt, der nicht lief, fehlt (nie
„0“). Die Zahlen stehen in `answer['zeiten']` und damit im gespeicherten Gespräch, nie mit Frage oder Text; eine
Auswahl aus früheren Quellen (`choose`) trägt keine, weil dort kein Modell lief.

* **Zeile unter der Antwort:** „3,2 s · Suche 0,3 · Sätze 2,1“, klein, ohne Farbe, nur mit vorhandenen Zeiten. Über
  8 s (`LANGSAM_S` in `antwortzeit.ts`, gleich dem Ziel der Messlatte) steht ein Satz mit der Ursache, etwa „Der zweite
  Modellaufruf für die Sätze brauchte 12 s.“
* **Protokoll:** Einstellungen, Lokale KI, „Antwortzeit“: Median und 90-Prozent-Wert je Abschnitt über die letzten 50
  Antworten, dazu die Modelle der Rollen `frage` und `antwort`. Quelle sind die gespeicherten Gespräche
  (`ConversationStore.antwortzeiten`, `GET /api/v1/antwortzeiten`, `zeiten_routes.py`); es gibt keinen neuen Speicher.
* **Schalter „Antworten in Sätzen formulieren“** (Vorgabe an) an derselben Stelle: `PUT /api/v1/models/saetze`,
  Einstellung `antwort_saetze`. Aus heißt Zitatmodus ohne zweiten Modellaufruf. Der Schalter setzt `Agent._saetze`
  (`agent_verdrahtung.verdrahte_zusaetze`), also dieselbe Stelle wie bisher, und baut den Agenten neu.
* **Messlatte:** `lauf` und `lokal` berichten Median und 90-Prozent-Wert für Abruf, Antwort (warm) und die Abschnitte des
  Produkts und schreiben „Antwortzeit im Ziel: ≤ 8 s Median“ mit bestanden oder nicht bestanden, wenn ein Modell lief
  (sonst „nicht gemessen“).

Entscheiden nach der Messung: Liegt der Median über dem Ziel und ist `saetze_modell` der größte Teil, den Schalter
ausschalten; die Antworten zeigen dann die Belege wörtlich. Browserprobe: `scripts/probe_antwortzeit_ui.py --ausgabe DIR`
(Modell mit absichtlicher Wartezeit; Zeile, Ursache, Tabelle, Schalter, leere Konsole).

## Neue Kennzahlen der Messlatte

Bericht und JSON führen jetzt getrennt: Fragen und Belege mit verbotenen Belegen **gesamt** und
**ungekennzeichnet** (der Kontext nennt die Quelle nicht als überholt), Kontextgröße (Mittel,
Median, Höchstwert, Quellen) und, je Frage, die Zählung der Akten. Neue Schalter für Versuche:
`--einordnung regel`, `--ohne-akten`, `--plaetze N`, `--kontext-zeichen N`.

## Sabotageproben

Jede Zusicherung wurde absichtlich gebrochen (ein Ausdruck im Code ersetzt), die Tests der
beiden Etappen liefen, dann wurde zurückgesetzt (18 von 18 gefangen; das Skript liegt nicht im
Repository, die Ausdrücke stehen in `akten_kontext.py`, `satzantwort.py`,
`working_memory_answers.py`, `messlatte/bewertung.py`).

| Nr. | Bruch | scheiternde Tests | davon |
|---|---|---|---|
| S1 | Überholtes wird im Kontext nicht gekennzeichnet | 1 | `test_das_modell_bekommt_ueberholtes_gekennzeichnet_und_nachrangig` |
| S2 | Überholtes steht nicht nachrangig | 1 | `test_gekennzeichnetes_steht_nachrangig_und_nichts_faellt_weg` |
| S3 | Überholte Angabe ohne Wandel und neue Quelle als Stand erlaubt | 2 | `test_ueberholte_frist_als_stand_wird_verworfen_…`, `test_ohne_wandelwort_oder_ohne_neue_quelle_…` |
| S4 | Satzprüfung wirkt nicht (erfundene Zahl besteht) | 8 | `test_erfundene_zahl_wird_verworfen_…` und 7 weitere |
| S5 | Kein Rückfall auf Zitate, wenn kein Satz besteht | 3 | `test_erfundene_zahl_wird_verworfen_…`, zwei Fälle von `test_jeder_fehler_des_modells_…` |
| S6 | „Nichts liegt vor“ wird zu Zitaten | 2 | `test_nichts_liegt_vor_sagt_die_antwort_ehrlich_…`, `test_nichts_vorhanden_wird_zur_ehrlichen_antwort_…` |
| S7 | Relative Zeit ohne Auflösung gegen den Stichtag | 1 | `test_relative_zeit_gilt_nur_gegen_den_stichtag_…` |
| S8 | Zeitraum ohne Beleg für einen Tag darin | 1 | `test_relative_zeit_ohne_beleg_fuer_den_tag_wird_verworfen` |
| S9 | Sätze werden beim Anzeigen nicht erneut geprüft | 1 | `test_gespeicherte_saetze_werden_beim_anzeigen_erneut_geprueft` |
| S10 | Frische ignoriert die Akten | 1 | `test_ohne_zugang_zu_den_akten_gilt_eine_antwort_mit_akten_als_veraltet` |
| S11 | Anweisungen an das Modell werden nicht geschwärzt | 1 | `test_absaetze_die_das_modell_anweisen_werden_geschwaerzt_…` |
| S12 | Cloudmodell wird gefragt | 1 | `test_ein_cloudmodell_bekommt_nichts_…` |
| S13 | Wandel wird nicht ergänzt | 1 | `test_ueberholte_frist_als_stand_wird_verworfen_…` |
| S14 | Zitatmodus nennt Überholtes nicht | 1 | `test_auch_im_zitatmodus_steht_das_ueberholte_hinten_und_sagt_es` |
| S15 | Fingerabdruck ignoriert die Kennzeichnungen | 1 | `test_eine_neue_frist_aendert_den_fingerabdruck_…` |
| S16 | Messlatte zählt Gekennzeichnetes nicht ab | 2 | `test_gekennzeichnete_verbotene_belege_zaehlen_…`, `test_ist_alles_gekennzeichnet_…` |
| S17 | Antwort zeigt Belege, die kein Satz benutzt | 2 | `test_die_antwort_zeigt_nur_belege_…`, `test_sorgfaeltiges_modell_ergibt_…` |
| S18 | Mehrdeutiger Name löst eine Sache auf | 1 | `test_sachen_finden_loest_nur_eindeutige_namen_auf` |

Die fehlende Egress-Zusicherung „nur lokal“ für die Auswahl selbst prüfen die bestehenden Tests
von `prepare`; der neue Test deckt beide Aufrufe ab.

## Offene Punkte

* **Qualität mit echtem Modell** (Sätze, zu vorsichtiges `nichts_vorliegend`, Zeit des zweiten
  Aufrufs) ist auf dem Zielgerät zu messen; bis dahin ist der Zitatmodus der sichere Weg
  (der Schalter unter Einstellungen, Lokale KI, schaltet die Sätze ab; siehe „Antwortzeit“).
* **Überholtes erkennt die Akte** mit Wortstämmen und Fristwörtern; wo Ebene 1 keine Art
  vergibt oder eine Quelle keiner Sache zugeordnet ist, bleibt sie ungekennzeichnet (Zahl oben).
  Namensvettern und Zeiträume kennzeichnet seit dem Nachtrag [`39-kennzeichnung.md`](39-kennzeichnung.md) der
  Kontext ebenfalls (ungekennzeichnet 15 auf 8, mit 10.000 Rauschquellen 13 auf 8); „ältere Fassung ohne
  gemeinsamen Gegenstand“ und Fallen kennzeichnet weiter nichts, dort entscheidet das Modell der Auswahl.
* **Kontextbudget:** Echte Mails sprengen 32.000 Zeichen bei 16 Quellen; eine zweistufige
  Auswahl (erst Titel und Abschnitt, dann Volltext) wäre der nächste Schritt.
* **Frische** siehe oben (Ranking-Drift bleibt).
* Die Bezüge werden höchstens alle 3 Sekunden nachgeführt; eine Mail von eben fehlt der Akte
  bis dahin.

## Zweistufige Auswahl für lange Quellen

Stand: 30. September 2026. Code: `absatzauswahl.py` (neu), Haken in `working_memory_answers.py`
(`_candidates`, `_akten_zugaben`, `prepare`), `satzantwort.py` (Belege), `akten_kontext.py` (`stellen`);
Messlatte: `lange.py`, `abruf.py`, `bewertung.py`, `bericht.py`. Tests: `test_absatzauswahl.py`,
`test_absatzauswahl_saetze.py`, `messlatte/tests/test_lange.py`, `test_kontext_abgeschnitten*.py`.
Berichte: `docs/evaluations/messlatte/2026-09-30-zweistufig-*`.

**Das Problem.** Jede Zeile der Auswahl trug die ganze Quelle als `context`. Die Welt der Messlatte hat kurze Quellen
(Mails im Mittel unter 300 Zeichen); echte Mails haben 2 bis 4 KB, Transkripte mehr. Dann ist das Budget nach zehn
Quellen voll, der Rest fällt weg, und das Modell liest Signatur, Haftungsausschluss und zitierte Vor-Mails mit.

**Zuerst messbar gemacht** (eigene Schritte davor): Kennzahl „Kontext abgeschnitten“ (erwartete Quellen, die gefunden,
aber vom vollen Budget verdrängt wurden; getrennt von „nicht gefunden“ und von „wegen Länge nie eingeordnet“),
„erwartete Belege im Kontext ohne tragende Textstelle“ (keine Pflichtaussage, die der Volltext der Quelle trägt, mehr zu
sehen) und `--lange-quellen` (jede Mail, auch im Rauschen, auf 3.000, jedes Transkript auf 30.000 Zeichen: Signatur,
Haftungsausschluss, zitierte Vor-Mail, Small Talk; der Originaltext bleibt wörtlich, die Pflichtaussagen stehen in
denselben Quellen wie vorher, deterministisch je Startwert).

**Die zweite Stufe.** Quellen bis 1.500 Zeichen bleiben ganz. Längere gehen als Auszug ins Modell:

| Teil | Regel |
|---|---|
| Kopf | führende `Von:`-, `Adresse:`-Zeilen des Textes (Betreff, Absender, Datum stehen ohnehin in der Zeile) |
| passende Absätze | Fenster von 300 bis 600 Zeichen an Absatz-, Zeilen- und Satzgrenzen (kleine benachbarte gleicher Art werden zusammengefasst); die zwei besten nach den Suchwörtern der Frage samt Umschreibungen (dieselbe Zerlegung, Wortformen und Wortteile wie die Suche, `WorkingMemoryStore.query_terms`); seltene Wörter der Quelle zählen mehr; Zitat (`>`), Signatur (ab `--`) und Haftungsausschluss nur, wenn der Fließtext nichts Passendes hat |
| Stellen der Akte | die überholte Angabe und die bevorzugten Zeilen der Akte (`akten_kontext.stellen`) kommen dazu, auch wenn die Frage sie nicht nennt |
| nie leer | ohne passenden Absatz: Kopf und erster Absatz |
| Vermerk | `… [gekürzt, 3 von 12 Absätzen]` am Ende, `[…]` zwischen getrennten Stellen; die Anweisung der Auswahl und der Satzformulierung sagt, was das heißt (fehlt etwas im Auszug, ist es weder bestätigt noch verneint) |
| Fundstelle | steht als `text` in der Zeile und im `context` nur als „[Fundstelle: siehe text]“ |

**Was nie gekürzt wird.** Verweise (`ref`), Kennungen S1…, die Reihenfolge und die Rangfusion der Kandidaten; kurze
Quellen; der Volltext für alles, was Text prüft: Identität, Projekt, Zeitbezug und Fokus in `working_memory_*` lesen
`Zeile.volltext` (`volltext_zeilen`), die Satzprüfung prüft gegen den Volltext der Quelle (ohne Geschwärztes), nicht
gegen den Auszug (`AntwortBeleg.pruef_text`). Eine Angabe aus einem nicht gezeigten Absatz besteht die Prüfung also; sie
steht in der Quelle, die „Weg nach unten“ zeigt.

**Budget.** 32.000 Zeichen, unverändert. Es zählt den Auszug, die Stellen der Akte und die Hinweise auf Überholtes
(`_akten_zugaben`; bisher zählten die Hinweise nicht mit, bei mehr Quellen im Kontext hätte das das Budget in einem
ersten Versuch um bis zu 90 % überschritten). Was nicht mehr passt, fällt von hinten weg und steht in
`search.abgeschnitten`. Nicht mitgezählt bleiben die Felder `andere_person` und `ausserhalb_zeitraum` (rund 150 Zeichen
je betroffene Zeile). Die Satzformulierung zeigt dem Modell und der Oberfläche denselben Auszug (Fundstelle vorn); die
Suchanfrage wird mit der Satzantwort gespeichert (höchstens 2.000 Zeichen, nur Wörter der Frage), damit das Anzeigen
dieselben Absätze zeigt.

### Messung

Vier Läufe wie bei den Paketen davor (Regel-Einordnung, ohne Modell, `--seed 1`). „kurz“ ist die Welt wie bisher, „lang“
dieselbe mit `--lange-quellen`. „vorher“ ist Commit `9a1b2c6` (schon mit den neuen Kennzahlen), „nachher“ der Stand
dieses Pakets.

| Kennzahl | kurz 0: vorher → nachher | kurz 10k | lang 0 | lang 10k |
|---|---|---|---|---|
| Erwartete Belege gefunden (von 136) | 124 → 124 | 109 → 109 | 114 → **117** | 106 → **109** |
| Fragen mit allen Belegen (von 71) | 64 → 64 | 57 → 57 | 55 → **57** | 51 → **54** |
| **Kontext abgeschnitten**, Fragen (Belege) | 0 → 0 | 0 → 0 | 3 (3) → **0 (0)** | 3 (3) → **0 (0)** |
| erwartete Belege ohne tragende Stelle | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 |
| wegen Länge nie eingeordnet (Transkripte über 12.000) | 0 | 0 | 5 → 5 | 5 → 5 |
| Fragen mit verbotenen Belegen (von 77) | 21 → 21 | 18 → 18 | 16 → 18 | 11 → 15 |
| davon ungekennzeichnet (Fragen, Belege) | 8 (8) → 8 (8) | 8 (8) → 8 (8) | 2 (2) → 2 (2) | 2 (2) → 2 (2) |
| Rückfragen mit allen Bedeutungen (von 7) | 7 → 7 | 7 → 7 | 6 → 6 | 5 → 5 |
| Unnötige Rückfragen (von 70) | 0 → 0 | 0 → 0 | 0 → 0 | 1 → 1 |
| Quellen im Kontext (Mittel) | 15,5 → 15,5 | 15,8 → 15,8 | 9,9 → **13,4** | 10,1 → **14,1** |
| Kontext der Auswahl, Zeichen (Mittel) | 20.615 → 20.888 | 18.214 → 18.487 | 38.212 → **35.084** | 36.247 → **31.734** |
| höchster Kontext, Zeichen | 23.683 → 23.956 | 22.328 → 22.601 | 43.646 → 38.045 | 43.112 → 37.513 |
| Abruf je Frage, Median / P90 | 0,10 / 0,14 → 0,11 / 0,16 s | 0,90 / 1,50 → 1,03 / 1,74 s | 0,15 / 0,23 → 0,24 / 0,33 s | 2,23 / 4,16 → 2,53 / 4,26 s |

Die Zeiten schwanken mit der Last (je zwei Läufe gleichzeitig auf vier Kernen); der Aufschlag von etwa 0,01 bis 0,09 s
je Frage kommt aus dem Zerlegen der Texte in Fenster. Die Kontextgröße enthält die Anweisung (rund 5.300 Zeichen).

**Gelesen.**

* Die kurze Welt bleibt, wie sie war: gleiche Belege, Rückfragen, verbotene Belege (der Kontext wächst um 273 Zeichen
  durch den Satz der Anweisung zum Vermerk).
* Auf der langen Welt sinkt „Kontext abgeschnitten“ von 3 auf 0 Fragen, der Kontext um 8 % (ohne Rauschen) und 12 % (mit
  10.000), und es passen 40 % mehr Quellen hinein (9,9 → 13,4). Drei Belege mehr kommen an (mit Rauschen ebenfalls drei).
  Der Kontext bleibt nah am Budget, weil die Fundstelle (`text`, bei Zitatblöcken bis 2.400 Zeichen) und die Metadaten der
  Zeile (rund 760 Zeichen im Mittel) weiter ganz dastehen; der Auszug selbst ist rund 730 Zeichen lang (Stichprobe mit
  einer früheren Einstellung: 3 Fenster, 40 Kandidaten).
* **Nicht besser, eher schlechter:** Auf der langen Welt stehen bei mehr Quellen im Kontext auch mehr verbotene Belege
  (16 → 18 Fragen, mit Rauschen 11 → 15); ungekennzeichnet bleiben 2 (die Kennzeichnung greift). Rückfragen (6 von 7, mit
  Rauschen 5 von 7) und die eine unnötige Rückfrage sind schon im Ist-Stand schwächer als auf der kurzen Welt (7 von 7):
  Lange Quellen verändern die Bedeutungssuche, nicht erst die Auswahl. Das ist eine Lücke der ersten Stufe, nicht dieser
  Änderung; offen.
* „Ohne tragende Stelle“ bleibt 0 mit Fenstern bis 600 Zeichen; mit 450 waren es 2 Belege (Versuch), deshalb 600.
* **Die größere Lücke liegt davor.** Das Arbeitsgedächtnis ordnet Quellen über 12.000 Zeichen gar nicht ein
  (`MAX_SOURCE_CHARS`; auch höchstens 24 Blöcke zu je 4.000 Zeichen). Ein Transkript von 30.000 Zeichen kann nie ein Beleg
  werden, gleich wie die Auswahl aussieht: 5 erwartete Belege fehlen deshalb auf der langen Welt, vorher wie nachher. Eine
  Zusatzmessung mit Transkripten von 11.000 Zeichen (unter der Grenze, nur nachher gemessen): 119 Belege, „zu lang“ 0,
  „abgeschnitten“ 1, „ohne tragende Stelle“ 1 Beleg.

### Entscheidung: Kandidaten

Vorgabe war, die erste Stufe zu vergrößern (z. B. 40). Gemessen mit Auszügen, ohne Rauschen (mit 10.000 in Klammern):

| Kandidaten | kurz: Belege | kurz: verbotene / ungekennzeichnet | kurz: Kontext | lang: Belege | lang: abgeschnitten (Fragen) |
|---|---|---|---|---|---|
| **16** | **124** (109) | 21 / **8** (8) | **20.888** (18.487) | **117** (109) | **0** (0) |
| 24 | 127 (112) | 23 / 10 (8) | 28.322 (24.283) | 118 (108) | 3 (2) |
| 40 | 127 | 23 / 10 | 34.591 | 118 | 4 |

**Entscheidung: 16 bleiben.** 24 oder 40 bringen auf der kurzen Welt drei Belege, auf der langen einen, bei zwei mehr
ungekennzeichneten verbotenen Quellen, bis zu 65 % mehr Kontext (mit echtem Modell mehr Zeit) und auf der langen Welt
wieder abgeschnittenen Quellen. Die zweite Stufe allein holt auf der langen Welt, was das Budget kostete; mehr
Kandidaten kaufen wenig. Die Zahl steht in `MAX_REFS`, Versuch mit `--plaetze N`.

### Sabotageproben

Jede Zusicherung wurde absichtlich gebrochen (ein Ausdruck im Code ersetzt), die Tests liefen, dann wurde zurückgesetzt:
41 von 41 gefangen. Bei der ersten Durchsicht fingen die Tests sechs Brüche nicht (Kopf, Seltenheit, Wortteile, Budget der
Akte, Stellen im Beleg, Länge der Anzeige); dafür gibt es jetzt je einen Test (bei den Wortteilen traf das Wort „gibt“ der
Frage den Fülltext und verdeckte den Bruch). Das Skript liegt nicht im Repository.

| Gruppe | Brüche (je gefangen) | Tests |
|---|---|---|
| Kennzahl (Messlatte) | Budget meldet nichts; „abgeschnitten“ zählt Nicht-Gefundene; „ohne Stelle“ zählt Nicht-Gezeigte; „nichts zu verlieren“ zählt als verloren; „zu lang“ ohne Grenze; Bericht ohne Zahl (6) | `test_kontext_abgeschnitten*.py` |
| `--lange-quellen` | Zufall nicht je Kennung; Startwert wirkt nicht; Mail nicht aufgefüllt; Original hinten; Transkript vorn statt Mitte; Sperrliste in Sätzen, Signatur und Namen nicht geprüft; Notizen aufgefüllt; Zitat mit Leerzeilen; Rauschen bleibt kurz; Kopf nennt Option nicht (11) | `test_lange.py` |
| Absatzauswahl | kurze Quellen gekürzt; Vermerk fehlt oder falsch; Fenster zu groß; kein erster Absatz; Kopf fehlt; Zitat und Signatur zählen voll; Seltenheit, Wortformen, Wortteile zählen nicht; Fundstelle doppelt; Stellen der Akte fehlen (im Kontext); Zeilen ohne Volltext; Budget zählt Volltext; Akte ohne Budget; Prüfungen lesen den Ausschnitt; Anweisung ohne Vermerk; Kürzung nicht gemeldet (18) | `test_absatzauswahl.py` |
| Sätze | Satzprüfung gegen den Auszug; Beleg zeigt den Volltext; Suche nicht gespeichert; Belege ohne Suchwörter; Stellen der Akte fehlen im Beleg; Anzeige schneidet vor dem Vermerk ab (6) | `test_absatzauswahl_saetze.py` |

### Offene Punkte

* **Quellen über 12.000 Zeichen** wurden nie eingeordnet, also nie Beleg. Behoben am 30. September durch die Einordnung in
  Abschnitten ([unten](#lange-quellen-in-abschnitten)).
* **Rückfragen und Bedeutungssuche bei langen Quellen** sind schwächer (6 von 7 statt 7 von 7); Ursache in der ersten
  Suchstufe, nicht untersucht.
* **Fundstelle und Metadaten** sind jetzt der größere Teil einer Zeile (Fundstelle bis 2.400 Zeichen bei Zitatblöcken):
  Die Fundstelle selbst ließe sich mit derselben Fensterwahl kürzen.
* **Mit echtem Modell messen:** ob Auszüge die Auswahl und die Sätze verbessern (weniger Rauschen) oder verschlechtern
  (fehlender Umkreis), und die Modellzeit bei 14 statt 10 Quellen. Die Messlatte sieht nur, ob die tragende Stelle im
  Auszug steht.
* Das Füllmaterial der langen Welt ist gleichförmiger als echte Post (`messlatte/lange.py`).

## Lange Quellen in Abschnitten

Stand: 30. September 2026. Code: `abschnitte.py` (neu), `working_memory_analysis.py` (`interpret_abschnitt`,
`interpret`), `working_memory_worker.py` (`Zwischenstand`, `ABSCHNITTE_JE_PAKET`), `working_memory_store.py`
(`MAX_SOURCE_CHARS`, `search(je_quelle=…)`, Ordnung bei Gleichstand), `source_candidates.py`, `logbuch.py` (Art `zu_lang`).
Tests: `test_abschnitte.py`, `test_abschnitte_einordnung.py`, `test_working_memory_analysis.py`. Berichte:
`docs/evaluations/messlatte/2026-09-30-abschnitte-*`. Zum Hintergrund: [`46-hintergrund.md`](46-hintergrund.md).

**Das Problem.** Das Arbeitsgedächtnis ordnete nur Quellen bis 12.000 Zeichen ein (höchstens 24 Absätze zu je 4.000
Zeichen, ein Modellaufruf). Ein Transkript von 30.000 Zeichen wurde zurückgestellt und konnte nie Beleg werden; auf
der langen Welt der Messlatte waren das 5 erwartete Belege.

**Die Abschnittsbildung** (`abschnitte.bilden`, ohne Modell, deterministisch):

| Schritt | Regel |
|---|---|
| Einheiten | Die Absätze des Arbeitsgedächtnisses (`_blocks`, wie bei kurzen Quellen). Ein Absatz über 3.000 Zeichen wird geteilt: Transkript an Sprecherwechseln („Name: Text“, Beiträge bis 1.500 Zeichen gebündelt, ein Beitrag wird nie mitten geschnitten, solange er unter 3.000 bleibt), Mail an Zitatgrenzen (eigener Text und `>`-Zeilen getrennt), sonst an Zeilen-, Satz- und Wortenden. Die Schnittregeln sind die der Auswahl (`absatzauswahl.teilen`, `ist_zitatzeile`, `transkript_eingang.ist_sprecherzeile`). |
| Abschnitt | Ganze Einheiten, bis 3.000 Zeichen erreicht sind (also 3.000 bis unter 6.000), höchstens 24 Einheiten (das Maß eines Aufrufs). |
| Überlappung | Der nächste Abschnitt beginnt mit der letzten Einheit des vorigen. |
| Zeichenbereiche | Jeder Abschnitt trägt `start`, `ende` und die Bereiche seiner Einheiten; alle Zahlen sind Stellen im **Volltext**. |
| Kurze Quellen | Bis 6.000 Zeichen, 24 Absätze und keiner über 4.000 Zeichen: ein Abschnitt, genau die Einteilung wie vorher. |

**Die Einordnung je Abschnitt.** `interpret_abschnitt` schickt die Einheiten eines Abschnitts durch denselben Anbieter und
dieselbe Prüfung wie früher (Schema, Werkzeugaufrufe, jede Block-ID genau einmal); die Anfrage trägt bei langen Quellen
`abschnitt: {nr, von}` und einen Satz, dass der erste Block schon im vorigen Abschnitt stehen kann. Ergebnis sind
`{start, end, kind}` im Volltext. `abschnitte.zusammenfuehren` macht daraus je Quelle eine Liste: Die Überlappung liefert
eine Einheit zweimal, **die erste Einordnung gilt** (auch „belanglos“), `irrelevant` fällt erst dort weg. Im Bestand
steht je Einheit ein Verweis; `MAX_ITEMS` ist von 24 auf 2.000 gestiegen. Regel-Einordnung und Modell laufen durch
denselben Weg, die Einordnung bleibt eine.

**Obergrenze.** Statt 12.000 gilt `MAX_SOURCE_CHARS = 200.000` Zeichen (Dokument in der Datenbank höchstens 768 KiB,
vorher 64.000 Bytes; mehr als 2.000 Absätze ebenfalls zu lang). Darüber bleibt die Quelle zurückgestellt
(„Nicht eingeordnet · Quelle zu umfangreich“), und das Logbuch vermerkt sie einmal je Fassung
(`zu_lang`, im Briefing: „1 Quelle zu lang zum Einordnen“). Was Berichte an das Modell und Berichtigungen betrifft,
bleibt es bei 12.000 (`MAX_BERICHT_CHARS`); die Themenvorschläge (`memory_categories`) kennen weiter ihre 12.000.

**Belege zeigen auf die Stelle.** Der Verweis (`ref`) ist (Anfang, Ende) im Volltext; `satzantwort._beleg_aus`,
`pruef_text` und der „Weg nach unten“ lesen unverändert. Das Prüfmodell sieht ein Fenster von 4.000 Zeichen um die
Mitte der Fundstelle (`satzpruefung_modell._fenster`); eine Einheit ist höchstens 3.000 Zeichen, das Fenster deckt sie
also ganz ab, auch am Anfang und Ende der Quelle (Tests). Grenze: Steht eine Aussage, die nur im Zusammenhang mit einem
weit entfernten Absatz stimmt, nicht im Fenster, sieht sie das Prüfmodell nicht; die Regelprüfung liest den Volltext.

**Häppchen.** Der Arbeitsgang bearbeitet je Paket höchstens `max(8, Quellen je Paket)` Abschnitte. Fertige Abschnitte
merkt der `Zwischenstand` im Speicher (Stellen und Arten, nie Text; für eine Fassung und ein Modell; höchstens 256
Quellen); die Quelle kommt im nächsten Paket zuerst dran; geschrieben wird erst mit dem letzten Abschnitt, nie Halbes.
Einzelheiten und Rücksicht auf den Menschen: [`46-hintergrund.md`](46-hintergrund.md).

**Was die Suche dazu lernen musste.** Die ersten Messläufe zeigten, dass eine lange Quelle die Suche verzerrt: Sie hat
viele Absätze, und irgendeiner trifft immer.

1. *Pool.* Die Wortsuche holt 64 Verweise; eine Quelle mit 60 Absätzen füllte ihn allein. Jetzt zählt der Pool einen
   Verweis je Quelle (`search(je_quelle=1)`, `source_candidates`); ohne Angabe bleibt die Suche unverändert. Ohne diese
   Änderung (Zwischenmessung, nicht im Repository): lange Welt 127, aber drei bisher gefundene Belege (`mainz-011`,
   `profil-001`, `terminvorbereitung-002`) gingen verloren; zwei bisher fehlende (`kontakt-vor-jahren-003`,
   `paraphrase-010`) kamen zufällig dazu. Mit dem Pool: 126 (Belege verloren: `terminvorbereitung-002`, `-008`).
2. *Gleichstand.* Bei gleicher Trefferzahl geht eine Quelle unter 9.000 Bytes (Dokument) einer längeren vor
   (`LANGE_QUELLE_BYTES`), vor der Aktualität; das holte `terminvorbereitung-002` zurück (126 → 127). Das betrifft nur Welten mit langen Quellen: Auf der kurzen Welt gibt es keine, dort bleibt jede
   Reihenfolge gleich (gemessen).

### Messung

Vier Läufe wie bei den Paketen davor (Regel-Einordnung, ohne Modell, `--seed 1`; „lang“ = `--lange-quellen`, Transkripte
30.000 Zeichen). „vorher“ ist `c1ba712`, „nachher“ dieser Stand. 142 erwartete Belege (136 der alten Fragen und 6 der
neuen der Kategorie `inhalt`).

| Kennzahl | kurz 0: vorher → nachher | kurz 10k | lang 0 | lang 10k |
|---|---|---|---|---|
| Erwartete Belege gefunden (von 142) | 130 → 130 | 115 → 115 | 123 → **127** | 114 → **117** |
| Fragen mit allen Belegen (von 77) | 70 → 70 | 63 → 63 | 63 → **67** | 59 → **61** |
| wegen Länge nie eingeordnet | 0 → 0 | 0 → 0 | 5 → **0** | 5 → **0** |
| Kontext abgeschnitten (Belege) | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 |
| Unnötige Rückfragen (von 76) | 0 → 0 | 0 → 0 | 0 → 0 | 1 → 1 |
| Dauer des Laufs | 13 → 12 s | 237 → 226 s | 26 → 36 s | 558 → 574 s |

**Was gewonnen und was verloren ging (lang 0).** Gewonnen: `meeting-protokoll-009`, das Transkript, das bisher nie eingeordnet
wurde, in fünf Fragen (5 Belege). Verloren: `terminvorbereitung-008` in „Wann und wo ist mein Termin morgen?“; die Frage
nennt nur Allgemeines („Termin“, „morgen“), und sechs jetzt einordenbare Transkripte treffen das mit ihrem Füllmaterial
(dort steht „Guten Morgen“, „der letzte Termin“) ebenso. Netto also **+4 statt der erwarteten +5**; das Ziel „mindestens
5 gewonnene Belege“ ist brutto erreicht (5), netto um einen verfehlt. Mit 10.000 Rauschquellen: `meeting-protokoll-009` kommt nur in zwei der
fünf Fragen in den Kontext, dazu kommt `terminvorbereitung-002`, nichts geht verloren; netto **+3**. Das Füllmaterial ist gleichförmiger als echte
Post (`messlatte/lange.py`); wie stark lange echte Mitschriften allgemeine Fragen verdrängen, sagt erst `lokal`.

### Sabotageproben

Jede Zusicherung wurde in einer Kopie des Codes gebrochen, die Tests liefen, dann wurde zurückgesetzt (das Skript
liegt nicht im Repository). Elf Brüche, alle gefangen; zwei fingen die Tests zuerst nicht (Sprecherwechsel bei
einzeiligen Beiträgen, Pool je Quelle durch den Volltextindex verdeckt) und haben jetzt je einen Test.

| Bruch | Gefangen von |
|---|---|
| Obergrenze zurück auf 12.000 | `test_die_alte_grenze_von_12000_zeichen_gilt_nicht_mehr`, `test_ein_transkript_ueber_12000_…`, `test_abschnitte.py` |
| falscher Zeichenbereich (relativ zum Abschnitt) | `test_der_beleg_zeigt_auf_die_stelle_tief_im_volltext`, `test_das_fenster_des_pruefmodells_…`, `…_am_anfang_und_am_ende_…` (Prüfmodell sieht das falsche Fenster), Überlappung, Einordnung |
| keine Überlappung | `test_der_naechste_abschnitt_beginnt_mit_der_letzten_einheit_des_vorigen` |
| Zusammenführen: letzte statt erste Einordnung; `irrelevant` bleibt | `test_die_ueberlappung_liefert_keine_dublette_…`, `test_irrelevant_faellt_erst_beim_zusammenfuehren_weg` |
| Paketmaß wird nie verbraucht | `test_eine_angefangene_quelle_kommt_im_naechsten_paket_zuerst_dran` |
| Obergrenze ohne Logbuch-Vermerk | `test_eine_quelle_ueber_der_obergrenze_…` |
| keine Ordnung „kürzere zuerst“ | `test_bei_gleicher_trefferzahl_geht_die_kuerzere_quelle_der_langen_vor` |
| Pool ohne `je_quelle` | `test_der_kandidatenpool_der_wortsuche_…` |
| Transkript nicht an Sprecherwechseln | `test_ein_mehrzeiliger_beitrag_wird_nicht_mitten_im_beitrag_geteilt` |
| Zwischenstand gilt für jedes Modell | `test_der_zwischenstand_gilt_nur_fuer_dieselbe_fassung_und_dasselbe_modell` |

### Offen

* **Themenvorschläge** (`memory_categories`) überspringen weiter Quellen über 12.000 Zeichen; sie brauchen dieselbe Abschnittsbildung.
* **Modell statt Regel:** Die Messung läuft mit der Regel-Einordnung; ob ein Modell Abschnitte ebenso einordnet (und wie lange
  ein Paket dann dauert), ist auf dem Zielgerät zu messen.
* **Zwischenstand nur im Speicher:** Ein Neustart mitten in einer langen Quelle beginnt sie von vorn.
* **Allgemeine Fragen und lange Quellen:** siehe oben; eine Seltenheitsgewichtung in der Wortsuche (wie im Volltextindex) wäre
  der nächste Schritt.
* Fortschrittsanzeige zählt Quellen, nicht Abschnitte.

## Zweites Tor: Prüfmodell

Stand: 30. September 2026. Code: `satzpruefung_modell.py` (neu), Haken in `satzantwort.py` (`_zweites_tor`,
`_urteilen`, Speichern), Verdrahtung `agent_verdrahtung.pruef_tor`, Rolle `pruefung` in `model_roles.py` und
`model_recommendation.py`, Schalter `PUT /api/v1/models/satzpruefung`. Tests: `test_satzpruefung_modell.py`,
`test_zweites_tor.py`, `test_pruefrolle.py`, `messlatte/tests/test_pruefmodell.py`. Browserprobe:
`scripts/probe_pruefmodell_ui.py`.

**Die Lücke.** Die Satzprüfung ohne Modell fängt, was sich an Zahlen, Daten, Namen, Kennungen, Status und
Verneinungswörtern festmachen lässt. „Die Schulleitung hat dem Vorschlag zugestimmt.“ besteht, wenn die Quelle sagt:
„Der Vorstand hat dem Vorschlag zugestimmt, die Schulleitung hat sich dagegen entschieden.“ Alle Wörter stehen im
Beleg. Die sechs Fragen der Kategorie `inhalt` in der Messlatte sind genau solche Fallen; alle zwölf Sätze (richtig und
falsch) bestehen die erste Prüfung.

**Das Tor.** Jeder Satz, der die erste Prüfung bestanden hat, geht einzeln an das Modell der Rolle `pruefung`: der
Satz und die Textstellen seiner Belege (Kopfzeile und Volltext der Quelle, bei langen Quellen ein Fenster von
4.000 Zeichen um die Fundstelle; nie der Auszug, den das Antwortmodell sah), dazu „Wird der Satz durch die Belege
gestützt? Antworte mit genau einem Wort: ja, nein, unklar.“ Nichts sonst: keine Frage des Nutzers, keine anderen
Quellen. Auch der vom Programm ergänzte Wandel einer Frist geht durch das Tor.

| Urteil | Folge |
|---|---|
| `ja` | Satz bleibt, trägt `pruefmodell: ja` |
| `nein` | verworfen, Grund „Prüfmodell: nicht gestützt“ |
| `unklar`, unlesbare Ausgabe, Fehler, Werkzeugaufruf | verworfen (fail closed) |
| keine Antwort in 2 s je Satz oder 6 s für alle Sätze | verworfen („keine Antwort im Zeitbudget“); nach 6 s wird nicht mehr gefragt |

Bleibt kein Satz, gilt wie bisher der Zitatmodus. Die Zeit steht im Abschnitt `pruefung_modell` (`zeitmessung.py`,
Protokoll unter Einstellungen, Lokale KI).

**Modellfamilien.** Eine Zeile je Familie in `satzpruefung_modell.ADAPTER`: `bespoke-minicheck` bekommt „Document: …
Claim: …“ und muss genau „Yes“ oder „No“ sagen; jedes andere Modell (auch `tev1`, bis Messlauf D etwas anderes zeigt)
bekommt JSON mit Schema `{"urteil": "ja|nein|unklar"}`, gelesen streng (genau dieses Objekt, zur Not genau eines der
drei Wörter).

**Schalter und Vorgabe.** Einstellung `satzpruefung_modell`, Vorgabe an. Das Tor ist nur an, wenn der Rolle ein belegt
lokales Modell zugewiesen ist (`model_roles.anbieter_fuer_pruefung`: kein Rückfall auf den Standard, nie Cloud). Ohne
Modell ist es still aus; die Modellkarte sagt es in der Zeile „Sätze gegenprüfen“, der Schalter unter Einstellungen,
Lokale KI („Sätze vom Prüfmodell gegenprüfen“) ist dann gesperrt und sagt warum. Wirkt ab der nächsten Frage.

**Gespeichert.** `answer['satzantwort']['pruefung']` hält Zustand (`an`, `aus`, `kein_modell`), Modell und die Zahl der
am Tor verworfenen Sätze; jeder Satz sein Urteil. `wiederherstellen` fragt das Modell nicht erneut, verlangt aber bei
Zustand `an` von jedem gespeicherten Satz das `ja`; sonst Zitatmodus. Ältere Antworten ohne diesen Teil gelten als
„kein Modell“.

**Anzeige.** „1 Satz verworfen (Prüfmodell).“ getrennt von „… weil die Belege ihn nicht getragen haben“; im Fuß von
„Weg nach unten“ steht, ob ein Prüfmodell mitprüfte, ausgeschaltet oder nicht eingerichtet ist.

## Verlässlichkeit je Satz

`verlaesslichkeit.py`, eine stille Einstufung aus Regeln (kein Modell), gespeichert mit dem Satz und beim Anzeigen neu
gerechnet (mit dem Stichtag der Antwort):

| Stufe | Regel |
|---|---|
| `duenn` | ein Beleg trägt eine Kennzeichnung (andere Person gleichen Namens, außerhalb des Zeitraums), oder der Satz besteht nur mit der Kopfzeile der Belege (Betreff, Absender, Datum), nicht mit ihrem Text |
| `gut` | mindestens zwei Belege oder einer jünger als 90 Tage, und das Prüfmodell sagte ja |
| `einfach` | sonst: ein Beleg, älter als 90 Tage (oder ohne Datum), oder das Prüfmodell lief nicht |

Überholtes zählt nicht als Kennzeichnung: Ein solcher Satz besteht nur mit Wandel und neuerer Quelle. Angezeigt wird
nur bei `einfach` und `duenn` ein gedämpfter Nebensatz hinter dem Satz, und nur mit einem Anlass, der den Satz betrifft:
„(nur eine Quelle, von 2025)“, „(nur über Betreff oder Absender belegt)“, „(gestützt auf eine gekennzeichnete
Quelle)“. Dass das Prüfmodell für die ganze Antwort nicht lief, steht einmal im Fuß, nicht hinter jedem Satz.

### Messung

Berichte `docs/evaluations/messlatte/2026-09-30-pruefmodell-*`, Regel-Einordnung.

| Lauf | Ergebnis |
|---|---|
| Regel-Lauf ohne Modell, alte 77 Fragen | 124 von 136 Belegen, 64 von 71 vollständig, mit 10.000 Rauschquellen 109 und 57; Rückfragen 7 von 7, unnötige 0: **unverändert** (das Rauschen ist Quelle für Quelle gleich, geprüft) |
| dito, sechs neue Fragen `inhalt` | 6 von 6 Belegen, auch mit 10.000 |
| Skript sorgfältig, Prüfmodell an (`--nur inhalt`) | 6 von 6 richtig, 0 Sätze verworfen |
| Skript unaufmerksam (richtiger und falscher Satz), Prüfmodell an | 6 von 6 richtig, **0 falsche Aussagen, 6 Sätze vom Prüfmodell verworfen**, 0 von der ersten Prüfung |
| Skript unaufmerksam, ohne Prüfmodell | **6 von 6 falsche Aussagen**: die erste Prüfung lässt alle durch |

Das Skript-Prüfmodell ist ideal (es kennt die falschen Sätze der Welt). Gemessen ist die Mechanik: dass falsche Sätze
am Tor enden, getrennt gezählt werden, kein richtiger verloren geht und die Abrufzahlen bleiben. Wie oft ein echtes
Modell zu Unrecht `nein` oder `unklar` sagt (dann fällt ein richtiger Satz weg) und was es kostet, zeigt Messlauf D
(`40-messplan-modelle.md`).

### Sabotageproben

22 Brüche, je ein Ausdruck ersetzt, Tests des Pakets gelaufen, zurückgesetzt: 22 von 22 gefangen (Skript nicht im
Repository).

| Bruch | gefangen von |
|---|---|
| Tor umgangen | 16 Tests, u. a. `test_das_pruefmodell_verwirft_den_falschen_satz_…` |
| `unklar` durchgelassen; Fehler als `ja` | `test_unklar_und_fehler_lassen_keinen_satz_durch`, `test_fehler_und_werkzeugaufrufe_…` |
| Satzbudget ignoriert; Gesamtbudget ignoriert | `test_ein_langsamer_satz_…`, `test_ist_das_gesamtbudget_verbraucht_…`, `test_das_zeitbudget_wird_eingehalten_…` |
| Klassifikation oder JSON lax gelesen; Adaptertabelle falsch | `test_klassifikation_liest_nur_genau_yes_oder_no`, `test_json_wird_streng_gelesen`, `test_jede_modellfamilie_…` |
| nicht lokaler Anbieter als Tor; Rolle darf in die Cloud; Rolle nimmt ohne Zuweisung den Standard | `test_das_tor_ist_nur_mit_…_lokalem_modell_aktiv`, `test_pruefrolle.py` |
| Schalter aus wirkt nicht | `test_vom_nutzer_ausgeschaltet_…`, `test_mit_pruefmodell_ist_das_tor_an_und_der_schalter_…` |
| gespeicherter Satz ohne Ja wird gezeigt | `test_gespeichert_und_beim_anzeigen_neu_geprueft` |
| Alter zählt nicht; Kennzeichnung oder Kopfzeile macht nicht dünn | `test_verlaesslichkeit.py`, `test_nur_ueber_die_kopfzeile_…`, `test_ein_alter_einzelner_beleg_…` |
| Prüfmodell sieht den Auszug statt des Volltexts | `test_json_modell_bekommt_…`, `test_lange_quellen_gehen_als_fenster_…` |
| Wandel geht nicht durchs Tor; Zeit nicht gemessen | `test_auch_der_vom_programm_ergaenzte_wandel_…`, `test_die_zeit_steht_im_abschnitt_…` |
| Messlatte zählt das Prüfmodell nicht | `test_der_pruefmodus_des_skriptmodells_ist_skriptbar` |
| Orchester zählt die Prüfung nicht; Prüfung gibt nicht zuerst Speicher her | `test_orchester.py`, `test_orchester_routes.py` |

### Offen

* **Echte Prüfmodelle** (Messlauf D): Tag-Namen und Größen im Katalog sind von den Modellseiten übernommen, nicht gegen
  `ollama pull` geprüft; ob `tev1` ein eigenes Format braucht, ist ungeklärt (bis dahin JSON mit Schema). Die
  wichtigste Zahl ist die Quote zu Unrecht verworfener richtiger Sätze.
* **Zeit:** bis zu 2 s je Satz, nacheinander; bei fünf Sätzen und einem langsamen Modell werden die letzten wegen des
  Gesamtbudgets verworfen. Parallel fragen wäre schneller, hängt aber an `OLLAMA_NUM_PARALLEL`.
* Ein Faden, der das Budget überschreitet, läuft bis zur Zeitgrenze des Anbieters im Hintergrund weiter (sein Ergebnis
  wird nie gelesen).

## Quellenhinweis der Gedächtnisantwort

Stand: 1. Oktober 2026. Die belegte Gedächtnisantwort (bestätigte Einträge, `EvidenceAnswer.render_readable`) zeigte
im Gespräch Rohdaten: `Quelle [1]: Gespräch · "conversation:c-…:message:m-…"`, `Ereigniszeit:
2026-10-01T10:25:07.79…+00:00; Erfasst: …`, `Gültigkeit: ab … bis ausschließlich …`. Jetzt steht dort, was ein Mensch
sagen würde, und die Quelle ist einen Klick entfernt:

| Quelle | Hinweis (Zeiten in der Zeitzone des Nutzers, `KINGFISHER_TIMEZONE`, Vorgabe Europe/Berlin) |
|---|---|
| Gespräch | `Quelle [1]: Gespräch vom 1. Oktober 2026, 12:25 Uhr` |
| Mail | `Quelle [1]: E-Mail „Angebot Projekt Atlas“ von Lena Probe vom 29. September 2026, 09:00 Uhr` |
| Termin | `Quelle [1]: Termin „Abstimmung Atlas“ am 2. Oktober 2026, 10:30 Uhr` |
| Dokument ohne eigene Zeit | `Quelle [1]: Dokument „Protokoll“, aufgenommen am 29. September 2026, 10:00 Uhr` |

* **Wo:** `quellenhinweis.py` (Satz und Datenfeld), `datumstext.zeitpunkt_text`/`tag_text` (Zeit beim Nutzer, ohne
  Sekunden; Mitternacht nur als Tag), `evidence_answer.render_readable(…, angaben=…)` und `.quellen(…)`,
  `Agent._quellen_angaben` (Titel und Absender aus der gespeicherten Quelle, nichts geraten). Ein gespeicherter Wert,
  der nur ein ISO-Zeitpunkt ist, wird ebenso lesbar; die Gültigkeit heißt „Gilt ab … bis …“, bei einem Ende um
  Mitternacht „bis einschließlich“ des Vortags.
* **Datenfeld statt Text:** `context.quellen` trägt je Nummer den Hinweis, die Art, Claim, Quelle (`episode_id`,
  `source_ref`) und bei Gesprächen `conversation_id` und `message_id`. Es wird mit der Nachricht gespeichert und fällt
  weg, wenn die Antwort beim Öffnen zurückgehalten wird (`knowledge_answer_view`).
* **Oberfläche:** `BelegQuellen.tsx`, `quellenWeg.ts`. Unter der Antwort „Quelle 1 öffnen“: in demselben Gespräch
  springt der Klick zur Nachricht, aus einem anderen öffnet er das Gespräch an der Nachricht (`#message-…`), bei Mail,
  Termin oder Dokument die bestehende Quellenansicht. Die Kennungen stehen nur im Aufklapper „Für Techniker“ und als
  Datenattribut (`data-quelle-ref`).
* **Container:** `tzdata` ist jetzt eine Abhängigkeit des Sidecars; das schlanke Python-Abbild bringt die
  Zeitzonendatenbank nicht sicher mit, und ohne sie stünde die Zeit in UTC mit Versatz.
* **Andere Antwortwege** wurden durchgesehen: Arbeitsgedächtnis (Zitatmodus) und Originalstellen nennen Zeiten schon mit
  `readable_time` und Herkunft als Satz, die Satzantwort ihre Belege mit Titel; dort stand keine Kennung im Text.

**Vertragstest.** `scripts/verify_container.py` (`evidence_reply`) prüft weiter dieselbe Strenge: Status `evidence`,
Modell gefragt, genau der bestätigte Claim, keine Rückfallantwort. Die Zuordnung der Quelle steht jetzt im Datenfeld:
genau eine Quelle, Nummer 1, derselbe Claim, Art Gespräch, `source_ref`, Gespräch und Nachricht der Merkzeile; der
Hinweis in Alltagssprache steht als `Quelle [1]: …` im Text, und im Text steht weder die Kennung noch eine ISO-Zeit.
`scripts/verify_browser.py` prüft das Datenattribut im sichtbaren Verweis und klickt ihn: Der Fokus muss auf genau der
Merkzeile liegen. `scripts/test_contract_model.py` hält dafür zwölf Ablehnungen bereit (andere Nachricht, anderes
Gespräch, anderer Claim, zwei Quellen, Rohkennung, ISO-Zeit …).

**Prüfung:** `sidecar/tests/test_quellenhinweis.py`, `test_readable_memory_answers.py`,
`test_memory_evidence_answers.py`, `test_vertragsmodell.py`, `app/kingfisher/tests/quellen-weg.test.mjs`, Browserprobe
`scripts/probe_quellen_ui.py`. Sabotageproben: Kennung zurück in den Text (31 Tests rot), falsche Nachricht im
Datenfeld (Integrationstest rot, Containernachbau bricht beim Seed ab: „Die Quelle führt nicht zu der Nachricht, aus der
der Satz stammt.“), Sprung im selben Gespräch durch die Quellenansicht ersetzt (`quellen-weg.test.mjs` rot).

**Offen:** Die Quellenansicht selbst (`ProfileSource`, außerhalb der eigenen Frage) nennt unter „Herkunft“ weiter die
Quellenkennung einer Mail; sie gehört in einen späteren Schritt hinter „Für Techniker“. Ältere, schon gespeicherte
Antworten behalten ihren damaligen Text.

### Sichtbar unter jeder Antwort: „Gestützt auf“ oder „ohne Beleg“ (Fremdprobe 2)

Die Fremdprobe 2 ([`51-fremdprobe-2.md`](51-fremdprobe-2.md), Befund 13) fand unter einer Antwort keinen Beleg und unter
der eigenen Frage „Gesprächsquelle ansehen“, das die eigene Frage zeigte; links stand „Keine aktuell verwendbaren
Gedächtnispunkte.“. Jetzt (`beleg.ts belegStand`):

* Eine belegte Gedächtnisantwort zeigt unter dem Text „Gestützt auf“ und je Quelle den lesbaren Hinweis aus
  `context.quellen` („[1] Gespräch vom 1. Oktober 2026, 12:25 Uhr“) mit „Quelle 1 öffnen“ daneben (`BelegQuellen.tsx`).
  Eine Antwort aus Rohquellen (`context.source_links`) zeigt ihre Quellen unter derselben Überschrift; eine Antwort in
  Sätzen behält ihren Weg nach unten.
* Jede andere Antwort trägt „Ohne Beleg: Diese Antwort stützt sich auf keine Quelle aus deinem Gedächtnis.“. Hinweise
  des Programms (Gedächtnisvorschlag) und Rückfragen tragen keine Zeile und kein „Stimmt nicht?“.
* Unter der eigenen Nachricht heißt der Weg „So ist deine Nachricht gespeichert“ (`server.EIGENE_FRAGE_ANSEHEN`).
* Die linke Spalte sagt, wenn dort keine Aussage steht, ob sich Antworten im Gespräch auf das Gedächtnis stützen
  (`kontextLeerSatz`), statt „Keine aktuell verwendbaren Gedächtnispunkte.“.

Der Container-Vertrag (`scripts/verify_browser.py`, `visible_evidence`) verlangt zusätzlich, dass unter der Antwort
„Gestützt auf“ mit demselben Hinweis wie im Text sichtbar ist; `probe_quellen_ui.py` prüft dasselbe.
