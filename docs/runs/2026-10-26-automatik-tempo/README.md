# Paket T Tempo (26.10.2026)

Auftrag: [66-automatik.md](../../66-automatik.md), Zeile „Tempo“. Branch `feat/automatik-tempo`. Nur synthetische
Daten; Modelle und Cloud sind Attrappen, kein bezahlter Aufruf.

## Was gebaut ist

1. **Cloud für Gedächtnisantworten, nur mit Einwilligung** (`sidecar/icarus_memory/gedaechtnis_cloud.py`). Ist der
   Anbieter der Rolle `antwort` ein Cloudanbieter, den `model_roles` mit gültiger Einwilligung gebaut hat (Marke
   `cloud_einwilligung`), baut der Agent daraus einen eingegrenzten Anbieter `GedaechtnisCloud`. Nur diesen oder einen
   lokalen nehmen `working_memory_answers.prepare` und `satzantwort.formulieren`. Vor **jedem** Versand: Einwilligung neu
   gelesen (`freigabe_gueltig`) und Ausgangsprüfung des Agenten (`assert_egress_allowed`, Grenze `normal`). Nur JSON
   nach Schema; Referenzen, Sätze und zweites Tor wie lokal. Bestätigte Einträge (K) gehen nie hinaus. Die Antwort
   vermerkt `gedaechtnis_cloud: {anbieter, modell, gesendet: ["frage", "textstellen"]}` und
   `answer_contract.model_egress = "external"`; die Oberfläche zeigt „Über Anthropic beantwortet.“.
   `history_egress` bleibt `local_only`: Es regelt, ob der Verlauf später an ein fremdes Modell darf, und die Antwort
   enthält lokal Gelesenes, das nicht hinausging (Gedächtnisantworten gehen ohnehin nie in den Modellverlauf).
   Einwilligungssatz **erweitert**: „… Textstellen samt Absender, Betreff und Datum … auch bei Fragen an dein Gedächtnis.“
   (Oberfläche und Sidecar), weil die Nutzlast diese Angaben enthält.
2. **Lokal schneller.** Ein eigenes Modell (`kingfisher-*`) bleibt nach einer Gesprächsantwort 5 Minuten statt 15 s
   (`ollama_memory.halten_fuer`, nur für das Antwortmodell, nur im Gespräch). RAM-Grund respektiert: Vor jedem Aufruf
   werden die anderen eigenen Modelle weiter entladen; die 5 Minuten entsprechen Ollamas eigener Vorgabe für alle
   übrigen Modelle. Vorwärmen beim Öffnen eines Gesprächs (`POST /api/v1/gespraech/vorwaermen`, Faden, kein Warten):
   kein Aufruf ohne lokales Ollama-Modell (Cloud, anderer Port, entfernter Host, Ollama-Cloud), nie während eines
   anderen Modellaufrufs (Ampel und Sperre ohne Warten), höchstens einmal je Minute.
   **Auswahl nicht verkleinert**, weil jede kleinere Eingabe auf der Messlatte verliert (unten).
3. **Sichtbar warten.** Die Frage von Heute öffnet sofort das Gespräch; die eigene Frage steht nach 0,2 s da, darunter
   der echte Schritt (`zeitmessung.melde` beim Beginn jedes Abschnitts, `GET /api/v1/conversations/{id}/fortschritt`,
   ohne Sperre, ohne Fragetext). Keine Zeitangabe. Scheitert das Senden einer übergebenen Frage, bleibt sie stehen,
   mit „Erneut senden“.
4. **Ein Satz statt Rätsel.** Unter einer lokalen Antwort über 8 s bei ausgeschalteter Cloud: „Lokal dauert das. Mit
   der Cloud geht es in wenigen Sekunden.“, Knopf „Cloud einschalten“ (führt zum Schalter, Einwilligung bleibt dort),
   „Nicht mehr zeigen“ (im Browser gemerkt).

## Messlatte: Größe der Auswahl (ohne Modell, Regel-Einordnung)

| Plätze / Zeichen | kurz: Belege (von 143) | kurz: Fragen komplett (von 78) | lang: Belege | lang: komplett | lang: abgeschnitten | lang: Kontext (Mittel) |
|---|---|---|---|---|---|---|
| **16 / 32.000 (bleibt)** | **132** | **71** | **130** | **70** | 0 | 29.792 |
| 16 / 24.000 | 132 | 71 | 128 | 68 | 2 | 25.969 |
| 16 / 20.000 | 132 | 71 | 127 | 67 | 3 | 23.128 |
| 14 / 28.000 | 131 | 70 | 130 | 70 | 0 | 26.184 |
| 12 / 24.000 | 130 | 69 | 127 | 68 | 1 | 22.849 |

Jede Verkleinerung verliert Belege (kurze oder lange Welt). Deshalb bleiben `MAX_REFS = 16` und `MAX_CONTEXT = 32000`.
Die Beschleunigung kommt aus warmem Modell, Vorwärmen und der Cloud. **Nicht gemessen:** die Wirkung auf dem Zielgerät
mit echtem Modell (kein Ollama hier). Zu messen mit `python -m messlatte lauf --modell ollama:NAME` und der Antwortzeit
unter Einstellungen.

## Prüfungen

- Backend neu: `test_tempo_gedaechtnis_cloud.py` (16), `test_tempo_fortschritt.py` (11). Rot vor dem Code (5 der
  Cloudtests; die Grenztests waren schon grün und müssen es bleiben).
- Volle Suite: siehe unten (Abschnitt Zahlen).
- Oberfläche: `tsc` ohne Befund, `node --test` alle grün, `vite build` grün; neu `gespraech-warten.test.mjs`, Satz der
  Einwilligung in `zusagen-nach-kuerzen.test.mjs` festgehalten.
- Browser: `scripts/probe_tempo_ui.py` (Skriptmodell wartet 3,5 s bei der Auswahl und 5 s bei den Sätzen): Frage nach
  0,2 s sichtbar, Schritte „Wählt Quellen …“ → „Formuliert …“, Satz zur Cloud nach 9,9 s, Knopf führt sichtbar zum
  Schalter, „Nicht mehr zeigen“ hält nach Neuladen; Cloud mit Einwilligung antwortet in 1,0 s mit Vermerk; ohne
  Einwilligung 0 Cloudaufrufe (`local_only`). Kein seitliches Überlaufen bei 1280 und 390 px, hell und dunkel, Konsole leer.

## Sabotageproben (je Zusicherung gebrochen, richtiger Test rot, zurückgesetzt)

| Bruch | gefangen von |
|---|---|
| Einwilligung nicht geprüft | `test_ohne_gueltige_einwilligung_geht_nichts_in_die_cloud` |
| bloßer Cloudanbieter erlaubt | `test_prepare_und_saetze_nehmen_keinen_blossen_cloudanbieter` |
| keine Prüfung vor jedem Versand | `test_widerruf_mitten_in_der_antwort_stoppt_den_naechsten_versand` |
| bestätigte Einträge gehen mit | `test_bestaetigte_eintraege_gehen_nie_in_die_cloud` |
| ohne Ausgangsprüfung | `test_ausgangspruefung_haelt_sensibles_zurueck` |
| Rückfall ohne Schlüssel bekommt Marke | `test_rollen_markieren_nur_den_cloudanbieter_mit_einwilligung_und_schluessel` |
| Metadaten fehlen | `test_mit_einwilligung_waehlt_die_cloud_die_quellen_und_sagt_es` |
| Antwortmodell nur 15 s | `test_antwortmodell_bleibt_im_gespraech_fuenf_minuten_sonst_15_sekunden` |
| Vorwärmen trotz laufendem Aufruf | `test_vorwaermen_laedt_das_lokale_antwortmodell_einmal_je_minute` |
| Vorwärmen ohne lokales Modell (beide Prüfungen entfernt) | `test_ohne_lokales_ollama_modell_kein_einziger_aufruf` (nach Nachschärfen: entfernter Host auf 11434) |
| kein Zwischenstand | `test_zeitmessung_meldet…`, `test_waehrend_der_antwort_steht_der_echte_schritt_bereit` |
| andere eigene Modelle beim Vorwärmen nicht entladen | `test_vorwaermen_eines_eigenen_modells_entlaedt_erst_die_anderen` |
| Satz zur Cloud trotz Cloud an | `gespraech-warten.test.mjs` |
| Schritt nach Ende der Antwort | `gespraech-warten.test.mjs` (nach Nachschärfen) |
| Wegklicken nicht gemerkt | `gespraech-warten.test.mjs` |
| Einwilligungssatz gekürzt | `zusagen-nach-kuerzen.test.mjs` |
| Cloudantwort ohne Vermerk | `gespraech-warten.test.mjs` |

Zwei Brüche fing zuerst kein Test (Schritt nach Ende; nur eine der zwei Lokal-Prüfungen beim Vorwärmen); dafür gibt es
jetzt je einen Fall.

## Bilder

`tempo-warten-1280.jpg`, `tempo-warten-390.jpg`, `tempo-warten-1280-dunkel.jpg` (Frage sofort, Schritt darunter);
`tempo-langsam-1280.jpg`, `tempo-langsam-390.jpg`, `tempo-langsam-1280-dunkel.jpg` (Satz zur Cloud);
`tempo-schalter-1280.jpg` (Ziel des Knopfs); `tempo-cloud-1280.jpg` („Über Anthropic beantwortet.“).

## Grenzen

- Echte Zeiten auf dem Zielgerät nicht gemessen; ob 5 Minuten Haltezeit und Vorwärmen dort die erwarteten Sekunden
  sparen, zeigt erst die Antwortzeit unter Einstellungen.
- Für Modelle ohne `kingfisher-`-Namen bestimmt Ollama selbst die Haltezeit (Vorgabe 5 Minuten); das Vorwärmen setzt
  sie beim Laden auf 5 Minuten.
- Ist das Prüfmodell ein anderes eigenes Modell, entlädt sein Aufruf das Antwortmodell weiterhin (RAM-Regel); die
  nächste Frage lädt es dann neu.
- Während eine Antwort läuft, lädt das Gespräch selbst nicht (bestehende Sperre `conversation_lock`); deshalb steht dort
  nur die eigene Frage mit dem Schritt. Eine Wiederholung („Wiederholen“) zeigt nur „Kingfisher antwortet …“.
- Der Hinweis „Nicht mehr zeigen“ ist je Browser gemerkt, nicht im Sidecar.
- Die Cloudantwort setzt voraus, dass der Anbieter reines JSON liefert; sonst fällt die Antwort auf „konnte nicht
  zuverlässig ausgewählt werden“ bzw. auf die wörtlichen Belege zurück. Mit einem echten Anbieter nicht geprüft.
