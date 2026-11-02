# Scoped Harness bridge — 2026-11-02

The bridge is experimental and **not registered on the personal server**. It does not enable a competing memory, a global MCP door, a cloud fallback or personal-data execution.

Controller-created grants last at most 120 seconds, cover at most 20 selected originals and allow eight read-only tool calls / three local model calls. Every read and final model result rechecks source eligibility, fingerprints, confirmed skill versions and new selection conflicts. Revocation and cancellation withhold old context. The original request selects confirmed skills automatically; worker arguments cannot change that selection.

The standalone protocol supports literal source discovery, excerpts of already discovered sources, and current skills. General resources, file/shell tools and writes are denied. Text normalization preserves all supported content and keeps historical JSON arguments intact until the normal provider conversion. The pinned upstream SDK dependency tree is in `integrations/harness`; installation scripts must remain disabled.

Independent review of `d92bef9` reproduced three important defects: a current non-original observation could be mislabeled as evidence, malformed nested JSON types could escape validation, and forced termination left the token-bearing temporary home. Six red regressions reproduced these issues. The final repair uses the existing original-evidence eligibility gate, checks scalar types before membership, and lets the parent own and clean the isolated temporary directory after process-group termination.

Final affected regression: **198 passed** in 31.49 seconds, one existing Starlette deprecation warning. The live local probe after the fixes used the existing Qwen9B/8K profile and unchanged artificial originals, completed in **22.138 seconds**, selected the confirmed test skill automatically, searched the actual scoped store and excluded the ungranted distractor. Its answer was inspected against the original: “Die Zugangskarte liegt in Fach A42.” followed by the correct source ID.

The automated oracle checks token/source presence, scope and immutability; it is a smoke check, not a general semantic judge. The actual sentence requires review before asserting quality. Model retention cleanup still logged a warning. No paid or personal-source calls were made. The intake extra-category failure remains open and the bulk import remains paused.

## Reproduction

Use Node 24.22.2 and the exact locked SDK 0.2.2-alpha.2 tree, installed with `npm ci --ignore-scripts` in a separate directory. The probe requires an already installed local `kingfisher-qwen3.5:9b-8k`; it never downloads a model.

```sh
PYTHONPATH=sidecar:.:scripts python scripts/probe_harness_memory.py \
  --node /absolute/path/to/node \
  --runtime /absolute/path/to/pinned-sdk-install \
  --output /absolute/path/to/new-artificial-report.json
```

The subprocess profile is not OS isolation. A stronger Mac process sandbox failed its startup experiment. **Production activation requires a separate verified isolation and packaging delivery**, plus normal backup/update and native Mac acceptance. Nothing here establishes that this larger objective is complete.
