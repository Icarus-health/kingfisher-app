# Independent review: missing deadline explanation

Final reviewed head: `ac8087568b3f2bfdd6daf2eabf2ec6260509f9f0`, against base `edd5fcb`. Delta-only review of the public selector/render changes, synthetic tests and short plan, including resolution of findings on superseded head `3bd7634`. No private artifacts, services, network or models accessed. No repository edits.

## Assessment

**No remaining actionable correctness findings in the scoped final diff.** The prior query-scope bug and relative-time instruction ambiguity are resolved. The change is suitable to proceed to bounded model acceptance; these synthetic checks do not establish actual model compliance or equivalence.

The deadline classifier is removed entirely. All unknown answers now say `Die erfragte Angabe konnte ich in den geprüften Quellen nicht belegen.` This expresses missing evidence without guessing the requested field or claiming that the archive contains no information. The added reason/duration/indirect-author/call-window countercases therefore receive appropriate query-neutral wording. The existing exact-copy test update reflects the intended wording change without weakening its status contract.

The renderer preserves the existing freshness gate, confirmed-claim fallback, coverage notices, `working_unknown` status and empty links. It does not promote unselected candidates. Conditional positive reports retain the original wording and source link, and source withdrawal still invalidates the saved unknown explanation.

## Source-linked dates and relative time

The selector now distinguishes an unrelated date field from a date explicitly linked to the requested deadline: `Ohne ausdrücklichen Fristbezug ersetzt ein anderes Datumsfeld keine Rücksende-/Abgabefrist.` This permits a source-defined deadline tied to an employment start while prohibiting silent substitution of an unrelated start date.

An additional focused real-store/scripted-selection check used `Bitte den Erfassungsbogen spätestens zum Beschäftigungsbeginn am 09.12.2026 zurücksenden.` For the return-deadline question it retained the complete original, the same source reference/link and `working_reports`. This verifies downstream preservation when selected; it does not prove a model will identify the link correctly.

The explicit sentence `Ein nötiger fehlender relativer Zeitbezug verlangt weiterhin needs_missing_time_reference.` preserves the existing status rule for a requested concrete date whose relative deadline lacks a necessary reference. It resolves the earlier conflict with the general permission to report conditional timing evidence.

## Verification and limits

- Independently ran only `test_missing_deadline_explanations.py` and `test_source_selection_pages.py` at the final head: **51 passed in 2.95s**.
- Additional scripted synthetic source-linked employment-start deadline check passed.
- `git diff --check edd5fcb..ac80875` is clean; exact HEAD verified.
- Selector instruction grows from 3,923 to 4,349 UTF-8 bytes: **+426 bytes**, or **+427 bytes within JSON serialization**, on each selector request. Candidate/page/deadline/context limits are unchanged, and the existing native-budget paging regression passes. Near-boundary real requests may still need another page or fail the existing limits.
- All selection decisions in these new tests are scripted. Actual acceptance must still distinguish unrelated versus explicitly linked dates and preserve time clarification for relative deadlines with missing reference. No claim about a private pilot, actual model behavior or broader regression suite is made here.
