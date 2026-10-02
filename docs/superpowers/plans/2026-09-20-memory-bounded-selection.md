# Bounded local memory selection

Continuation of the approved memory roadmap. Baseline cd4fecde47eaa00105f6a0b04242b35ecf9a1d1d.

Observed cause: Agent.answer_memory uses unrestricted complete() for a maximum of five evidence aliases even though the local provider already supports bounded schema-based completion. Previous eight-case diagnostics recorded 13–61 second model calls and one syntax fallback.

Change: use existing complete_json with 256 tokens and a closed schema containing only captured aliases; retain independent parser validation, local-only egress, freshness checks, deterministic original-source display and no tools. A bounded provider failure is never retried through unrestricted chat. Custom local providers lacking the optional capability retain their previous path. RecordingProvider must preserve the delegate capability and capture the exact bounded request.

Validation: observed seven new regression cases fail before implementation; targeted tests pass after implementation. Compare both transports on identical frozen synthetic fixtures with alternating order, disclose model/cache/load effects and retrieval misses. Run broader existing countercases, full macOS/Linux tests, immutable independent review and isolated HTTP acceptance. Merge and update the Mac app with a new backup and copied-data verification after these checks.

Scope boundary: this patch changes generation limits, not lexical normalization or semantic ranking. German inflection misses, hybrid false positives and bounded index coverage require separate measured changes; do not silently alter the persisted lexical-v1 contract or enable experimental semantic search. Human multi-day usefulness remains unverified.
