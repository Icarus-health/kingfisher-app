# Independent final review: confirmed-task mail-thread hints

Date: 2026-10-11. Read-only code review of the exact file hashes below. No product changes, independent test execution, model calls, network, live services or private data access. Implementer/root test results are separate evidence and are not claimed as reviewer-executed tests.

## Result

No remaining blocking correctness regression found within the requested scope. Earlier findings are closed in the reviewed code:

- Source classification uses the current EpisodeStore source, not the confirmed task's USER_STATED provenance. The permanent HTTP test accepts a real TaskCandidates proposal and then verifies its new exact-thread hint. Non-mail sources are excluded before the detailed mail-task cap.
- Exact account-scoped SELF/REPLY tokens expand transitively in both directions, including siblings and late-imported predecessors. Per-task token membership prevents unrelated batched tasks borrowing matches. Ignored and superseded sources are filtered on every SQL read.
- Shared SQLite VM work budget covers classification and all expansion hops. The progress handler is removed in finally. Classification interruption yields an explicit global coverage status; later search caps yield task-specific incomplete-review hints. This is not a hard wall-clock deadline.
- A hint states only that another message was captured after task creation. It does not infer current applicability, completion, cancellation, or responsibility. It does not write the task or invoke a provider. Source dates remain distinct from capture dates.
- originalOnly forces readOnly, prevents categories/relations mounting, and propagates through attachments and corrections. Both task-source and Today follow-up entrypoints use it. The source GET remains a raw source read with status presentation.
- The final Today UI presents source_review directly with an Aufgaben link and excludes it from connection failures. A review-only source status points to tasks; mixed calendar/mail failures retain access settings. Truncated status summaries call extra entries neutral Hinweise.

## Limits

Static bounded review, not a new end-to-end runtime proof. Results describe a request snapshot. Existing saved originals remain explicitly inspectable after withdrawal with source-status labels. The lookup is a capped header-metadata component search, not semantic mail analysis or proof that a task still holds. Broader existing dashboard behavior is outside this slice. No remaining counterprobes are running.

## Exact reviewed content

- `sidecar/icarus_memory/task_source_review.py`: `215bc57e7427ccdfcdf792f7a53e3948f04e5fe467876a1d605fa961adc5f908`
- `sidecar/icarus_memory/server.py`: `da79f69fda305ea0b8fcb9c495b60fe4f49f562e1b7914aeb8d1d908a957b823`
- `sidecar/icarus_memory/briefing.py`: `e4a7ab53f42dd36288052515f48ff64d4d515b23663da9e3c3ea688a950c0ba5`
- `sidecar/icarus_memory/morning.py`: `1b94483d18cd560eff3e8b730f71ec8219a3fec5a0dfd391d340a83345162db7`
- `sidecar/tests/test_task_source_review.py`: `38bc1e47992de9281a40720a24be63c90ec674c05bb82531515712f87901683b`
- `app/kingfisher/src/ProfileSource.tsx`: `4d45fcc8d20f51c7d1c683c77f6c6394e6580fc0701921379f8ddcc1467eaf23`
- `app/kingfisher/src/TaskSource.tsx`: `e3e11a5d206718aeba3828b6000813d576837d64124ef275aa3d96089d1d1434`
- `app/kingfisher/src/TodayTaskActions.tsx`: `870f368d29cc60c4256f245f36d3919aaf4bc5e2776d7c97ae3823595620232c`
- `app/kingfisher/src/api.ts`: `9f54bd68169f9304e283fdb6b4564f72b997d4680bc5c58929a90921e143d9de`
- `app/kingfisher/src/App.tsx`: `5b2077bc0c34ff04cb801cc64cd94c03c84f21006280d8f0559d5013130881e4`
- `app/kingfisher/src/TodayOverview.tsx`: `a62ed70cf4ebde68e78261a584811fb47eba09c317a107de0e97f47e4e7419b1`
- `app/kingfisher/src/TodaySourceStatus.tsx`: `cbef19e5b5ebeaadcaf02a0508e8cd83968c598cf0f9e634ec1170da02fe9759`
- `app/kingfisher/src/dailyFlow.ts`: `af13399120e40defcd4714ec9dbf2fad27eec5c4fa45673d54c797f82d9f9021`
- `app/kingfisher/tests/daily-flow.test.mjs`: `a00b46864982496d4ff7f700c4ae6aa0b21875c6ad5fd3649549b97ec09711e7`
