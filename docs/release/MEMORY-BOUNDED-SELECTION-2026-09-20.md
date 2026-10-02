# Memory selection: bounded local generation

Baseline cd4fecd; production implementation 45bdd4020e73b2612232d4c2ac3764cd2c3abb45.

Evidence answers previously called unrestricted chat to select at most five aliases. They now reuse the existing local JSON completion with 256 output tokens, a closed schema limited to captured aliases, temperature zero and the provider's 30-second timeout. Independent parsing, source freshness, local-only egress and original-source rendering still decide what can be displayed. No automatic action or unrestricted retry follows a failed bounded call. Unsupported custom local providers retain their prior path, including through model routing; capability follows the selected provider, not the router's method name.

## Validation

- Red/green: seven initial regressions failed before implementation; two routed-capability regressions reproduced the reviewer finding before correction. Focused 129-test suite passed after correction.
- macOS Python 3.12: 2,005 tests plus four calendar subtests passed, two upstream deprecation warnings, 143.81 seconds. Isolated ICARUS_DATA_DIR; full `sidecar/tests scripts`.
- Linux Python 3.10: 1,982 tests passed, two upstream deprecation warnings, 201.41 seconds; full sidecar and the CI diagnostic scripts in a read-only clean clone.
- Clean Docker image including React TypeScript/Vite build passed. Schema/example, legacy JavaScript syntax and asset contract passed. Rust is unchanged and was not rerun on this Mac.
- Independent immutable review found one P2 custom-provider routing regression, fixed in 45bdd40. Final review: no blockers, 90 focused tests and three additional selected-provider integration checks passed. Reviewer did not certify model quality, platform suites or deployment.
- Real HTTP/model/restart/withdrawal acceptance passed on isolated synthetic data.

[Raw synthetic measurements and reproduction](../evaluations/memory-quality/runs/2026-09-20-bounded-selection/README.md): median 26.630 → 1.158 seconds across seven model-call pairs, all eight displayed answers identical. Broader 16-case diagnostic completed without technical/format failure. Development measurements do not qualify broad semantic relevance; retrieval, extraction, large-store coverage and multi-day usefulness remain open as detailed in the preceding everyday acceptance record.

No personal data or secrets are included in these artifacts. Merge and private-app deployment are recorded separately after verification.
