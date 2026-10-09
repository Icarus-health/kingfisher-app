# Independent content review: final normative run

Frozen catalog SHA-256 `3db9c664ffbea385d291b7c4d2500ecd032502bd4f360ba7aa33c7239698fada` and flow SHA-256 `1797e42405390de693078d25c48fd4994cb05dd90877789c0dc1d88a9d1761f1` match 8b37. All 19 original UTF-8 source body hashes match the recorded intake hashes (HTTP 200); displayed references validate for all rows, with W02 correctly showing no source because the answer is unknown.

**Strict content grade: 14 adequate, 2 partial, 0 wrong.** The same strict 8b37 baseline is 14/2/0. Statuses and selected-source sets are unchanged. Nine row displays are byte-for-byte equal; the seven changed row hashes are listed in the JSON, including timestamp/framing changes and W05’s additional time-unclear badge. Selection flags were not used as correctness evidence.

| ID | Grade | Content assessment |
|---|---|---|
| IA01 | adequate | Correctly distinguishes the return/solvent rule from the dry-only cleaning rule before curing. The return sentence is extra but clearly scoped. |
| IA02 | adequate | S2 directly states that the surface must be dust-free before application and expressly ties it to the P-18 protective coating; it is sufficient for the asked prerequisite. |
| IA03 | adequate | Directly prohibits removal before acceptance and preserves permission only afterward. |
| IA04 | adequate | “Only during the running flushing process” answers yes for the asked interval and preserves the exclusive limit. |
| IA05 | partial | The battery may be replaced only after technical inspection, correctly. The answer also includes the unrelated pre-shipment seal-photo fact, contrary to the frozen instruction not to answer with that separate timing fact. This exact answer is unchanged from 8b37; it is not a new regression. |
| IA06 | adequate | Preserves room scope: room A is after-hours only, while room B may be opened during working hours for ventilation. |
| IA07 | adequate | Uses the current correction: calibration alone is insufficient and the device stays off until documented release. |
| IA08 | adequate | States the post-acceptance written-order condition, so it does not imply automatic permission. The archive sentence is extra but does not change the rule. |
| W01 | adequate | Correctly attaches below 8 °C to placing the sample in the cooler. The batch code appears as a separate, sourced label fact, not a prerequisite. |
| W02 | adequate | Returns unknown rather than inventing a prerequisite. The source describes storage but gives no permission condition. |
| W03 | adequate | Explicitly says the lid may not be removed before weighing and preserves the separate permission afterward. |
| W04 | partial | Quotes both relevant facts accurately: use only after the pressure test and actual use before it. The displayed answer still omits the requested conclusion that the trial use was not permitted. The same gap was present in 8b37. |
| W05 | adequate | Surfaces both same-dated contradictory instructions and does not choose a rule. Caveat: the time-unclear labels on both sources are noisy and may suggest a chronology explanation, although the displayed conflict statement is correct. |
| DE01 | adequate | Preserves the no-removal-before-completion rule and both later requirements: archive creation and checking. |
| DE02 | adequate | Preserves the pre-approval prohibition and the after-written-approval soft-brush method, without strengthening “not worked” into “not touched.” |
| DE03 | adequate | Prohibits removal before the night capture ends and preserves both later conditions: capture completed and optics covered. |

W04 remains incomplete: the displayed answer quotes the after-test rule and before-test use but does not state the requested conclusion that this use was impermissible. IA05 remains partial because it adds the unrelated pre-shipment seal-photo fact. Its full displayed answer hash is compared with 8b37 row by row; the wording is byte-for-byte unchanged, so this is not a new regression. W05 safely presents the conflict without selecting a rule; the time-unclear badges remain a presentation caveat.

After restart, all 16 displayed answers were unchanged and replayed byte-for-byte with zero provider calls. The withdrawal probe passed: status `working_unavailable`, zero provider calls, original text retained. Runtime reports completion, successful preflight, unchanged native blobs/manifests, no production endpoint touched, no settings/private directories loaded, and cloud/prune disabled. `production_memory_policy_verified` remains false; the run is synthetic-only.

Separate from this normative grade, the root-provided CoS review reports 8/9 entity matches with one NOA miss while the core 23 answers were adequate. That remains a bounded factual follow-up; no extra run was made.

The JSON contains all 19 raw body hashes and per-question final/prior display SHA-256 values, literal sources, frozen gold requirements, references, replay rows, and withdrawal fields.
