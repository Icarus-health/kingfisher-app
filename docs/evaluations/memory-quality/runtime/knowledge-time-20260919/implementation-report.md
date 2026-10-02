# Task 1 – M2c Implementierung

Arbeitsbasis `ebb2e63bc61f7bfcc867ffd3e03c28b5db3614c3`, Branch `fix/knowledge-semantic-time-context`.
Status: Produktionsänderungen abgeschlossen und eingefroren; finaler Gesamtlauf grün. Kein Push, kein Modell, keine privaten Daten/Container, keine Downloads.

## Vertrag und Eingriffspunkte

- `knowledge_render.py`: reine `knowledge-context-v3`-Projektion aus kopierten, exakt geprüften Claims/Original-Snapshots. `KnowledgeInputBuild` hält genau einen Zeitpunkt sowie höchstens 128 verschiedene Claims und 128 verschiedene Quellen pro Aufbau/Neuprüfung, ohne Verdrängung. Jede Evidenz einschließlich zusätzlicher Zitate derselben Quelle wird geprüft. Snapshotmechanismus und Quotevalidator aus M1d, keine SelfModel-Producerautorisierung.
- `ContextItem.knowledge_projection`: exakte JSON-Datenzeile mit Designfeldern einschließlich `reason`; `knowledge_input`: `{version:1, claim_id, primary_episode_id, projection_sha256, source_generations}`. Die Generationen umfassen alle transitiven Originale. Signatur bindet kanonische Semantik und primären Beleg, ohne Auswahlgrund/Format. Kopien in API-Metadaten verhindern nachträgliche Objektänderung.
- UTC-kanonische Zeitfelder; unbekanntes `occurred_at=null`; getrennte Annahme-, Import- und Ereigniszeit. `evidence_at_basis` benennt das kompatible `evidence_at`. Primär bleibt erster gespeicherter Beleg. `[valid_from, valid_until)` bleibt maßgeblich.
- Höchstens 5 ausgelieferte Zeilen, 8192 UTF-8-Bytes pro vollständiger JSON-Zeile, 32768 Bytes für präfixierte Zeilen und tatsächliche Newline-Trenner insgesamt. Feste Hinweise sind **nicht** Teil dieses Datenzeilenbudgets. Ganze übergroße Zeilen werden ausgelassen, weitere begrenzte Kandidaten geprüft. `payload_omitted` zählt nur wegen Bytes geprüfte/ausgelassene Kandidaten; nur ausgelieferte Zeilen gehen in Items/Signaturen ein.
- `knowledge_history.py`: Lineage v2 mit exakter Gleichheit `knowledge_claim_ids` und `knowledge_inputs`-Schlüsseln, strikten Versionen/Shapes/Duplikaten, passender ausgewählter Teilmenge, gemeinsamer Historie aller gelieferten Wurzeln. Unterschiedliche alte/neue Signaturen werden nicht überschrieben. Nichtleere v1-Historie ist unbekannt; strikt leere v1-Historie wird ausdrücklich als leer akzeptiert.
- Agent: Aufnahme und Neuprüfung getrennt; bestehende Vor-/Nach-Provider-/ProviderError-/Toolgrenzen prüfen frische Projektionen und transitive Generationen. Reset/load/scoped propagieren korrekte Grenzen. Externe Anbieter erhalten weiterhin keine Wissensdaten.
- Freigaben: zusätzliche eingefrorene Wissensbindung pro Antrag, einschließlich leerer Bindung. Bleibt beim Historiereset erhalten, wird mit Scoped-Agenten derselben Policy geteilt und gegen `Policy.pending()` bereinigt. Veraltete Anträge werden vor Aktion abgelehnt. Damit kann das Zurücksetzen einer ersten veralteten Freigabe keine weitere alte Freigabe bereinigen.
- Server: tatsächlicher/scoped/injizierter Agent erhält Snapshotcallback; abweichender ClaimStore bei Injektion wird abgelehnt. Aktuelle Karten werden mit einem frischen gemeinsamen Build geprüft und bei Abweichung ausgeblendet; historische Metadaten bleiben unverändert. Manueller Mailentwurf speichert seine tatsächlich leere Lineage bereits bei Antragserzeugung, keine Nachzertifizierung beim Einlösen.
- API-Typen transportieren nur neue Metadaten; keine neue Oberfläche/Timeline.
- Recorder: `ProbeFixture.expected_manifest` ist vor Agentaufruf eingefrorener JSON-Text aus synthetischen kanonischen Zeilen, unabhängig vom Produktionsrenderer. Berichte bewahren Manifest+SHA256 sowie `knowledge_payload_version=3`. Unabhängiger, strikt feldgenauer v3-Matcher und eigener Zeitnormalisierer; v2 historisch weiter strikt. Beide Referenzmodi behalten Anfragebytes/Reihenfolge/Bedeutung.

## TDD und genaue Befehle

Alle Pythonaufrufe aus Worktreewurzel, Python3.12 aus vorhandener `.venv`. Erste RED-Ausgaben liegen im Toolprotokoll; keine nachträglich erfundenen RED-Logdateien.

1. `PYTHONPATH=sidecar:scripts .venv/bin/python -m pytest sidecar/tests/test_knowledge_time.py -q`: zunächst ein korrigierter Testimport-Sammelfehler (`test_context_identity` → `tests.test_context_identity`), danach erwarteter **RED12failed** vor Produktion: v2 verliert Semantik/Zeit, Metadatenmutation wird nicht abgefangen, UTF8-Zeilen fehlen als Grenze. Danach alle12 grün.
2. Kombinierter erster Kontextlauf: dieselbe Präfixumgebung mit `sidecar/tests/test_knowledge_time.py sidecar/tests/test_context_identity.py sidecar/tests/test_evidence_validity.py -q`: **43passed,9failed** ausschließlich alte Versionszusicherungen; neue Tests grün. Versionsassertionen aktualisiert, historische v1-Gegenfälle behalten.
3. `... pytest sidecar/tests/test_knowledge_time.py::test_changed_context_rejects_pending_approval_before_action scripts/test_probe_memory_pipeline.py -k 'strict_v3 or expectations_precede or changed_context' -q`: **RED13failed** (alte Freigabe führte Aktion aus; v3 noch nicht verifizierbar; Erwartungsmanifest fehlt). Nach Implementierung `... pytest sidecar/tests/test_knowledge_time.py scripts/test_probe_memory_pipeline.py -q`: **126passed**.
4. `... pytest sidecar/tests/test_knowledge_time.py -k changed_context -q`: **RED1failed,1passed**, weil Reset alte Freigabebindung verlor. Nach separater Antragsbindung grün.
5. `... pytest sidecar/tests/test_knowledge_time.py -k exact_projection_shape -q`: **RED4failed** für falsches `evidence_at`, falsche Basis, unbekanntes Projektionsfeld, fehlendes predicate. Nach strikter Shape-/Kompatibilitätsprüfung grün.
6. `... pytest sidecar/tests/test_knowledge_time.py -q`: **37passed**,2 vorhandene Starlette/anyio-DeprecationWarnings. Zwischenzeitlich ein Testfixturefehler mit nicht unterstütztem ClaimStore-Kontextmanager; korrigiert zu try/finally.
7. `... pytest sidecar/tests/test_knowledge_time.py sidecar/tests/test_evidence_validity.py sidecar/tests/test_profile_history.py -q`: **95passed** auf damaligem Teststand.
8. `... pytest scripts/test_probe_memory_pipeline.py -k 'timestamp_normalizer or historical_parser or bytes_remain or expectations_precede' -q`: **12passed**. Der Referenzbyte-Test hatte zunächst eine unvollständige handgeschriebene Erwartung (bestehendes identity_semantics-Feld/Reihenfolge fehlten); Fixture korrigiert, Produktionsreferenzfunktion nicht geändert.
9. Erster Gesamtlauf: `PYTHONPATH=sidecar:scripts .venv/bin/python -m pytest sidecar/tests scripts/test_memory_probe_support.py scripts/test_memory_probe_agent.py scripts/test_probe_memory_pipeline.py -q > /tmp/m2c-full-tests.log 2>&1`: **1740passed,2failed**,116.65s,2 DeprecationWarnings. Fehler `test_reply_requires_approval_and_preserves_exact_account` und `test_removed_sender_never_falls_back_to_another_account` in `test_mail_conversation_flow.py`: gespeicherter manueller Mailentwurf besaß keine Lineage. Echter Erzeugungspfad korrigiert, keine Aufweichung beim Resolve. Originalausgabe kopiert nach `checks/full-first.log`.
10. `PYTHONPATH=sidecar:scripts .venv/bin/python -m pytest sidecar/tests/test_mail_conversation_flow.py sidecar/tests/test_knowledge_time.py -q`: **47passed**,4.23s,2 DeprecationWarnings nach Mailkorrektur.
11. Finaler Gesamtlauf: gleiche vollständige Testliste, Ausgabe `/tmp/m2c-full-tests-final.log`, unverändert nach `checks/full-final.log` kopiert. **1753 passed, 2 vorhandene DeprecationWarnings**, 117.49s. Aufteilung: **1587 Backendtests + 166 Probetests** (11 zusätzliche Verifierkontrollen seit erstem Gesamtlauf).
12. `npm run build` in `app/kingfisher`: **PASS**, tsc -b und Vite,75Module.
13. `.venv/bin/python` mit `jsonschema.Draft202012Validator.check_schema(schema)` und `.validate(json.load(open('schema/beispiel-profil.json')))` gegen `schema/self-model.schema.json`: **PASS**, "schema and example valid".
14. `git diff --check`: **PASS**.

## Kontrollmatrix

| Kontrolle | Nachweis |
|---|---|
| Echter Versand/kanonische Semantik/3 unterschiedliche Zeiten | RecordingProvider mit vorab handgefrorenen erwarteten Feldern |
| null Ereigniszeit / äquivalente Offsetschreibweise | neue RecordingProvider- und harte unabhängige Normalisierertests |
| Halb offenes Intervall | exakt Start eingeschlossen, exakt Ende ausgeschlossen |
| primärer vs sekundärer Beleg / mehrere Zitate | erster Beleg bleibt primär; zweites ungültiges Zitat derselben Quelle sperrt |
| 128Claim-/128Quellen-Gesamtbudget | viele Wurzeln/129Quellen, kein Nachladen durch Verdrängung |
| Mutationen vor/während Provider/ProviderError | 3Felder ×3Fenster; keine stale Antwort/kein Vorabprovider bei Vorfenster |
| zurückgegebene Tools / wartende Freigabe / Historiereset | keine Aktion/kein neuer Antrag; alte Freigabe auch nach Reset gesperrt |
| Historie gleiches/neues Agentobjekt, Generationen | primäre, sekundäre und Vorfahrquelle ignore→reopen; alte Signatur bleibt erhalten; nach Reset nächster unveränderter Zug ohne erneuten Reset |
| Karten vs historisches Transkript | echte FastAPI-TestClient-Route blendet aktuelle Karte aus, historische exakt erhalten |
| strikte Lineage | Duplikate, fehlender Eintrag, bool-Version, zusätzliche Generation, manipulierte Daten, nichtleerev1 |
| UTF8/Zeilen-/Gesamtbudget/Omissions |6überlange Zeilen plus kleiner Kandidat; 32KiB-Fall mit weiterem passendem kleinem Kandidaten |
| v3Recorder |11Semantik-/Zeit-/Original-/Versions-/Extrafeldmutationen; tatsächlicher Inside-Provider-Mutationsversand bleibt unabhängig zuordenbar |
| v2/Referenzen | v2historisch strikt; v2 darf v3Metadaten nicht erfüllen; beide Referenzanfragen bytegenau unverändert |
| Gesamtschutz | vollständige vorhandene Backend-/Probe-/Egress-/Archival-/M1c-/M1d-Suiten |

## Offene Grenzen

- Optimistische Vor-/Nachprüfung; keine atomare DB/Modelltransaktion. Bereits gesendete Daten können bei Mutation während des Provideraufrufs nicht zurückgeholt werden; Rückgabe/Aktion wird unterdrückt.
- Generationen sind Kontinuitätsbindungen der gelieferten Quellen, keine neue ClaimStore-Annahme/Freigabe. Keine Restorefreigabe, kein Restorejournal/Antirollback; M1d-/M3-Grenzen unverändert.
- Keine echte Modellqualität/Modellgewichte geprüft. Unabhängige reale HTTP-/Containerabnahme und Review liegen bei Root.
- Python3.12 lokal geprüft; Python3.10-Kompatibilität im Code beachtet (bestehende UTC-Z-Kanonisierung), hier kein installierter3.10-Lauf behauptet.
- Bestehende Starlette/anyio-DeprecationWarnings nicht Teil dieses Patches.

## Selbstprüfung / Freeze

Diff auf Produktionsgrenzen, Referenzmodi, separate Aufnahmecaches und begrenzte Metadaten geprüft. `git diff --check` grün. Keine ClaimStore-Schemaänderung, keine M3-Datei verändert. Root-Nachweise gehören zum unabhängigen Abschluss; sie wurden nicht als eigene Prüfung umetikettiert. Commit `5bc9227` enthält ausschließlich die 13 eigenen Code-/Testdateien. Produktionscode eingefroren; kein Push.

## Nachtrag: unabhängiger Recorder unter Python 3.10

Roots korrigierter Python-3.10.21-Lauf identifizierte **1 failed, 221 passed**: `test_independent_timestamp_normalizer_rejects_invalid[2026-09-14T09:00:00ZZ]` akzeptierte den ungültigen doppelten UTC-Suffix. Der erste Rootlauf enthielt zusätzlich 26 reine Harnessfehler wegen fehlendem Git; diese sind nicht Produktfehler und wurden von Root separat korrigiert.

Eigenständig vor Fix auf vorhandenem `python:3.10-slim` reproduziert: Die tatsächliche Funktion aus `scripts/probe_memory_pipeline.py` wurde per AST unverändert in einem Standardbibliothek-Prozess geladen. Sowohl `2026-09-14T09:00:00ZZ` als auch `2026-09-14T09:00:00Z+00:00` wurden fälschlich akzeptiert. `...+00:00Z` wurde bereits abgelehnt.

Enger Fix ausschließlich im unabhängigen Recorder: ein `Z` darf nur genau einmal als abschließender Suffix nach einer Ziffer vorkommen. Danach erfolgt die vorhandene Offsetnormalisierung. Kein Import aus Produktionsrenderer/-serializer, keine Änderung an Agent/Server/Produktionsprojektion. Zwei zusätzliche malformed-Suffix-Testfälle.

Prüfung nach Fix:

- `PYTHONPATH=sidecar:scripts .venv/bin/python -m pytest scripts/test_probe_memory_pipeline.py -k timestamp_normalizer -q`: **11 passed**, Python 3.12.
- Vorhandenes `python:3.10-slim`, `docker run --rm -i --network none --mount type=bind,...,readonly`: **11 unabhängige Zeitkontrollen bestanden**, Python 3.10.21; ausgeführt gegen tatsächliche Funktions-AST, ausschließlich Standardbibliothek. Kein vollständiger pytest-Lauf dadurch behauptet; Roots separater kompletter Kompatibilitätslauf folgt.
- `PYTHONPATH=sidecar:scripts .venv/bin/python -m pytest scripts/test_memory_probe_support.py scripts/test_memory_probe_agent.py scripts/test_probe_memory_pipeline.py -q`: **168 passed in 2.49s**.
- Keine Produktänderung seit dem grünen Backendgesamtlauf; neue Sammlung ist 1587 Backend + 168 Probe = 1755. Dies ist kein behaupteter erneuter kombinierter 1755-Lauf.

Nach diesem engen Recorderfix erneut eingefroren. Native/API-/Dockerproduktnachweise bleiben unverändert anwendbar.

## Kombinierte Fixwelle nach finalem Integrationsreview: tatsächlicher Freigabestatus

Einziger P2 aus `final-review.md`: Der Gesprächsserver leitete `approval_outcome` ausschließlich aus dem gewünschten `granted` ab. Eine wegen veränderter Wissensgrundlage tatsächlich abgelehnte Freigabe wurde deshalb dauerhaft als `approved` angezeigt. Kein Ausführungsbypass; fehlerhafter gespeicherter/angezeigter Status.

Enger Produktfix:

- `Turn.approval_outcome` trägt die tatsächliche Policy-Entscheidung separat vom Kontext der folgenden Antwort.
- `Agent.resolve` setzt `rejected` direkt nach erfolgreicher Ablehnung (Nutzerablehnung oder ungültige Grundlage) bzw. `approved` direkt nach erfolgreichem `Policy.grant`. Falsche Bestätigung wirft weiterhin vorher; die spätere Modellantwort kann die ursprüngliche Entscheidung nicht überschreiben.
- Der Gesprächsserver persistiert diesen tatsächlichen Wert. Fehlender Wert ergibt konservativ `unknown`, niemals eine aus dem Wunsch nachträglich abgeleitete Freigabe. Die bestehende Ausnahmebehandlung für unklare Ergebnisse bleibt erhalten.
- Das bestehende ActionAgent-Testdouble bildet den expliziten Rückgabevertrag ab; keine Rückfalllogik auf `granted` oder `context.invalidated`.

Zwei echte FastAPI/TestClient-Regressionsfälle prüfen jeweils POST-Antwort, anschließendes GET, gespeicherte Metadaten und einmalige Verarbeitung:

1. Quellenmutation **vor Aktion**: kein Sinkaufruf; `context.invalidated=True`; Metadaten und Karte dauerhaft `rejected`.
2. Erfolgreiche Aktion, Quellenmutation **im folgenden Provideraufruf**: genau ein Sinkaufruf; Folgetext verworfen/`context.invalidated=True`; Metadaten und Karte bleiben dauerhaft `approved`.

RED vor Produktänderung:

`PYTHONPATH=sidecar:scripts .venv/bin/python -m pytest sidecar/tests/test_knowledge_time.py -k http_resolution -q`

**1 failed, 1 passed, 37 deselected**, 0.70s, zwei vorhandene DeprecationWarnings. Erwarteter Fehler: `approved != rejected` im Vor-Aktions-Fall. Originalausgabe `checks/approval-outcome-red.log`.

GREEN nach Produktänderung:

`PYTHONPATH=sidecar:scripts .venv/bin/python -m pytest sidecar/tests/test_knowledge_time.py sidecar/tests/test_mail_conversation_flow.py sidecar/tests/test_agent.py sidecar/tests/test_conversation_actions.py sidecar/tests/test_routing_runtime.py sidecar/tests/test_evidence_validity.py sidecar/tests/test_profile_history.py -q`

**149 passed**, 15.80s, dieselben zwei vorhandenen DeprecationWarnings. Enthält normale Freigabe, ausdrückliche Ablehnung, falsche Bestätigung mit erneutem Versuch, einmalige Ausführung, unbekanntes Ergebnis, Mailkonto-Bindung und Scoped-Agent-Freigaben. Originalausgabe `checks/approval-outcome-focused-green.log`.

Wegen des gemeinsamen Resolve-Rückgabevertrags wird auch die vollständige Backend-/Probe-Suite erneut ausgeführt; Ergebnis und Fixcommit werden nach Abschluss ergänzt. Keine Frontend-/Schemaänderung in dieser Fixwelle. Root-Dokumentationsänderungen bleiben unberührt; nur eigene Produkt-/Testdateien werden committed.

Finaler Gesamtlauf dieser Fixwelle:

`PYTHONPATH=sidecar:scripts .venv/bin/python -m pytest sidecar/tests scripts/test_memory_probe_support.py scripts/test_memory_probe_agent.py scripts/test_probe_memory_pipeline.py -q`

**1757 passed, 2 warnings in 116.95s** (1589 Backendtests + 168 Probetests). Originalausgabe `checks/approval-outcome-full-green.log`. `git diff --check` ebenfalls grün. Keine neuen offenen Befunde; nur die zwei bereits dokumentierten Abhängigkeitswarnungen. Der Fix ist bereit für das vereinbarte begrenzte Re-Review der Outcome-Änderung.

Fixcommit und erneuter Freeze: `ccb47b1f8a60ee8fe57665dd7b557516ad45e4fb`. Ausschließlich vier eigene Dateien (`agent.py`, `server.py`, `test_conversation_actions.py`, `test_knowledge_time.py`) committed, kein Push. Roots Dokumentationsänderungen und sämtliche Planungsdateien unberührt. Produktionscode erneut eingefroren.
