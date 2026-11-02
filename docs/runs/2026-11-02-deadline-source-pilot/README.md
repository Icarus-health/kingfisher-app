# Missing evidence, deadline explanations and bounded mail quality

Unknown source selections previously rendered a statement that there was no information in the classified sources. The renderer now reports that the requested information could not be substantiated. It does not guess whether the user asked for a date, reason, duration or person. Existing source freshness, coverage warnings, unknown status, confirmed-claim fallback and empty selection remain unchanged.

The existing selector instruction now explicitly preserves conditional timing evidence, keeps clarification mandatory when a necessary relative-time reference is missing, and distinguishes an unrelated date from an explicitly source-linked deadline. It still returns only the existing schema; no heuristic promotes unselected candidates.

Mail quote alignment now recognizes one physical wrap inside a complete known HTML entity. It restores the exact original span, including the encoding and proved quotation prefixes. Unknown entities, recursive decoding, multiple wraps, paragraph breaks, ambiguous occurrences, operators and changed words/numbers remain rejected. Normalization remains mail-only; literal evidence and all provenance checks remain in force.

Both category-analysis prompts now distinguish product/app/subscription names from explicitly named projects. This is a model instruction, not a deterministic guarantee about every classification. No brands are hardcoded and the entity schema is unchanged.

## Evidence

- Unknown-answer regressions exercise real source stores, scoped wording, coverage, withdrawal and reason/duration/person/call-window countercases.
- Five wrapped-entity positive regressions failed before the repair; four independently supplied boundary cases failed before tightening to one logical line separator and at most 40 token characters.
- Final affected tests: **241 passed**.
- Independent review of deadline handling and selection paging: **51 passed**.
- Independent final mail-alignment review: **55 passed**, no remaining scoped findings.
- Complete final sidecar regression is running against product head `edfb4d84cc306655c36fce1eda1f61bdb7e31049`; no completion claim is made here yet.

The separate explicitly authorized private pilot is recorded outside the repository. It is not a public fixture, universal extraction benchmark, or authorization to resume a bulk import. Actual source acceptance, private cost receipts, local installation and the native Mac window are tracked separately. No private messages, attachments, identifiers or model responses are included here.
