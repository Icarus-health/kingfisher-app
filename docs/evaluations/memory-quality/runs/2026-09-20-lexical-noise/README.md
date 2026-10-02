# Bounded lexical noise filtering: final review

Production code tested: a273c431f2cb8a6c4d1a1948d53e481472c78cbb, following PR #59 candidate 171579e. This is a narrow default-retrieval correction, not semantic-search qualification.

## Result

When another candidate has a lexical match outside the closed forms `liegt`/`liegst`, a purely lexical match on only those forms is omitted. A match backed by the experimental semantic channel is retained for the existing canonical checks. The stored lexical-v1 index, identities, source validity and model configuration remain unchanged.

The original access-card question now delivers the card source without an unrelated report that merely shares `liegt`. In the frozen 22-case development corpus, exact source sets improve 12/22 to 13/22. Only everyday-search-5 changes; the other 21 source sets remain equal to the committed word-form baseline. This is not a general relevance score or a holdout.

## Independent corrections and tests

- The former overlap-count implementation removed a relevant single-noun match; the revised code retains it.
- Independent reproductions with a revoked dependency or an oversized competing claim retain the unrelated valid access-card source. The permanent tests now use a one-term valid source, matching the reported regression exactly.
- A further review found that `liege` and `liegen` can be furniture nouns. Two new tests failed on 171579e because the relevant Liege/Liegen source disappeared. Removing these ambiguous forms from the closed filter makes both pass. No tokenizer or index change.
- Experimental semantic candidates remain protected from this lexical filter. They still require the existing canonical evidence validation; this is not a semantic accuracy guarantee.

## Validation

- 51 focused relevance/time tests passed.
- macOS Python 3.12, isolated ICARUS_DATA_DIR, `PYTHONPATH=sidecar:scripts python -m pytest -q sidecar/tests scripts`: 2,039 passed, two existing dependency deprecation warnings. Four calendar subtests initially failed because the fresh checkout had no generated build/kingfisher-calendar executable.
- After `bash scripts/build_calendar_reader.sh`, the exact failed file was rerun: `python -m pytest scripts/test_calendar_reader.py -q` -> 1 passed, 4 subtests passed. No source change was needed. The already-passing suite was not repeated.
- Dockerfile build passed, image kingfisher:pr59-a273c43 (fd7619272b78). Unchanged frontend layers reused the build cache.
- In the built runtime package, with `--network none`, a synthetic CaptureOnly/delivered_context probe confirmed all 22 source sets above, reopened the persisted access-card fixture and withdrew its source successfully. Installed package used; the source package was not placed on PYTHONPATH. No actual model call, HTTP/UI acceptance or private-app update is claimed by this check.
- `git diff --check` passed. Rust unchanged; no Rust rebuild, separate Python 3.10 run or broad model qualification in this review.

GitHub check annotations explicitly say jobs did not start because recent account payments failed or the spending limit needs adjustment. GitHub CI is not asserted green; no manual CI reruns. Local checks are the owner-authorized alternative. Broader paraphrase recall, extraction, scale and multi-day usefulness remain open.
