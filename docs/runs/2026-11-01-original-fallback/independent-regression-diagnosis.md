# Read-only Diagnose: Header-only-Rückfall nach fehlgeschlagener Satzantwort

## Urteil

**Ein wichtiger, konkreter Qualitätsverlust bestätigt:** Bei `reports` mit fehlgeschlagener oder leerer Satzantwort entfernt der neue kompakte Rückfall die vorhandene vollständige Originalaussage aus der Hauptantwort. Damit verschwinden auch Datum, Vorbehalt, Negation oder gesuchter Ort. Quellenwahl, gespeichertes Original, aktuelle Referenz, Original-GET und Entzug waren in den ausgewählten synthetischen Kontrollen weiterhin korrekt. Die alten Inhaltsassertions sind deshalb nicht pauschal überholte Volltext-Goldens.

Das ist kein Grund, Bedingungen zu entfernen, Oracles auf unbekannt zu setzen oder das native Frageprüftor zu lockern. Die Satz-/Native-Gates schützen in den geprüften Fällen korrekt. Der Verlust folgt erst beim Rendern.

## Stand und Umfang

- Ausgang: sauberer Root-Checkout `/private/tmp/kf-skill-categories-20261031`, HEAD `c0e6265f6c20120974f445539fce6a8960b0745a`.
- Nur die benannten Fehlertypen und wenige synthetische Kontrollen gelesen/untersucht; keine Vollsuite, privaten Dateien, echten Modelle, Netzwerkzugriffe oder Repositoryänderungen durch diesen Reviewer.
- Root-Logs: `kf-memory-1.0.37-final-sidecar-20261101.log` und enges terminales `kf-memory-1.0.37-failure-triage-20261101.log`. Sandbox-HTTP-/Swiftfehler gehören nicht zu diesem Befund.
- Nach Abschluss der fünf unabhängigen Diagnosefälle änderte sich der gemeinsame Root-Arbeitsbaum bei unverändertem HEAD: `agent.py`, `working_memory_answers.py`, `test_answer_clarification_projection.py`. Ein danach gestarteter Altfall-Lauf ist unten ausdrücklich getrennt und keine unveränderte c0-Baseline oder Patchfreigabe.

## Ursache im tatsächlichen Kontrollfluss

`working_memory_answers.py:1342-1345` setzt `kompakt` für aktuelle versionierte `reports` bei `nichts` oder nicht wiederherstellbaren `zitate`. Die korrekte Schutzentscheidung `nichts` → keine bestätigte Abwesenheit bleibt erhalten (`1346-1350`). Dann übergibt `1380` jedoch `originaltext=not kompakt` an `_zitate`.

`_zitate` verwirft damit genau `episode.body` (`1272-1273`), während Titel, Quellenzeit und Originalquellenlinks weiter ausgegeben werden. Die Quelle enthält den gesuchten Beleg also noch, aber die Antwort liefert ihn nicht mehr. Für alte gespeicherte `status=saetze`, deren Satzbindung beim Lesen scheitert, greift dieser kompakte Sonderzweig nicht; dieselbe Quelle wird dort vollständig gezeigt. Der fresh/saved-Unterschied hängt folglich am gespeicherten Status und nicht an anderer Evidenz.

## Eigene synthetische Gegenproben

Unveränderte Diagnosen außerhalb des Repositorys:

`/private/tmp/kf_header_only_diagnostic_20261101.py`

Ausführung vom Ausgangscheckout:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:. /private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python -m pytest -q -s -p no:cacheprovider /private/tmp/kf_header_only_diagnostic_20261101.py
```

Log: `/private/tmp/kf-header-only-diagnostic-20261101.log`. **5 bestanden in 1,89 s.** Diese Tests bestätigen die Diagnose samt Schutzgrenzen, keine gelungene Produktantwort.

| Gegenprobe | Beobachtung und Bedeutung |
|---|---|
| 70-Zeichen-Original `Die Lieferung Orion erfolgt am 14. Oktober vorbehaltlich der Freigabe.`; verkürzter Kandidat ohne Vorbehalt | Kandidat korrekt verworfen, `zitate`, `working_reports`, aktuelle Quellenreferenz. Hauptantwort enthält weder `14. Oktober` noch `Freigabe`. Bestehender `_zitate(..., originaltext=True)` liefert das ganze Original mit identischen Links. Alter gespeicherter ursprünglich gültiger Satz mit anschließend absichtlich verkürztem Text fällt dagegen korrekt auf das vollständige Original zurück. |
| 624-Zeichen-Atomabsatz mit Datum und `Wir melden uns, sobald es Neuigkeiten gibt.` | Vollständige Einheit überschreitet das Satzlimit; **0 Satzmodellcalls**. Trotzdem fallen Datum und Bedingung aus der Hauptantwort. Dieser Fall ist unabhängig von einem Fakeanbieter, der den neuen Original-ID-Vertrag nicht kennt. Die richtige Grenze ist keine partielle Datumsantwort. |
| Echte Upload → WMA → Berichtigung → Frage → Konversations-GET → Original-GET → Entzug-Pipeline | Nur im Satzschritt wird absichtlich eine legitime `ProviderError` ausgelöst; Einordnung/Auswahl laufen weiter. Aktuelle Ref zeigt ausschließlich auf die Berichtigung. Altes Original ist unverändert und ignoriert. Original-GET enthält exakt `Mainz: Anna liefert den Entwurf am 28. September 2026, nur wenn die Freigabe vorliegt. Die Freigabe fehlt noch.` Die Hauptantwort und ihr gespeicherter GET zeigen davon weder Datum noch fehlende Freigabe. Nach Entzug: `working_unavailable`, keine Links und kein Mainz-Suchref. Kein Daten-/Entzugsfehler nachgewiesen, aber klarer Antwortverlust. |
| Echte semantische Suche mit lokalem synthetischem ConceptEmbedder, dann legitimer Satz-ProviderError | `semantic_basis` und ausgewählte Ref enthalten die tatsächliche Quelle `Die Zugangskarte liegt im Schrank neben dem Empfang.` Original-GET vollständig; Hauptantwort enthält weder diese Aussage noch `Schrank`. Semantischer Abruf erfolgreich, nutzbare Ortsauskunft durch Darstellung entfernt. |
| Echter synthetischer MIME-DOCX → remember → WMA → prepare/render wie alter `docx_table_context`-Fall | `Beschäftigungsbeginn:\n18.11.2026\tRücksendedatum:` bleibt genau einmal im Original. Es wird **kein aktives Frageprüftor** übergeben. Daher korrekt weiter `zitate`, keine akzeptierte Satzstruktur; Datum und Formular verschwinden erst aus render. Der alte Inhaltsfehler beweist hier keinen neuen nativen Erfolg und erfordert kein Umgehen des Gates. |

Die API-Proben verwenden bewusst eine echte behandelte Satzanbieter-Störung statt eines veralteten Antwortformats. Sie behaupten keine semantische Modellgüte. So bleibt die parallel untersuchte Fakeanbieter-/Original-ID-Frage vom nachgewiesenen Rückfallfehler getrennt.

## Einordnung der genannten Altfallgruppen

- `conditional_report_binding`: Erforderliche Vorbehalte müssen im sichtbaren Original erhalten bleiben. Fresh-Verlust ist echt. Bereits gespeicherter ungültiger `saetze`-Fall schützt und zeigt das Original noch; er darf nicht verschlechtert werden.
- `source_correction_flow`: Geprüfte Berichtigung und Entzug arbeiten korrekt. Die frühen Inlineassertions verdecken nachfolgende wichtige Kontrollen; diese wurden in der externen Diagnose tatsächlich fortgesetzt. Der korrigierte Inhalt einschließlich `nur wenn` und `Freigabe fehlt noch` ist in der Hauptantwort erforderlich.
- `working_memory_semantic`: In der überprüften Synonymfrage geht der Treffer nicht verloren, sondern die Ortsaussage. Ein korrekter Quellenlink allein erfüllt den vorgesehenen alltagstauglichen Abruf nicht.
- `pilot_memory_guards`: Reports-Fälle mit z.B. `Das Hotel ist noch offen` müssen diese Negation als vollständigen Originalbericht zeigen können. Diese Teilgruppe ist nicht durch eine Titel-/Linkassertion ersetzbar. Personunklarheit ohne echte Auswahloptionen ist nach Rootvorgabe eine andere bewusst kompakte Darstellung und bleibt vom Korrekturvorschlag ausgenommen. Der Pilot wurde gelesen, nicht als ganzes erneut ausgeführt.
- `docx_table_context`: Der betrachtete Altfall scheitert weiterhin am Originalanzeige-Vertrag. Kein Anlass, seine fehlende aktive Native-Prüfung durch eine angenommene erfolgreiche Antwort zu ersetzen.

Nicht alle 58 Rootfehler wurden hier unabhängig klassifiziert; keine Behauptung, dass jeder dieselbe Ursache hat.

## Kleinster belegter Korrekturvorschlag, noch keine Implementierung

Für frische gültige `reports`, die nach Satzversuch im Zitatmodus verbleiben, wieder den vorhandenen vollständigen **Originalbericht** durch `_zitate` ausgeben. Die Unsicherheitsansage kann erhalten bleiben; die visuelle Kompaktheit darf den Body nicht aus dem Antwortvertrag löschen. Im jetzigen Kontrollfluss genügt konzeptionell, die Entscheidung `originaltext` von dem allgemeinen `kompakt` zu trennen und nur für die bewusst kompakte Personunklarheit ohne Optionen zu unterdrücken. `nichts` muss weiter in Zitate zurückfallen und darf keine globale Abwesenheit beweisen.

Progressive UI-Darstellung kann die vollständigen, klar als Quelle gerahmten Originale einklappen bzw. aufklappbar darstellen. Sie muss Inhalt und Quellenzugriff erhalten. Keine neue Auswahlrunde oder neue Ausschnittheuristik nötig; gerade ganze Originale vermeiden abgeschnittene Mehrsatzbedingungen. Vollständige Originalberichte sind unbestätigte Quellenwiedergabe, keine Freigabe des verworfenen Satzes.

Unverändert zu halten: gültige Sätze, unversuchte Originalberichte, Native-Frage-/Vorbehaltsgate, All-or-nothing, Quelle-/Eltern-/Fingerprintvalidierung, aktuelle Refmenge, Wiederlese-/GET-/Entzugsprüfung und bewusst kompakte Personunklarheit ohne Optionen. Keine erforderlichen Bedingungen, Negationen, Chronologie oder Urheberhinweise aus Tests entfernen. Tests, die bewusst nur Header ohne Original verlangen, müssen als neuer Produktvertrag diskutiert werden; sie rechtfertigen den belegten Inhaltsverlust nicht.

## Getrennter späterer Kontrolllauf

Nach den bereits vorhandenen fremden Arbeitsänderungen im gemeinsamen Root-Checkout lief eine enge unveränderte Auswahl alter Tests:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:. /private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python -m pytest -q -p no:cacheprovider sidecar/tests/test_conditional_report_binding.py -k '(conditional_original_remains_visible and vorbehaltlich) or oversize_conditional_paragraph_falls_back_without_hiding_date or condition_guard_does_not_restore_withdrawn_source or (complete_conditional_original_can_still_answer and vorbehaltlich)'
```

Ergebnis: **5 bestanden, 43 abgewählt in 0,64 s**; Log `/private/tmp/kf-header-only-original-tests-20261101.log`. Enthält fresh/saved Vorbehalt, vollständigen gültigen Vorbehalt, Oversize-Rückfall und Entzug. Dieser Lauf ist zusätzliche Evidenz an der laufenden Arbeitsänderung, keine unabhängige Freigabe eines eingefrorenen Reparaturcommits. Keine weiteren Proben oder Repositoryedits durch diesen Reviewer.
