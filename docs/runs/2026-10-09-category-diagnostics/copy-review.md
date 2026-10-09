# German category diagnostics review

No actionable copy or state blocker found for the requested contract.

- Failed, deferred, pending, and unverified category work all keep analysis unfinished, preventing completion and capping displayed percentages below 100% (`app/kingfisher/src/mailIntakeProgress.ts:46-61`).
- The retry action is available for real category failures and remains available when unverified category status is the only remaining issue (`mailIntakeProgress.ts:49-50`; `app/kingfisher/src/MailIntake.tsx:195-200,217-219`). The unverified-only case gets the specific label “Weitere Einordnungen prüfen.” Its test asserts retry availability (`app/kingfisher/tests/intake-progress.test.mjs:69-77`).
- Unknown failure codes use a fixed generic label, and tests cover raw-looking unknown strings (`app/kingfisher/src/categoryFailureText.ts:15-18`; `app/kingfisher/tests/category-failure-text.test.mjs:5-10`). Both category failure UI paths call this helper (`SourceCategories.tsx:46-47`; `MailIntake.tsx:110-114`).
