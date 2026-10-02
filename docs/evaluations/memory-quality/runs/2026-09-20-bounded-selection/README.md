# Local bounded evidence-selection diagnostic

Synthetic prepared claims only; no private data, model downloads or paid model calls. The installed local model is `qwen3.5:4b`.

## Comparison

`paired.json`: eight frozen `probe_everyday_memory.cases('meaning')` cases, one observation per arm, alternating legacy/bounded order. Runtime cf603b4; bounded selection uses production `complete_json`. Legacy disables that optional method and follows the former production `complete` path. Fresh fixture claim/episode IDs differ between arms; source content, aliases, business time and other message fields match after those two ID fields are normalized. `comparison-analysis.json` records this check and exact displayed-answer equality (8/8).

Seven cases call the model. End-to-end median: **26.630 s legacy → 1.158 s bounded**; ranges 13.213–41.687 s and 0.986–1.268 s. All seven produce source-bound evidence in both arms. The eighth remains unknown without inference: query `Atlasbericht` does not retrieve `Atlasberichte`. This patch does not fix that lexical miss. Unlike the earlier under-load diagnostic, no full suite or image build ran during this comparison. A focused reviewer suite ran independently; cache state and external machine load were not controlled. These are development observations, not a general speed guarantee or semantic acceptance.

`paired_probe.py` preserves the executed scratch driver's procedure with portable repository/output paths. Reproduce from the repo root with a new output filename:

```sh
PYTHONPATH=sidecar:scripts .venv/bin/python docs/evaluations/memory-quality/runs/2026-09-20-bounded-selection/paired_probe.py --output /tmp/kingfisher-paired-new.json
```

## Broader cases and actual runtime

`countercases.json`: existing frozen 16-case evidence-answer subset at 45bdd40. All completed: ten evidence answers, one unknown, four clarifications, one stale-calendar response; 11 model calls, median 1.236 s, maximum 1.950 s. No format fallback or technical failure. Model metadata/digest was stable before/after. Exact wire requests include the schema and token budget. The existing diagnostic transport uses its own 60-second read limit; the production adapter's 30-second timeout is separately covered by integration tests. Source rendering retains denial, quotations, exploratory status and attribution; these observations are not an independent human semantic verdict.

`http-result.json`: real Docker app with a new synthetic volume and actual local model on port 19001. Default conversation routing → source-bound denial → process restart → same source-bound answer → source ignored → unknown without another model call. Passed. The acceptance container was stopped; synthetic data retained. Its timing overlapped full platform tests and is not used in the speed comparison.

## Remaining gates

Search is unchanged: lexical inflection/paraphrase misses; opt-in semantic false positives and partial large-store coverage; no broad extraction/semantic qualification. Experimental semantic retrieval remains disabled in the private app. Multi-day owner use requires elapsed real use and independent expectations.
