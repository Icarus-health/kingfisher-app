# Recovery Preflight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Historische Sicherungen und vorhandene Vergleichsstände ohne Wiederaktivierung nachvollziehbar prüfen.

**Architecture:** Ein reiner Read-only-Prüfer liefert aggregierte Evidenz. Die Inspection-App authentifiziert vor dem Prüfen und zeigt den Befund. Rechte, Daten und Markierung bleiben unverändert.

**Tech Stack:** Python 3.10+, SQLite, FastAPI, vorhandener HTML-Viewer.

**Spec:** ../specs/2026-11-04-recovery-preflight-design.md

## Global Constraints

- Keine echten Nutzerdaten, Cloudaufrufe, Mac-Installation oder Fortsetzung des Großimports.
- Keine Aktivierung, Migration, automatische Zusammenführung oder neuen Abhängigkeiten.
- Aktueller Zustand bleibt ungeklärt, auch wenn vorhandene Tabellen gleich sind.

## Review Focus

1. Später entzogene Quelle/Skill unterscheidet sich trotz gleicher Zeilenzahl.
2. Fehlende, neue oder defekte Datenbereiche dürfen keine Null-Unterschiede vortäuschen.
3. WAL, Symlink und Änderung während der Prüfung machen Ergebnisse unbrauchbar.
4. Unauthentifizierte/ungültige Aufrufe beginnen keine teure Prüfung.
5. Wiederholtes Prüfen verändert weder Daten noch Rechte und bleibt zeitlich/speicherseitig begrenzt.

### Task 1: Lesende Prüfung und authentifizierter Produktweg

**Files:** create `sidecar/icarus_memory/recovery_preflight.py`; modify `sidecar/icarus_memory/restore_inspection.py`; create `sidecar/tests/test_recovery_preflight.py`.

**Interfaces:** `preflight(directory: Path) -> dict` liest nur die feste Sicherungs-Allowlist; `POST /api/v1/recovery/preflight` akzeptiert ausschließlich `{}` und liefert denselben Befund.

- [x] Zuerst reale Snapshot/Restore-Gegenproben schreiben: entzogene Quelle/Skill, gleiche Daten nach VACUUM, unbekannte/fehlende Daten, WAL/Symlink/Korruption, Rechte und unveränderte Dateien.
- [x] Betroffene Tests ausführen; vor Implementierung fehlt die Route (423).
- [x] Prüfer mit Arbeitslimit, typisierten Fingerprints und explizit ungeklärten Ergebnissen implementieren. Authentifizierung vor Prüfung, keine beliebigen Pfade.
- [x] Verständliche Zusammenfassung und aufklappbare Befunde im bestehenden Viewer ergänzen.
- [x] Neue und benachbarte Wiederherstellungs-/Boundary-Tests ausführen; unabhängiges Review, relevante Korrekturen mit Gegenprobe.
- [x] Befunde und Grenzen dokumentieren, committen und in den bestehenden Draft PR aufnehmen. Echte Fensterprüfung bleibt von der ausstehenden Test-App-Freigabe abhängig.

Weiterer P5-Umfang steht im Spec; diese Lieferung allein schließt P5 nicht ab.
