# Offline-Lauf der lexikalischen Wortsuche: `--lexical-only`

Geprüfter Commit `2613618`. Keine privaten Daten, keine Modell-Downloads, keine
kostenpflichtigen Anfragen — und diesmal ausdrücklich auch kein Ollama. Keine
semantische Freigabe und keine Fachprüfung; reine Quellen-Trefferauswertung.

## Ausgangslage

`scripts/probe_everyday_memory.py --mode retrieval` initialisierte bisher immer
`LocalEmbedder`, bevor es die drei Varianten `lexical`, `live_cold` und
`live_warm` ausführte — auch wenn nur die reine Wortsuche geprüft werden
sollte. Ohne laufendes Ollama mit installiertem `bge-m3` schlug damit schon
der Start fehl, siehe die vorherige Fehlermeldung `Connection refused` beim
Verbindungsversuch zu `127.0.0.1:11434`.

## Änderung

Der neue Schalter `--lexical-only` beschränkt den Lauf auf die Variante
`lexical` und überspringt `LocalEmbedder` sowie `RefreshingKnowledgeSearch`
vollständig — kein Netzwerkzugriff, keine Modellanfrage. Der bisherige Aufruf
ohne den Schalter bleibt unverändert und prüft weiterhin alle drei Varianten.
Der Bericht weist `arms_selected`, `arms_skipped` und `embedding_initialized`
aus, damit nie unklar bleibt, welche Variante lief und welche absichtlich
ausblieb. Datensatz, Hash und die Auswertung über `delivered_context` (den
tatsächlich an den Capture-Provider übergebenen Kontext, nicht bloße
Suchkandidaten) sind unverändert.

## Exakter Aufruf

```sh
.venv/bin/python scripts/probe_everyday_memory.py --mode retrieval --lexical-only \
  --output docs/evaluations/memory-quality/runs/2026-09-20-offline-lexical/lexical-only.json
```

Voraussetzung ist nur `make sidecar-dev` (installiert `icarus-memory` samt
Testabhängigkeiten); kein Ollama, kein Modell, kein Netzwerk. Laufzeit rund
drei Sekunden.

## Ergebnis

`lexical-only.json`: `status: "completed"`, `arms_selected: ["lexical"]`,
`arms_skipped: ["live_cold", "live_warm"]`, `embedding_initialized: false` —
kein `embedding_model_key` im Bericht. Alle 22 Fragen wurden genau einmal
ausgewertet, `dataset_sha256` ist identisch mit dem vorherigen
Wortform-Lauf (`3ad687f…8ba56f4`).

**12/22 exakte Quellen-Treffer** — deckungsgleich mit dem zuvor dokumentierten
Stand der lexikalischen Variante (`docs/evaluations/memory-quality/runs/2026-09-20-word-forms/README.md`:
„Default lexical exact-source matches improve 11/22 → 12/22“). Dieser Lauf
ändert an der Suche selbst nichts; er macht denselben bekannten Stand nur ohne
Ollama reproduzierbar.

Acht Fälle fehlt die erwartete Quelle (`everyday-search-2, 4, 6, 10, 12, 16,
18, 20`), drei liefern eine zusätzliche, nicht erwartete Quelle
(`everyday-search-5, 14, 18`; `everyday-search-18` fehlt zugleich `S9` und
enthält stattdessen `S8`). Die zwei Negativkontrollen (`everyday-search-21,
22`, keine erwartete Quelle) bleiben korrekt leer. Diese bekannten
lexikalischen Lücken bestehen unverändert fort; die Erwartungen wurden nicht
angepasst, um den Lauf grün zu bekommen.

## Prüfungen

```sh
.venv/bin/python -m pytest scripts/test_probe_everyday_memory.py -q
```

10 von 10 Tests bestanden auf sauberem Arbeitsbaum. Eine Sabotageprobe (die
Bedingung, die `LocalEmbedder` für `--lexical-only` überspringt, testweise
entfernt) ließ fünf der zehn Tests gezielt fehlschlagen, bevor die Änderung
zurückgenommen wurde — die Tests fangen die Zusicherung tatsächlich ein.

Ebenfalls geprüft, unverändert grün:

```sh
.venv/bin/python -m pytest scripts/test_memory_probe_support.py scripts/test_memory_probe_agent.py \
  scripts/test_probe_memory_pipeline.py scripts/test_probe_hybrid_memory.py \
  scripts/test_memory_probe_catalog.py scripts/test_memory_answer_comparison.py \
  scripts/test_probe_everyday_memory.py -q
```

222 von 222 Tests bestanden — keine Regression an den bestehenden Varianten.

## Grenzen

Reine Diagnose-Infrastruktur, keine Suchverbesserung. Semantische Suche bleibt
standardmäßig aus. `--lexical-only` gilt nur für `--mode retrieval`; für
`--mode meaning` bleibt ein installiertes lokales Modell nötig und
unverändert erforderlich. Kein Anspruch auf semantische oder fachliche
Freigabe — reine Quellen-Trefferauswertung wie bisher.
