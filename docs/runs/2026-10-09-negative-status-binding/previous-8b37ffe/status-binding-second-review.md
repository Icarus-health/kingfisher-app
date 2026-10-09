# Revised status-binding prototype review

Reviewed prototype `satzpruefung.py` SHA-256 `fef7b03cafd574762f25985b1c7ca52319b39e6202c4053d777d337830bcb3fc` against product commit `0911e4cac1cdd1115d2fa1b1d26f8232debfea8f`. I checked the revised 15-negative/9-positive scratch cases and ran bounded synthetic probes only; no source edit or broad suite run.

The four previously reported cases are closed in their tested forms: explicit mismatched IDs and names are excluded; tied candidates with different explicit identities and an unqualified answer fail closed; colon-prefixed IDs stay with their status clause; and `_KENNUNG` casefolding accepts `z-204` versus `Z-204`. The exact rule-plus-negative-status original remains among the positive controls. This is a bounded lexical/status check, not general semantic interpretation.

## Remaining concrete false accepts

- **Two independently identified subjects in one coordinated clause can swap statuses and pass.** Source: `Die Rechnung R-719 ist bezahlt und die Rechnung R-720 ist offen.` Answer: `Die Rechnung R-719 ist offen und die Rechnung R-720 ist bezahlt.` The prototype returns `bestanden=True`: `_status_abschnitte` does not split `und`, the whole unit has the same two-ID set, and the union of statuses contains both requested groups. This is a direct status-to-ID binding hole. A narrow remedy is to check each repeated-ID/name coordinated segment separately; preserve one-subject coordination such as `Die Rechnung ist bezahlt und unterschrieben` when only one identity is present.
- **An untagged competing source unit can still donate/conflict.** `Die Rechnung ist bezahlt.` citing `Die Rechnung R-719 wurde bezahlt.` and `Die Rechnung ist noch offen.` returns `bestanden=True`. The ambiguity check counts distinct nonempty ID sets only (`if ids`), so the untagged open unit is ignored; the union still contains `bezahlt`. Treat a tied, lexically relevant untagged unit as unresolved when another best candidate has an ID/name and statuses differ or conflict; fail closed rather than assuming they refer to the same record.

Related same-identity conflict: if two strongest units explicitly bind the same ID but state opposite statuses, the union contains the answer’s group and the current loop skips the contrary group. For example, `R-719 wurde bezahlt.` plus `R-719 ist noch offen.` still supports `R-719 wurde bezahlt.`. If conflicting current records are expected to stay ambiguous, reject when a strongest same-identity set contains both the requested group and its opposite.

Updated scratch hash: `6c22064b5c95b864464cbdb7c8f80e12a6765b16551c5a41c7ea75255218c98c`. No network, model, UI, or private data used.
