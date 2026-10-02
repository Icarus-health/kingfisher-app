# Bericht ↔ Report: geschlossenes Nomenpaar-Synonym zur Abfragezeit

„Vorher“-Commit `673c8f6bd2084eb409e9e174a5289be3cc666063` (main nach PR #58/#59),
„Nachher“-Commit `4464356` (dieser Fix). Keine semantische Freigabe, keine
Modellprüfung — reine Quellen-Trefferauswertung wie bisher.

## Problem

„Was steht im Report?“ fand keinen Treffer für einen Beleg, der nur „Bericht“
enthält, und umgekehrt — unabhängig vom eingefrorenen 22-Fragen-Datensatz mit
echten ClaimStore-/FTS-Kandidaten und dem tatsächlich gelieferten
Provider-Kontext reproduziert. Im eingefrorenen Fall `everyday-search-18`
(„Kann der fertige Report veröffentlicht werden?“, erwartet S9) lieferte die
Suche stattdessen nur die Bildlizenz S8.

## Korrektur

„Bericht“ und „Report“ sind unterschiedliche Wörter für dieselbe Sache, keine
Flexionsformen eines Lemmas — deshalb ein eigenständiges, geschlossenes
Synonympaar (`word_forms.NOUN_SYNONYMS_V1`/`synonym_alternatives`/
`synonym_matching_terms`), getrennt von `NOUN_FORMS_V1` und dessen
Kompositum-Suffix-Abgleich in `alternatives()`. `claim_index.search()` bezieht
das neue Synonym in die Kandidatensuche ein; `Agent._knowledge_context_items()`
bezieht es in den späteren Term-Überlapp ein und weist einen reinen
Synonym-Treffer in der Begründung ausdrücklich als „(Synonym)“ aus, nie als
„(Wortformen)“. Keine Änderung an `lexical-v1`, Indexschema oder gespeicherten
Quellen. Keine Kompositum-Zerlegung: „Reisebericht“, „Geschäftsbericht“ und
„Reporter“ bleiben unberührt, da die Funktion nur exakte Formen vergleicht,
nie Suffixe.

## Exakter Offline-Vergleich

```sh
.venv/bin/python scripts/probe_everyday_memory.py --mode retrieval --lexical-only \
  --output docs/evaluations/memory-quality/runs/2026-09-20-bericht-report-synonym/lexical-only-before.json
# (auf Commit 673c8f6, vor der Änderung)

.venv/bin/python scripts/probe_everyday_memory.py --mode retrieval --lexical-only \
  --output docs/evaluations/memory-quality/runs/2026-09-20-bericht-report-synonym/lexical-only-after.json
# (auf Commit 4464356, nach der Änderung)
```

`dataset_sha256` identisch in beiden Läufen — die 22 eingefrorenen Fragen,
Quellen und Erwartungen sind unverändert. **Einzige Änderung: `everyday-search-18`**
liefert jetzt `[S8, S9]` statt `[S8]`. Alle anderen 21 Fälle liefern identische
Quellen wie zuvor. Exakte Treffer bleiben bei **13/22** — Fall 18 gewinnt die
erwartete Quelle S9 hinzu, bleibt aber wegen der zusätzlichen S8 kein exakter
Treffer. Eine bessere Trefferabdeckung ist hier also kein zusätzlicher exakter
Treffer, wie erwartet.

**S8 bleibt bestehen — dokumentiert, nicht behoben:** S8 („Die Lizenz für das
Bild darf nur intern verwendet werden.“) matcht Frage 18 weiterhin literal über
das Wort „werden“, das in Frage und Quelle gleichermaßen vorkommt und aktuell
nicht in `_LIGHT_VERB_FORMS` (`agent.py`) steht. Diese Schwäche ist vom
Bericht/Report-Synonym unabhängig und wird hier ausdrücklich **nicht** durch
stillschweigende Erweiterung der Verbfilterliste behoben — das wäre eine
eigene, gesondert zu prüfende Änderung.

## Gegenprüfungen (neu: `sidecar/tests/test_knowledge_bericht_report_synonym.py`, 14 Tests)

- Beide Richtungen (Bericht→Report-Quelle, Report→Bericht-Quelle) über
  Kandidatensuche (`agent._knowledge.search_context`) **und** tatsächlich
  gelieferten Provider-Kontext (`turn.context['items']`, `provider.messages`).
- Plural-/Genitivformen in beiden Richtungen (`Berichte`/`Reports`,
  `Berichts`/`Reports`).
- Wörtlicher Treffer und Synonym-Treffer überleben nebeneinander für dieselbe
  Frage; die Begründung unterscheidet sie korrekt (`(Synonym)` nur beim
  Synonym-Treffer).
- Fremdes Thema bleibt unberührt.
- Komposita `Reisebericht`/`Geschäftsbericht` werden **nicht** zu „Report“
  aliasiert; „Reporter“ wird in keiner Richtung aliasiert.
- Eine unabhängige bestehende Wortform-Regel (Vertrag/Verträge) bleibt von der
  neuen Regel unberührt — keine unbeabsichtigte Ausweitung.
- Widerrufener Quellbeleg (`episodes.ignore`/`retract`) bleibt ausgeschlossen,
  wenn er nur über das Synonym gefunden würde.
- Abhängiger Treffer mit widerrufener Grundlage bleibt ausgeschlossen; ein
  direkter, unabhängiger Treffer bleibt weiterhin geliefert.

Kontextgrößenbegrenzung und Kandidatenbegrenzung nutzen bewusst die
bestehenden, dafür bereits vorhandenen Tests
(`test_exact_candidate_survives_many_newer_inflected_candidates`,
`test_alternatives_cannot_exhaust_exact_claim_dependency_validation` in
`test_knowledge_word_forms.py`, `test_candidate_limit_is_strictly_bounded` in
`test_claim_index.py`) — dieselbe Kandidaten-Pipeline und dasselbe
Suffix-/Term-Budget verarbeitet jetzt zusätzlich die Synonym-Erweiterung, eine
zweite Kopie derselben Absicherung wurde nicht neu gebaut.

**Sabotageprobe:** Der Fix wurde testweise zurückgenommen (`git stash`, kein
Sabotage-Commit im veröffentlichten Verlauf) — **9 der 14 neuen Tests**
schlugen exakt an der erwarteten Stelle fehl, die 5 übrigen (Negativkontrollen,
die die neue Regel gar nicht brauchen) blieben grün. Änderung danach
zurückgeholt und erneut geprüft.

## Genaue Prüfkommandos und Ergebnisse

Getesteter Commit: `4464356`, sauberer Arbeitsbaum, `make sidecar-dev`.

```sh
.venv/bin/python -m pytest sidecar/tests/test_knowledge_bericht_report_synonym.py \
  sidecar/tests/test_knowledge_word_forms.py sidecar/tests/test_knowledge_context_relevance.py \
  sidecar/tests/test_knowledge_time.py sidecar/tests/test_knowledge_search.py \
  sidecar/tests/test_live_knowledge_search.py sidecar/tests/test_agent.py \
  sidecar/tests/test_context.py sidecar/tests/test_claim_index.py sidecar/tests/test_claims.py \
  sidecar/tests/test_decision_knowledge_flow.py sidecar/tests/test_memory_agent_boundary.py \
  scripts/test_probe_everyday_memory.py scripts/test_probe_memory_pipeline.py \
  scripts/test_memory_probe_support.py scripts/test_memory_probe_agent.py -q
```
→ **420/420 bestanden.**

## Grenzen

Reine Diagnose-/Suchkorrektur, keine Suchqualifikation. `S8`-Falschtreffer bei
Fall 18 bleibt offen (siehe oben, eigene Ursache). Kein Kompositum-Stemming,
keine automatisch erzeugte Synonymliste — genau ein von Hand geprüftes Paar.
Semantische Suche bleibt standardmäßig aus. Keine neuen Abhängigkeiten, keine
CI-Workflow-Änderungen. Kein vollständiger erneuter Sidecar-Gesamtlauf ohne
konkreten Anlass (die oben aufgeführten, betroffenen Testdateien decken den
geänderten Code direkt ab).

## Unabhängige Nachprüfung und Korrektur

Geprüfter Code: `f193bab5f4cc9efacb707069753f6195425e8cdf`.

Die obigen 420 Tests waren die gezielte Prüfung des ursprünglichen Beitrags,
kein vollständiger Backend-Lauf. Die Nachprüfung ergänzt:

- Diagnosefehler behoben: Die Kandidatensuche zählte bislang reine
  Synonymtreffer als `word_form_candidates` und Synonymalternativen als
  `word_forms_used`. Jetzt gibt es getrennte `synonym_version`, `synonyms_used`
  und `synonym_candidates`. Wortform- und Synonymkandidaten können sich bei
  mehreren Suchbegriffen überlappen; die Zeile zur Erkennung abgeschnittener
  Ergebnisse zählt nicht als zurückgegebener Kandidat. Kandidatenauswahl,
  Sortierung, maximal zwei FTS-Abfragen und ihre Grenzen bleiben unverändert.
- Drei Diagnose-Gegenproben schlugen auf dem ursprünglichen PR fehl und
  bestehen mit der Korrektur. Dazu Prüfung der zusätzlichen Grenzzeile sowie
  eines zu großen Synonymtreffers. Zwei bestehende Budgettests laufen jetzt
  zusätzlich mit `Bericht`/`Report`; vorher verwendeten sie nur Wortformen.
- Vollständiger lokaler Lauf auf macOS/Python 3.12, nach Bau des vorhandenen
  Kalenderhelfers: **2070 Tests und 4 Untertests bestanden**, zwei Warnungen
  aus Abhängigkeiten. Befehl: `PYTHONPATH=sidecar:scripts
  ICARUS_DATA_DIR=<isoliertes Testverzeichnis> python -m pytest -q sidecar/tests scripts`.
- Der offizielle Offlinevergleich liefert dieselben Quellen wie der
  ursprüngliche PR in allen 22 Fällen. Weiterhin 13/22 exakte Quellensätze;
  einzig Fall 18 verändert sich gegenüber `673c8f6` von S8 zu S8 und S9.
- Docker-Image aus dem geprüften Code gebaut. Alle 22 Fälle zusätzlich mit
  dem installierten Paket, synthetischen Daten und ohne Netzwerk geprüft;
  Quellenmengen identisch. Wiederöffnen und Quellenwiderruf ebenfalls geprüft.
- Tatsächlicher Browserablauf am separat gestarteten Container mit einer
  synthetischen Quelle und lokalem `qwen3.5:4b`: Frage nach dem Report findet
  den Bericht, Antwort erhält den Originaltext „Entwurf ohne Freigabe“,
  Begründung kennzeichnet das Synonym. Antwort und erneute Suche bestehen
  Neuladen und Containerneustart. Nach Quellenwiderruf: kein aktueller Treffer,
  Antwortstatus `unknown`, keine Browserfehler. Ergebnis in
  `reviewed-runtime.json`.

Grenze: Historische Nachrichten einschließlich damaliger Belegtexte bleiben
wie zuvor im gespeicherten Gespräch sichtbar. Der Widerruf entfernt sie aus
aktuellem Kontext und neuer Beantwortung; er löscht nicht den Gesprächsverlauf.
Eine zunächst zusätzlich angenommene vollständige Verlaufsredaktion ist kein
bestehender Vertrag dieses Flows (`server._conversation_payload`, gegenüber
`673c8f6` unverändert) und wird durch diese Prüfung nicht zugesichert.

Die GitHub-Check-Annotation des ursprünglichen PR-Heads bestätigt, dass die
Sidecar-Ausführung wegen fehlgeschlagener Zahlungen bzw. des Ausgabenlimits
nicht gestartet wurde. Keine CI-Wiederholung ausgelöst. Die lokalen Belege
sind keine Behauptung einer erfolgreichen GitHub-CI oder allgemeinen
Gedächtnis-/Sprachverständnis-Abnahme.
