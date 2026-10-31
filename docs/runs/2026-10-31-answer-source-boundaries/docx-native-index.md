# Native Originalzeilen trotz irrelevanter Modelleinstufung erhalten

Basis: `b8d0a2ab7da92062d636ecf568f126e69d85cce4`. Nur synthetische
MIME-/Storetests und feste lokale Attrappen; keine privaten Quellen oder
tatsächlichen Modelle, keine Root-Änderung, kein Netz, Push oder Backfill.

## RED und kleinster Schnitt

Echte MIME-Aufnahme eines DOCX mit `Prüfdatum\n18.11.2026` liefert einen
gültigen nativen Nachweis. Wenn der Klassifikations-Fake jeden Originalblock
als `irrelevant` einordnet, enthält das reguläre `interpret`-Ergebnis null
Items. Auf der Basis speichert `WorkingMemoryStore.commit` damit einen
vollständigen, aber leeren Index: der neue Positivtest scheiterte mit
`len(found) == 0` statt eines bewiesenen Originalverweises.

Der Nachtrag ergänzt elf Produktzeilen im bestehenden Commitpfad. Erst nach
dessen vorhandenen Frische-/Entzugs-/Recheckprüfungen wird unter derselben
Transaktion der aktuelle native Nachweis erneut aus dem aktuellen Snapshot
gelesen. Nur ein vollständiger geeigneter Nachweis bei Rawbody bis 4000 Zeichen
darf ganze Raw-Rows als `uncertain` ergänzen. Body, Offsets, Source-Key,
Fingerprint, Elternbindung und alle bisherigen Native-Grenzen bleiben erhalten.

**Jede vorhandene relevante Überlappung hat Vorrang.** Ein bestehendes
`historical`, `conditional`, `uncertain` oder anderes gültiges Modell-Item,
das auch nur einen Teil der Row erfasst, verhindert die zusätzliche isolierte
Row. Art, Grenzen und Inhalt vorhandener Items werden nicht verändert.
Unberührte Rows werden nur innerhalb des vorhandenen `MAX_ITEMS`-Budgets
ergänzt. Kein zusätzlicher Verweis für ungültige/doppelte Metadaten,
unvollständige Quellen, ungeeignete Zeilen oder gewöhnliche irrelevante Prosa.

## Nachweis im unveränderten Antwortpfad

MIME → `remember` → generierter Anhangbody → tatsächliches `interpret` mit
allen Blöcken `irrelevant` → Commit → Wortindex → `prepare` → native
Satzprüfung mit aktiver Fake-Gegenprüfung → `render` liefert jetzt die
vollständige Zeile als `Quelle berichtet: „…“`. Der Fake-Prüfer erhält weiter
die getrennte Frage und den vollständigen unveränderten Rawbody. Die Row
bleibt `uncertain`; keine Datumsrolle, Person, Aufgabe oder dauerhafte
bestätigte Aussage entsteht daraus. Normale native Frage-/Vorbehaltsprüfung
und Unsicherheitsrückfall sind unverändert.

Der Test umfasst sowohl die einzelne Zweiparagraphen-Zelle als auch eine
Formularzeile mit leerem Nachbarfeld und separater Datenschutzregel.
Die externe Klassifikationsgrenze wird jeweils genau einmal aufgerufen;
der Nachtrag selbst ruft kein Modell auf.

## Recheck, Antworten und Suchcache

`ANALYSIS_VERSION` bleibt 1. Es gibt keine Migration oder automatische
Nachanalyse. Ein bereits vollständiger leerer Index bleibt ohne expliziten
Recheck unangetastet. Der vorhandene `explicit_recheck=True` kann denselben
vollständigen Snapshot mit seinen unveränderten vorhandenen Items erneut
committen; danach ergänzt der normale Merge fehlende Rows. Wiederholung mit
den gespeicherten Items erzeugt keine doppelten Keys und ändert keine Arten.

Der bestehende Revisions-/Signaturweg erfasst die zusätzlichen Originalkeys.
Flüchtiger und dauerhafter semantischer Cache nehmen sie regulär auf, ohne
Sonderinvalidierung oder neuen Fingerprint. Wiederholter identischer Recheck
erhält gespeicherte gültige Antworten und vorhandene Vektoren. Elternentzug
sperrt weiterhin Resolver, gespeicherte gerenderte Antwort und beide Caches.
Alle Vektoren im Test sind feste synthetische Zahlen; kein Embedding-Modell
wurde benutzt.

## Gezielte Prüfungen

49 neue Kontrollen: echte MIME-/Klassifikationskomposition, alle acht Arten
mit exakter/weiterer/teilweiser Überlappung und angrenzenden Grenzen,
Idempotenz, unveränderte Eingabelisten, Items-/Dublettenlimits, ungültige und
doppelte Tags, fehlender Proof, Quotes, Draft, freie Werte, unsupported XML,
Truncation, Rawbudget, veraltete/entzogene/dismissed Quellen, Prooflesen erst
im Commit-Lock sowie expliziter Recheck, Antworten und beide Suchcaches.

Der gezielte Abschlusslauf kombiniert diese Kontrollen mit vorhandenen
Native-/Tabellen-/Store-/Klassifikations-/Worker-/Semantik-/Original-/Absatz-
Tests und den sechs Pflichtkernmodulen aus `CONTRIBUTING.md`. Keine komplette
Suite: **425 bestanden in 39,32 Sekunden**, eine vorhandene
Starlette/httpx-Deprecation-Warnung. `git diff --check` ist sauber.
Ausgeführt mit `PYTHONPATH=sidecar:.` und dem vorhandenen Python-3.12-Venv:

```sh
python -m pytest -q sidecar/tests/test_docx_native_index.py \
  sidecar/tests/test_docx_native_rows.py sidecar/tests/test_docx_table_context.py \
  sidecar/tests/test_working_memory_store.py sidecar/tests/test_working_memory_analysis.py \
  sidecar/tests/test_working_memory_worker.py sidecar/tests/test_working_memory_semantic.py \
  sidecar/tests/test_working_memory_semantic_index.py sidecar/tests/test_working_memory_semantic_inventory.py \
  sidecar/tests/test_original_sentence_selection.py sidecar/tests/test_normative_paragraph_context.py \
  sidecar/tests/test_absatzauswahl_saetze.py sidecar/tests/test_context.py \
  sidecar/tests/test_egress.py sidecar/tests/test_agent.py sidecar/tests/test_kingfisher.py \
  sidecar/tests/test_claims.py sidecar/tests/test_graph.py
```
