# In die Akte übernehmen

Stand: 30. September 2026. Das Gegenstück zu „Stimmt nicht?“ ([`38-rueckkanal.md`](38-rueckkanal.md)):
Eine Antwort, die stimmt, soll der Nutzer mit einem Klick festhalten können, statt morgen dieselbe Frage
noch einmal zu stellen. Es ist ein Schritt der Runde 2 (M2, [`41-zielbild.md`](41-zielbild.md),
[`26-plan-stabschef.md`](26-plan-stabschef.md)). Die Regel des Gedächtnisses gilt unverändert
([`10-verdichtung.md`](10-verdichtung.md)): **Der Klick schlägt vor. Wissen wird ein Satz erst, wenn ein
Mensch den Vorschlag annimmt.**

Code: `uebernehmen.py` (Vorschläge), `uebernehmen_routes.py` (Routen), `akten_aussagen.py` (Abschnitt der
Akte), `proposals.ProposalStore.von`, `relations.py` (Beziehung `aussage`). Oberfläche: `Uebernehmen.tsx`,
`uebernehmen.ts`, `AkteAbschnitte.tsx` („Angenommen“). Tests: `sidecar/tests/test_uebernehmen.py`,
`app/kingfisher/tests/uebernehmen.test.mjs`. Browserprobe: `scripts/probe_uebernehmen_ui.py`.

## Was es tut

**Der Link.** Unter jeder Antwort in Sätzen steht still „In die Akte übernehmen“, in einer Zeile mit
„Stimmt nicht?“ und ebenso zurückhaltend. Rückfragen, Auswahlfragen und der Zitatmodus ohne Sätze tragen ihn
nicht (`uebernehmbar`).

**Die Rückfrage, ein Satz.** „Welche Sätze sollen in die Akte von Förderteam?“ Die Sätze der Antwort sind eine
Klick-Auswahl. Vorgewählt ist, was nichts gegen sich hat: Ein Satz, der auf einer überholten oder gekennzeichneten
Quelle beruht (`akten_kontext.py`, `kennzeichnung.py`), ist wählbar, aber nicht vorgewählt und trägt seinen
Hinweis („Die Quelle ‚Ausschreibung …‘ ist überholt: 15. Oktober 2026 gilt nicht mehr, jetzt 12. November 2026.“).
Ein Satz, der schon in der Akte steht, ist nicht vorgewählt und heißt „Steht schon in der Akte.“ Dazu ein freies
Feld „Notiz“. Die Akte ist die Sache der Frage (`answer['akten']`, also `akten_kontext.sachen_finden`); nannte die
Frage keine, sind es Projekt, Organisation oder Person aus den Belegen, und zwar die mit den meisten Belegen
(Projekt vor Organisation vor Person). Bei mehreren Sachen wählt ein Klick; eine andere als die angebotenen
nimmt der Server nicht an.

**Vorschlagen.** „Vorschlagen“ legt je gewähltem Satz einen Vorschlag an (`KnowledgeService.propose`, Art
`knowledge`) und zeigt „Vorgeschlagen.“ mit der Vorschlagskarte je Satz: Satz, Beleg im Wortlaut, Hinweis, und
„Bestätigen“ oder „Nicht speichern“.

| Feld des Vorschlags | Inhalt |
|---|---|
| Subjekt | die Sache der Akte (`person:a:…`, `organisation:…`, `projekt:…`) |
| Beziehung | `aussage` (mehrwertig, `relations.py`: zwei Sätze derselben Akte widersprechen sich nicht) |
| Aussage und Wert | der Satz, so wie der Nutzer ihn las (relative Zeiten schon mit Datum) |
| Belege | je Quelle, auf die der Satz sich stützt: Kennung, **wörtliche Textstelle** (der Satz der Quelle mit den meisten gemeinsamen Wörtern), Fingerabdruck der Quelle |
| Begründung | „Aus einer Antwort von Kingfisher übernommen …“, die Frage, bei Kennzeichnung vorn „Hinweis: …“, die Notiz |
| `proposed_by` | `antwort:<Gespräch>:<Nachricht>`: damit findet die Antwort ihre Vorschläge wieder, auch nach dem Neuladen |

**Annahme.** Über den vorhandenen Weg, `POST /api/v1/memory/candidates/{id}/accept` (die Karte ruft ihn).
Erst er legt die Aussage an. Der Wissenspfad prüft dabei wie immer, dass die Quelle noch gilt, der
Fingerabdruck stimmt und das Zitat in der Quelle steht. „Nicht speichern“ lehnt ab (`reject`); der Vorschlag
bleibt als abgelehnt sichtbar.

**In der Akte.** Bis hierher zeigte die Akte nur Zitate aus Quellen, eine bestätigte Aussage kam in ihr nicht
vor, und eine Quelle, die in Wissen einging, wird nirgends mehr roh gezeigt (`mappe.lesen`). Damit der Satz
nicht einfach verschwindet, hat die Akte den Abschnitt **Angenommen** (`akten_aussagen.py`): die Aussagen der
Sache als Aussage, nie als Zitat, mit Datum der Annahme und Beleg (Quelle und Textstelle, ein Klick öffnet das
Original).

**Überholt.** Nennt eine **jüngere**, noch ungeprüfte Quelle derselben Akte denselben Gegenstand anders, trägt
die Aussage den Hinweis „Möglicherweise überholt: …“ mit der neueren Angabe und der Quelle. Dieselbe grobe
Regel wie bei den Quellen der Akte (`gleicher_gegenstand`, Fristen mit anderem Datum, neuere Änderung oder
Statusmeldung), ohne Modell. Dasselbe Datum noch einmal gesagt bestätigt die Aussage, überholt sie nicht. Die
Aussage wird dabei **nicht** widerrufen oder geändert; was daraus wird, entscheidet der Mensch (Widerruf in der
Karte, neuer Vorschlag aus einer neuen Antwort).

**Routen** (beide mit Token):
`GET /api/v1/antworten/uebernehmen?conversation_id=…&message_id=…` (die Rückfrage: Sätze, Ziele, bisherige
Vorschläge mit Zustand) und `POST /api/v1/antworten/uebernehmen` (Gespräch, Nachricht, Satznummern, Ziel-Sache,
Notiz; Antwort je Satz: `vorgeschlagen`, `steht_schon`, `liegt_vor` oder `fehler`). Die Oberfläche schickt nie
Text: Antwort, Sätze und Belege liest der Server aus der Gesprächsansicht (`app.state.gespraech_ansicht`) und
**prüft jeden Satz erneut** (`satzantwort.wiederherstellen`). `server.py` bekam einen Aufruf.

## Was es nicht tut

* Es legt **keinen Claim an** und nimmt nichts an. Ein Vorschlag ist eine Behauptung auf Probe.
* Es ist **nicht außenwirksam**: nichts wird gesendet, geteilt oder hochgeladen.
* Es **schlägt nichts doppelt vor**: ein Satz, der (bis auf Schreibweise und Schlusspunkt) schon als nutzbare
  Aussage in der Akte steht, nicht; einer, zu dem ein Vorschlag offen ist, bleibt bei diesem einen.
* Es **ändert weder Quelle noch Akte**, außer dass die Akte die angenommene Aussage zeigt.

## Was danach mit der Antwort geschieht (Grenze, ehrlich)

Mit der Annahme geht die Quelle in Wissen ein. Die vorhandene Frischeprüfung (`working_memory_answers._fresh`)
behandelt die ursprüngliche Antwort dann als veraltet („Die Grundlage dieses Arbeitsstands hat sich verändert.
Bitte frage erneut.“, dazu „Mit aktuellem Stand neu beantworten“), und der Link entfällt: Aus einer veralteten
Antwort lässt sich nichts mehr übernehmen. Wer mehrere Sätze will, wählt sie **vor** dem Vorschlagen oder
entscheidet die schon angelegten Vorschläge der Reihe nach (sie bleiben nach dem Neuladen an der Antwort
sichtbar, solange sie noch gilt). Eine neue Frage zum selben Gegenstand beantwortet Kingfisher danach nicht mehr in
Sätzen, sondern mit dem bestätigten Eintrag („Bestätigter Eintrag zum Suchbegriff“): Die Sätze (E3,
[`35-belegte-antworten.md`](35-belegte-antworten.md)) entstehen nur aus ungeprüften Quellen und nur, wenn kein
bestätigter Eintrag zur Frage passt (`claim_basis`). Das ist die bestehende Trennung von Quellen und Wissen, kein
Fehler dieses Schrittes, und ein Punkt für später (siehe „Offen“).

## Nachweis

Sabotageproben (Zusicherung gebrochen, richtige Tests rot, zurückgestellt):

| Gebrochen | Rot |
|---|---|
| „Vorschlagen“ nimmt den Vorschlag gleich an (direktes Schreiben) | 3: Vorschlag statt Fakt, Annahme erst über die Karte, offener Vorschlag wird nicht verdoppelt |
| Dopplungsprüfung liefert immer „nicht vorhanden“ | 2: Dopplung über die Route, Vergleich bis auf Schreibweise |
| Hinweise bleiben leer | 3: Rückfrage, Vorschlag mit Hinweis, Hinweise für Namensvetter |
| Textstelle ist erfunden | 10: der Wissenspfad lehnt das Zitat ab |
| Überholt-Regel findet nie etwas | 1: jüngere Quelle kennzeichnet die Aussage |
| Dasselbe Datum zählt als überholt | 1: bestätigt statt zu überholen |
| `POST` ohne Token | 1: Routen brauchen das Token |
| UI: Vorgabe ignoriert Hinweise / `uebernehmbar` immer wahr | je 1 |

Browserprobe im echten Chromium (`scripts/probe_uebernehmen_ui.py`): still, eine Zeile mit „Stimmt nicht?“,
Rückfrage mit Vorgabe und Hinweis, „Vorgeschlagen.“ mit Karte bei null Claims, Neuladen findet den Vorschlag,
„Nicht speichern“, „Bestätigen“ („In der Akte von …“), die Akte zeigt „Angenommen“ mit Beleg, die alte Antwort
gilt als veraltet; Konsole leer.

## Datenschutz

Vorschläge liegen in `proposals.sqlite3` wie alle anderen, Frage und Notiz in der Begründung. Nichts davon
verlässt den Rechner. Tests und Probe arbeiten mit erfundenen Texten.

## Offen

* **Sätze nach der Annahme.** Damit eine Antwort nach der Annahme nicht ganz in den Zitatmodus fällt, müssten
  bestätigte Aussagen als Belege der Satzantwort zugelassen werden (mit eigener Prüfung gegen ihre Belege und
  der Kennzeichnung „überholt“). Das ist ein eigener Schritt und berührt die Satzprüfung.
* **Überholt** ist eine Vermutung derselben Güte wie in der Akte; ein Widerruf bleibt Sache des Menschen.
* Ob ein Satz pro Vorschlag im Alltag zu viele Karten macht, zeigt erst die Woche.
