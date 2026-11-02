# Kingfisher modular Chief of Staff — accepted objective, 2026-11-02

## Intent and authorization

The user explicitly authorized continuous implementation of the clarified goal: keep the Kingfisher interface and source-aware memory, add a plugin/agent execution layer and reusable skills, use local models first and optionally Mistral for suitable harder work, and independently verify the result on GitHub and the Mac. The user delegated implementation choices and asked to continue without repeated planning approvals. Existing unfinished memory acceptance remains part of this objective; it is not declared complete or discarded.

## Outcome

A usable personal Chief of Staff with one visual interface for conversations, memory, mail, calendar and tasks. Incoming information is linked to the correct person/project and source time; recall exposes evidence and asks for identity clarification; corrections and source withdrawal invalidate derived work. Modules share the canonical memory and skill library. New integrations can add bounded capabilities without rewriting that memory.

## Architecture decisions

- Preserve Python/FastAPI stores, source-currentness checks, source originals, identity uncertainty, confirmed corrections and existing React/native Mac interface.
- Prefer DeepSeek Harness as a separate, pinned execution process after a real integration experiment. Do not replace the source-of-truth stores or create a competing memory.
- Kingfisher owns authoritative tool authorization, data release, source freshness, costs and side-effect approval. Harness plugins get explicitly scoped capabilities; no direct personal database, shell, filesystem, master application token or inherited cloud credentials.
- Initial capabilities are read-only memory search/source evidence, current skill selection, tasks, mail and calendar reads through the existing application. Follow-on actions use the existing proposal/confirmation routes. A plugin cannot grant itself access or treat quoted source text as a user instruction.
- Local Qwen9B and BGE-M3 remain defaults. Mistral is an optional explicitly consented route with the actual regional endpoint and documented retention conditions. Slow/failed local inference alone is not permission to disclose data. No paid calls until concrete scope and budget are authorized.
- Preserve active/pending/revoked skill versions, matching scopes, conflict handling and source dependencies. Learned procedures are inactive proposals until confirmed; communication preferences remain scoped profile data, not one copied executable skill per person.
- Keep import versus regular operation separate, background work bounded and interruptible. Bulk import stays paused until a mixed quality sample passes.

## Considered approaches

1. Continue a wholly custom plugin runtime: preserves control but duplicates an existing agent engine.
2. Replace Kingfisher with a complete agent product: risks losing the user's preferred interface and source-aware memory contracts.
3. Preserve Kingfisher and integrate a pinned Harness behind constrained tools: preferred, conditional on compatibility and quality evidence. A failed spike is an integration finding, not authorization to weaken permissions or start a full rewrite.

## Phase A — precision repairs before plugin integration

1. A requested optional attribute must remain optional. For the supported German cues `idealerweise`, `vorzugsweise`, `nach Möglichkeit` and `wenn möglich`, a proposed short title may omit the optional detail or retain the cue, but may not repeat a distinct optional attribute as unconditional. Use the existing exact-source-quotation fallback for unsupported generated titles. Do not remove the underlying real request.
2. Distinguish a communication restriction (e.g. no status-chasing) from an actionable request. Add a closed semantic-review kind `communication_constraint`; retain the complete original as contextual memory. Keep operational waiting and concrete negative duties eligible for semantic review; no blanket negation filter.
3. Shared topic instructions in both entity-anchor paths distinguish substantive content from portal branding, delivery notices, headers, greetings, signatures and boilerplate. Real newsletters and mixed substantive messages remain possible. This is prompt-level semantic guidance, not a deterministic guarantee; require a controlled synthetic live-model evaluation before claiming model quality.
4. Never silently rewrite previously saved unconfirmed candidates. Source-scoped reanalysis must explicitly supersede/review them under the existing provenance and context rules.

## Subsequent bounded deliveries

- B: inspect and pin the actual official SDK/runtime; prove custom local model and read-only tools in synthetic isolation; explicitly disable default shell/file tools and outbound log/inventory contributors. Verify cancellation, missing tools and malformed requests. If the official protocol cannot meet a requirement, document the measured limitation before choosing a small adapter.
- C: integrate the accepted constrained plugin seam with memory and current skills, then existing mail/task/calendar reads and proposal boundaries. Show understandable status and failures in the existing UI.
- D: prepare Mistral routing through the existing regional credentials/consent mechanisms; extend background support only through counted source-scoped jobs. Quality, cost reservation, cancellation and revocation tests precede any paid personal evaluation.
- E: independent branch review, regression and adversarial tests; synthetic end-to-end model run; authorized mixed private sample; backup, normal update and real native Mac interaction. Preserve source originals and global import pause throughout.

## Acceptance and limits

No observed critical person mix-ups, fabricated deadlines, unconditional optional details, unsupported completion claims or stale-source execution in the defined acceptance set. Include ambiguous names, changed/withdrawn sources, conflicting and revoked skills, repeated confirmation, interrupted imports, model errors, budget exhaustion and failed saves. Record live model semantics separately from injected-response tests, publication separately from installation, and installation separately from a user-run everyday-use week. No universal error-free claim. Health/password/social/audio additions remain later plugins after this foundation works.
