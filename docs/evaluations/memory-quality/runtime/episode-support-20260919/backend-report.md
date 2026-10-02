# M1d Backend: Übergabe und Prüfmatrix

Stand: 2026-09-19, gemeinsamer nicht deployter Branch `fix/self-model-episode-support`. Kein Commit, Push, Modellaufruf, Zugriff auf private App-Daten oder Deployment durch diesen Agenten. Alle Tests verwenden synthetische Quellen und isolierte Stores; die bestehende autouse-Fixture setzt `ICARUS_DATA_DIR` pro Test.

## Implementiert

- Episoden-v6: monotone relationale Entzugsgeneration, gepflegter/rückwärts indizierter `Episode.produced`-Lookup, geschützte Projektion und REPLACE-Verbot; Original-/Head-/Metadaten-/Dokumentprüfung aus einem SQL-Snapshot. Rückwärts-Head-Mehrdeutigkeit ist unbekannt und kann keine Autorisierung erhalten. Zeitinstanzen werden zeitzonenunabhängig verglichen.
- Vorschläge-v5: indexiertes `produced_assertion_id`, keine neueste-N-Suche, nicht eindeutige Produzenten scheitern geschlossen. Lokale Autorisierung liegt ausschließlich in der relationalen Spalte und wird weder durch Vorschlags-JSON, `_put`, generische Annahme noch Migration erzeugt oder ersetzt.
- Striktes portables `episode_support`-Format in Modell, Parser, Schema, Backends und Export. Redaction entfernt alle darin enthaltenen Zitate. Gewöhnliche stale Writes können jüngere Supportdaten nicht überschreiben; SQLite prüft und schreibt unter `BEGIN IMMEDIATE`, MemoryBackend unter reentrant Lock.
- Annahme reserviert zuerst den ausstehenden Produzenten, dann den gesamten Selbstmodell-Batch einschließlich vorheriger Ersetzungslinks. Commitreihenfolge: Produzent, dann Selbstmodell. Vor Veröffentlichung fehlgeschlagene Aufnahme/Produzenten-Commit rollt den offenen Selbstmodell-Batch zurück. Scheitert der spätere Selbstmodell-Commit, bleibt ein akzeptierter, aber mangels kanonischer Aussage unbenutzbarer Produzent bestehen. Keine verteilte Atomarität behauptet.
- Gemeinsamer bounded Resolver für jede SelfModel-Ahnenaussage, Kontext, Version-3-Historie, aktuelle Gesprächskarten, scoped Agents, tatsächlichen Providerwechsel und explizite Vorschau. Historische Entscheidungen können eine vollständige sichtbare, zurückgezogene Grundlage qualifizieren; unvollständige/geschützte Grundlagen halten die gesamte Ableitung zurück.
- Authentifizierte Listen-/Vorschau-/Submit-Routen gemäß `api-contract.md`, strikte Anfrage mit tatsächlichem `confirmed: true`, einmalige/ablaufende gebundene Tokens, beschränkte Scan-Seiten, CAS ausschließlich für Support. Datum, sachliche Bestätigung, Status und andere Aussagefelder bleiben erhalten. Restore verdrahtet die Dienste kohärent neu und verwirft Tokens.
- Policy-Ablehnungen nennen die Einschränkung ohne deren Text zu zitieren. Damit kann eine weiterhin restriktiv ausgewertete Grenze weder durch Toolresultat noch durch Notices oder direkte Aufrufe ausgeschlossenen Quelltext an ein Modell zurückgeben.
- Der Produzenten-Commit ist die dauerhafte Autorisierungsentscheidung. Ein anschließend fehlgeschlagenes zusätzliches Audit führt zu einer ehrlichen Erfolgsantwort mit Warnung. Auditargumente enthalten ausschließlich Kennungen, Hashes und tatsächliche Autorisierungszeit, keine Zitate.
- Reviewfund Werkzeugweg: `gedaechtnis_suchen` trägt ein explizites Tool-Merkmal; Agent rendert Treffer über denselben Resolver und erfasst die exakt gerenderte Herkunft zusätzlich zur anfänglichen Kontextauswahl. Werkzeug-only Ableitungen werden vor/nach Provideraufrufen und nach Reload revalidiert. Direktes `Agent.invoke` verwendet ausdrücklich externen Scope unabhängig vom lokal eingerichteten Provider.

## Prüfmatrix

Alle nachstehenden Funktionen stehen in `sidecar/tests/test_episode_support.py`, sofern nicht anders bezeichnet.

| Vertrag | Konkrete Prüfung |
| --- | --- |
| Vollständige neue Annahme, lokale Entscheidung, Originale | `test_future_acceptance_captures_every_original_and_local_commitment` |
| Generation, Wiederholung, Reopen, stale Consolidation | `test_withdrawal_generation_survives_reopen_and_stale_consolidation`, `test_second_source_withdrawal_and_reopen_require_new_explicit_review` |
| Fehler direkt nach record ohne kaputte alte Ersetzung | `test_failure_after_record_rolls_back_existing_supersession` |
| Echte zwei Verbindungen, gleiche Annahme, Gewinnerkorrespondenz | `test_two_connections_accept_once_with_reciprocal_supersession` |
| Echte zwei Verbindungen, Annahme gegen Ablehnung | `test_accept_versus_reject_share_real_database_pending_reservation` |
| Produzenten- und Selbstmodell-Commitfehler | `test_commit_failure_preserves_old_supersession_and_never_grants_usable_orphan` (2 Fälle) |
| Unterbrochene zweite Reassessment-Schreibphase | `test_failed_commitment_publication_keeps_intermediate_reassessment_unusable` |
| CAS gegen confirm/retract/redact auf anderer SQLite-Verbindung | `test_preview_cas_detects_concurrent_mutation_on_another_sqlite_connection` (3 Fälle) |
| Stale gewöhnlicher Writer und Redaction | `test_stale_generic_writer_cannot_undo_support_and_redaction_clears_quotes` |
| Legacy-Neubewertung ohne sachliche Auffrischung | `test_legacy_reassessment_preserves_factual_document_and_replay_fails` |
| Gealterte ACTIVE-Aussage behält Datum/Qualifikation | `test_age_outdated_root_keeps_original_factual_date_and_qualification` |
| Vorschau bindet Root/Producer/Ahnen/Scope | `test_preview_binding_rejects_changes_without_new_authorization` (4 Fälle) |
| Sekundärquelle nach Vorschau verändert | `test_second_source_withdrawal_and_reopen_require_new_explicit_review` |
| Replay/Expiry/Kapazität/leer gefilterte Scan-Seite | `test_legacy_reassessment_preserves_factual_document_and_replay_fails`, `test_token_expiry_capacity_and_paginated_orphan_scan_are_bounded` |
| Echter HTTP-Auth-/Strict-Body-/Boolean-Vertrag | `test_actual_api_requires_auth_and_strict_explicit_confirmation` |
| Import pending/accepted + generische Annahme keine Autorität | `test_generic_proposal_import_rejects_forged_authority` (2 Fälle) |
| Import über bestehenden Produzenten | `test_existing_producer_cannot_import_replacement_authority` |
| Kopierte Proofdaten für andere Root | `test_copied_typed_support_cannot_grant_import_authority` |
| Export/Import + unbekannte Felder | `test_portable_support_roundtrip_is_data_not_authorization` |
| Migration ohne Autorisierungs-Backfill | `test_legacy_migration_creates_no_support_or_authorization_and_keeps_ambiguous_identity_blocked` |
| Produzent hinter 5001 neueren/unverwandten Einträgen + Duplikat | `test_index_finds_old_producer_behind_5001_unrelated_proposals_and_rejects_duplicate` |
| Alle einzelnen Zitate; übergroße Gesamtmenge abgelehnt | `test_all_distinct_quotes_validated_and_bounds_reject_whole_capture` |
| Archivoriginal bleibt; Head-/Metadatenwechsel sperrt | `test_tracked_metadata_head_and_archive_contract` |
| Projektion kann nicht versteckt/gefälscht werden; Löschung | `test_projection_cannot_be_hidden_or_forged_and_delete_is_maintained` |
| Mehrdeutige Legacy-Heads | `test_ambiguous_legacy_heads_never_authorize_acceptance_or_review`, zusätzlicher Migrationstest |
| Zeitwechsel Mac/Docker einschließlich Neustart/Neubewertung | `test_source_and_authorization_survive_timezone_change_and_restart` |
| Fehlende Ahnenautorität nicht durch Root-Vorschau überspringen | `test_missing_ancestor_support_cannot_be_waived_by_root_preview` |
| Historische Entscheidung stabil qualifiziert, fehlende Quelle sperrt | `test_withdrawn_complete_episode_basis_can_qualify_decision_history_but_missing_cannot` |
| Tatsächlicher Provider: zweite Quelle, scoped, Neustart, extern | `test_actual_provider_revalidates_secondary_episode_and_persisted_history` (4 Fälle) |
| Aktuelle API-Karten verschwinden; Transkript bleibt | `test_current_cards_drop_secondary_withdrawal_without_erasing_historical_message` |
| Tool-only Quellen: aktiv/zurückgezogen/extern/Reload | `test_model_recall_tool_enforces_support_and_tracks_tool_only_history` (4 Fälle) |
| Direkter Tool-Aufruf erbt keine lokale Freigabe | `test_direct_memory_tool_does_not_inherit_local_provider_permission` |
| Tool-only Entzug während Provideraufruf / historische Qualifikation | `test_tool_only_lineage_guards_completion_and_keeps_historical_qualifier` (2 Fälle) |
| Policy-Ergebnis darf keine ausgeschlossene Grenze zitieren | `test_restrictive_policy_does_not_quote_unavailable_constraint_into_provider_or_tool_result` (3 Fälle: lokaler Entzug, externes Modell, direkter Aufruf) |
| Auditfehler nach dauerhafter Zustimmung | `test_audit_failure_reports_durable_authorization_honestly` |
| Bestehende M1c-Eltern-, Datenschutz-, Lebenszyklus- und Historieproben | `test_self_model_basis.py`, `test_profile_history.py`; positive Inference-Fixtures jetzt mit echten expliziten Stores |
| Schema-/Migrations-/Backupbestand | `test_migrations.py`, `test_source_versions.py`, `test_mail_ingestion.py`, `test_task_detection.py`, `test_backup.py`; historische Fixture-Downgrades entfernen v6/v5-Erweiterungen vollständig |

## Nachweise und Grenzen

- RED-Baseline der vorhandenen Teilimplementierung: Deadlock durch nicht reentrante Store-Locks; danach fehlende Snapshot-/Annahmestrecke. Vorhandene drei Supporttests wurden grün.
- Unabhängiger Reviewfund Legacy-Head-Mehrdeutigkeit: neue Prüfung zuerst rot (`DID NOT RAISE ProposalError`), nach Single-Snapshot-Gegenprüfung grün.
- Unabhängiger Reviewfund Tool-Egress/Herkunft: vier neue Fälle zuerst rot (zurückgezogener/externer Text ging ans Modell; aktive Tool-only Herkunft fehlte). Nach gemeinsamer Render-/Herkunftsstrecke vier grün. Direkter Tool-Scope separat erst rot, dann grün.
- `.venv/bin/pytest sidecar/tests/test_episode_support.py sidecar/tests/test_agent.py sidecar/tests/test_mcp.py -q --tb=short`: **99 bestanden**, zwei bestehende Starlette/AnyIO-Deprecation-Warnungen.
- Vollständiger früherer Lauf nach Hauptintegration: **1529 bestanden**, zwei Deprecation-Warnungen. Dieser Lauf lag vor dem zusätzlichen Toolfund und ist deshalb nicht alleiniger Endnachweis.
- Weiterer Gesamtlauf nach Toolfix: **1537 bestanden**, zwei Deprecation-Warnungen.
- Policy-Denial-Fund separat: drei neue Fälle zuerst rot mit dem geschützten Text in Toolantwort/Notices, nach generischer Ablehnungsbegründung grün; restriktive Wirkung bleibt bestehen.
- **Finaler Gesamtlauf nach allen drei Reviewfixes:** `.venv/bin/pytest sidecar/tests -q --tb=short` → **1540 bestanden**, zwei vorhandene Starlette/AnyIO-Deprecation-Warnungen, 124,50 Sekunden. Log: `backend-suite-final.log` im selben SDD-Arbeitsverzeichnis. Die M1d-Datei enthält 51 ausgeführte Fälle.
- `git diff --check` bestanden. Tatsächliche Browser-/Docker-/Fake-Provider-Abnahme und Dokumente koordiniert der Root-Agent, dieser Bericht behauptet hierfür keinen eigenen Lauf.

Kein Schutz gegen beliebiges Ersetzen/manuelles Fälschen ganzer SQLite-Dateien, Restore verlorener späterer Entzugsentscheidungen, physische Löschung oder vollständige Modellqualifizierung. Optimistische Quellenprüfung kann spätere echte Änderungen nicht ausschließen; jede weitere Verwendung prüft erneut. Unterbrochene storeübergreifende Veröffentlichung bleibt gegebenenfalls gespeichert und unbenutzbar, nicht angeblich atomar zurückgerollt.

## Python-3.10-CI-Nachkorrektur

Nach Commit `7424101` zeigte ausschließlich der Python-3.10-CI-Lauf, dass `datetime.fromisoformat` den vom Assertion-Serializer ausgegebenen UTC-Suffix `Z` noch nicht akzeptiert. Der enge Nachtrag in `canonical_instant` normalisiert genau diesen terminalen Suffix zu `+00:00`; zeitzonenlose und malformed Werte bleiben abgewiesen. Doppelte `Z` werden vor der Normalisierung ausdrücklich verworfen, weil Python 3.10 sonst `...Z+00:00` überraschend akzeptiert.

Delta dieses Agenten: **5 Produktionszeilen** in `source_snapshot.py`, **21 Testzeilen / 10 parametrisierte Fälle** in `test_episode_support.py`. Keine weiteren Produktionsänderungen, kein Commit/Push.

- Tatsächliches `python:3.10-slim`, **Python 3.10.21**, isolierte Container-Daten, Sidecar/Schema nur lesbar eingebunden: neuer UTC-Z-Fall zuerst rot (`1 failed, 9 passed`); nach Korrektur `docker exec kingfisher-m1d-python310-check python -m pytest /src/sidecar/tests/test_episode_support.py /src/sidecar/tests/test_verdichtung.py -q -p no:cacheprovider --tb=short` → **93 passed**, zwei vorhandene Deprecation-Warnungen, 4,44 Sekunden.
- Lokales Python 3.12: `.venv/bin/pytest sidecar/tests/test_episode_support.py sidecar/tests/test_verdichtung.py -q --tb=short` → **93 passed**, dieselben zwei Warnungen, 2,60 Sekunden.
- `git diff --check` bestanden. Keinen neuen lokalen Gesamtlauf oder Frontend-/Docker-App-Abnahmelauf für diesen Parsernachtrag behauptet; erneute vollständige Matrix führt der Root-Agent über CI aus.
