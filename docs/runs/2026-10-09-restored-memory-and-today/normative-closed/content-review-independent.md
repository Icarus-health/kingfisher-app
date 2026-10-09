# Independent content review: closed synthetic memory run

Reviewed the frozen `catalog.json` against all 16 user questions and the corresponding persisted answers in `answers.json`. This is a manual source-grounding review; I did not use `selection_pass` as a correctness signal. I did not edit the catalog, answers, product, or tests.

## Question-by-question findings

| ID | Finding | Source-grounded assessment |
|---|---|---|
| IA01 | Sufficient | Correctly preserves the dry-only rule for cleaning before curing. The separate solvent rule is visibly scoped to return, so it is not transferred to cleaning. |
| IA02 | Sufficient; reference-set caveat | The cited S2 itself says the surface must be dust-free before application and expressly applies that condition to P-18’s protective coating. S1 gives the application action but adds no prerequisite. S2 alone answers the question correctly, though citing both sources would give fuller context. |
| IA03 | Sufficient | Correctly says the cover may not be removed before acceptance and may be removed afterward. |
| IA04 | Sufficient | “Only during the ongoing flush” answers yes for the asked interval and retains the exclusive limit. |
| IA05 | Correct with irrelevant extra fact | The replacement rule is correctly stated as exclusively after technical inspection. The pre-shipment seal-photography fact is true in S1 but unrelated to the question and adds distraction. |
| IA06 | Sufficient | Correctly distinguishes room B’s during-work ventilation permission from room A’s after-hours restriction. |
| IA07 | Sufficient | Correctly follows the March 5 correction over the March 3 start rule: calibration alone is insufficient and the device stays off pending documented approval. A direct “No” would make the response clearer. |
| IA08 | Sufficient | The quoted source makes clear that post-acceptance reset is not automatic and requires the duty technician’s written order. It also includes an unrelated protocol-archiving sentence. |
| W01 | Correct with irrelevant extra fact | Correctly gives the strict under-8 °C condition. The batch code 731 is true in S1 but unrelated and could be mistaken for a condition. |
| W02 | Correct unknown | The source only says the part is stored in the metal cabinet; it gives no prerequisite or permission rule. The answer appropriately limits its claim to information in the sources processed so far. |
| W03 | Sufficient | Correctly says no before weighing and preserves the separate permission after weighing. |
| W04 | Incomplete | The quoted source facts are accurate and relevant, but the answer never draws the requested conclusion that the documented use was not permitted. This is the sole material answer gap. |
| W05 | Correct ambiguity | It presents both same-dated, directly conflicting instructions and does not choose a current rule without resolving evidence. The uncertainty is appropriate. |
| DE01 | Sufficient | Correctly preserves both parts of the rule: do not remove before archive completion; removal is allowed only after the archive has been created and checked. |
| DE02 | Sufficient | Correctly attaches the soft-brush method to written approval by the restorer and preserves the before-approval prohibition. |
| DE03 | Sufficient | Correctly answers no before the observation ends and retains both later conditions: the observation is complete and the optics are covered. |

## Cross-cutting observations

Across the 16 answers, I found no source-level factual reversal or unsupported operational rule. The main content defect is W04’s missing explicit conclusion. IA05 and W01 include unrelated but source-supported facts. IA02 is substantively complete despite citing only S2; S2 directly contains the applicable prerequisite. IA07 correctly uses the later correction, while W05 correctly leaves an unresolved conflict unresolved.

The repeated footer “Jeder Satz wurde zusätzlich von einem Prüfmodell gegen seine Belege geprüft” is a system-level assurance, not evidence supplied by the source documents. It should not be counted as proof of answer correctness; the manual judgments above are based on the source text itself.

The run record reports all 16 saved answers unchanged after restart with zero provider calls during retrieval. It also reports one post-restart withdrawal check: the affected answer became `working_unavailable`, source links disappeared, no provider call occurred, and original source text remained stored. This supports that tested case only; it does not establish withdrawal behavior for every answer path.

## Bounded conclusion

The run produced 15 answers that are sufficient for their questions (including one appropriately unknown answer and one appropriately ambiguous answer), with the relevance and citation caveats noted above, and one incomplete answer (W04). This is a successful synthetic exercise of the closed flow and persistence path, not a general accuracy guarantee or proof of production memory-policy behavior.
