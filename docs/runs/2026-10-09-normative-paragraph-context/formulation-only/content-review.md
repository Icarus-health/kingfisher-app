# Independent content review — paragraph formulation controls

Reviewed the frozen six-question run against its synthetic original-source catalog. This is a fixed-source formulation check only; it says nothing about retrieval, indexing, intake, or general memory quality.

## Frozen evidence

- Product/source commit: `e8cfc26d5aee8ef42a6206da4ffa02a3bbced966`; archive SHA-256: `ca15ecbd7b917a698d7c6f3193623e8b3e7ffd68b296420e6b46da70e8a6d830`.
- `catalog.json` SHA-256: `4eaed5adeab90bd5e15206d4563bd24b962b791defdc46168d4ad8dfff632242`.
- `answers.json` SHA-256: `dd39cf6833d6f0e98d7532c2e70ca5eda60a9184cdf9b83f8acd9ebdcb7ec29d`; it binds the same catalog digest and is marked completed.
- `runtime.json` SHA-256: `2e0783f65a5006efb317a5c05a1225cd2df46cd3586cf3202d22cd77ea6d6bc4`.

## Content findings

- **L01 — adequate.** The accepted sentence reproduces both the opening permission and its exclusive condition: written approval by the plant manager.
- **L02 — adequate.** The accepted text includes the historical-draft heading, the signal condition, and that the draft was never approved. It does not turn the draft into a current authorized rule.
- **S01 — adequate.** The answer directly gives the condition “after the inspection.”
- **F01 — adequate and focused.** The answer says the report is in the safe. The adjacent key location is outside the question and its omission is not misleading.
- **H01 — no accepted prose; safe fallback path, not a successful direct answer.** The model returned two sentence IDs for a paragraph that must remain atomic; formulation fell back with `Modell ohne brauchbare Ausgabe (ValueError)`. The source states the flap may be opened only during the inspection. The saved artifact does not establish that the user-facing quote renderer displayed that condition, so quote usability remains unverified.
- **C01 — no accepted prose; safe fallback path, not a successful direct answer.** The model likewise returned two sentence IDs and triggered the same fallback. The source’s condition is exclusive written approval. The actual user-facing quote display is unverified here.

Accounting: 4 adequate accepted sentence answers, 2 safe non-answer fallbacks, 0 accepted answers with an unsupported condition or lost historical-status qualifier. Do not count the two fallback rows as answer successes.

## Run and limits

The run records `completed=true`, client and server exit codes `0`, and no watchdog stop. It used an isolated real blob directory (not a symlink), `OLLAMA_NO_CLOUD=1`, and `OLLAMA_NOPRUNE=1`; preflight records distinct source/clone inodes and matching layer hashes. The four native source blobs are recorded unchanged by SHA-256 and metadata after the run. This is consistent with successful cleanup in the saved runtime evidence.

Generation and the second gate both used `qwen3.5:4b`; the second gate’s “ja” is therefore not an independent truth check. The result is a narrow synthetic formulation outcome, not a claim that the product is generally reliable or that the quote UI was verified.
