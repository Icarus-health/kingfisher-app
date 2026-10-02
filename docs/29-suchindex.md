# Suchindex über alle Rohquellen (Etappe C2)

Stand: 29. September 2026. Umsetzung von C2 aus
[`26-plan-stabschef.md`](26-plan-stabschef.md), Grundlage für „Suchen von unten“
in [`27-schichten-und-fragen.md`](27-schichten-und-fragen.md) (E2). Code:
`sidecar/icarus_memory/source_index.py` (Index), `source_candidates.py` (Fusion
mit der Wortsuche), `source_search.py` (wörtliche Suche, jetzt über den Index),
Migration 12 in `episodes.py`. Tests: `sidecar/tests/test_source_index.py`,
`test_source_search.py`.

## Befund: wie die Kandidatensuche lief und wo Treffer verloren gingen

Der Weg einer Gedächtnisfrage bis zu den Quellen, die das Modell sieht
(`working_memory_answers._candidates`):

1. `WorkingMemoryStore.search` nimmt die Wörter der Frage (`lexical.terms_v1`:
   ab drei Zeichen, Stoppliste mit rund 55 Wörtern, höchstens 16 Wörter).
2. Drei Stufen nacheinander: die Wörter selbst; Wortformen und die geschlossene
   Synonymliste (`word_forms.py`); Suffixköpfe langer Wörter ab sechs Zeichen
   (`working_memory_words.py`, „Rechnung“ findet „Stromrechnung“).
3. Jede Stufe liest gehashte Terme (`working_memory_terms`) der **eingeordneten
   Abschnitte** und sortiert nach Zahl der getroffenen Wörter, dann nach
   Aktualität. Zusammen werden höchstens 500 Abschnitte untersucht.
4. Übrig bleiben **zwölf Abschnitte** (`MAX_REFS`), nicht zwölf Quellen. Jede
   Zeile trägt den ganzen Quelltext als Kontext; das Budget liegt bei 24.000
   Zeichen.
5. Auf einem zweiten Weg sucht `source_search.py` wörtliche Zeichenfolgen linear
   in allen Quelltexten, mit 0,5 Sekunden Budget.

Untersucht wurden die Fehlfälle der Basismessung bis zur Ursache
(`messlatte/instanz` und `abruf`, Skript im Arbeitsverzeichnis). Sechs Ursachen
belegen den Verlust; zwei weitere liegen außerhalb dieses Pakets.

| Ursache | Beleg |
|---|---|
| **Kein Maß für Seltenheit.** Ein Fragewort („wann“, „los“, „eigentlich“, „mal“, „war“) zählt so viel wie ein Eigenname. | `kontakt-vor-jahren-01`: Der Beleg enthält von der Frage nur „Küchensoftware“, die Wortsuche reiht ihn auf Platz 20 von 64; geliefert werden zwölf. `mainz-01`: Beleg auf Platz 16. |
| **Zwölf Abschnitte statt zwölf Quellen.** Mehrere Abschnitte einer Mail belegen die Plätze. | Im Mittel 8 verschiedene Quellen auf 12 Plätzen; `fremde-anweisung-04`: 12 Abschnitte sind 5 Quellen. |
| **Neue Alltagsmails verdrängen Treffer.** Bei gleicher Wortzahl entscheidet die Aktualität; hinzu kommt das 500er-Suchbudget. | `adresse-geaendert-01` mit 10.000 Rauschquellen: alle zehn gelieferten Quellen sind Rauschen, der Beleg fehlt. |
| **Komposita und Wortteile.** | `mainz-04`: Der Beleg hat nur „Beratungsangebot“ (Titel) zur Frage nach dem „Angebot“ (Platz 13). `frist-verschoben-01` („einreichen“ ~ „Einreichfrist“) und `-04` („Förderung“ ~ „Förderhöhe“): in keiner Stufe ein Treffer. |
| **Wörtliche Suche mit Zeitbudget.** | Auf 50.000 Quellen endeten „Weinbergweg 12“ und „MenüPilot Diät“ leer (`budget_exhausted`), obwohl die Quelle da ist. |
| **Unsichtbar ohne Ausweis.** Zu große Quellen wurden nie eingeordnet und damit nie Kandidat; die Antwort sagt es nicht. | Seit dem 30. September ordnet das Arbeitsgedächtnis lange Quellen in Abschnitten ein (Grenze 200.000 statt 12.000 Zeichen, [`35-belegte-antworten.md`](35-belegte-antworten.md#lange-quellen-in-abschnitten)); darüber zählt die Suche sie weiter (`ohne_einordnung`, `nicht_indexiert`), und das Logbuch vermerkt sie. |
| Nicht im Bestand: Termine. | `fremde-anweisung-04`, `mainz-03`, `namensgleich-03`, `meeting-protokoll-04`: behoben durch C1. |
| Kein gemeinsames Wort (Paraphrase); Fragen ohne Textbezug. | `paraphrase-01` („Catering“, „Tagung“ ~ „Verpflegung“, „Fachtag“), `wartet-auf-01` („Worauf warte ich noch?“), `terminvorbereitung-06` („Was steht morgen an?“). Braucht Bedeutungssuche, Umschreibungen (E1) oder Abfragen nach Art und Zeit (D/E). **Bleibt offen.** |

## Entwurf

**Ein Index, eine Aufgabe.** `source_index.py` beantwortet: Welche Quellen
enthalten die Wörter dieser Frage, in welcher Reihenfolge? Er kennt weder
Arbeitsgedächtnis noch Antwortkontext.

* **Was im Index steht.** Titel, Beteiligte und Text jeder verwendbaren Quelle,
  nur gefaltet (klein, ohne Akzente, ß = ss, Leerraum vereinheitlicht). Der
  Originaltext bleibt in `episodes`; der Index ist jederzeit neu aufbaubar
  (`neu_aufbauen`). Tabellen: `source_index` (FTS5, Tokenizer `trigram`,
  Spalten Titel/Beteiligte/Text), `source_index_docs` (Zuordnung Zeile ↔
  Episode, Art), `source_index_skipped` (zu große Quellen).
* **Warum Trigramme.** FTS5 mit `trigram` findet jede Zeichenfolge ab drei
  Zeichen mitten im Text; „Rechnung“ trifft „Stromrechnung“, „Angebot“ trifft
  „Beratungsangebot“. Die Gegenrichtung („Stromrechnung“ gegen „Rechnung
  Strom“) trägt die Zerlegung der Fragewörter: Ein Wort ab acht Zeichen wird nur
  dort geteilt, wo **beide Teile im Bestand als ganze Wörter** stehen
  (Fugen-s/-es/-n/-en/-e fallen weg). Die Teile suchen am Wortanfang; ohne die Regel „ganzes Wort“
  zerfiel jedes Wort in Bruchstücke wie „rech“ und „nung“, die irgendwo stehen.
  Fragewörter (`FUNKTIONSWOERTER`) werden nicht gesucht; `lexical.terms_v1`
  bleibt als versionierter Vertrag unverändert.
* **Ranking.** BM25 mit den Gewichten Titel 4, Beteiligte 2, Text 1; bei
  Gleichstand die neuere Quelle, dann die ID (deterministisch).
* **Nur verwendbare Quellen** (Art Nachricht, Dokument oder Termin; nicht
  ignoriert; nicht durch eine neuere Fassung ersetzt; kein Gesprächsnachschlag),
  gesichert zweifach, unabhängig voneinander:
  1. *Pflege am Zustandswechsel:* Jeder Schreibweg des `EpisodeStore` (`_put`,
     `advance_source_head`, `enrich_chat_source`, `delete_summary`) ruft danach
     `source_index.synchronisieren` in derselben Transaktion auf. Die Funktion
     ist zustandslos: Sie liest, was `episodes` jetzt sagt, und nimmt die Quelle
     auf oder entfernt sie. Ignorieren entfernt, Wiederöffnen nimmt wieder auf,
     eine neue Fassung ersetzt die alte.
  2. *Prüfung beim Lesen (fail-closed):* `suchen` gibt nur Quellen zurück, die
     `episodes` in diesem Augenblick als verwendbar ausweist. Ein veralteter
     Indexeintrag bringt eine ignorierte, ersetzte oder gelöschte Quelle nicht
     zurück. Danach prüft `WorkingMemoryStore.resolve` jeden Abschnitt erneut
     (Beleg, Aktualität), wie bisher.
  Beim Start gleicht `abgleichen` beide Seiten ab (nur lesend, solange nichts
  abweicht, also ohne Schreibsperre).
* **Migration 12** legt die Tabellen an und nimmt alle verwendbaren Quellen auf
  (Erstbefüllung in derselben Transaktion). `verify` prüft das Schema beim
  Start, wie bei den anderen Erweiterungen. Braucht SQLite ab 3.34 mit FTS5;
  fehlt der Tokenizer, bricht die Migration mit einer klaren Meldung ab.
* **Keine stillen Grenzen.** Zu große Quellen (Text über 512 KB oder Dokument
  über 768 KB, wie in der alten wörtlichen Suche) stehen nicht im Index, werden
  aber gezählt (`nicht_indexiert`, `abdeckung`). Ein abgeschnittenes Ergebnis
  nennt die Gesamtzahl der Treffer. Wörter der Frage ohne Vorkommen
  (`ohne_treffer`) und gekürzte Fragen (`frageworte_gekuerzt`) stehen im
  Ergebnis.

**Fusion (`source_candidates.py`).** Wortsuche und Index liefern je bis zu 64
Quellen. Die Rangfusion (RRF, k = 30) vereint sie über die **Quelle**; aus jeder
Quelle kommt ein Abschnitt, damit zwölf Plätze zwölf Quellen sind. Kennt das
Arbeitsgedächtnis für eine Indexquelle keinen Abschnitt der Wortsuche, wählt
`WorkingMemoryStore.best_reference` den Abschnitt mit den meisten Suchwörtern. Eine
Quelle ohne eingeordnete Abschnitte kann kein Beleg werden; sie wird gezählt.
Fällt der Index aus (Datenbankfehler), gilt allein die Wortsuche, und die Zählung
sagt es. `_ordered_refs` (Projekt zuerst, Zeitraum zuerst) und alles danach sind
unverändert.

**Ausweis im Kontext.** Der Arbeitsstand trägt unter `search` die Zählung:
Treffer im Index, Quellen der Wortsuche, Suchwörter, nicht eingeordnete Quellen,
geprüfte und verworfene Kandidaten. Bei begrenzter Auswahl nennt die Antwort
Zahlen: „Es passten mindestens 37 Quellen; geprüft wurden 12.“

**Wörtliche Suche (`source_search.py`).** Gleiche Semantik wie vorher (Zeichenfolge
im Text, `casefold`), jetzt über den Index: Er nennt Kandidaten seitenweise
in ID-Reihenfolge, und jeder wird am Originaltext bestätigt (der Index faltet
Akzente und findet ein Übermaß). Nach 21 bestätigten Treffern ist Schluss; das
Budget von 0,5 Sekunden und die Obergrenze von 5.000 Kandidaten gelten nur der
Bestätigung, und ein Überschreiten liefert wie bisher keinen Teiltreffer.

### Entscheidungen, die die Messung getroffen hat

(Die Einzelmessungen dieser Tabelle liefen vor dem Zusammenführen mit C1, auf
Beständen ohne Termine; „von 136“ bzw. „von 127“ ist die Zahl der erwarteten Belege
mit Episode.)

| Frage | Ergebnis |
|---|---|
| Trigramm oder Wortindex (`unicode61`)? | Auf 10.000 Rauschquellen 90 gegen 87 von 127 erwarteten Belegen in den ersten zwölf Quellen, auf 45.000 86 gegen 82 (nur Index, gleiche Zerlegung). Der Trigramm-Index ist 3× größer und rund 2,5× langsamer. Gewählt: Trigramm, weil er Wortteile ohne Wortliste findet und der Zugewinn im Bestand mit echten Komposita größer sein dürfte als in dieser kleinen Welt. **Der Preis ist Platz** (siehe Größe). |
| Abschnitte je Quelle | 1 gegen 2: 96 gegen 91 von 136 (10.000 Rauschquellen), auf 50.000 94 gegen 85. Gewählt: 1. |
| RRF-Konstante | k = 10/30/60: 99/97/96 (10.000) und 95/95/94 (50.000). Gewählt: 30. Standardwert 60 ist kaum schlechter; der Unterschied liegt im Rauschen der kleinen Welt. |
| Gewicht des Index | Doppeltes Gewicht für den Index: 98 (10.000), aber 90 (50.000); doppeltes Gewicht für die Wortsuche: 93 (10.000). Gewählt: gleich. |
| Wortstamm und Zerlegung | Nur Index, 10.000, erwartete Belege in den ersten zwölf Quellen von 127: ohne beides 86, nur Zerlegung 91, nur Stamm 85, beides 90. Die Zerlegung trägt, der Wortstamm („einreichen“ → „einreich“) nicht; er wurde wieder entfernt (Messlatte mit Stamm: 121/96/96, ohne 119/97/95 von 136). |

## Messung

Ohne Modell (Stufe „Abruf“), Welt v1, 77 Fragen, `python -m messlatte lauf
--welt messlatte/welt --modell keins [--rauschen N]`. „Basis“ ist der Stand vom
29. September (`4fb80b8`), „C1“ der Stand mit Terminen im Gedächtnis (`b271de2`),
„C2“ dieses Paket auf C1. Berichte: `docs/evaluations/messlatte/2026-09-29-nach-c1-*`
und `2026-09-29-nach-c2-*`.

| Kennzahl | 0: Basis | C1 | **C2** | 10.000: Basis | C1 | **C2** | 50.000: Basis | C1 | **C2** |
|---|---|---|---|---|---|---|---|---|---|
| Erwartete Belege gefunden | 95 von 136 | 101 von 136 | 119 von 136 | 85 von 136 | 91 von 136 | 97 von 136 | 81 von 136 | 87 von 136 | 95 von 136 |
| Fragen mit allen Belegen | 42 von 71 | 47 von 71 | 60 von 71 | 37 von 71 | 41 von 71 | 49 von 71 | 35 von 71 | 39 von 71 | 46 von 71 |
| Belege auf Rang 1 | 29 von 136 | 26 von 136 | 31 von 136 | 29 von 136 | 26 von 136 | 31 von 136 | 29 von 136 | 26 von 136 | 29 von 136 |
| … bis Rang 5 | 82 von 136 | 85 von 136 | 94 von 136 | 75 von 136 | 80 von 136 | 81 von 136 | 73 von 136 | 77 von 136 | 74 von 136 |
| … bis Rang 12 | 93 von 136 | 99 von 136 | 117 von 136 | 83 von 136 | 89 von 136 | 95 von 136 | 79 von 136 | 85 von 136 | 93 von 136 |
| Fragen mit verbotenen Belegen im Kontext | 15 von 77 | 15 von 77 | 21 von 77 | 15 von 77 | 14 von 77 | 18 von 77 | 12 von 77 | 12 von 77 | 18 von 77 |
| Rückfragen mit allen Bedeutungen | 0 von 7 | 0 von 7 | 0 von 7 | 0 von 7 | 0 von 7 | 0 von 7 | 0 von 7 | 0 von 7 | 0 von 7 |
| Abruf je Frage, Median | 0.02 s | 0.06 s | 0.06 s | 0.09 s | 0.14 s | 0.21 s | 1.37 s | 0.70 s | 0.81 s |
| Abruf je Frage, P95 | 0.03 s | 0.11 s | 0.10 s | 0.32 s | 0.41 s | 0.47 s | 5.91 s | 2.61 s | 2.67 s |
| Abruf je Frage, Höchstwert | 0.04 s | 0.28 s | 0.12 s | 0.60 s | 0.78 s | 0.69 s | 9.65 s | 4.89 s | 4.99 s |
| Dauer des ganzen Laufs | 4 s | 15 s | 8 s | 86 s | 334 s | 175 s | 1794 s | 1051 s | 1060 s |

Die Läufe liefen in einer Entwicklungsumgebung mit wechselnder Last (zeitweise
bis zu 25 gleichzeitige Prozesse auf vier Kernen); Zeiten sind nur innerhalb
eines kontrollierten Nachlaufs vergleichbar (siehe unten). Die Zahl der Belege
schwankt von Lauf zu Lauf um etwa ±2, weil Episoden-IDs zufällig sind und
Gleichstände danach entschieden werden (gleicher Bestand, zwei Läufe:
10.000 Rauschquellen 96 und 97, 50.000 Rauschquellen 95 und 95 von 136, mit
verschiedenen Einzelfragen).

Fragen, die sich mit C2 gegenüber C1 verbessern oder verschlechtern:

* **ohne Rauschen.** Verbessert (15): `kontakt-vor-jahren-01`, `-03`, `-04`,
  `mainz-01`, `-02`, `-04`, `namensgleich-04`, `paraphrase-01`, `-04`, `profil-01`,
  `-02`, `terminvorbereitung-01`, `zeitraum-06`, `zusage-abgesagt-02`, `-03`.
  Verschlechtert (1): `terminvorbereitung-02` (verliert `-008`).
* **10.000 Rauschquellen.** Verbessert (11): `adresse-geaendert-01`,
  `kontakt-vor-jahren-01`, `-03`, `mainz-01`, `-04`, `namensgleich-04`, `profil-02`,
  `terminvorbereitung-01`, `zeitraum-05`, `-06`, `zusage-abgesagt-02`.
  Verschlechtert (4): `mainz-07` (verliert `mainz-005`), `meeting-protokoll-06`,
  `profil-01` (verliert `profil-001`), `terminvorbereitung-03`.
* **50.000 Rauschquellen.** Verbessert (11): `adresse-geaendert-01`,
  `kontakt-vor-jahren-01`, `-03`, `mainz-02`, `-04`, `namensgleich-04`,
  `paraphrase-01`, `profil-02`, `terminvorbereitung-01`, `zeitraum-06`,
  `zusage-abgesagt-02`. Verschlechtert (4): `fremde-anweisung-04`, `mainz-01`,
  `meeting-protokoll-06`, `zeitraum-06` (verliert einen Termin, `mainz-009`).
  In einem zweiten Lauf über denselben Bestand ist `fremde-anweisung-04`
  vollständig; die Verluste an der Grenze der zwölf Plätze wechseln von Lauf zu
  Lauf.
* **Rang bis 5** sinkt auf 50.000 Rauschquellen von 77 auf 74 von 136: Die
  Fusion bringt mehr passende Quellen unter die ersten zwölf, ordnet sie aber
  nicht immer nach vorn. Für das Modell zählt die Menge der zwölf.
* **Verbotene Belege im Kontext** neu in 10 Fragen (ohne Rauschen), 9 (10.000)
  und 10 (50.000): `adresse-geaendert-02`, `-03`, `frist-verschoben-02`,
  `namensgleich-01`, `-02`, `-05`, `zeitraum-01`, `-04`, `zusage-abgesagt-01`
  (ohne Rauschen außerdem `adresse-geaendert-01`, `zeitraum-05`; mit 50.000
  außerdem `falle-05`). In keiner Frage ist einer verschwunden, außer `falle-04`
  auf 50.000 gegenüber der Basis.

Die Zahl **verbotener Belege im Kontext** steigt: Die Auswahl zeigt jetzt im Mittel
11,6 statt 8,3 verschiedene Quellen, und darunter sind auch die veralteten (alte
Adresse, alte Frist) und die der Namensvetter. Das ist kein neuer Fehler der
Suche, sondern die Kehrseite höherer Vollständigkeit: Die Quellen sind
verwendbar und passen zur Frage. Sie zu unterscheiden (neuer Stand vor altem,
Identität der Person) ist Sache von D und E; bis dahin entscheidet das Modell.
Ob es das schafft, misst die Stufe „Antwort“ auf dem Mac.

### Dauer und Größe

| Größe / Dauer | Messung |
|---|---|
| Erstbefüllung (Migration 12), Messlatte-Bestand mit 45.282 Episoden (kurze Texte, rund 130 Zeichen) | 3,8 s; danach Start mit Prüfung und Abgleich 0,5 s |
| Erstbefüllung, 50.000 Episoden mit je rund 1,8 KB deutschem Text (synthetisch, aus `docs/`) | 36,5 s; danach Start mit Prüfung und Abgleich 0,2 s. Für Mails à 4 KB sind grob 80 s zu erwarten |
| Indexpflege je aufgenommener Episode (1,8 KB) | 2,3 ms zusätzlich (1,6 → 3,9 ms je `record`) |
| Größe, Messlatte-Bestand 50.000 | Episodendatei 228 → 285 MB |
| Größe, 50.000 × 1,8 KB Text (91 MB Text) | 239 → 739 MB (Index rund 5,5× der Textmenge) |
| Suche im Index allein, Messlatte-Bestand 50.000 (Fragen der Welt, Trefferzahl im Hundert bis Tausend) | Median 21 ms, P95 61 ms (ruhiger Rechner) |
| Suche im Index allein, synthetischer Bestand 50.000 (drei zufällige Wörter, im Mittel 15.000 Treffer) | Median 140 ms, P95 323 ms (Last) |
| Wörtliche Suche, 50.000, seltene Zeichenfolge (Basis: nach 0,5 s leer) | 1–2 ms, vollständig (`Weinbergweg 12`: 2 Treffer, `MenüPilot Diät`: 3) |
| Wörtliche Suche, 50.000, häufiges Wort | 15 ms, 20 Treffer (`truncated`) |
| **Abruf je Frage, 50.000 (kontrollierter Nachlauf, gleicher Bestand)** | Basis-Stand C1: Median 0,49 s, P95 2,32 s. **C2: Median 0,65 s, P95 2,79 s.** Der Aufschlag entsteht durch fünf Kandidatenberechnungen je Frage (Suche, Anzeige, zweimal Frischeprüfung) mit je rund 25 ms Indexsuche und der größeren Wortsuche (64 statt 12). |

Wohin die Zeit einer Abruffrage bei 50.000 Quellen geht (Profil über 13 Fragen,
12,6 s): 10,0 s liegen in `_fresh`, das die Kandidaten je Frage vier- bis
fünfmal neu berechnet; davon rund 4,9 s in `candidate_signature` und 4,7 s in
der alten Wortsuche mit dem 500er-Budget, 1,6 s im neuen Index. Das größte
Einsparpotenzial liegt also nicht im Index, sondern darin, die Kandidaten je Frage
einmal zu berechnen (Zwischenspeicher in `prepare`/`render`). Nicht Teil von C2.

## Sabotageproben

Jede Zusicherung wurde absichtlich gebrochen, die Tests liefen, dann wurde
zurückgesetzt (`sabotage.py`, Wiederholung nach jeder Änderung an den Zusicherungen):

| Nr. | Bruch | scheiternde Tests | davon |
|---|---|---|---|
| 1 | Kompositum in der Frage: Zerlegung abgeschaltet | 8 | `test_kompositum_in_der_frage_findet_getrennte_woerter`, `test_zerlegung_teilt_nur_an_woertern_die_im_bestand_stehen`, `test_fugen_s_wird_bei_der_zerlegung_uebersprungen` und 5 weitere |
| 2 | Wortteil in der Quelle: Tokenizer unicode61 statt trigram | 2 | `test_wortteil_findet_das_kompositum`, `test_fremde_neue_quellen_aendern_die_reihenfolge_der_treffer_nicht` |
| 3 | Pflege: Ausschluss entfernt die Quelle nicht aus dem Index (_put) | 4 | `test_termine_landen_im_index_und_entzogene_verschwinden`, `test_ignorierte_quelle_kommt_nicht_zurueck_und_kehrt_beim_oeffnen_wieder`, `test_lesepruefung_gilt_auch_wenn_die_pflege_versagt` und 1 weitere |
| 4 | Pflege: Zustandswechsel im Speicher aktualisieren den Index nicht (_put) | 31 | `test_zu_viele_woerter_werden_gezaehlt_nicht_still_gekuerzt`, `test_termine_landen_im_index_und_entzogene_verschwinden`, `test_wortteil_findet_das_kompositum` und 28 weitere |
| 5 | Pflege: ersetzte Fassung bleibt im Index (advance_source_head) | 2 | `test_ersetzte_fassung_kommt_nicht_zurueck`, `test_lesepruefung_gilt_auch_fuer_ersetzte_fassungen` |
| 6 | Lesen: Verwendbarkeit wird beim Lesen nicht geprüft | 2 | `test_lesepruefung_gilt_auch_wenn_die_pflege_versagt`, `test_lesepruefung_gilt_auch_fuer_ersetzte_fassungen` |
| 7 | Migration: keine Erstbefüllung | 1 | `test_migration_allein_fuellt_den_index_auch_ohne_start_abgleich` |
| 8 | Start: kein Abgleich | 1 | `test_start_abgleich_repariert_fehlende_und_ueberzaehlige_eintraege` |
| 9 | Ranking: nicht nach BM25 sortiert | 3 | `test_seltenes_wort_schlaegt_haeufiges`, `test_ranking_ist_wiederholbar_und_unabhaengig_von_der_einfuegereihenfolge`, `test_bei_gleichem_rang_gewinnt_die_neuere_quelle` |
| 10 | Ranking: Gleichstand nicht nach Aktualität | 1 | `test_bei_gleichem_rang_gewinnt_die_neuere_quelle` |
| 11 | Grenzen: Gesamtzahl bei begrenztem Ergebnis nicht gezählt | 1 | `test_begrenztes_ergebnis_nennt_die_gesamtzahl` |
| 12 | Grenzen: zu große Quelle nicht gezählt | 3 | `test_migration_mit_grosser_quelle_zaehlt_sie_statt_sie_zu_verschweigen`, `test_zu_grosse_quelle_bleibt_draussen_und_wird_gezaehlt`, `test_oversize_sources_are_skipped_and_reported` |
| 13 | Fusion: nur die Wortsuche zählt | 4 | `test_index_findet_quelle_die_die_wortsuche_verfehlt`, `test_nicht_eingeordnete_quelle_wird_gezaehlt_und_nicht_zum_beleg`, `test_bereich_gilt_fuer_beide_quellen` und 1 weitere |
| 14 | Fusion: keine Begrenzung je Quelle | 1 | `test_je_quelle_hoechstens_ein_abschnitt` |
| 15 | Fusion: Quelle ohne Einordnung wird nicht gezählt | 1 | `test_nicht_eingeordnete_quelle_wird_gezaehlt_und_nicht_zum_beleg` |
| 16 | Wörtliche Suche: Kandidaten werden nicht am Original bestätigt | 2 | `test_search_matches_body_literally_with_unicode_casefold`, `test_accent_folding_of_the_index_does_not_widen_the_literal_semantics` |
| 17 | Wörtliche Suche: Zeitbudget ohne Wirkung | 1 | `test_budget_exceeded_while_confirming_discards_partial_ids` |
| 18 | Wörtliche Suche: Grenze der bestätigten Kandidaten ohne Wirkung | 1 | `test_more_candidates_than_can_be_confirmed_are_reported_not_cut_silently` |

Die Proben 3 und 4 unterscheiden zwei Bruchstellen der Pflege (nur Ausschluss;
jede Änderung); die Probe 6 sichert die Prüfung beim Lesen unabhängig von der
Pflege (die Tests legen absichtlich veraltete Indexeinträge an); die Probe 7
prüft die Erstbefüllung der Migration ohne das Netz des Start-Abgleichs (die
Probe „keine Erstbefüllung“ blieb zunächst unbemerkt, weil der Abgleich beim
Start dieselbe Lücke schloss; dafür gibt es jetzt einen eigenen Test). Die
Probe 10 blieb zunächst unbemerkt, weil der Test vom Zufall der Episoden-IDs
abhing; er prüft jetzt acht Quellen in genau absteigender Zeit.

## Wortteile nur für die letzten N Jahre (Einstellung `suchindex.wortteile_jahre`)

Der Trigramm-Index ist rund fünfmal so groß wie der Text. Wer Platz sparen will, begrenzt die Wortteile auf die
letzten N Jahre: Ältere Quellen stehen dann nur in einem zweiten, **wortbasierten Index** (`source_index_woerter`,
FTS5 mit `unicode61`, Migration 15). Vorgabe ist **0**: alle Quellen mit Wortteilen, der zweite Index bleibt leer, und
die Suche verhält sich wie zuvor (gemessen: keine Frage der Messlatte weicht ab, siehe unten).

* **Eine Quelle steht in genau einem Index** (`source_index_docs.wortteile`, 1 = Trigramm). Maßgeblich ist das Alter
  der Quelle (`occurred_at`, sonst `recorded_at`) gegen „heute“ minus N Jahre; in der Messlatte ist „heute“ der Stichtag
  der Welt. Undatierte Quellen bekommen Wortteile.
* **Die Grenze wandert.** Neue Quellen kommen nach ihrem Alter in den passenden Index (eine importierte Mail von vor
  fünf Jahren sofort in den Wortindex). Was mit der Zeit zu alt wird, zieht `abgleichen` beim Start um
  (`umstufen`; `stimmt` erkennt es ohne Schreibsperre). Bei laufender App geschieht das erst beim nächsten Start.
* **Eine Änderung der Einstellung baut um** (`EpisodeStore.suchindex_einstellen`). Der Umbau stuft nur die Quellen
  um, die im anderen Index stehen müssten (`umstufen`, seitenweise zu 500, die Sperre gibt zwischen den Seiten frei);
  das Ergebnis gleicht einem vollständigen Neuaufbau (`neu_aufbauen`, geprüft im Test), ohne alles neu zu lesen. Eine
  Quelle steht dabei nie in keinem Index: Sie wird in derselben Transaktion aus dem einen entfernt und im anderen
  aufgenommen, die Suche ist also währenddessen vollständig. Danach werden beide FTS5-Indizes zusammengeführt
  (`optimize`) und der frei gewordene Platz per `VACUUM` an das Dateisystem zurückgegeben. **Beides ist nötig:** Ein
  erster Versuch ohne das Zusammenführen machte den Index von 432 auf 541 MB *größer*, weil FTS5 gelöschte Quellen erst
  beim Zusammenführen freigibt. Die Einstellung steht in `einstellungen.json` (`suchindex.wortteile_jahre`) und im
  Index (`source_index_meta`); beim Start gleicht `suchindex_routes.anwenden` beide ab (nach einer Wiederherstellung kann
  der Index aus einer Sicherung anders stehen).
* **Suche.** `source_index.suchen` fragt beide Indizes und vereint die Listen; Schnittstelle und Ergebnis
  (`Suchergebnis`) sind unverändert, `source_candidates` merkt nichts. Der Wortindex findet **ganze Wörter und
  Wortanfänge** („Rechnung“ findet „Rechnungen“), aber keine Wortteile mitten im Wort („Rechnung“ findet in alten
  Quellen nicht „Stromrechnung“). Die Zerlegung zusammengesetzter Fragewörter prüft beide Indizes; die wörtliche Suche
  (`literal_kandidaten`) liefert aus dem Wortindex, wenn die Zeichenfolge mit ganzen Wörtern beginnt (das letzte Wort
  darf ein Wortanfang sein) und blättert über beide nach Quellen-ID; jeder Kandidat wird weiter am Original bestätigt.
  Die Listen werden **nach BM25-Punkten** vereint, nicht nach Rang: Ein Abwechseln nach Rang (erster Versuch) hob den
  einzigen Treffer des kleineren Index auf Platz 2, auch wenn er schwach war, und kostete in der Messlatte mit Rauschen
  zwei Belege mehr. Die Punkte der beiden Indizes sind nicht identisch skaliert (eigene Wortstatistik), aber
  vergleichbar genug; die Messung stützt das.
* **Oberfläche:** Einstellungen → Für Techniker → Suchindex: eine Auswahl „Wortteile suchen“ (in allen Quellen, in den
  Quellen des letzten Jahres, der letzten 2, 3, 5, 10 Jahre; seit der Fremdprobe, Befund 28, kein Zahlenfeld mehr; die Wahl
  gilt sofort), ein Satz Erklärung, die Zahl der Quellen je Index (im Singular „Die eine Quelle …“) und die belegte Größe des Index (`dbstat`; „unbekannt“, wenn diese SQLite sie nicht nennt).
  Routen: `GET`/`PUT /api/v1/suchindex` (`suchindex_routes.py`). Der Schalter ist umkehrbar (0 stellt alles zurück),
  deshalb ohne Rückfrage; die Anzeige sagt, wie viele Quellen umgestellt wurden.
* **Messlatte:** `python -m messlatte lauf … --wortteile-jahre N`; der Bericht nennt Einstellung, Verteilung und
  Indexgröße.

### Messung

Welt v1, ohne Modell, `--einordnung regel`, Stichtag 29.09.2026. Von den 176 Quellen der Welt sind 11 älter als zwei
Jahre (alle aus `kontakt-vor-jahren`: Oktober 2023 bis Juni 2024, dazu `adresse-geaendert-001/-002`,
`fremde-anweisung-001`).

| Kennzahl | Vorgabe 0 (vorher → nachher) | 2 Jahre (gegen vorher) | 10.000 Rauschquellen, Vorgabe 0 | 10.000, 2 Jahre |
|---|---|---|---|---|
| Erwartete Belege gefunden (von 136) | 124 → 124 | 124 | 109 → 109 | **110** |
| Fragen mit allen Belegen (von 71) | 64 → 64 | 64 | 57 → 57 | 57 |
| Belege auf Rang 1 / bis Rang 5 / bis Rang 12 | 26 / 88 / 106 → gleich | **24 / 87** / 106 | 24 / 72 / 90 → gleich | 24 / **74** / **91** |
| Fragen mit verbotenen Belegen (ungekennzeichnet) | 21 (15) → gleich | 21 (15) | 18 (13) → gleich | 18 (13) |
| Rückfragen mit allen Bedeutungen, unnötige | 7 von 7, 0 von 70 | gleich | gleich | gleich |
| Fragen, deren Belege oder verbotene Belege sich ändern | keine | keine | keine | 3 (unten) |

* **Vorgabe 0 ist identisch:** Bei beiden Bestandsgrößen weicht keine einzelne Frage ab.
* **Ohne Rauschen ändert sich bei 2 Jahren kein Beleg.** Die Fragen mit alten Quellen (`kontakt-vor-jahren-01` bis `-05`,
  Kategorien `rueckblick`, `paraphrase`, `identitaet`, und die Fragen nach der alten Adresse) finden dieselben Belege.
  Die **alten Belege rücken im Rang nach hinten**, vermutlich, weil die Punkte des Wortindex anders skaliert sind (eigene Wortstatistik) und schwächer ausfallen als die
  des Trigramm-Index: `kontakt-vor-jahren-01`: `-001` von Rang 1 auf 4, `-003` von 6 auf 10; `-02`: `-001` von 1 auf 2;
  `-04`: `-001` von 1 auf 2, `-003` von 3 auf 6. Junge Belege rücken nach vorn (`adresse-geaendert-04`: `-011` von 3
  auf 2; `namensgleich-01`: `-004` von 2 auf 1). Alle bleiben innerhalb der 16 Plätze; deshalb sinkt die Zahl der Belege
  auf Rang 1 von 26 auf 24 und bis Rang 5 von 88 auf 87, die bis Rang 12 nicht.
* **Mit 10.000 Rauschquellen** (davon rund ein Drittel, 3.337 von 10.176 Quellen, älter als zwei Jahre) ändern sich drei
  Fragen. `kontakt-vor-jahren-04` („… wegen einer Speiseplan-Software für Klinikküchen …“, Kategorie `paraphrase`)
  **verliert** `kontakt-vor-jahren-003`, eine Telefonnotiz vom 16.10.2023: Sie nennt „Küchensoftware“, und nur der
  Trigramm-Index findet „software“ *in* dem Kompositum. Das ist der vorhergesagte Preis der Einstellung und kein Fehler.
  Die Frage `kontakt-vor-jahren-01` (Kategorie `rueckblick`), in der „Küchensoftware“ als ganzes Wort steht, findet
  `-003` weiter (Rang 10). `terminvorbereitung-03` und `zeitraum-02` **gewinnen** je einen Beleg einer jungen Quelle
  (`terminvorbereitung-009`, `zeitraum-010`): Die Wortstatistik des Trigramm-Index ändert sich, wenn ein Drittel der
  Quellen fehlt, und die Reihenfolge an der Grenze der 16 Plätze verschiebt sich. Das ist dieselbe Schwankung von
  ±2 Belegen wie zwischen zwei Läufen (siehe oben), keine Wirkung auf alte Quellen.

| Größe (50.000 × 1,8 KB deutscher Text aus `docs/`, 88 MB, über sechs Jahre verteilt) | Vorgabe 0 | 2 Jahre |
|---|---|---|
| Quellen mit Wortteilen / nur als Wörter | 50.000 / 0 | 16.709 / 33.291 |
| Belegter Platz des Index (`dbstat`) | 432 MB | **245 MB (−43 %)** |
| Episodendatei | 662 MB | **474 MB** |
| Suche im Index allein, Median / P95 (Last) | 61 / 148 ms | 32 / 54 ms |
| Umbau auf die Einstellung (Umstufen, Zusammenführen, `VACUUM`) | – | 42 s |
| Zurück auf 0 | – | 46 s; Index wieder 431 MB |

Messlatte-Bestand mit 10.000 Rauschquellen (kurze Texte): Index 12,2 MB gegen 9,7 MB. Auf Bestände mit langen
Mails wirkt die Einstellung stärker, weil dort der Text den Index dominiert. Die Zeit des Umbaus wächst mit der Zahl
der Quellen. Das Umstufen gibt die Sperre zwischen den Seiten frei; das Zusammenführen und der `VACUUM` am Ende halten
sie für ihre Dauer (Sekunden je Gigabyte).

### Sabotageproben der Einstellung

Wie oben: Zusicherung brechen, `test_suchindex_wortteile.py`, `test_source_index.py` und `test_source_search.py` laufen
lassen, zurücksetzen (Skript liegt nicht im Repository). 18 von 18 gefangen.

| Bruch | scheiternde Tests | davon |
|---|---|---|
| Einstellung ignoriert: jede Quelle bekommt Wortteile | 10 | `test_einstellung_ueberlebt_den_neustart`, `test_neue_quellen_kommen_je_nach_alter_in_den_richtigen_index`, `test_wortteil_mitten_im_wort_findet_nur_die_junge_quelle` und weitere |
| Einstellung ignoriert: Grenze immer leer | 10 | `test_zwei_jahre_verschiebt_nur_aeltere_quellen_in_den_wortindex` und weitere |
| Grenze falsch herum (jüngere statt ältere im Wortindex) | 10 | `test_zwei_jahre_verschiebt_nur_aeltere_quellen_in_den_wortindex` und weitere |
| Änderung stuft nicht um | 9 | `test_zwei_jahre_verschiebt_nur_aeltere_quellen_in_den_wortindex`, `test_die_grenze_liegt_bei_n_jahren_vor_dem_stichtag` und weitere |
| Suche fragt den Wortindex nicht | 9 | `test_suche_findet_junge_und_alte_quellen_zusammen` und weitere |
| Wortindex-Treffer fallen in der Vereinigung weg | 8 | `test_suche_findet_junge_und_alte_quellen_zusammen` und weitere |
| Vereinigung nach Rang statt nach Punkten | 2 | `test_treffer_beider_indizes_stehen_nach_punkten_nicht_nach_herkunft[True]`, `[False]` |
| Lesen prüft die Verwendbarkeit nicht (Wortindex) | 5 | `test_lesepruefung_gilt_auch_fuer_den_wortindex` und weitere |
| Löschen entfernt nur aus dem Trigramm-Index | 2 | `test_ignorierte_alte_quelle_verschwindet_aus_dem_wortindex`, `test_umbau_gleicht_einem_neuaufbau` |
| Abgleich stuft gealterte Quellen nicht um | 2 | `test_mit_der_zeit_alternde_quellen_zieht_der_abgleich_um`, `test_neustart_stuft_gealterte_quellen_um` |
| Start-Prüfung übersieht falsch eingestufte Quellen | 2 | dieselben beiden |
| Gesamtzahl zählt nur den Trigramm-Index | 1 | `test_begrenztes_ergebnis_zaehlt_beide_indizes` |
| Zerlegung sieht den Wortindex nicht | 1 | `test_zerlegte_fragewoerter_finden_auch_alte_quellen` |
| Wörtliche Suche fragt den Wortindex nicht | 2 | `test_woertliche_suche_findet_alte_quellen_bei_ganzen_woertern`, `test_woertliche_suche_blaettert_ueber_beide_indizes` |
| Route speichert die Einstellung nicht | 1 | `test_route_nennt_stand_und_setzt_die_einstellung` |
| Start gleicht die Einstellung nicht ab | 1 | `test_start_bringt_den_index_auf_die_gespeicherte_einstellung` |
| Jahre werden nicht geprüft | 1 | `test_ungueltige_jahre_werden_abgewiesen` |
| Umbau führt die Indizes nicht zusammen (Platz bleibt belegt) | 1 | `test_umbau_macht_den_index_kleiner` |

Die erste Fassung der Probe „Änderung stuft nicht um“ ließ einen Test endlos laufen statt scheitern (er wartete auf ein
Ende, das nie kam); die Tests und `suchindex_einstellen` begrenzen ihre Durchgänge jetzt.

## Grenzen und offene Punkte

* **Größe des Index.** Der Trigramm-Index (mit Textkopie) ist rund das 5- bis
  6-Fache des Textes. Gemessen mit 50.000 deutschen Texten à 1,8 KB: Datei ohne
  Index 239 MB, mit Index 739 MB. Für 50.000 Mails à 4 KB wären es rund 1,2 GB.
  Ein Wortindex käme mit etwa einem Drittel aus, findet aber keine Wortteile.
  Die Einstellung `suchindex.wortteile_jahre` (siehe oben) macht aus diesem Tausch eine
  Wahl des Nutzers; Vorgabe bleibt der volle Trigramm-Index. Bei 2 Jahren sank der
  Index im Beispiel von 432 auf 245 MB.
* **Wortteile in alten Quellen** (mit Einstellung über 0): Komposita mitten im Wort sind
  dort nicht mehr auffindbar (`kontakt-vor-jahren-04`). Die Alterung der Grenze wirkt erst
  beim nächsten Start.
* **Ranking-Drift.** BM25 hängt von der Größe des Bestands ab. Neue, fremde Mails
  verändern die Reihenfolge bekannter Fragen an der Grenze der zwölf Plätze:
  100 unverwandte neue Mails ändern bei 9 von 77 Fragen die Kandidatenliste (5
  davon, die bisher nicht schon durch die Kandidatensignatur veralteten). Die
  Frischeprüfung (`_fresh`) verlangt gleiche Kandidaten, also gelten solche
  gespeicherten Antworten als veraltet („Bitte frage erneut“). Das ist sicher,
  aber lästiger. Abhilfe: `_fresh` prüft je Beleg der Grundlage statt die ganze
  Liste, ergänzt um eine Indexsignatur (Menge der passenden Quellen, unabhängig
  vom Ranking). Nicht umgesetzt, weil es die Frischeprüfung berührt.
* **Zwölf Plätze.** Mit 10.000 Rauschquellen gehen im Mittel 5 der 12 Plätze an
  Rauschen. Mehr Kandidaten helfen: 20 Abschnitte mit 40.000 Zeichen Kontext
  finden 104 statt 97 von 136 (10.000). Das kostet Modellzeit (Kontext rund 1,7×)
  und ist eine Entscheidung für E2/E3 (zweistufige Auswahl), nicht für C2.
* **Paraphrase und Fragen ohne Textbezug** (siehe Befund) bleiben offen.
* **Quellen ohne eingeordnete Abschnitte** finden Wortsuche und Index, aber sie
  können kein Beleg werden, solange die Einordnung sie nicht erreicht (zu groß,
  offen, zurückgestellt). Die Zählung weist sie aus.
* **Bedeutungssuche** (Embeddings) ist nicht Teil von C2.
