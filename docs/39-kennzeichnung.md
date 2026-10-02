# Namensvettern und Zeiträume im Antwortkontext kennzeichnen (Nachtrag zu E2)

Stand: 30. September 2026. Code: `kennzeichnung.py`, dazu gezielte Haken in `working_memory_answers.py`,
`satzantwort.py`, `personenfrage.py`, `time_scope.py`, `agent.py`; Messlatte: `abruf.py`, `bewertung.py`,
`bericht.py`, `ergebnisse.py`. Tests: `test_kennzeichnung.py`, `test_kennzeichnung_saetze.py`,
`test_kalenderzeitraum.py`, `messlatte/tests/test_kennzeichnung.py`. Berichte:
`docs/evaluations/messlatte/2026-09-30-namensvettern-regel-*`.

E2 kennzeichnet im Kontext des Modells, was die **Akten** als überholt führen (`ueberholt`,
[`35-belegte-antworten.md`](35-belegte-antworten.md)). Zwei Arten verbotener Quellen blieben ungekennzeichnet, obwohl
Kingfisher sie kennt: die Mail des **anderen Menschen gleichen Namens** (seit C3 über die Adresse unterschieden,
[`C3-identitaet.md`](evaluations/messlatte/C3-identitaet.md)) und die Quelle **außerhalb des gefragten Zeitraums**.
Die Suche legt beide schon nach hinten; im Kontext stand nichts dran. Jetzt steht es dran. Nichts wird entfernt.

## Was wir zuerst sahen: die 15 (mit 10.000 Rauschquellen 13) Fragen

Endstand vor diesem Paket (Commit `64bf811`, Regel-Einordnung, ohne Modell): 15 Fragen mit verbotenen Belegen im
Kontext, die der Kontext nicht kennzeichnet (27 Belege). Die Tabelle sagt je Frage, was es ist und was daraus wurde.
„Ältere Fassung“ heißt: dieselbe Person oder Sache, ein früherer Stand, aber ohne gemeinsamen Gegenstand in der Akte,
den E2 erkennen könnte.

| Frage | Art | Verbotene, ungekennzeichnete Belege | Danach |
|---|---|---|---|
| namensgleich-02 | Namensvetter | 004, 005 (Catering, gefragt ist das Institut) | gekennzeichnet `andere_person` |
| namensgleich-05 | Namensvetter | 006, 009 (Institut, gefragt ist das Catering) | gekennzeichnet `andere_person` |
| namensgleich-01 | Namensvetter + ältere Fassung | 006, 009, 010 (Institut); 003 (alter Preis derselben Person) | 3 von 4 gekennzeichnet, **003 bleibt** |
| zeitraum-01 | Zeitraum „letzte Woche“ | 003, 005, 013 | gekennzeichnet `ausserhalb_zeitraum` |
| zeitraum-05 | Zeitraum „diese Woche“ | 010, 011 | gekennzeichnet `ausserhalb_zeitraum` |
| zeitraum-04 | Zeitraum „im Frühjahr“ | 009, 010, 011, 013 | gekennzeichnet `ausserhalb_zeitraum` |
| falle-04 | Falle mit Zeitraum „im Juli 2026“ | 007 (Dez. 2025), 010 (Jan. 2026) | gekennzeichnet `ausserhalb_zeitraum` |
| meeting-protokoll-01 | Zeitraum „im September“ | 003 (Transkript vom 12. August) | gekennzeichnet `ausserhalb_zeitraum` |
| meeting-protokoll-02 | ältere Fassung | 003 (Zusage des ersten Treffens) | bleibt |
| meeting-protokoll-03 | ältere Fassung | 003 (Zusage des ersten Treffens, „im letzten Treffen“ ist kein Kalenderzeitraum) | bleibt |
| terminvorbereitung-04 | ältere Fassung | 004 (Telefonnotiz, später per Mail korrigiert) | bleibt |
| adresse-geaendert-02 | ältere Fassung | 005 (Mail von der alten Adresse, nennt die Adresse nicht) | bleibt |
| frist-verschoben-01 | Überholtes ohne Akte | 004 (Notiz ohne erkennbaren Bezug zur Stiftung, ohne Modell) | bleibt |
| falle-02 | Falle | 005 (Angebot 2025, gefragt ist 2026: „2026“ ist der Gegenstand, nicht der Eingang) | bleibt |
| falle-05 | Falle | 001 (Kongress vom März 2026, „nächster“ gefragt) | bleibt |

Nach Art gezählt: 3 Namensvettern, 5 Zeiträume (falle-04 ist Falle und Zeitraum), 4 ältere Fassungen, 2 Fallen
ohne Zeitraum, 1 Überholtes ohne Akte. Mit 10.000 Rauschquellen fehlen falle-04 und zeitraum-05 in der Liste (ihre
verbotenen Quellen kommen dann nicht in den Kontext), die übrigen 13 sind dieselben.

## Was gekennzeichnet wird

**Namensvettern (`andere_person`).** `personenfrage.gemeinte_unter_namensvettern` liefert je Name der Frage, der mehreren
Menschen gehört und für den die Frage eine Person entscheidet, die gemeinte Person und die anderen. Die Entscheidung
ist dieselbe wie bei den Kandidaten der Suche (`unterscheidet`: ein Wort der Frage, das nur zu einer Person passt,
etwa „Catering“ oder „Fragebogen“), nicht eine zweite Regel. Eine Quelle trägt die Kennzeichnung, wenn sie die Adresse
eines Namensvetters führt und **nicht** die der gemeinten Person. Nicht gekennzeichnet werden: eine Quelle mit
beiden Adressen, ein bloßer Name ohne Adresse („Alex Winter hat angerufen“, geraten wird nie), Namen, deren Adressen
nacheinander wirken (Adresswechsel, `nacheinander`), Teilnamen. **Ist die Person nicht eindeutig, bleibt es bei der
Rückfrage (E1)**: Es gibt keine neue Rückfrage und keine neue Ausnahme (unnötige Rückfragen 0 von 70). Nach einer
Antwort auf die Rückfrage gilt der Rahmen der gewählten Bedeutung; er enthält nur die Quellen dieser Person, da gibt
es nichts zu kennzeichnen.

**Zeiträume (`ausserhalb_zeitraum`).** Den Zeitraum liest `time_scope.mentioned_period` (gestern, diese und letzte
Woche, letzter Monat, die letzten N Tage; dasselbe, was die Suche schon ordnet) und neu `time_scope.kalenderzeitraum`:
ein Monat oder eine Jahreszeit („im Frühjahr“, „im Juli 2026“, „im September“), aber **nur im Rückblick**
(Frage mit „passiert“, „besprochen“, „zugesagt“, „wurde“ …) und **nur, wenn der Zeitraum begonnen hat**. „Wann ist die
Abnahme im Oktober?“ meint den Inhalt, nicht den Eingang, und „im Oktober“ ohne Jahr, das noch kommt, ist
mehrdeutig: dann gibt es keinen Zeitraum. Das Ordnen der Suche bleibt unverändert (`kalenderzeitraum` wird nur zum
Kennzeichnen gelesen). Eine Quelle außerhalb trägt das Datum der Quelle: ein Termin nach seinem Beginn
(`occurred_at` der Termin-Episode), eine Mail nach ihrem Datum (`reference_time`). Eine Quelle ohne eigenes Datum ist
nie „außerhalb“.

**Im Kontext des Modells.** Die Zeile der Quelle trägt das Feld `andere_person` (Name, Adresse dieser Person,
gemeinte Adresse) oder `ausserhalb_zeitraum` (Datum der Quelle, gefragter Zeitraum). Solche Zeilen stehen **hinter**
den passenden, ihre Kennungen S1… bleiben. Die Anweisung der Auswahl und die der Satzanfrage nennen je einen Satz
dazu, wie bei `ueberholt`.

**Satzprüfung.** Ein Satz, der sich **nur** auf Belege mit derselben Kennzeichnung stützt, besteht nicht
(`satzantwort._fremde_quellen`), außer er sagt es ausdrücklich: „ein anderer Alex Winter“, „Namensvetter“,
„gleichnamig“, „nicht derselbe“; „außerhalb des Zeitraums“, „nicht im gefragten Zeitraum“
(`kennzeichnung.benennt`). Stützt er sich auch auf einen passenden Beleg, trägt dieser ihn. Anders als beim
Wandel einer Frist ergänzt das Programm **nichts**. Damit der ausdrückliche Hinweis die Namensprüfung der
Satzprüfung übersteht, gelten „außerhalb“, „Zeitraum“, „Namensvetter“, „gleichnamig“ und „andere(r)“ nicht als
erfundene Namen (`satzpruefung._FUNKTION`, `_GATTUNG`).

**Gespeichert und beim Anzeigen.** Der Rahmen (gemeinte Personen, Zeitraum) steht in `answer['kennzeichnung']` und in
der gespeicherten Satzantwort. Beim Anzeigen wird daraus gerechnet, nicht neu geraten: „letzte Woche“ meint morgen
noch dieselbe Woche wie heute. Ein ungültiger Rahmen macht die Antwort veraltet (fail-closed). Der Zitatmodus nennt
es in der Überschrift („· andere Person“, „· außerhalb des Zeitraums“) und darunter („Andere Person gleichen Namens
(Alex Winter, …)“, „Außerhalb des gefragten Zeitraums (der letzten Woche): Quelle vom 23.03.2026“). Die Belegliste der
Satzantwort und `satzantwort.struktur` (je Beleg `kennzeichen`) tragen es ebenfalls.

**Messlatte.** Der Kandidatenerfasser liest alle drei Felder. `bewertung`/`bericht` zählen jede Art als
gekennzeichnet (ungekennzeichnet sinkt) und weisen sie getrennt aus: Kennzahl „gekennzeichnet nach Art“,
Fehlerliste („ungekennzeichnet: …; gekennzeichnet: überholt: …; andere Person: …“), JSON
(`verbotene_belege_gekennzeichnet`, `verboten_gekennzeichnet`). Ein Beleg mit zwei Arten zählt in beiden. Die Welt
blieb unverändert; der Test baut sein Szenario (zwei Alex Winter, ein Angebot über Monate, ein Termin, der im August
angelegt wurde und in der letzten Woche beginnt) in einer Kopie der Mini-Welt.

## Messung

Welt v1, 77 Fragen, Regel-Einordnung, ohne Modell. „vorher“ ist der Endstand (Commit `64bf811`, Berichte
`2026-09-30-endstand-regel-*`, dieselben Zahlen wie in diesem Worktree vor der Änderung nachgemessen), „nachher“
Commit `2391d82`.

| Kennzahl | 0: vorher | nachher | 10.000: vorher | nachher |
|---|---|---|---|---|
| Erwartete Belege gefunden (von 136) | 124 | 124 | 109 | 109 |
| Fragen mit allen Belegen (von 71) | 64 | 64 | 57 | 57 |
| Fragen mit verbotenen Belegen im Kontext (von 77) | 21 | 21 | 18 | 18 |
| verbotene Belege im Kontext | 37 | 37 | 32 | 32 |
| **Fragen mit verbotenen Belegen ungekennzeichnet** | 15 | **8** | 13 | **8** |
| **verbotene Belege ungekennzeichnet** | 27 | **8** | 23 | **8** |
| davon gekennzeichnet: überholt | 10 | 10 | 9 | 9 |
| davon gekennzeichnet: andere Person | – | 7 | – | 7 |
| davon gekennzeichnet: außerhalb des Zeitraums | – | 12 | – | 8 |
| Rückfragen mit allen Bedeutungen (von 7) | 7 | 7 | 7 | 7 |
| Unnötige Rückfragen | 0 von 70 | 0 von 70 | 0 von 70 | 0 von 70 |
| Erwartete Belege gekennzeichnet | – | 0 | – | 0 |
| Kontext der Auswahl, Zeichen (Mittel) | 20.021 | 20.615 | 17.628 | 18.214 |
| Abruf je Frage, Median / P95 | 0,11 / 0,17 s | 0,11 / 0,17 s | 0,87 / 1,75 s | 0,95 / 1,85 s |

Die Zahl der Belege, Vollständigkeit und Rückfragen ändern sich nicht (nichts wird entfernt, nichts umgeordnet, was
die Suche liefert: `basis` und Ränge sind unverändert). Kein erwarteter Beleg trägt eine der neuen Kennzeichnungen (am JSON
geprüft, beide Größen). Die 8 übrigen Belege stehen in den 8 Fragen der nächsten Tabelle.

Kosten: Der Kontext wächst um rund 600 Zeichen (3 %); mit 10.000 Quellen kostet das Nachschlagen der genannten
Personen und die Kennzeichnung im Median etwa 0,08 s je Frage. Ein erster Stand rief das Nachschlagen der Namen
zweimal auf (Median 1,14 s statt 0,87 s); jetzt rechnet `Agent._personen_der_frage` es einmal für Quellen und
Namensvettern (Test). Die Laufzeiten schwanken mit der Last der Maschine um einige Prozent.

### Was ungekennzeichnet bleibt und warum

| Frage | Beleg | Warum |
|---|---|---|
| namensgleich-01 | 003 | Der alte Preis (34 Euro) derselben Person; die Akte der Person ist mehrdeutig (zwei Adressen), also keine Akte, die „Stand“ führt. |
| adresse-geaendert-02 | 005 | Mail von der alten Adresse, die die Adresse nicht nennt: kein gemeinsamer Gegenstand. |
| meeting-protokoll-02, -03 | 003 | Zusage des ersten Treffens; „im letzten Treffen“ ist kein Kalenderzeitraum, der Gegenstand (Entwurf, Handbuch) steht in beiden Protokollen, ohne dass ein Wort den Wandel anzeigt. |
| terminvorbereitung-04 | 004 | Telefonnotiz mit „grob 15.000“, später per Mail auf 12.000 korrigiert; ohne Modell vergibt die Einordnung dem Absatz keine Art, die die Akte verbindet. |
| frist-verschoben-01 | 004 | Notiz zum Förderantrag ohne erkennbaren Bezug zur Stiftung (ohne Modell), also keine Akte, in der ihre Frist als ersetzt stünde. Ein Modell der Einordnung mit Erwähnungen würde sie verbinden. |
| falle-02 | 005 | Das Angebot stammt von 2025, gefragt ist „für 2026“: Das Jahr ist der Gegenstand, nicht der Eingang. Als Zeitraum gelesen, würde ein 2025 versandtes Angebot für 2026 zu Unrecht gekennzeichnet. |
| falle-05 | 001 | Der Kongress vom März 2026 hat schon stattgefunden, gefragt ist der nächste: Der Beleg ist richtig, nur kein „nächster“; das ist eine Frage der Antwort, nicht des Datums. |

Vier davon sind „ältere Fassung ohne gemeinsamen Gegenstand“ und brauchen mehr als Datum oder Adresse: die Einordnung
der Absätze (Modell der Ebene 1) oder ein Vergleich der Gegenstände. Das ist der Teil, den die Regel-Einordnung nicht
sieht und der mit einem echten Modell erst zu messen ist.

## Sabotageproben

Jede Zusicherung wurde absichtlich gebrochen (ein Ausdruck im Code ersetzt), die Tests dieses Pakets liefen, dann
wurde zurückgesetzt (23 von 23 gefangen; das Skript liegt nicht im Repository). Die erste Fassung der Tests fing K5
nicht: Die Suche legt Namensvettern und Zeiträume der Suche schon selbst nach hinten, der Test sah also nie eine Zeile,
die erst die Kennzeichnung versetzt. Der Test mit der Frage nach dem Frühjahr (kein Zeitraum der Suche) schließt die
Lücke.

| Nr. | Bruch | scheiternde Tests | davon |
|---|---|---|---|
| K1 | Namensvettern werden nicht gekennzeichnet | 10 | `test_die_frage_entscheidet_fuer_eine_person_…`, `test_das_modell_sieht_andere_person_…`, `test_namensvetter_sind_gekennzeichnet_…` (Messlatte) u. a. |
| K2 | Quelle mit beiden Adressen gilt als fremd | 1 | `test_eine_quelle_mit_beiden_adressen_und_ein_bloszer_name_…` |
| K3 | Quellen außerhalb des Zeitraums werden nicht gekennzeichnet | 6 | `test_eine_mail_zaehlt_nach_ihrem_datum_…`, `test_der_kontext_nennt_den_zeitraum_…` u. a. |
| K4 | Ein Termin zählt nach dem Anlegen statt nach seinem Beginn | 3 | `test_eine_mail_zaehlt_nach_ihrem_datum_ein_termin_nach_seinem_beginn` u. a. |
| K5 | Gekennzeichnete Zeilen stehen nicht hinten | 1 | `test_im_rueckblick_auf_das_fruehjahr_rutscht_die_neuere_quelle_hinter_die_passende` |
| K6 | Satzprüfung ignoriert Namensvettern und Zeiträume | 4 | `test_ein_satz_nur_aus_der_quelle_des_namensvetters_besteht_nicht` u. a. |
| K7 | Ein Satz fällt schon durch, wenn nur eine Quelle gekennzeichnet ist | 1 | `test_ein_satz_der_auch_die_passende_quelle_nennt_besteht` |
| K8 | Der ausdrückliche Hinweis genügt nie | 3 | `test_benennt_erkennt_nur_den_ausdruecklichen_hinweis` u. a. |
| K9 | Der Rahmen wird nicht mit der Antwort gespeichert | 3 | `test_ein_ungueltiger_gespeicherter_rahmen_macht_die_antwort_veraltet` u. a. |
| K10 | Die Frischeprüfung ignoriert einen ungültigen Rahmen | 1 | `test_ein_ungueltiger_gespeicherter_rahmen_macht_die_antwort_veraltet` |
| K11 | Kalenderzeitraum auch in Fragen, die nicht im Rückblick stehen | 1 | `test_kalenderzeitraum_gilt_nur_im_rueckblick_…[Bis wann …]` |
| K12 | Ein kommender Monat ohne Jahr wird geraten | 1 | `test_kalenderzeitraum_gilt_nur_im_rueckblick_…[… im Oktober …]` |
| K13 | Ohne Entscheidung der Frage gilt die erste Person als gemeint | 1 | `test_ohne_entscheidung_der_frage_gibt_es_keine_namensvettern_die_rueckfrage_bleibt` |
| K14 | Wer die Adresse wechselt, gilt als Namensvetter | 1 | `test_wer_nacheinander_die_adresse_wechselt_ist_kein_namensvetter` |
| K15 | Beim Anzeigen wird der gespeicherte Rahmen ignoriert | 1 | `test_gespeicherte_satzantwort_traegt_den_rahmen_…` |
| K16 | Die Auswahl bekommt keine Anweisung zu den neuen Feldern | 1 | `test_die_auswahl_bekommt_die_anweisung_zu_den_neuen_feldern` |
| K17 | Die Satzanfrage zeigt dem Modell die Kennzeichnung nicht | 1 | `test_die_satzanfrage_zeigt_dem_modell_die_kennzeichnung_…` |
| K18 | Der Zitatmodus sagt es nicht | 6 | `test_der_zitatmodus_zeigt_die_andere_person_hinten_und_sagt_es` u. a. |
| K19 | Die Namen werden zweimal nachgeschlagen | 1 | `test_die_namen_werden_fuer_quellen_und_namensvettern_nur_einmal_nachgeschlagen` |
| K20 | Messlatte: Erfasser liest nur „ueberholt“ | 6 | `test_der_erfasser_liest_alle_drei_kennzeichnungen_getrennt` u. a. |
| K21 | Messlatte: nur „überholt“ zählt als gekennzeichnet | 4 | `test_gekennzeichnete_verbotene_belege_stehen_je_art_…` u. a. |
| K22 | Messlatte: Bericht führt die Arten nicht aus | 1 | `test_der_bericht_fuehrt_die_arten_getrennt_in_kennzahl_und_fehlerliste` |
| K23 | Messlatte: Fehlerliste nennt die Art nicht | 1 | `test_der_bericht_fuehrt_die_arten_getrennt_in_kennzahl_und_fehlerliste` |

## Offene Punkte

* **Oberfläche (erledigt).** `SatzAntwort.tsx` zeigt im „Weg nach unten“ hinter dem Titel des Belegs ruhig, was der
  Sidecar kennzeichnet: „Andere Person gleichen Namens (Alex Winter, …)“ und „Außerhalb des gefragten Zeitraums (der
  letzten Woche): Quelle vom 28.09.2026“, wie „überholt durch [1]“ (`belegHinweis.ts`, gedämpfter Beleg). Browserprobe:
  `scripts/probe_satzantwort_ui.py` (Fragen „vetter“ und „zeitraum“), Test `app/kingfisher/tests/beleg-hinweis.test.mjs`.
* **Projekt als Entscheidung.** Die Person wird über Wörter der Frage entschieden, die zu einer Adresse passen. Dass
  eine Frage den Namensvetter über ein genanntes Projekt entscheidet, ist nicht umgesetzt (das Projekt der Quelle steht
  nicht in `Erwaehnung`); eine solche Frage bleibt eine Rückfrage.
* **Namen ohne Adresse.** Ein Transkript oder eine Notiz, in der nur „Alex Winter“ steht, bleibt ungekennzeichnet; es
  gibt keinen Beleg, zu welchem der beiden sie gehört.
* **Zeiträume sind Eingangszeiträume.** „im Juli“ heißt: Quellen vom Juli. Eine Mail aus dem August, die eine
  Julisitzung beschreibt, trägt „außerhalb“ und darf nur mit diesem Hinweis in einem Satz stehen. Das ist gewollt
  (die Antwort soll es sagen); ob es zu oft stört, zeigt erst ein echtes Modell.
* **Qualität mit echtem Modell:** ob Modelle den Hinweis beachten (Auswahl und Sätze), ist auf dem Zielgerät zu
  messen; die Satzprüfung fängt den Fehler ab, das Modell soll ihn nicht erst machen.
