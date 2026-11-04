# Calendar source-outage previews

Base: `1b5a262711fa86b7af6d508ab2eae734a11617a4`. Tested implementation: `23092a6` (following `8479069`). This is one bounded P3/P4 repair, independently based on main.

## User behavior

An explicitly failed calendar source no longer erases its previously loaded appointments from the same open range. The UI retains those rows with their last-read timestamp and an unverified label, while fresh sources remain current. Stale events have no preparation, follow-up or mutation actions. An already-open edit retains the user's fields but cannot submit until a fresh read confirms the event.

Successful empty reads, changed ranges, rebuilt source configurations, Mac calendar selection/permission changes and disappearing selected Mac calendars invalidate previews. Removed mirror copies cannot inherit a surviving source's action destination. Backend memory and model paths still perform strict current reads; preview rows exist only in the frontend.

Old UID-only preparation links resolve their event date through the existing compatibility lookup. Preparation then waits for a fresh read of that visible range, rather than mounting from a retained old event object.

This is **not persistent offline calendar support after restart**, and arbitrary transport failures without a current authorization context do not retain rows. The native app, live provider failure behavior, accessibility acceptance and full P3/P4 completion are not claimed.

## Evidence

- Read-only aggregate check of the existing local calendar: 18 appointments, two visible source groups, five proven mirror groups, no unmerged similar pairs within the inspected two weeks. No personal event content is included here; no event was changed. This gave no evidence for changing title-based duplicate matching.
- Initial regression tests observed failing before implementation: five backend context tests, helper/UI preview cases.
- Independent whole-branch review of `1b5a262..8479069`: no Critical issues, three Important findings. All corrected in one fix pass: disappearing selected Mac calendar, old preparation revived after range navigation, missing per-event stale label in month view.
- Review regression evidence: new backend availability case failed before the fix; three UI navigation cases and month-label case failed before the fix. Final targeted run: six backend context tests and nine UI component cases passed, including legacy link compatibility. The UI tests allow the normal fresh-range request to settle before asserting preparation availability.
- Final affected backend: 109 tests passed in 26.70 seconds across calendar read context, copies, context, actions, window/display/period, search cache, preparation, multi-integrations and Mac calendar; three next-appointment tests also passed. Total **112**.
- Full frontend suite: **1,045 passed** in 12.42 seconds. TypeScript and Vite build passed; existing bundle-size warning remains.
- `git diff --check` passed.
- Rendered synthetic check: **18 assertions passed** using the actual CalendarPage and CalendarActionForm, mocked local API responses, four viewport widths (390/900/1280/1440), no provider/model requests, no POST requests. See [QA results](qa-result.json), [month](month-preview.png), [list at 900 px](list-preview.png).
- Tested interactions include editing then source failure with draft preservation and disabled submission, opening an unverified event, successful-empty clearing, context change, range navigation, HTTP409 clearing and recovery. Month view distinguishes the failed source's old event from the other source's fresh event.
- No relevant unexpected console errors or framework overlay; the deliberately simulated HTTP409 is recorded. CSS 200% zoom was only an overflow smoke check, not native/browser zoom or complete accessibility acceptance.

## Test setup and limitations

Browser plugin not available; used existing local Playwright with headless Chrome and an isolated Vite page at 127.0.0.1:5197, exclusively synthetic data. Initial QA attempts exposed test setup errors (case-sensitive close-button name, tab role, and missing fixture asset directory), corrected using actual source/rendered evidence. Those failures were not product regressions. Final server and QA browser closed in cleanup.

No Mistral key, paid call, private data upload, bulk import, personal settings change, native installation or live-calendar mutation occurred. The separate native test window has an existing unsaved draft; it was not reloaded. Independent review did not cover unchanged shared account-status bookkeeping or persistent offline snapshots; those remain separately scoped work.

## CI timing follow-up

Run `41887449067` passed Python 3.10 and the UI job; its Python 3.12 job failed only the unchanged recurrence timing case beginning in 1975 (`FREQ=MINUTELY;INTERVAL=30`): 1.39 seconds against its one-second limit. The other 10,031 tests passed, two skipped. Neither the recurrence parser nor this test changed in this PR.

All 33 parametrized recurrence timing cases passed locally with the original one-second assertions. A separate profile of the reported parser case returned 1,439 occurrences in 0.147 seconds; that local observation does not establish the cause of the slower CI measurement. The full test duration also includes a dateutil reference calculation outside the timed block and is not the parser measurement.

CI now runs these 33 strict timing cases in a separate sequential step after the parallel functional suite. The test budget, hard timeout, expected occurrences and parser remain unchanged; no test is omitted. Collection verifies 10,001 of 10,034 cases in the parallel selection and exactly the complementary 33 cases in the timing selection. This removes concurrent pytest-worker load from that measurement without weakening its threshold. The earlier failed run remains failed; no manual retry was requested.
