# Frageverständnis (Etappe E1)

Stand: 29. September 2026. Umsetzung von E1 aus
[`27-schichten-und-fragen.md`](27-schichten-und-fragen.md). E2 (Suchen von oben und
unten) und E3 (Antworten aus Akten) sind **nicht** Teil dieser Lieferung.

## Was vorher falsch lief

Deutsche Einzelmuster (`memory_routing.py`, `bedeutungen.py`, `is_question`)
entschieden über den Weg einer Frage. Die Messlatte (ohne Modell, Stufe „Abruf“)
zeigte am Stand vor E1:

* „Was ist **eigentlich** mit Mainz los?“ war keine offene Frage; kein Klick, keine Bedeutungen.
* Rückfragen boten nicht alle Bedeutungen an (2 von 7). Private Bedeutungen wie „Urlaub in
  Mainz“ gingen in „Weitere Erwähnungen“ unter; „Wie hoch ist mein Angebot?“,
  „Wann ist das Gremium?“, „Was ist mit dem Workshop?“, „Was ist der Stand bei Roth?“
  bekamen keine Auswahl.
* 12 der 77 Fragen gingen im Gespräch in den freien Chat, darunter echte Gedächtnisfragen
  („Seit wann kenne ich Claudia Reinhardt?“, „Findet der Workshop … statt?“,
  „Warum wurde der Workshop … abgesagt?“, „Muss ich noch etwas wegen des Hotels tun?“).
* Paraphrasen („Catering für die Tagung“ gegen „Verpflegungspauschale Fachtag“) fanden nichts,
  weil kein Wort übereinstimmt.

## Aufbau

| Modul | Aufgabe |
|---|---|
| `frage.py` | Übersetzt eine Frage in eine `Anfrage` (Sachen, Zeitraum, Absicht, Suchworte, Umschreibungen). Mit Modell (Rolle `frage`), sonst deterministischer Rückfall. Prüft jede Modellausgabe streng. Kein Zugriff auf den Bestand. |
| `frage_weg.py` | Löst die genannten Sachen gegen den Bestand auf und entscheidet: **Rückfrage**, **direkt in einer Bedeutung antworten** oder **gewohnter Weg**. Liest nur den Bestand. |
| `bedeutungen.py` | Sammelt alle belegten Bedeutungen eines Begriffs (Projekt, bestätigter Eintrag, Gegenpartei, Ort, Zusammenhang, Termin), jede mit Gewicht und einer Zeile Kontext. Umgebaut, nicht verdoppelt; `begriff_aus_frage` ist eine Kurzform von `frage.rueckfall`. |
| `memory_routing.py` | `route(..., anfrage=)`: Ob eine Frage in den belegten Gedächtnisweg oder den Chat geht, entscheidet die Anfrage statt Einzelmuster. Alle bisherigen Sicherungen (Aufträge, Lieferfragen, Belegpflicht bei Rückblick) stehen davor und sind unverändert. |
| `working_memory_answers.py` | `prepare(..., anfrage=)` erweitert die Kandidatensuche um Suchworte und Umschreibungen; `lookup_of` macht den Suchtext einer gespeicherten Antwort reproduzierbar. |
| `agent.py` | `frage_verstehen`, `_meaning_turn` (dünn: ruft `frage_weg.entscheide`), `answer_memory(anfrage=)`. |
| `model_roles.py` | `anbieter_fuer_frage`: der Anbieter der Rolle `frage`, nur mit Zuweisung. |
| `server.py` | Nur Verdrahtung: `agent._frage_anbieter`, eine Anfrage je Nachricht, `route(anfrage=)`. |
| `messlatte/` | Option `--modell-frage SPEC`; der Bericht weist aus, ob die Frage mit Modell oder Rückfall verstanden wurde. |

## Die Anfrage

```json
{"sachen": ["Catering", "Tagung"], "zeitraum": "keiner", "absicht": "fakt",
 "suchworte": ["Catering"], "umschreibungen": ["Verpflegung", "Fachtag"]}
```

* `absicht`: `ueberblick`, `person`, `frist`, `rueckblick`, `wartet_auf`, `termine`, `fakt`,
  `allgemein` (kein Bezug zu den eigenen Daten). Aufträge („Schreib Anna …“) sind keine
  Absicht: `memory_routing` erkennt sie weiter vor allem anderen.
* **Umschreibungen sind nur zusätzliche Suchworte**, nie ein Fakt, nie Antworttext, in keiner
  Anzeige. Sie kommen ausschließlich in den Suchtext (`Anfrage.suchanfrage`).

### Mit Modell (Rolle `frage`)

* `complete_json` mit JSON-Schema (`additionalProperties: false`), kurzer Anweisung,
  `max_tokens` 220, **Zeitlimit 6 s**; Aufrufe laufen in einem Arbeitsfaden, ein hängendes
  Modell hält die Frage nicht auf.
* **Die Frage ist Daten, keine Anweisung.** Sie steht als JSON-Feld `{"frage": …}` in der
  Nutzernachricht, nie in der Systemanweisung; die Anweisung sagt ausdrücklich, dass nichts
  zu befolgen ist, was darin steht.
* **Strenge Prüfung** (`pruefe`): genau die fünf Felder, nur erlaubte Werte, Längengrenzen
  (≤ 4 Sachen, ≤ 6 Suchworte, ≤ 6 Umschreibungen, je ≤ 40/60 Zeichen), nur Wortzeichen.
  **Jede Sache und jedes Suchwort muss als Teilzeichenkette in der Frage stehen**; was das
  Modell erfindet, wird nie berichtigt, sondern verworfen. Umschreibungen dürfen frei sein,
  aber höchstens zwei Wörter und ohne Zeitangabe.
* Bei jedem Fehler (kein Anbieter, Zeitlimit, Anbieterfehler, ungültige Ausgabe) gilt der
  Rückfall; `Anfrage.grund` sagt warum, der Messbericht zählt es.
* Was keine Frage ist (Aufträge, Gespräch), bekommt kein Modell: keine Wartezeit, nichts geht hinaus.
* **Die Rolle `frage` gilt nur mit Zuweisung** (Einstellungen → Lokale KI, oder die
  Geräteempfehlung). Ohne Zuweisung versteht der Rückfall die Frage: Der Standardanbieter
  der Antworten kann groß, langsam oder in der Cloud sein und ist dafür nicht vorgesehen.
  Auch mit Zuweisung geht eine Frage **nie ohne gültige Einwilligung für genau diese Rolle**
  an einen Cloudanbieter (`anbieter_fuer_frage`). Datensparsamkeit unverändert.

### Rückfall (deterministisch, ohne Netz)

Deutlich breiter als die früheren Einzelmuster, gleiche Form für jede Eingabe:

* **Füllwörter** fallen vor dem Erkennen weg: eigentlich, denn, mal, so, gerade, nochmal,
  nun, also, überhaupt, eben, halt, ja, doch, wohl, nur, momentan, aktuell, jetzt …
* **Formen** der offenen Frage: „Was ist (eigentlich) mit/bei X (los)?“, „Was ist der Stand
  bei X?“, „Wie steht es um X?“, „Wie sieht es bei X aus?“, „Was gibt es Neues zu X?“,
  „Was läuft/passiert bei X?“, „Erzähl mir von X“, „Was weißt du über X?“, „Update zu X“,
  Einwortfragen „X?“.
* **Sachen** sind Namen und Hauptwörter (großgeschriebene Folgen ohne Anrede, Frage- und
  Rahmenwörter wie Termin, Frist, Jahr, Kontakt, Zusage ausgenommen), jede wörtlich in der Frage.
* **Absicht** aus Mustern (Warten, Termine, Person, Rückblick, Frist), sonst `fakt`; eine
  Nichtfrage und eine Bitte in Frageform („Kannst du … zusammenfassen?“) ist `allgemein`.
* Pronomen sind keine Sachen („Was ist mit dir los?“ ist keine Frage an den Bestand).

## Auflösen der Sachen

`bedeutungen.py` sammelt für einen Begriff alle Bedeutungen. **Jede Quelle gehört zu genau
einer**, keine geht in „Weitere Erwähnungen“ unter. Reihenfolge:

1. **Projekte**, deren Name der Begriff ist (Grundgewicht 5).
2. **Bestätigte Einträge** (Organisation, Ort, Person, Thema) (4).
3. **Absender**, deren Adresse oder Name den Begriff trägt (2).
4. **Gegenpartei** (2, **4**, wenn der Nutzer selbst dorthin geschrieben hat): der erste fremde Beteiligte einer Quelle über seine Adresse
   (Anker aus `identitaet.py`, die eigenen Adressen sind „ich“). Hinter einer Firmendomäne
   zählt die Domäne (mehrere Ansprechpartner, eine Firma; Beschriftung „Mails mit
   klinikum-rheingau-sued.example“, Kontext „mit Dr. Volker Amann, Nora Feldmann“), hinter
   Freemail-Adressen die Adresse.
5. **Notizen und Termine ohne Beteiligte** wandern zur Gegenpartei, deren Namen (Namensteile,
   Firmenname aus der Domäne) sie nennen, aber nur bei genau einer passenden. Termine, deren
   `Ort:` den Begriff trägt, werden ein **Ort** (1,5); gleiche Betreffe eine Gruppe; alles Übrige
   bleibt eine eigene, schwache Zeile („Notiz: Titel“).
6. **Kleine Gruppen** (bis 2 Quellen), die **dieselben Tage nennen** („23. Oktober“, „23.10.“,
   „23. bis 26. Oktober“), sind ein **Zusammenhang** (1,5): Hotel, Fahrkarten, Notiz und Mail an
   Katja werden eine Zeile mit der Beschriftung „Zusammenhang Urlaub Mainz Ideen“. Gleiche Tage sind ein Hinweis,
   kein Beweis; deshalb trägt die Zeile die letzten Betreffe, an denen ein Mensch es prüft.
7. **Termine** im Umfeld von heute aus dem Kalender (unverändert).

**Tragend** ist eine Bedeutung, wenn sie Projekt, Eintrag, Absender, Ort, Zusammenhang, Betreff
oder Termin ist oder eine Gegenpartei mit mindestens zwei Quellen. **Eine einzelne Quelle ist
keine Bedeutung für sich** („Python“ in dreißig Mails von dreißig Absendern): Bis zu zwei stehen
als eigene, schwache Zeile, mehr gehen gesammelt in die Sammelzeile („Weitere Erwähnungen“). Auch
was über sechs Zeilen hinausgeht, steht dort mit den Quellen der ausgeblendeten Bedeutungen und
der Zahl „und N weitere“; jede Quelle bleibt per Klick erreichbar.

**Gewicht** = (Grundgewicht + ln(1 + Anzahl Quellen)) × 1,5, wenn die jüngste Quelle höchstens
30 Tage alt ist. Die Zeile nennt Anzahl, Datum der jüngsten Quelle und Kontext.

## Wann wird zurückgefragt?

`frage_weg.entscheide` fragt **eng**, damit eindeutige Fragen nie aufgehalten werden:

* Nur bei einer **offenen Überblicksfrage** (`ueberblick`) oder wenn **genau eine Sache**
  genannt ist. Eine genaue Frage mit mehreren Sachen („Wann fahre ich nach Mainz in den
  Urlaub?“, „Wann ist meine Präsentation beim Klinikum in Mainz?“) grenzt sich selbst ein und
  geht direkt weiter.
* Vorher entscheidet **das Unterscheidungsmerkmal in der Frage**: Ein Wort der Frage (oder
  eine weitere Sache), das in den Titeln, Beteiligten oder der Bezeichnung **genau einer**
  Bedeutung steht, wählt sie („Was ist mit Mainz im Urlaub los?“). Verglichen wird mit den
  Merkmalen, nicht mit dem Volltext: Ein Wort, das irgendwo im Text vorkommt, unterscheidet nichts.
* Überwiegt eine Bedeutung klar (Faktor `UEBERWIEGT` = 2 gegenüber der zweiten), wird direkt
  in ihr geantwortet (nur bei Überblicksfragen) und der Rest steht unter „Auch gefunden“.
* Bei genauer Frage mit einer Sache fragt Kingfisher nur zurück, wenn **mindestens zwei
  tragende Zusammenhänge mit je mindestens zwei Quellen** passen und keiner überwiegt. Zwei Notizen
  zum „Förderantrag“ oder vier Werbemails, deren Absendername das Wort trägt, sind noch keine
  Bedeutungen.
* Gibt es **keine tragende Bedeutung** (nur einzelne Erwähnungen), gibt es nichts zu klären: gewohnter Weg.
* Nennt eine **genaue** Frage einen **Beteiligten beim Namen** („Was wollte Dr. Amann letzte Woche von
  mir?“; sein Name steht bei mindestens zwei Quellen im Absender), wird nicht zurückgefragt: Seine
  Mails und die Mails über ihn sind keine zwei Bedeutungen. Rückgefragt wird bei Themen („Gremium“).
* Bestätigtes Wissen bleibt die oberste Stufe: Der gewohnte Weg zeigt es, die Klärung darf es nicht verdecken.
* Sonst: **alle Bedeutungen anbieten**, auch private, je eine Zeile mit Kontext, ein Klick
  (vorhandener Klickweg über `meaning_scope`; `bereich()` kennt die neuen Arten
  `gegenpartei`, `ort`, `zusammenhang`, `quelle`).

## Der Weg der Frage

`route(message, …, anfrage=)`: Die Sicherungen davor (Aufträge, Lieferfragen, Nachfragen zu
einer Antwort, Belegpflicht bei Rückblick auf eigene Aussagen) laufen unverändert zuerst.
Dann gilt: **Gedächtnisfrage** (Absicht ≠ `allgemein`) und Bestandsbezug (Wortsuche mit
Suchworten und Umschreibungen, Projektname, Sache im Bestand, Bedeutungssuche) →
`memory_evidence` (Agent.answer_memory); sonst Chat. Hält das **Modell** eine Frage für
allgemein, bleibt sie nur dann im Bestand, wenn sie eine Sache nennt oder von „ich/wir“
spricht: Ein Fehlurteil des kleinen Modells schickt eine Gedächtnisfrage nie in den freien Chat.

## Suche: Umschreibungen und Frischeprüfung

`prepare(question, …, anfrage=)` sucht mit `anfrage.suchanfrage(question)` (Frage plus neue
Suchworte und Umschreibungen; Wortsuche und Volltextindex sind ODER-Suchen) und nimmt den
Zeitraum der Anfrage, wenn die Frage ihn nicht nennt. **Die strukturierte Anfrage steht in der
Antwort** (`working_answer.anfrage`). Die Frischeprüfung berechnet den Suchtext daraus
(`lookup_of`, eine reine Funktion) und fragt das Modell **nie** erneut. Wird die gespeicherte
Anfrage verändert oder passt sie nicht mehr zur Frage (Sache, Suchwort, Absicht, Version), ist
sie ungültig und die Antwort gilt als nicht mehr frisch. Eine Nachfrage im Gespräch
bringt ihren Suchtext (`retrieval_query`) mit; er hat Vorrang.

## Messlatte

`python -m messlatte lauf … --modell-frage ollama:NAME` (oder `kompatibel:URL:NAME`,
`anthropic:NAME`) misst gezielt die Rolle `frage`; ohne die Option gilt, wie im Produkt ohne
Zuweisung, der Rückfall (auch wenn `--modell` läuft). Der Bericht nennt im Kopf das Modell der
Rolle und oben: Rückfragen mit allen Bedeutungen, **unnötige Rückfragen bei eindeutigen
Fragen**, Fragen im freien Chat, und **wie viele Fragen mit Modell und wie viele mit Rückfall
verstanden wurden** (bei Rückfall mit Grund).

## Messung

Messlatte, Welt v1 (77 Fragen), **ohne Modell**: Es misst die Stufe „Abruf“ und damit den
**Rückfall** des Frageverständnisses. Vorher: Stand `340ab14` (Etappe C2 übernommen), nachher:
`35b2683` (E1, zusammen mit D1/D2 gemerged). Beide Male
`python -m messlatte lauf --welt messlatte/welt --modell keins`, ohne und mit 10.000
Rauschquellen (Seed 1). Protokolle: `docs/evaluations/messlatte/2026-09-29-vor-e1-*` und
`2026-09-29-nach-e1-*`.

| Kennzahl | ohne Rauschen: vorher → nachher | 10.000 Rauschquellen: vorher → nachher |
|---|---|---|
| Erwartete Belege gefunden (von 136) | 121 → 121 | 99 → 103 |
| Fragen mit allen erwarteten Belegen (von 71) | 62 → 62 | 51 → 53 |
| Belege auf Rang 1 / bis Rang 5 / bis Rang 12 | 32 / 92 / 117 → 31 / 87 / 106 | 26 / 75 / 95 → 26 / 72 / 88 |
| Fragen mit verbotenem Beleg im Kontext (von 77) | 21 → 21 | 18 → 18 |
| **Rückfragen, die alle Bedeutungen anbieten (von 7)** | **2 → 7** | **2 → 7** |
| **Unnötige Rückfragen bei eindeutigen Fragen (von 70)** | 0 → 0 | 0 → 0 |
| **Fragen im Weg „freier Chat“ (von 77)** | **12 → 1** | **12 → 1** |
| Frage verstanden mit Modell / mit Rückfall | – / 77 | – / 77 |

Was daran zu lesen ist:

* **Rückfragen:** `mainz-01`, `mainz-06`, `meeting-protokoll-06`, `zeitraum-06` und
  `zusage-abgesagt-06` bieten jetzt alle erwarteten Bedeutungen an (vorher gingen sie in den
  Arbeitsstand); `namensgleich-04` und `-06` (Etappe C3) blieben. Auch bei 10.000 Rauschquellen
  (dort mit mehr als 100 Zusammenhängen für „Angebot“; angeboten werden die stärksten, der Rest
  steht in der Sammelzeile).
* **Unnötige Rückfragen:** Zählt jede Frage der Welt, deren erwartetes Verhalten nicht die
  Rückfrage ist, und bei der das Produkt trotzdem mit einer Auswahl antwortet: 0 von 70, auch
  bei `mainz-02` (Kategorie `mehrdeutigkeit`, Verhalten `antworten`). Zwischenstände dieser
  Arbeit hatten 1 bis 2 solcher Fälle (`frist-verschoben-01`, `frist-verschoben-02`,
  `zeitraum-02`, `namensgleich-03` bei 10.000); sie führten zu den Regeln „nur bei einer
  Sache“, „nur bei zwei Zusammenhängen mit je zwei Quellen“ und „benannte Beteiligte fragt man
  nicht zurück“ (siehe oben).
* **Freier Chat:** 12 Fragen gingen im Gespräch in den freien Chat (`adresse-geaendert-01/-05`,
  `fremde-anweisung-03`, `frist-verschoben-02/-05`, `kontakt-vor-jahren-01/-04`,
  `namensgleich-04`, `profil-02`, `zusage-abgesagt-01/-02/-04`). Übrig bleibt
  `adresse-geaendert-01` („An welche Adresse soll ich die Rechnung für Frau Krüger
  **schicken**?“): Die Sicherung gegen Aufträge (Verb „schicken“) steht vor allem anderen und
  bleibt bewusst unverändert.
* **Rang:** Die Rangzahlen sinken, weil bei fünf der sieben Rückfragen die erwarteten Belege
  nicht mehr als Kandidaten, sondern als Bestandteil der angebotenen Bedeutungen geliefert werden
  (Herkunft `angebot` im JSON); gefundene Belege und vollständige Fragen sind unverändert.
  Eine Rückfrage hat keinen Rang.
* **Belege bei 10.000:** 99 → 103 und 51 → 53 liegen im Rahmen der Schwankung von Lauf zu Lauf
  (etwa ±2; ein Zwischenlauf ergab 104). Ein Gewinn durch E1 ist daraus nicht abzuleiten.
* **Dauer:** Gesamtlauf 9,5 → 10,8 s (ohne Rauschen), 175 → 199 s (10.000, geteilte Maschine mit
  schwankender Last). Die Zeit der einzelnen Frage wurde nicht gesondert gemessen.

**Nicht gemessen** (kein Modell in der Entwicklungsumgebung): ob ein kleines Modell für die Rolle
`frage` brauchbare Sachen, Absichten und Umschreibungen liefert, die Antwortqualität und die
Paraphrasen (`paraphrase-01`, `-02` ohne Modell weiter unvollständig). Was gezeigt ist: Liefert
das (hier skriptbare) Modell die Umschreibungen „Verpflegung“, „Fachtag“ zu „Catering für die
Tagung“, steht der erwartete Beleg `paraphrase-010` auf Rang 1; mit „Teilnehmer“, „Tagung“,
„Fachtag“ zu „Veranstaltung, die ich im November ausrichte“ findet `paraphrase-02` den Beleg
`paraphrase-008` auf Rang 11 statt keinen. Das zeigt den Mechanismus, nicht die Qualität eines
Modells; dafür ist `--modell-frage` auf dem Mac da.


## Sabotageproben

Nach jeder neuen Zusicherung wurde sie absichtlich gebrochen (Text im Quellcode ersetzt), die
zuständigen Tests liefen, dann wurde die Datei wiederhergestellt. Jede Probe schlug fehl:

| Zusicherung | gebrochen durch | fehlgeschlagene Tests (Auszug) |
|---|---|---|
| Rückfall erkennt „eigentlich“ | Füllwort aus der Liste entfernt | 5, u. a. `test_rueckfall_erkennt_offene_fragen_mit_fuellwoertern`, `…_die_eigentlich_form_des_messlatte_befunds` |
| Modellausgabe mit erfundener Sache oder erfundenem Suchwort wird verworfen | Teilzeichenketten-Prüfung abgeschaltet | 3, u. a. `test_modell_ausgabe_mit_erfundener_sache_wird_verworfen` |
| Eingeschleuste Anweisung wird nicht befolgt | zusätzliche Felder der Ausgabe geduldet | 2, `test_eine_eingeschleuste_anweisung_wird_nicht_befolgt` |
| Die Frage ist Daten | Frage in die Systemanweisung gesetzt | 1, dieselbe Probe |
| Zeitlimit | `result(timeout=…)` ohne Frist | `test_zeitlimit_fuehrt_zum_rueckfall` |
| Nichtfragen brauchen kein Modell | Vorabprüfung abgeschaltet | `test_was_keine_frage_ist_braucht_kein_modell` |
| Rolle `frage` nur mit Zuweisung | Standardanbieter ohne Zuweisung | `test_ohne_zuweisung_der_rolle_frage_…` |
| Nie Cloud ohne Einwilligung | Einwilligungsprüfung ausgehebelt | `test_die_frage_geht_nie_ohne_einwilligung_an_einen_cloudanbieter` |
| Alle Bedeutungen, auch private | Notizen und Termine ohne Beteiligte wieder in die Sammelzeile | 4, u. a. `test_rueckfrage_bietet_alle_bedeutungen_auch_private` |
| Kleine Gruppen mit gleichen Tagen sind ein Zusammenhang | Zusammenlegen entfernt | 3, dieselben und `test_die_private_bedeutung_ist_per_klick_erreichbar` |
| Merkmal entscheidet ohne Rückfrage | Merkmalvergleich abgeschaltet | `test_ein_unterscheidungsmerkmal_in_der_frage_entscheidet_ohne_rueckfrage` |
| Überwiegende Bedeutung wird direkt beantwortet | Zweig entfernt | `test_ueberwiegt_eine_bedeutung_klar_wird_direkt_geantwortet_…` |
| Eine genaue Frage mit mehreren Sachen wird nie aufgehalten | `hauptsache` nimmt immer die erste Sache | 2, u. a. `test_eine_genaue_frage_mit_mehreren_sachen_wird_nie_aufgehalten` |
| Zwei Zusammenhänge mit je zwei Quellen für die Rückfrage | Mindestanzahl entfernt | 2, `…_absender_mit_dem_begriff_im_namen_und_nur_einer_mail_…` |
| Benannter Beteiligter wird nicht zurückgefragt | Regel abgeschaltet | `test_ein_beteiligter_beim_namen_wird_bei_einer_genauen_frage_nie_zurueckgefragt` |
| Ohne tragende Bedeutung nichts zu klären | Regel abgeschaltet | 2, u. a. `test_ohne_treffer_oder_ohne_sache_gibt_es_nichts_zu_klaeren` |
| Austausch mit dem Nutzer wiegt schwerer | Grundgewicht wie empfangene Mails | `test_ein_austausch_mit_dem_nutzer_wiegt_schwerer_…` |
| Viele einzelne Erwähnungen werden gesammelt | Sammeln abgeschaltet | `test_many_single_mentions_are_collected_and_stay_reachable` |
| Eigene Adresse ist nie die Gegenpartei | „ich“ nicht ausgeschlossen | 2, `test_gegenpartei_der_eigenen_adresse_ist_immer_der_andere` |
| Gedächtnisfragen gehen nicht in den Chat | Routing wieder nur mit der alten Fragewortliste | 7, u. a. `test_gedaechtnisfragen_gehen_in_den_belegten_weg_und_nicht_in_den_chat`, `test_route_wertet_die_anfrage_aus_statt_einzelmustern` |
| Ein Fehlurteil des Modells schickt nichts in den Chat | „allgemein“ ohne Sache und ohne „ich“ auch bei Bezug | `test_haelt_das_modell_eine_frage_fuer_allgemein_…` |
| Frischeprüfung nutzt die gespeicherte Anfrage | Suchtext wieder nur aus der Frage | 2, `test_die_gespeicherte_anfrage_bestimmt_die_frischepruefung_…`, `test_lookup_of_ist_eine_reine_funktion_…` |
| Gespeicherte Anfrage wird beim Lesen geprüft | Prüfung übergangen | 2, `test_gespeicherte_anfrage_wird_beim_lesen_erneut_geprueft` |
| Die Anfrage steht in der Antwort | Speichern entfernt | `test_die_gespeicherte_anfrage_bestimmt_die_frischepruefung_…` |
| Anfrage wird an die Suche durchgereicht | `anfrage=` aus `answer_memory` entfernt | dieselbe Probe |
| Umschreibungen erweitern die Suche | Suchtext wieder nur die Frage | dieselbe Probe |

Die Proben liegen als Skript nicht im Repository (Ersetzungen im Quelltext); jede der Zeilen
lässt sich mit der genannten Änderung nachstellen.

## Grenzen und offene Punkte

1. **Die Modellseite ist nicht mit einem echten Modell gemessen.** Prompt, Schema, Zeitlimit und
   Prüfung sind mit skriptbaren Anbietern getestet; ob ein 1- bis 4-B-Modell in unter einer
   Sekunde brauchbare Sachen und Umschreibungen liefert, zeigt nur `--modell-frage` auf dem Mac.
   Der Prompt ist kurz und ungetunt. Bis dahin (und ohne Zuweisung der Rolle) gilt der Rückfall.
2. **Sachverzeichnis (`bezuege.py`) und Themen (`memory_categories.py`) sind nicht angeschlossen.**
   Beide entstehen erst im Hintergrund (Abgleich, Einordnung mit Modell) und wären in der
   Messlatte und bei frisch aufgenommenen Quellen leer; die Auflösung würde an deren Aktualität
   gekoppelt. Sie liest deshalb die Quellen selbst: Personen und Firmen über die Adresse
   (`identitaet.py`), Orte aus dem `Ort:` der Terminquellen (Art `event`), Zusammenhänge über
   Titel, Beteiligte und Tage, Projekte und bestätigte Einträge wie bisher. Der Anschluss der
   Sachen (Organisation, Ort, Thema mit Grundlage) und der Themen als Merkmal ist ein Schritt für E2.
3. **Gleiche Tage sind ein Hinweis, kein Beweis.** Zwei kleine Gruppen mit einem gemeinsamen Datum
   können zufällig zusammenfallen; die Zeile nennt die letzten Betreffe, damit man es sieht. Nichts
   wird dabei verworfen, nur zusammengezeigt.
4. **Firmendomänen gruppieren Ansprechpartner.** Verschiedene Personen einer Firma erscheinen als
   eine Zeile („Mails mit klinikum-rheingau-sued.example, mit Dr. Volker Amann, Nora Feldmann“).
   Private Anbieter (`identitaet.PRIVATE_ANBIETER`, dieselbe Liste wie für Organisationen in `bezuege`) gruppieren nach Adresse; die Liste ist klein und deutsch geprägt.
5. **Schwache Erwähnungen:** Einzelne Quellen (eine Mail, eine Notiz) sind keine Bedeutung. Bis zu
   zwei stehen als eigene Zeile, mehr gehen gesammelt in „Weitere Erwähnungen“ (mit Klick). Ein
   einzelnes privates Dokument neben vielen Erwähnungen kann so in der Sammelzeile stehen, nicht
   auf einer eigenen; erst zwei Quellen oder ein gemeinsamer Tag machen eine Bedeutung.
6. **Viele Bedeutungen bei generischen Wörtern.** Bei 10.000 Quellen hat „Angebot“ mehr als
   100 Zusammenhänge. Angeboten werden höchstens fünf, nach Gewicht; ein Austausch, in dem der
   Nutzer selbst geschrieben hat, zählt mehr als bloß Empfangenes (Grundgewicht 4 statt 2). Das
   ist eine Annahme, die die Messlatte stützt (`mainz-06` bei 10.000), aber kein Beweis für echte
   Postfächer; `python -m messlatte lokal` prüft sie dort.
7. **Aufträge in Frageform** („Kannst du … zusammenfassen?“, Fragen mit „schicken“, „schreiben“ …)
   bleiben im Chat mit Werkzeugen; das ist gewollt.
8. **Kappung der Suche:** Wortsuche und Index nehmen höchstens 16 Wörter; eine sehr lange Frage
   mit Umschreibungen kann die alphabetisch letzten Wörter verlieren (bisheriges Verhalten der
   Wortsuche, unverändert).
9. **Rang der Rückfragen:** Bei einer Rückfrage liefert die Messlatte keinen Rang. Wer Ränge
   über Etappen vergleicht, muss `angebot` und `kandidat` getrennt lesen.
10. **Die Messlatte wurde für Rückfragen nicht gelockert.** Ein Werbeabsender, der das Wort im Namen
    trägt („Rheinhessen-Therme“), darf als Bedeutung erscheinen; die verbotene Aussage der Mini-Welt
    wurde deshalb auf „Rheinhessen-Therme gebucht“ verengt (`messlatte/tests/mini_welt`). Die Regel
    „eine verbotene Aussage in den Auswahlknöpfen zählt“ (`test_bewertung`) gilt unverändert; in der
    großen Welt steht kein solcher Absender.
