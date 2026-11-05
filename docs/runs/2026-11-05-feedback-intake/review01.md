### Spec Compliance

- ❌ **Issues found.** A projected answer that crosses the feedback cap inside its appended notice still exports a notice fragment as part of the forbidden assertion. This misses the substantive-answer requirement for a supported snapshot boundary. See I1.
- ✅ The ordinary authenticated conversation → feedback POST → readback → export path preserves the displayed answer and source ID, and the actual matcher recognizes it as coverage changes and clears. The test also checks that an ordinary report returns no learning result and that the synthetic provider received one call across the scenario. `sidecar/tests/test_rueckmeldung.py:275`.
- ✅ The single structured sentence keeps precedence. Legacy, mismatched, non-string and empty notice metadata preserve the text. The multiple-sentence test retains a genuine, identical notice-like paragraph and removes only the appended copy. `sidecar/icarus_memory/rueckmeldung_faelle.py:42`, `sidecar/tests/test_rueckmeldung.py:113`, `sidecar/tests/test_rueckmeldung.py:122`, `sidecar/tests/test_rueckmeldung.py:131`.
- ✅ The change stays in the two authorized product files and the existing focused test file. It uses the existing snapshot column and request fields. The write still uses the projected message for text, structure and provenance. The learning calls remain conditional on explicit opt-in. No added provider or network call appears in the delta. `sidecar/icarus_memory/rueckmeldung_routes.py:29`, `:94`, `:110`, `:121`, `sidecar/icarus_memory/rueckmeldung.py:141`.
- ⚠️ Source withdrawal and active-skill transitions remain controlled by unchanged projection and learning internals. The route and opt-in boundary are visible, and the author reports affected learning suites, but the new roundtrip does not withdraw a source or exercise an opted-in promotion. Broader P2 acceptance, native behavior, live model quality and release state cannot be established from this task snapshot.

### Strengths

- The final `removesuffix` is literal, operates once and leaves the persisted displayed answer intact. The implementation separates reporting from export and avoids heuristic stripping. `sidecar/icarus_memory/rueckmeldung_routes.py:111`, `sidecar/icarus_memory/rueckmeldung_faelle.py:48`.
- The real authenticated path includes an exact comparison of the substantive answer across three intake states and checks the exported assertion with the production matcher. The RED log fails on the changed notice as claimed, and the GREEN log reports 94 passed. `sidecar/tests/test_rueckmeldung.py:275`, `feedback-intake-report.md:44`.

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

- **I1. The storage cap can leave a transient notice fragment in the regression case.** `sidecar/icarus_memory/rueckmeldung_routes.py:64` records no notice metadata whenever the full projected answer exceeds `MAX_ANTWORT`. The store strips and slices the displayed answer to 20,000 characters (`sidecar/icarus_memory/rueckmeldung.py:39`, `:135`, `:145`). With 19,970 characters of substantive text and an appended server notice, this keeps the complete substantive answer plus the first 30 characters of the transient suffix, including notice wording. The fallback in `sidecar/icarus_memory/rueckmeldung_faelle.py:48` exports the whole clipped snapshot, so the same substantive text after the notice clears fails the literal match. The existing cap test (`sidecar/tests/test_rueckmeldung.py:143`) clips before the real suffix and correctly protects a genuine lookalike at the cut. Keep that test and add the complementary cut-inside case. Derive the portion of the trusted suffix that actually enters the capped snapshot only after checking that the complete server notice is the exact suffix of the original projection. Remove only that verified portion from the regression assertion, preserving snapshot text, the single-sentence rule and the legacy fallback.

#### Minor (Nice to Have)

- **M1. Test output contains one existing dependency warning.** Both recorded runs emit Starlette's `httpx` TestClient deprecation warning. The warning is attributed to the pre-existing TestClient import in `sidecar/tests/test_rueckmeldung.py:7` and is documented in `feedback-intake-report.md:45`. Treat dependency cleanup separately from the scoped repair.

### Focused Checks

- **Snapshot boundary and repeat reporting.** Read only the relevant storage constant and `melden` write in `sidecar/icarus_memory/rueckmeldung.py:39` and `:129`. The store trims before slicing, and its conflict update keeps the first answer and structure together.
- **Metadata provenance and projection authority.** Checked the notice producer and the paired content/metadata append in `sidecar/icarus_memory/server.py:4265` and `:4494`. Read the omitted start of the feedback handler from the frozen file because the route hunk begins mid-handler. `sidecar/icarus_memory/rueckmeldung_routes.py:94` confirms feedback selects the assistant message from `gespraech_ansicht`.
- **Evidence.** Read the existing RED and GREEN log tails. No author suite was rerun. Review scope was base `6731dd5faf24b0d829a9054143e025d473309ae6` to the three-file review01 snapshot with controller-verified hashes.

### Assessment

**Task quality:** Needs fixes.

**Reasoning:** The ordinary regression is reproduced and repaired with a small, well-tested export change. The cap can still preserve a fragment of the transient notice in the forbidden assertion and recreate the same matching failure.
