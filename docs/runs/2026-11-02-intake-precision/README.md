# Intake precision — 2026-11-02

Tested product commit: `3b0413c`. Branch: `feat/modular-cos-20261102`.

The repair preserves optional task attributes, distinguishes communication constraints from actionable requests, and guides both category prompt paths by substantive content. Existing originals and saved proposals are not rewritten; acceptance still checks current evidence.

Independent review of `0378b77` found four important boundary/probe defects. Ten red tests reproduced them. The final fix pass passed 167 affected tests. Full final sidecar regression: **9,324 passed, 1 skipped, 26 subtests passed** in 1,325.60 seconds; one Starlette deprecation warning.

The real local probe used the existing `kingfisher-qwen3.5:9b-8k`, digest `8a5919e3ddda74b7729b65ca0bad9896d36615d872756ca98b17ec8a80374b17`, 8K context, seven artificial mails, 19 calls, 166.243 seconds. All seven person, task and deadline checks passed; all original texts remained unchanged. **Only six of seven category checks passed**: `explicit-deadline` omitted the additional personal category. This remains a failed overall quality gate, not a waived expectation. Model retention cleanup also logged warnings; no claim of complete load control follows from this run.

Dataset SHA-256: `5d1d15390f03db316d534d5fa339c7f7f04a3678b7839810ecbbac137db8aadc`. Run the documented probe script to reproduce; fixture-injected tests explicitly do not count as live model verification. No personal store was opened, no paid calls were made, and model roles were not changed.

The large import remains paused. This repair is not proof of universal semantic correctness or completion of the modular CoS objective.

## Separate Harness compatibility experiment

Official `@deepseek-ai/dsh-sdk-client`, `dsh-llm-pi-ai` and `dsh-mcp-client` version `0.2.2-alpha.2` were installed separately with scripts disabled and a locked dependency tree, using a separately verified portable Node 24.22.2. The reviewed upstream source was `ce7073d51254c26cd63b22a60835b8f948deb447`; published npm metadata does not prove binary/source correspondence.

Default shell/filesystem/working-directory tools and DeepSeek session-log/package-inventory uploads were disabled explicitly. A clean environment, artificial-only scratch home, bounded lifetime and local model endpoint were used. Both a simulated model and the real local Qwen completed MCP search → artificial source S1 → answer. Two protocol mismatches required a lossless text-block normalizer and normalization of null assistant content accompanying tool calls. No personal source or application token was supplied.

The MCP server returned one fixed artificial source, regardless of query: this proves protocol compatibility, **not retrieval quality**. The SDK also exposes three configured-server resource helpers, which were explicitly inventoried. A stronger macOS process sandbox did not start Node successfully; **OS isolation is not verified**. This experiment therefore does not authorize personal-data access or production activation. Next: scoped Kingfisher capabilities, freshness and revocation tests, then actual isolated source retrieval.
