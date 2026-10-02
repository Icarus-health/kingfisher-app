# Closed German noun-form retrieval: development evidence

Baseline 5cc6ed9; initial candidate 9208f13; reviewed correction ce68503. No private data, model downloads, paid calls or semantic-search activation. Persisted lexical-v1 index and all canonical documents remain unchanged.

## Frozen retrieval collection

The same 22 German questions and expected source sets as the preceding everyday evaluation were rerun. Dataset SHA256 equality was checked. Default lexical exact-source matches improve **11/22 → 12/22**, with no changed source set except the previously missing Server/Servers case, now correct. Experimental live cold/warm retrieval remains **15/22** including its existing irrelevant negative-control hit. This remains insufficient for enabling semantic retrieval by default.

`retrieval.json` is the initial candidate; `retrieval-final.json` repeats it after the budget correction. All 66 selected source sets match between these candidate revisions. This development collection is not an independent holdout and contains many paraphrases outside the closed noun list. No claim of comprehensive German morphology or broad relevance qualification.

## Meaning and model behavior

`meaning.json` uses the installed local qwen3.5:4b and eight prepared-source cases. All eight yield schema-valid source-bound answers; the former Atlasbericht/Atlasberichte miss now retrieves the original statement about Mira, including the explicit denial that it establishes the user's preference. No action or user-profile write occurs. First model call took 6.60 s, subsequent calls 0.89–1.14 s in this observation; not a controlled latency comparison.

`countercases-final.json` runs the existing 16-case suite after the final correction, with stable model metadata. Nine evidence answers, two unknown, four clarification, one stale-calendar result; no transport/format failure. **One existing case, newer-rejection-01, now abstains despite receiving both appropriate originals**, unlike the earlier run's evidence answer. Comparing requests shows fresh synthetic IDs and corresponding tie-order changes; source content and time fields remain present. This exposes model/ordering sensitivity, not a missing retrieval, and is retained as an open quality failure. No retry or prompt tuning hides the failed answer. Broad semantic reliability is not qualified.

## Regression review and source boundary

Twelve new cases failed before implementation; seven name/accent/compound negative controls already passed. Additional query-budget and unchanged-store reopen checks pass. Independent review reproduced an exact dependent claim lost when 200 alternative-form candidates exhausted the ranking build's claim cache. The correction reserves a fresh 128-claim/128-source validation build after the bounded 128 ranking reads. Its regression verifies exact delivery and exclusion after the dependency source is withdrawn. Final independent review: no open actionable findings, 111 focused tests and a mid-ranking withdrawal reproduction passed.

Full-suite and deployed-app evidence are in the release record. Multi-day owner usefulness requires real elapsed use and independent expectations.
