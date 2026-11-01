# Unabhängiges enges Backendreview: progressive Originaldarstellung

## Urteil

**Freigabe im vereinbarten Backend-/Trust-Scope. Keine kritischen oder wichtigen Funde.**

Geprüfter unveränderter Commit: `3d8c4ad3f803c6f34ef94dbff3e37a0e42688f4b`, Basis `c0e6265f6c20120974f445539fce6a8960b0745a`, Checkout `/private/tmp/kf-skill-categories-20261031`. Arbeitsbaum vor und nach den Läufen sauber. Dieser Reviewer hat keine Repositorydatei geändert.

**120 gezielte Repositorykontrollen plus 6 eigene externe synthetische Gegenproben bestanden.** Kein Vollsuitelauf, echte Modelle, private Quellen oder Netzwerkzugriffe. UI-Darstellung gehört zum separaten Review und wird hier nicht freigegeben.

## Produktdiff und Schutzgrenzen

Backendänderungen sind auf `working_memory_answers.py` und eine zusätzliche Kontextzeile in `agent.py` begrenzt. Satzgenerator, native Frage-/Vorbehaltsprüfung, Quellen-/Elternproof, Refresolver und Entzugsgates ändern sich im Diff nicht.

- Der Rückfall verwendet wieder `_zitate` mit vollständigem Originaltext (`working_memory_answers.py:1379`). `_zitate` löst weiterhin die aktuellen Referenzen auf; Anfang und Ende von `render` bleiben frischheitsgebunden. `nichts` wird weiterhin in Quellenwiedergabe überführt und beweist keine globale Abwesenheit.
- `original_fallback` ist ausschließlich eine Darstellungsmarke: Ohne geprüfte Struktur, ohne `claim_basis`, mit Refmenge und nach dem tatsächlich gerenderten Status. `working_selection_failed`, `working_unavailable`, unbekannte Antwort oder bestätigte Claimbasis erhalten diese Marke nicht (`1418-1425`). Die Marke erteilt keine semantische Bestätigung und erzeugt keine Claims.
- Agent und Wiederlesepfad verwenden denselben Helper nach `render`. `project_message` entfernt die gespeicherte Marke und Satzstruktur zuerst und berechnet beides neu (`1454-1464`); alte/falsche gespeicherte UI-Marken werden nicht als Beweis übernommen.
- Die Personenänderung setzt `person_question_optional` erst nach der vorhandenen Kontrolle von Seitenstatus und vollständiger ID-Union. Sowohl `adjust_selection` als auch der vorhandene Focus-Originalwächter müssen keine echte Personenmehrdeutigkeit festgestellt haben (`829-833`). Unterdrückt wird der Fragesatz zudem nur ohne echte Dropdownoptionen. Status und Refs werden dadurch nicht geändert; es gibt keinen weiteren Modellcall. Ohne dieses eng erzeugte Optionalmerkmal reicht ein leeres Dropdown nicht zum Unterdrücken der Frage.
- Vollständige Originale bleiben auch bei der darstellungsseitig markierten Personenunklarheit verfügbar. Dies akzeptiert keinen Satz und beantwortet keine ungeklärte Personenfrage durch eine angenommene Zuordnung.

## Eigene Gegenproben

Datei außerhalb des Repositories: `/private/tmp/kf_progressive_original_backend_independent_20261101.py`.

Log: `/private/tmp/kf-progressive-original-backend-independent-20261101.log`.

Ergebnis: **6 bestanden in 3,14 s**.

1. **Gestrippter Vorbehalt:** Quelle enthält `Die Lieferung Orion erfolgt am 14. Oktober vorbehaltlich der Freigabe. Die Freigabe fehlt noch.` Der verkürzte Kandidat wird korrekt abgelehnt. Vollständiges Original einschließlich Vorbehalt und Negation erscheint; keine Satzstruktur, `semantic_validation=False`, keine ausgewählten bestätigten Assertions. Agentantwort und gespeicherter Konversations-GET sind identisch. Original-GET unverändert; nach Entzug fehlen Body, Quellenlinks und Fallbackmarke.
2. **Legitimer Satzanbieterfehler:** Gleiche Prüfung mit absichtlicher `ProviderError` nur im Satzschritt. Fehler wird nicht als geprüfter Antworterfolg ausgegeben; es bleibt vollständige Quellenwiedergabe ohne Satzstruktur. Wiederlesen fragt das Modell nicht erneut; Entzug entfernt die Marke.
3. **Parsegültige leere Satzantwort:** Gleiche Prüfung mit `nichts_vorliegend` und leerer `originalstellen`-Liste. Die vorhandene Quelle bleibt sichtbar; daraus wird keine globale Abwesenheit und kein bestätigter Satz. Agent/GET/Entzug gleich wie oben.
4. **Ungültige Auswahl-ID:** `S999` führt weiter zu `working_selection_failed`, ohne Originalbody und Links. Weder Agent noch Wiederlesen setzen die Fallbackmarke. Eine absichtlich gespeicherte falsche Marke wird beim Wiederlesen entfernt. Der Originalrückfall verdeckt den Auswahlfehler nicht.
5. **Echte Namenmehrdeutigkeit ohne Dropdown:** Ein Original nennt `Lea Sommer liefert die Ventile ... Lea Winter liefert die Ventile ...`, bei Frage `Wann liefert Lea die Ventile?`. Trotz leerer `choices` bleiben `working_unclear/person`, beide Originalaussagen und `Welche der genannten Personen meinst du?` erhalten. Keine optionale Fallbackmarke; eine falsche gespeicherte Marke wird verworfen.
6. **Native falsche Datumsrolle:** Echter synthetischer MIME-/Native-Intake, zweimal valide leere Auswahl, bestehendes aktives Prüftor lehnt die Verwendung von Prüfdatum als Rücksendefrist mit `nein` ab. Weiter `zitate`, keine akzeptierte Satzstruktur und keine Claims. Die vollständigen Quellen werden als Originale gezeigt. Der Prüfauftrag enthält weiterhin die genaue Nutzerfrage und den vollständigen Rawbody. Wiederlesen entfernt eine gefälschte Satzstruktur; die Darstellungsmarke ändert das negative Gateurteil nicht.

## Ausgewählter Repositorylauf

Log: `/private/tmp/kf-progressive-original-backend-selected-20261101.log`.

**120 bestanden in 33,60 s**, eine vorhandene Starlette-Testclient-Abkündigungswarnung.

Vollständig ausgewählt wurden:

- `test_answer_clarification_projection.py`
- `test_conditional_report_binding.py`
- `test_source_correction_flow.py`
- `test_pilot_memory_guards.py`
- `test_docx_table_context.py`

Zusätzlich gezielt:

- Native identische Rows aus zwei Quellen, erste `ja`, zweite mit tragendem Vorbehalt `nein`/`unklar`/Timeout: kein akzeptierter Teilrest.
- Native falsche Datumsrolle bleibt geschlossen.
- Semantische Synonymfrage, gespeicherter Abruf bei ausgefallenem Embedder, Berichtigung statt altem Original und Quellenentzug.

Ausführung jeweils mit `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:.`, `/private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python -m pytest`, `-p no:cacheprovider`.

## Geänderte Assertions und Grenzen

Die geänderten Header-only-Assertions verlangen nun vollständigen Originalinhalt statt Textverlust. Sie behalten aktuellen Quellenlink, exakten Original-GET, unveränderten Quellenbody, keine zusätzlichen Modellcalls und Entzugskontrollen bei. Der geänderte Identity-Test fordert jetzt das richtige konkrete Dokumentoriginal, statt lediglich den bisherigen Unsicherheitshinweis zu akzeptieren. Das schwächt weder Personenbindung noch Qualifikatorinhalt.

Die neu geprüften Fälle für `claim_basis` und bereits gültige Sätze verbieten die neue Darstellungsmarke ausdrücklich; ihre bestehende Ausgabe bleibt erhalten. Der aktive DOCX-Frageprüfvertrag und die fehlende Antwort auf eine leere Rücksendefrist werden nicht durch Fallbackdarstellung ersetzt. Die Originalanzeige ist weiterhin eine Quellenwiedergabe, kein akzeptierter Satz.

Diese Freigabe belegt den begrenzten synthetischen Backendvertrag und die Behebung des zuvor isolierten Inhaltsverlusts. Sie ersetzt weder das separate UI-Review noch eine echte Quellen-/Modellstichprobe oder die vollständige Backendregression. Keine weiteren Suchbereiche oder Proben wurden eröffnet.
