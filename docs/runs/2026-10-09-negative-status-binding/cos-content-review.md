# Independent content review: status CoS run 7295b2e

## Verdict

All 23 displayed answers are adequate against the literal sources. The correct source mapping and reference flags are present on all 23 rows. This includes the quote fallbacks: RQ02 identifies Nora Voss, RQ05–06 quote the M-731 requirement and explicit missing approval, RQ10–11 show the replacement and original Epsilon dates, and RQ15 says the Depot Nord induction remains planned. RQ08 and RQ11 present items in reverse order from the question, but their source titles and cited IDs make the mapping clear. The four unknown answers are correct abstentions against the literal source set.

One requested count does not match the frozen catalog: it has **19 answerable questions and 4 unanswerable questions**, not 20 and 3. RQ04 (“Wer prüft die Ware im Auftrag KL-24?”) is marked unanswerable with no gold source. RCS02 says Nola Voss delivers the fastening kits; it does not say who inspects the goods. Its unknown answer is therefore correct. The other three unanswerables are RQ16–RQ18.

The 23 displayed answer strings match run 8b37 in substance. Six quote-fallback strings differ only in their captured-at time (10:38 vs 11:08). RQ06 remains adequate: its displayed M-731 source paragraph explicitly says “Die Freigabe liegt noch nicht vor.” This remains a source-quote fallback rather than a generated paraphrase.

## Person extraction and source identity

The nine-source `person_gold` diagnostic is **8/9 exact** in this run. RCS09’s raw source says “Noa Jansen bat um einen höhenverstellbaren Bildschirmständer für den Arbeitsplatz,” but the model returned an empty person-entity list. Run 8b37 extracted Noa Jansen from the same frozen source, so this is a regression in the extraction diagnostic. It does not change RQ16’s answer: the source contains no diagnosis, and the answer correctly abstains.

All 14 catalog source bodies and all 4 holdout bodies match their imported episode originals byte-for-byte; all 18 stored source digests match the body SHA-256. Each answer’s displayed/cited records map to the selected expected source IDs; all 23 `references_valid` and `exact_sources` flags are true. The complete per-row content, source-body verification, and person checks are in `independent-content-review.json`.

Catalog SHA-256: `857965be8e845fde716e5d22d94d5310f5011058db68a4b7107abae1e10e465a` (same as 8b37). Holdout SHA-256: `34c2880b1bce144af3486c4b4971f8b42dfa2cc8c2b034c651efcbbafabfa594`. Answers SHA-256: `729614e2ae6cd3842929e62ce28538d66fefa4acf603921cbfa0f4f8346114ed`. Runner SHA-256: `b5724ea6bd6cc845682257c7893e60d9ceb83448d6b5a2ecdf974c293677f0cd`.

The run metadata records completion with client/server exit 0 and unchanged native model blobs/manifests. This review covers only this finite synthetic run and does not establish general accuracy or production behavior.
