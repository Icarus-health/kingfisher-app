# M2b: Preserve canonical entity identity in actual model context

After M1b and indexed lexical retrieval, before attributing same-name failures solely
to a model or tuning its prompt. Use superpowers:subagent-driven-development.

## Observed gap

The same-name development fixture stores two distinct canonical person references.
Actual Agent input contains source text and source IDs but omits subject_ref,
target_ref and scope_ref. The source-only reference mode also omits fixture entity
identities. A correct source recall metric therefore does not certify complete
identity context. Missing clarification is still an answer-contract defect, but the
baseline does not isolate model behavior with explicit distinct entity metadata.

## Bounded change

Preserve already-authoritative claim entity references in ContextItem metadata and
actual rendered local knowledge context. Include stable subject/target/scope references
exactly as recorded in the immutable claim. No extra registry labels are required: the
existing statement supplies human-readable wording, while stable references establish
identity. This avoids adding untracked mutable label dependencies to history. Do not
infer new identities, aliases, relationships, groups or merges.
Only attach metadata of the same claims whose evidence chain passed validation.
Names/source text remain untrusted data, encoded as data rather than instructions.
No additional private context may be sent to external providers.

Two claims with different subject references must remain distinguishable despite
identical labels. Distinct IDs mean distinct unmerged records, not proof of two
different real humans; duplicates are possible. Preserve uncertainty and clarify
rather than asserting real-world distinctness or merging. Two claims with the same reference must not be presented as different
people merely because they have two source IDs or addresses. No automatic rejection of
legitimate multiple roles/addresses; the model must have the actual identity distinction.
Expose enough provenance for UI/source inspection without adding an entire new CRM.

Update the synthetic diagnostic reference path to optionally include declared fixture
entity/claim mappings strictly restricted to permitted delivered sources/claims. Do not
leak excluded mapping metadata through the diagnostic reference path. Version the
diagnostic mode/difference, preserve all previous raw
results; compare old source-only and new identity-bearing context explicitly. Do not
quietly redefine previous baseline results as fully specified identity reference runs.
Keep bidirectional actual-payload attribution tests, including forbidden/unreported
source detection, compatible with the new rendered fields.

## Acceptance

- [ ] Actual provider input distinguishes same-label different-person references.
- [ ] Same canonical person with two addresses/roles remains one identity.
- [ ] Scope/target is preserved as recorded; absent relationships are not invented.
- [ ] Ignored/retracted/expired/invalid evidence still removes accompanying identity data.
- [ ] Source wording containing instructions remains encoded data and cannot change rights.
- [ ] Offline recorder validates actual declared payload; old raw baseline unchanged.
- [ ] Small local-model diagnostic follows deterministic input assertions; no model
      qualification merely because IDs appear. Independent review and supported suites.

No semantic graph expansion, automatic identity merge or claim of complete person
resolution. This repairs loss of existing structure on the way to the model.
