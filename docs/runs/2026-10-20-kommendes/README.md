# Paket B2: „Was brauche ich morgen?“ – Zukunftsangaben im Gespräch

Stand 20.10.2026, Branch `feat/zukunftsangaben-20261020` auf `main` (1.0.26, `fa64c07`). Nur
synthetische Daten (Messlatte-Welt, Kalender- und Mail-Attrappen der Tests); kein Modell, kein
Postfach, kein Kartendienst.

## Was gebaut wurde

Bisher konnte die Heute-Seite sagen, was morgen ansteht, das Gespräch nicht: „Was brauche ich
morgen?“ ging in die Wortsuche. Jetzt antwortet das Gespräch deterministisch, ohne Modell, aus
Kalender, Akten und Aufgaben; Beschreibung in
[`31-frageverstaendnis.md`](../../31-frageverstaendnis.md#zukunft-was-brauche-ich-morgen-20102026).

| Bereich | Dateien |
|---|---|
| Kommender Zeitraum | `sidecar/icarus_memory/time_scope.py` (`kommender_zeitraum`, `WOCHENTAGE`) |
| Antwort | `sidecar/icarus_memory/kommendes.py` (neu); `fristlage.sammeln(tage_voraus=)`; `wegezeit.WegezeitDienst.auskunft(nur_lesen=)`, Status `nicht_berechnet` |
| Gespräch | `agent.py` (`_kommendes_turn`, `render_kommendes`, Verlauf ohne Zitat), `agent_verdrahtung.py` (`_kommendes`), `memory_routing.route`, `server.py` (Frage ohne Fragenverständnis; Wiedergabe beim Öffnen nur am Tag der Frage), `conversations.py` (gespeichert wird nur die Frage) |
| Messlatte | `messlatte/abruf.py` (Weg `kommendes`, Belege aus `source_links`), `messlatte/welt/szenarien/zeitraum.json` (`zeitraum-07`) |
| Tests, Probe | `sidecar/tests/test_kommendes.py`, `scripts/probe_kommendes_ui.py` |
| Doku | `docs/31-frageverstaendnis.md`, `33-briefing-und-vorbereitung.md`, `24-weg-zum-jarvis.md`, `DEVELOPER-START.md` |

Nicht geändert: Heute-Seite und Briefing (behalten `TAGE_VORAUS` = 7), `relative_zeit.py`,
`mentioned_period` („Was ist nächste Woche?“ ordnet weiterhin nichts, `test_answer_time_scope.py`),
`frage.py` (die Absicht `termine` zusammen mit dem Zeitraum zu vermerken war kein Pflichtteil und
blieb aus: `ZEITRAEUME` hätte eine Zukunftsangabe in die Suche nach Eingangsdatum getragen).

## Tests

Erst rot, dann grün: `sidecar/tests/test_kommendes.py` (zunächst 74 Tests) scheiterte vor dem Bau an
`ImportError: cannot import name 'kommendes'` (ganze Datei rot), danach 74 bestanden
(`python -m pytest tests/test_kommendes.py`, 20 bis 34 s). Zwei Sabotageproben zeigten Lücken der
Tests (Frist von heute bei „morgen“, Reihenfolge beim direkten Aufruf); nach den Ergänzungen sind es
75 Tests, alle grün.

Verwandte Bestandstests danach (`test_answer_time_scope.py`, `test_frage.py`, `test_relative_zeit.py`,
`test_offene_punkte.py`, `test_fristlage.py`, `test_wegezeit.py`, `test_wegezeit_routes.py`,
`test_memory_routing.py`, `test_calendar_answers.py`, `test_tagesbriefing.py`, `test_briefing.py`,
`test_terminvorbereitung.py`, `test_briefing_zeitzone.py`, `messlatte/tests`): 623 bestanden, 1
fehlgeschlagen: `messlatte/tests/test_akten_lage.py::test_kommandozeile_kennt_modell_hintergrund_und_meldet_falsche_wahl`
erwartet das Wurzelverzeichnis als Arbeitsverzeichnis (`messlatte/welt/welt.json: Datei fehlt`), aus
`sidecar/` gestartet; vom Wurzelverzeichnis aus besteht er. Nicht durch dieses Paket verursacht.

Volle Suite (`python -m pytest tests -q -p no:cacheprovider -n auto`, aus `sidecar/`, vier Kerne, parallel
zu den Sabotageproben): **7.804 bestanden, 3 übersprungen, 1 fehlgeschlagen** (26 Untertests bestanden,
31:39 min). Der Fehlschlag `test_cloud_memory.py::test_bulk_accepts_101_sources_after_pilot_and_uses_larger_budget`
(„Faden `cloud-memory-job` lebt noch“) ist zeitabhängig: allein wiederholt bestehen alle 50 Tests der
Datei (52 s). Ein erster Lauf mit `-x` brach an derselben Art Fehlschlag in `test_cloud_access.py`
ab (2.236 bestanden bis dahin); auch der besteht allein (18 Tests, 91 s). Beide Tests berühren keinen
geänderten Code (Cloud-Fäden); unter Last reißen sie die Wartefrist.

## Messlatte (ohne Modell, Stufe „Abruf“)

`python -m messlatte lauf --welt messlatte/welt --modell keins`, Welt v1 mit dem neuen Fall
`zeitraum-07` („Was steht nächste Woche an?“, erwartet Beleg `zeitraum-012`, verboten „du bist frei“
und das Gremium am 21.10.). Vorher = Stand `fa64c07` (per `git archive` ausgepackt, `PYTHONPATH` auf
dessen `sidecar`), nachher = dieser Branch. Achtung: Aus dem Wurzelverzeichnis lädt das venv
`icarus_memory` aus `/home/user/kingfisher-app/sidecar`, nicht aus dem Worktree; beide Läufe liefen
deshalb mit gesetztem `PYTHONPATH`.

| Kennzahl | vorher | nachher |
|---|---|---|
| Erwartete Belege gefunden (von 143) | 128 | 130 |
| Fragen mit allen erwarteten Belegen (von 78) | 69 | 70 |
| Belege auf Rang 1 / bis Rang 5 / bis Rang 12 | 35 / 92 / 112 | 36 / 94 / 114 |
| Fragen mit verbotenem Beleg im Kontext (von 84) | 22 | 22 |
| Rückfragen mit allen Bedeutungen (von 7) | 7 | 7 |
| Unnötige Rückfragen (von 77) | 0 | 0 |
| Fragen im freien Chat (von 84) | 0 | 0 |
| `zeitraum-07` | Weg Arbeitsstand, Beleg fehlt | Weg `kommendes`, Beleg `zeitraum-012` gefunden |
| Abruf je Frage, Median / 90 % (s) | 0,259 / 0,512 | 0,282 / 0,609 |
| Dauer gesamt (s) | 49,1 | 58,1 |

Die Unterschiede außerhalb von `zeitraum-07` (Rang 1: 35 → 36) liegen in der üblichen Schwankung von
Lauf zu Lauf; die Antwort von `zeitraum-07` nennt das Nachgespräch am 7.10. mit Vorbereitung und die
Vorsorgeuntersuchung am 6.10., beide mit Quelle, und keine Zusage außerhalb der Woche.

## Sabotageproben

Jede Zusicherung wurde in einer Kopie des Sidecars absichtlich gebrochen und `test_kommendes.py`
(74 Tests) lief; danach wurde die Datei wiederhergestellt. Jede Probe schlug fehl:

| Zusicherung | gebrochen durch | fehlgeschlagene Tests |
|---|---|---|
| „nächste Woche“ ist Montag bis Sonntag | Ende eine Woche später (`montag + 21`) in `time_scope.kommender_zeitraum` | 2: `test_kuenftige_angaben_werden_zu_zeitraeumen[nächste Woche]`, `[kommende Woche]` |
| Keine Frist außerhalb des Zeitraums | Datumsfilter in `kommendes._fristen` entfernt | 1: `test_morgen_in_fester_reihenfolge_jede_zeile_mit_quelle_nichts_ausserhalb` (erst nach Ergänzung der Frist von heute; davor fing die Grenze `tage_voraus` die obere Seite allein) |
| Nie „frei“ behaupten | leerer Fall: „Du bist morgen frei.“ | 1: `test_leer_ist_ehrlich_und_behauptet_nie_frei` |
| Gleicher Wochentag fragt nach | Mehrdeutigkeit abgeschaltet (heute genommen) | 2: `test_gleicher_wochentag_wie_heute_ist_mehrdeutig`, `test_mehrdeutiger_wochentag_fragt_nach_statt_zu_raten` |
| Neuer Weg vor `frage_verstehen` | Hook hinter `anfrage = anfrage or self.frage_verstehen(question)` geschoben | 1: `test_answer_memory_versteht_die_frage_nicht_erst_mit_dem_modell` (erst nach Ergänzung: Der Server gibt die Anfrage mit, deshalb sah der Gesprächstest die Reihenfolge nicht) |
| Wegezeit nur gelesen | `nur_lesen=False` in `kommendes._wegezeit` | 1: `test_wegezeit_wird_nur_gelesen_nie_angefragt` |
| `tage_voraus` erreicht `aus_akte` | Parameter in `fristlage.sammeln` nicht durchgereicht | 1: `test_fristlage_sammeln_reicht_tage_voraus_durch` |
| Alte Antwort gilt nur am Tag der Frage | `gilt_noch` immer wahr | 1: `test_eine_aeltere_antwort_wird_beim_oeffnen_nicht_still_fuer_einen_anderen_tag_gezeigt` |
| Nie weiter als `MAX_CALENDAR_WINDOW` | Grenze × 100 | 1: `test_zeitraum_reicht_nie_weiter_als_das_kalenderfenster` |
| Nie im freien Chat | Zweig in `memory_routing.route` entfernt | 6: `test_nie_im_freien_chat[4]`, `test_im_gespraech_ohne_modell_und_vor_dem_fragenverstaendnis`, `test_eine_aeltere_antwort_…` |
| Jede Fristzeile mit Quelle | Episode der Frist weggelassen | 2: `test_morgen_in_fester_reihenfolge_…`, `test_im_gespraech_ohne_modell_…` |
| Keine Termine außerhalb des Zeitraums | `display_events` umgangen | 1: `test_morgen_in_fester_reihenfolge_…` |
| Vergangenes bleibt `mentioned_period` | „letzte Woche“ als kommende Woche gelesen | 2: `test_vergangenes_und_unklares_ist_kein_kommender_zeitraum[letzte Woche]`, `test_letzte_woche_bleibt_sache_von_mentioned_period` |

Skript der Proben außerhalb des Repositorys (Ersetzungen im Quelltext, Lauf in einer Kopie des
Sidecars mit `tests/test_kommendes.py`, 75 Tests im Endstand).

## Browserprobe

`python scripts/probe_kommendes_ui.py --ausgabe DIR` (Chromium 1194, gebaute Oberfläche, Anbieter
schlägt bei jedem Aufruf fehl): Frage „Was brauche ich morgen?“ im Gespräch, Antwort mit Termin
(Ort, Teilnehmer, „vorbereitet“), Frist mit „[Quelle 1]“ und Knopf „Quelle 1 öffnen“, der die
Quellenansicht mit dem Betreff zeigt; der Termin in fünf Tagen fehlt; kein „frei“; `answer_contract`
`kommendes`, `model_called` false; 1280 und 390 px ohne seitliches Scrollen; Konsole leer. Bilder
`kommendes-1-antwort-1280.png`, `kommendes-2-quelle-1280.png`, `kommendes-3-antwort-390.png`
(außerhalb des Repositorys, nur synthetische Texte).

## Grenzen und offene Punkte

1. Nur, was im Kalender, in den Akten und in den Aufgaben steht; keine Modellantwort, keine Suche
   nach „morgen“ in Mails.
2. Der gleiche Wochentag wie heute fragt nach; „in N Wochen“ ist der Tag, nicht die Woche.
3. Die Wegezeit wird nur aus dem Zwischenspeicher gelesen; ohne Berechnung der Heute-Seite steht
   „Fahrzeit noch nicht berechnet“ da. Das ist Absicht (keine Adresse verlässt für eine Antwort den Rechner).
4. Aufgaben haben keinen Quellenlink (die Aufgabe ist selbst die Quelle); Termine, die nicht im
   Gedächtnis liegen, nennen den Kalender statt einer Episode.
5. `frage.py` vermerkt die Absicht `termine` nicht zusammen mit dem Zeitraum (optionaler Teil, nicht gebaut).
6. Die Antwort gilt nur am Tag der Frage; am Folgetag heißt es „Diese Antwort galt für den …“ mit
   „erneut fragen“. Ein Klick, der die Frage neu stellt, nutzt den vorhandenen Weg (`refresh_available`).
7. Die Messlatte misst ohne Modell nur den Abruf; die Antwortqualität am Mac ist nicht gemessen.
