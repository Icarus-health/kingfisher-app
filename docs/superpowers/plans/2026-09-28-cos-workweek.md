# CoS-Arbeitswoche Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for sequential implementation. The user authorized this evaluation; keep model costs bounded.

**Goal:** Evaluate a continuous five-stage memory history without resetting between days, preserving failed outcomes.
**Architecture:** Synthetic sources enter the existing HTTP API and real local classifier. Queries use the existing conversation route; assertions inspect source selection, status and verbatim evidence. This is the memory part of the full CoS acceptance, not evidence of autonomous calendar or booking execution.
**Tech Stack:** Python, FastAPI TestClient, existing SQLite stores, installed Ollama model.
**Spec:** User-approved working-week evaluation in this conversation; scenarios in `docs/evaluations/memory-quality/workweek/scenario.json`.

## Global constraints

No private data, cloud API, model download, production mutation, prompt fix or hidden retry to improve scores. Freeze scenarios before running; record commit, fixture digest, model digest, elapsed time and raw responses. Preserve failures. Distinguish scheduled source ingestion through a direct callback from real elapsed days and background throughput.

## Review focus

- Same name with different identities: require a clarification, not a merged deadline.
- Conditional commitment: preserve unmet approval and avoid promoting to unconditional work.
- New cancellation: retain earlier source but find cancellation alongside it.
- Withdrawal: previously delivered evidence must disappear from reopened history.
- Duplicate input: one source ID, no duplicate source creation.

## Tasks

- [x] Freeze five logical days of sources/questions, with named references and expected status before inference.
- [x] Build a standalone runner using one temporary app/database for the entire week; record all calls and exact source preservation.
- [x] Test evaluator against fabricated wrong-source, wrong-status and missing-condition answers.
- [x] Run once on the installed default local model; summarize failures without changing expectations.
- [x] Record JEV's hosted boundary, its locally adaptable interface, and limits of typed decisions.

## Remaining full-product acceptance

Actual task creation/delegation, calendar read/write including concurrent changes, approval and repeated tool execution need their own integration phases. They must not be called passed from document recall. Cloud comparison awaits separately configured account, endpoint and budget; no account is created by this work.

## Execution ledger

Completed the bounded memory phase. A small-model independent code review found weak withdrawal grading and environment leakage; both corrected, six grader tests pass. The first run and strengthened rerun both yield 7/11 strict query checks. One failure is a missing structured status despite a correct unknown reply; three concern actual retrieval/decision behavior. A too-strict check on retained invalidated lineage was corrected against the existing UI source-links contract and regraded from saved projections without another model run. See workweek/README.md for limits and next blockers. No production source changed.
