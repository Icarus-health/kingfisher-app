# Independent synthetic working-memory qualification

The [expected cases](expected.json) were written before the single local-model run. The [results](results.json) retain all 20 raw model JSON responses, selected source IDs, rendered answers, and per-call latencies. This is a small semantic spot check, not broad product qualification. It used 12 synthetic sources, 8 questions, temporary EpisodeStore and ClaimStore databases, and local `qwen3.5:4b` through `http://127.0.0.1:11434/v1`.

Seven of eight questions received the expected evidence and uncertainty decision. One failed: two distinct people named Nora Beck, identified by different email and street addresses, were treated as conflicting reports about one transaction. The model selected both appropriate sources but returned `{"status":"conflict","ids":["S1","S2"]}`. The rendered answer asked, **“Die Quellen enthalten unterschiedliche Angaben. Welche gilt für deinen Vorgang?”** The needed question is which Nora Beck the user means. This is a wrong person binding and a wrong clarification type. It did not silently choose one date.

| Case | Independent judgment | Evidence |
| --- | --- | --- |
| Q01 same name, different addresses | **Fail: wrong person binding** | Both sources selected; conflict clarification instead of person clarification. |
| Q02 address disambiguates name | Pass | Parkstraße 8 source alone; 6 October; no clarification. |
| Q03 request versus own promise | Pass, indirect wording | Elias's request labeled `Bitte`; no commitment claimed. The rendered response only quotes and labels the source rather than saying “No promise is evidenced.” |
| Q04 condition in another paragraph | Pass | Whole conditional source selected and labeled `Bedingte Aussage`; laboratory clearance remains visible. |
| Q05 quoted old mail and current cancellation | Pass | Old text classified `historical`, current text `status`; rendered answer includes current cancellation. |
| Q06 same author explicitly changes deadline | Pass | Correction source selected, current date 19 October; no conflict clarification. |
| Q07 sent offer without acceptance | Pass | Source states no reply or acceptance; no agreement inferred. |
| Q08 relative date with unknown source time | Pass, vague clarification | `time` uncertainty and unknown source time preserved. The generic “Welcher Zeitpunkt ist für diese Frage gemeint?” does not identify the missing source timestamp. |

All 12 sources were classified and committed; all 8 questions were prepared and rendered. There were no missed relevant sources, no unnecessary clarifications, and no fabricated acceptance or resolved relative date in this corpus. Total measured model call time was 38.402 seconds across 20 calls; this excludes other product overhead. The corpus is synthetic and deliberately narrow, so these counts should not be extrapolated to real mail quality or end-to-end user usefulness.
