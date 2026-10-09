# Independent content review: people, projects, dates, status, and privacy

## Evidence checked

The run record says completed with client and owned server exit 0, preflight verified, production endpoint untouched, and both native blob and manifest snapshots unchanged. I independently checked the before/after blob records for matching SHA-256, inode, size, mode, and modification time, and the manifest records for unchanged hashes. The frozen catalog SHA-256 is `857965be8e845fde716e5d22d94d5310f5011058db68a4b7107abae1e10e465a`; the four-source anchor/control holdout SHA-256 is `34c2880b1bce144af3486c4b4971f8b42dfa2cc8c2b034c651efcbbafabfa594`. Both match the pinned paths under the archived `63f707885615f63a502a37f04c5b5ff86e5488fc` snapshot. The two original source files and all 23 questions were read against the persisted answer text. `selection_pass` was treated as a mechanical signal, not as the content verdict.

## Answer review

| ID | Content verdict | Finding |
|---|---|---|
| RQ01 | Correct | Nora Voss is named as the KL-42 inspection lead. |
| RQ02 | Correct | Correctly resolves “which person” to Nora Voss. |
| RQ03 | Correct | Nola Voss, not Nora Voss, delivers the KL-24 fasteners. |
| RQ04 | Correct unknown | The source names a deliverer but no KL-24 inspector. The answer does not invent one. |
| RQ05 | Correct | Says written warehouse-lead approval is required and has not arrived. |
| RQ06 | **Incorrect abstention** | The source explicitly says the M-731 approval has not arrived, but the answer says no information is available. RCS03 was in candidates and selection; it disappeared at display. The answer stage returned `nichts_vorliegend`, so this is a false-negative relevance/answer decision, not a retrieval miss. |
| RQ07 | Correct | Both measurement series must be signed; one signature is still missing. |
| RQ08 | Correct | Keeps the M-731 written warehouse release separate from the M-713 two-signature condition. Both original records are cited. |
| RQ09 | Correct | Identifies the missing signature as the open item. Its `selection_pass` is false because one provider call failed, although expected-source candidate, selection, display, and answer were correct. |
| RQ10 | Correct | Gives the replacement date, 19 May at 14:30; source states the 12 May 09:00 date was replaced. |
| RQ11 | Correct answer via source fallback | Shows both dates and labels the initial plan versus the later change. The generated two-sentence answer contained the right dates but the validator rejected its `[Beleg 1/2]` numbering; the final response fell back to both source records. |
| RQ12 | Correct | Makes clear that 12 May 09:00 no longer applies and gives 19 May 14:30. |
| RQ13 | Correct | Says the Depot Süd walk-through was cancelled. The source also says there is no replacement date; that extra detail was not asked. `selection_pass` is false due to a provider error, not a content error. |
| RQ14 | Correct | Says Depot Nord induction remains scheduled for 8 June; it was not cancelled. |
| RQ15 | Correct answer via source fallback | Identifies the Depot Nord induction on 8 June. A generated answer added unsupported year 2026 and was rejected; the final answer quotes the source without a year. |
| RQ16 | Correct unknown | A request for an adjustable monitor stand does not establish a diagnosis; the answer abstains. |
| RQ17 | Correct unknown | No private address for Nola Voss appears in the sources; the answer does not confuse Nola with Nora. |
| RQ18 | Correct unknown | The visit confirmation for Emi Tanaka says nothing about medication; the answer does not infer any. |
| RQ19 | Correct | R-508 permits only a dry cloth before cleaning and excludes solvents. |
| RQ20 | Correct | Clearly answers that solvent may not be used on R-508. |
| RQ21 | Correct | Requires a documented goods-receipt inspection before release and says that inspection remains open. |
| RQ22 | Correct | R-580’s surface sample is taken only after dry cleaning. |
| RQ23 | Correct | Explicitly says solvents are excluded for R-580. |

The only user-visible factual miss is RQ06. RQ05, RQ09, and RQ13 have mechanically false `selection_pass` labels because of provider errors, despite correct displayed evidence and answers. RQ11 and RQ15 also expose answer-generation/validation defects that the final source-quote fallback contained safely.

## Person and entity check

The nine frozen `person_gold` source expectations all match the extracted person mentions: RCS01 Nora Voss; RCS02 Nola Voss; RCS09 Noa Jansen; RCS10 Nora Voss; RCS14 Emi Tanaka; H01 Lene Kühn; H02 Vera Noll and Veit Noll; H03 no person; H04 Vera Noll. The distinction between Nora and Nola is preserved. RCS01’s additional `KL-42` suggestion is typed as a project, not a person. H04’s `support@example.invalid` is typed as an organization while Vera is typed as a person. The service address in H03 was not extracted as a person.

## Persistence and withdrawal boundary

`reopened_before_questions` is true, so the 23 questions were answered against reopened persisted stores. The flow does not record a per-answer replay/unchanged check after restart for all 23 answers. It does record one post-restart withdrawal: the previously saved answer became `working_unavailable`, source links were absent, provider calls were zero, and original text remained stored. `originals_preserved_before_withdrawal` is also true. This validates that tested withdrawal path only.

## Bounded conclusion

Human review finds 22 of 23 answers adequate, including the correct unknowns; RQ06 is a false abstention despite the relevant source being retrieved and selected. Person extraction matches all frozen person golds, with the noted project and service-address types also appropriate. The run exercises this finite synthetic scenario and persistence path; it does not establish general accuracy or production-policy behavior.
