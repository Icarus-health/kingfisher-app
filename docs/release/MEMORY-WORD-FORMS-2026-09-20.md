# German noun forms in memory search

Production change ce68503, based on 5cc6ed9. Query-side alternatives cover 23 closed noun paradigms and their compounds with preserved alphabetic prefixes of at least three characters. Exact tokens own the candidate budget first. No general suffix stemming, accent folding, identity alias, persisted-token change, index migration, model request or new dependency.

The Agent preserves the same matching rules and marks form-based reasons. Ranking and canonical evidence validation now have separate bounded builds so unused alternative candidates cannot crowd out an exact claim's dependencies. Source/history freshness and original rendering remain mandatory.

Verification:
- Twelve initial regression failures reproduced; word-form, index, identity, hybrid, evidence and timing tests pass (156 focused tests after correction).
- Independent immutable review: one P2 budget regression fixed; final review without open blockers, 111 focused tests and independent concurrent-withdrawal reproduction passed.
- Final macOS Python 3.12 full suite: 2,027 passed plus four calendar subtests, two upstream deprecation warnings, 142.33 seconds. Isolated ICARUS_DATA_DIR; full sidecar/tests and scripts.
- Final Linux Python 3.10 suite: 2,004 passed, two upstream deprecation warnings, 198.15 seconds. Full sidecar plus CI diagnostic scripts in a read-only clean clone.
- Clean Docker build including React/Vite, schema/example, legacy JavaScript syntax and assets passed. Rust unchanged and not rerun locally.
- Final isolated real-model conversation/restart/withdrawal acceptance passed on port 19002. A singular Atlasbericht question retrieves a plural Atlasberichte source; the word-form reason, original denial, persistence after restart and exclusion after withdrawal were checked.

[Raw development results](../evaluations/memory-quality/runs/2026-09-20-word-forms/README.md): lexical exact sets improve 11/22 to 12/22; eight prepared meaning cases now all return source-bound evidence. Experimental semantic search remains 15/22 and off. Broader countercases retain an unnecessary model abstention with valid originals; semantic reliability and multi-day usefulness remain open. No blanket claim that memory or the six-step roadmap is finished.
