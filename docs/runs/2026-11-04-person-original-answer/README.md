# Person answers through original statement selection

The artificial native Mac-window test found a gap after the previous six-case
person-selection probe had passed: selecting the correct school contact could
still produce a quote fallback, because Qwen reordered a personal statement.
The actor/source guard correctly rejected the paraphrase. It remains strict.

## Repair

- Ordinary personal evidence now uses the existing numbered original-statement
  selection. Kingfisher copies the selected complete source text; the source,
  freshness, identity and second-model checks remain mandatory.
- Email addresses and URLs no longer split at their internal punctuation.
  Offsets still address the unchanged original text.
- An explicit, validated clarification choice reaches sentence selection as a
  bounded referent label. It grants neither factual authority nor tool rights.
  Automatic matching is never described as user confirmation.
- A short dedicated selection prompt replaces conflicting free-text generation
  instructions. Its schema permits only actually offered source/statement pairs;
  the parser still rejects invented, duplicate or oversized selections.
- Marked namesakes and superseded evidence retain their existing framing path.
  An unrelated long personal statement stays visible without preventing a short
  supported answer. Selecting the long statement still fails the output limit.

## Frozen artificial sources

Two unrelated Alex Winter mailboxes are kept separate:

```text
Alex Winter <winter@alpha.example> — Kontakt Einkauf
Alex Winter aus dem Einkauf ist unter einkauf@example.invalid erreichbar.
Alex Winter hat zugesagt, den Angebotsvergleich bis zum 6. November 2026 an Sören zu liefern.

Alex Winter <winter@beta.example> — Kontakt Schule
Alex Winter an der Schule ist unter schule@example.invalid erreichbar.
Alex Winter hat zugesagt, den Stundenplan bis zum 13. November 2026 an Sören zu liefern.
```

The first question is deliberately negative and asks for clarification. The user
then selects the school mailbox. The same three API questions were retained
through the final correction; expected answers were not weakened.

## Failed probes and review

1. Native window: correct person/source, reordered contact sentence rejected.
2. Initial original selector: empty selection. Adding the explicit choice alone
   was insufficient; the inherited long prompt still returned nothing.
3. Controlled Qwen comparison: a short dedicated prompt selected the correct
   original for the unchanged negative question. A positive question was a
   separate diagnostic control, not a replacement acceptance case.
4. First API run stopped at 24% free memory under the unchanged 25% gate.
   After resource recovery, contact passed but the deadline failed: Qwen chose
   nonexistent pair `(2,2)` from a single source. The parser rejected it.
5. The final constrained-pair schema completed all three original questions.

Independent review found two important regressions in the initial patch:
namesake framing could not be expressed using original IDs, and an unrelated
long personal statement prevented any answer. Both were reproduced before a
bounded fix. Supplemental review of the choice forwarding and shortened prompt
found no Critical/Important issue. A separate final review of the schema addition
also found no Critical/Important issue: both new tests and additional offline
checks verified pair binding, type/additional-field restrictions and absence of
global schema mutation. Other providers' decoder compatibility was not tested.

The local scratch directory `/private/tmp/kf-product-window-20261104` retains
the earlier trace files, resource-stop and invalid-pair results alongside the
final result. Public evidence is condensed to artificial content and hashes.

## Verification and limits

- [538 affected tests passed](tests.json), 63.02 seconds, one existing
  Starlette/httpx warning. This is an 18-file affected suite, not the whole backend.
- [Real local API: 3/3 passed](results.json), with correct source-linked school
  contact, school deadline and purchasing deadline. Persisted responses were
  read back. Eleven completed Qwen calls, 24.439 seconds of model time.
- End-to-end case durations: 4.277, 10.044 and 11.303 seconds. Minimum free memory
  31%, maximum pressure level 2. These are short, warmed local measurements;
  they do not establish sustained Mac fluidity or broad latency percentiles.
- Before the final backend correction, the isolated native window verified
  clarification buttons, correct source opening, calendar navigation and an
  unsent draft surviving navigation. The Mac then locked. Final corrected answer
  rendering in that window and the ordinary installed application remain open.
- Sources were seeded deterministically; BGE was disabled in this narrow answer
  probe. Neither intake nor personal mail accuracy is established by these cases.
- No cloud call, production data change, other-app closure, import resume,
  normal-app update or release occurred. The model-based sentence check uses the
  same Qwen model; it is not an independent model endorsement.

Follow-up UI finding: the existing promise “Mit der Cloud geht es in wenigen
Sekunden” is not supported by this test. Track under P4 rather than enabling
cloud or changing unrelated UI in this repair.
