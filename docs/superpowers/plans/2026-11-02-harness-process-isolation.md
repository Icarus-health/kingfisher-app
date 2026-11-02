# Harness process isolation — Implementation Plan

> Use superpowers:executing-plans, native implementation and one independent review before activation.

**Spec:** `docs/superpowers/specs/2026-11-02-modular-chief-of-staff-design.md`, phases B/C/E.

## Decision from the failed Mac sandbox spike

Use a separate Docker worker with a read-only image, unprivileged UID, dropped capabilities, no privilege escalation, bounded CPU/memory/process count, fresh temporary job homes and no personal volume or inherited credentials. It joins only a dedicated internal network. A separate gateway joins that network and owns all model/source/skill authorization. Disable external DNS forwarding on the worker; test both direct IP and DNS egress rather than assuming an internal network is sufficient.

The first gateway contains artificial EpisodeStore/ProcedureStore data only. This is an isolation and wiring proof, not production activation. The personal app and paused import stay unchanged. No unrelated Docker container, data volume or program may be stopped. Existing native update/backup/TCC behavior must be preserved by a later production packaging step.

## Tasks

1. Refactor the tested SDK runner into a bounded one-job HTTP service for a fixed gateway origin, while retaining the local CLI probe. Service credentials allow job submission only; SDK child environment excludes even that credential. Add tests for wrong service token, busy service, request/response bounds and unknown configuration.
2. Build an explicitly pinned Linux worker image and a separate artificial gateway from existing public source. No build scripts from dependencies; record binary/package lock hashes. Check capacity first; keep current and rollback software. Any needed app-cache offload must be exactly scoped, host-archived and hash-verified before deleting an unused software image. Never remove original sources or backups as an expedient.
3. Run synthetic source/skill retrieval across the internal network. Verify actual image digest/config, no mounts/host ports on worker, unprivileged user, read-only root, resource caps, denied external DNS/IP and denied host-service reachability. Confirm sources unchanged, outside-scope source excluded, cancellation and cleanup. Inspect the actual returned sentence; automated token-presence checks remain smoke evidence.
4. Review the isolated package independently and fix important defects with red/green tests. Only then design the normal Mac packaging and user-visible activation. No private-data or paid-provider activation follows automatically from an artificial proof.
