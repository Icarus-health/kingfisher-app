# Local source-selection capacity

The explicit 8K Ollama profile has a 16,000-byte native request limit. Its source selector reviews at most four pages under one shared 60-second deadline. Repeated instructions crowded otherwise admissible original candidates out of that budget.

This change compacts only the selector's instruction. Candidate count, source text, IDs, freshness checks, source withdrawal handling, JSON schema, byte limit, model profile, page limit and deadline are unchanged. The instructions still require independent subquestion coverage, conditional statements, identity and project clarification, temporal qualification, unresolved changes and protection of confirmed knowledge.

The new regression uses a real source store with sixteen synthetic multilingual originals and the real native budget builder. It fails with `selection_failed` on the published instruction and passes with the compact instruction. Every candidate is reviewed once, the full original texts remain visible through the existing projection, one scripted positive page is retained and the saved basis is still fresh. This verifies paging capacity; external model judgments are scripted, so it does not establish model relevance or prose quality.

Validation: source-selection test file 35/35 passed; combined selection, source-copy, annotation and routing regression 143/143 passed on the compatibility-adjusted instruction. An independent text/diff review requested four wording clarifications, all applied, then found no blocking issue. The first permitted full regression exposed five text-coupled fixtures (9,257 passed, one skipped). Stable instruction markers were retained, and the source-copy fixture was enlarged so it still checks an over-budget unpacked request versus a fitting packed request. All affected tests now pass. Final broad regression and real-device acceptance remain in progress.

Acceptance limitation: a local full-corpus question still exceeded the shared selection deadline. This patch is not an everyday-memory acceptance result and does not authorize resuming a large import. Private probe inputs and outputs are not part of this record.
