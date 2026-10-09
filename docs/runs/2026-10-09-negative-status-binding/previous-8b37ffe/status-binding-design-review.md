# Conservative status-donation fix design

**Recommendation:** make status support subject-scoped. A status word anywhere in the cited pool must not authorize that status for every cited subject. Keep the change inside status validation; do not alter permission, negation, date, source-validity, or second-gate logic.

The current mismatch has two parts: the general status-presence check compares against the union of all cited status words, while `_gegenstatus` only rejects an opposite status found in the best lexical-overlap source unit. If that best unit has no recognized status, an unrelated source can donate a status through the union. `_inhaltswoerter` strips answer status stems for overlap, but `_KENNUNG` and `_namensfolgen` are currently validated/pool-wide, not bound to a status unit.

For each status-bearing answer sentence or bounded clause, compute the relevant cited source units using the existing subject-word overlap, with status words excluded on both sides. Before scoring, reject a candidate unit as a subject match when it has an explicit identifier or proper-name identity disjoint from the answer unit. Use `_KENNUNG` for exact tokens such as `Z-204` and `R-719`; use `_namensfolgen` for proper names. If the answer and candidate both carry explicit IDs/names, a mismatch must never be rescued by a shared generic noun such as “Lieferung” or “Rechnung”. If identity is absent or cannot be associated confidently, retain the current lexical path only for unambiguous matches; otherwise fail closed to quotes.

At the strongest remaining subject match, require the answer’s status group to be present. Preserve the current opposite-status rejection, including ties: a tied source unit that says the opposite still rejects. If the strongest subject unit has no recognized status, do not borrow one from a different subject/source merely because the group occurs elsewhere in `_pool`. A source-level ID/name from the title can identify its clauses, but do not propagate arbitrary title text as status evidence. Do not infer status through an unresolved pronoun or across unrelated clauses; return an unsupported/ambiguous status reason instead.

Use the existing clause and sentence boundaries for status-bearing answer units and cited source units so two statuses in a paragraph remain independently attributable. Avoid treating a comma/semicolon or adjacent sentence as permission to transfer a subject or status. Keep the exact same-subject sentence positive (for example, an explicit “Zustimmung liegt noch nicht vor”), and preserve full normative paragraph validation separately. If a sentence contains multiple independent subjects/statuses that cannot be safely segmented or bound, fail closed rather than unioning their identities.

Counterexamples to reject:

- `Die Lieferung Z-204 wurde bezahlt.` citing `Die Rechnung R-719 wurde bezahlt.` plus `Die Lieferung Z-204 wurde vorbereitet.` (reproduced accepted today).
- `Die Rechnung R-720 ist offen.` citing `Die Rechnung R-719 ist offen.` plus `Die Rechnung R-720 wurde erstellt.` Same kind, different IDs.
- `Mira Sander ist bezahlt.` citing a paid status for Anna Keller and a non-status source about Mira Sander. Names must not transfer the status.
- Opposite status for the same ID/name must continue to fail, even if another cited unit supports the answer’s status.

Positive controls:

- A status explicitly reported for the same ID/name passes; its opposite fails.
- Two subjects with different statuses in separate clauses/sentences pass when each status is stated for its own subject, in either order.
- The full rule-plus-status paragraph `Bei Z-204 darf die Lieferung erst nach schriftlicher Zustimmung versandt werden. Die Zustimmung liegt noch nicht vor.` remains valid as a faithful complete original; rule-only evidence still does not establish either fulfillment or non-fulfillment.
- Existing exact-negation, conditional-permission, and contradictory-source checks remain active; status binding cannot exempt a sentence from any of them.

The scratch file’s three negative cases are useful seeds, but add same-kind/different-ID and distinct-name cases plus the positive same-subject and mixed-status controls above. This is a design review only; no source edits, tests, full-suite run, network, model, UI, or private data access.
