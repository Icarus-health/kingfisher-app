# Unabhängiges Review der Originalfallback-Testverträge

## Urteil

**Freigabe für den eingefrorenen Testpatch; keine kritischen oder wichtigen Funde.**

Commit `c09f0758cf3338b8362602d18a5f2c4c5d1f5242` gegen `f03f6eb0683288ea79a2978bf4797ab920c6c4b4`, Worktree `/private/tmp/kf-original-fallback-tests-20261101`. Vollständiger Diff gelesen: ausschließlich die drei vereinbarten Testdateien, 92 Ergänzungen/16 Entfernungen, kein Produktcode. Arbeitsbaum vor und nach Review sauber; kein Repositoryedit durch diesen Reviewer.

Die Umstellung ersetzt den überholten Header-only-Vertrag durch vollständige unbestätigte Originalwiedergabe. Fachliche Quellen, Termine, Zeitrichtung, Negation, falsche Prosa und Gateanforderungen werden nicht abgeschwächt. Eine abgelehnte Satzantwort bleibt ohne geprüfte Satzstruktur. Die beiden angeforderten isolierten Sabotagen machen die neuen Verträge tatsächlich rot.

## Vertrag und fachliche Inhalte

- `test_partial_answer_source_loss.py:54-63` verlangt weiterhin **beide** konkret erwarteten Originale: erste Planung am 12. Mai/09:00 Uhr und die spätere Verlegung auf den 19. Mai/14:30 Uhr einschließlich `Der alte Termin ist ersetzt.`. Die Quellen-/Linkmenge und fehlende Satzstruktur bleiben geprüft. Nach Verwerfung, Abwesenheitsantwort und gespeicherter Teilantwort müssen die ganzen Quellen nun auch im sichtbaren Text stehen. Der erfundene Termin 2035 bleibt ausgeschlossen.
- `test_satzantwort.py:87-108` bindet die Links exakt an die ausgewählten Ref-IDs und fordert jeden vollständigen zugehörigen Originalbody im Text. Die betroffenen Aufrufer verlangen zudem ihre konkreten Inhalte bzw. Quellen; der Vertrag besteht nicht nur aus einem leeren `all(...)`. Der Helper prüft weiterhin `working_reports`, ausdrücklich unbestätigte Darstellung, **keine** Satzstruktur, unveränderte Claimsrevision, exakt gleiche Projektion und Quellenlinks sowie Entfernung gespeicherter falscher Prosa/Struktur.
- Die Druckdatenbitte bleibt Original und wird nicht zur erfundenen Handlung von Alex Sommer. Die Ceder-Negation bleibt vollständig erhalten, die falsche verkürzte Aussage weiterhin ausgeschlossen. Diese fachlichen Goldens werden nicht auf unbekannt gesetzt oder durch einen Link ersetzt.
- `test_zweites_tor.py:69-85` behält die vertauschte Lieferbeziehung als falschen Satz bei. Weiterhin exakt eine Verwerfung, aktives Prüfmodell, erwarteter Ablehnungsgrund, zwei konkrete Prüfanfragen in der richtigen Reihenfolge, keine überlebende Satzliste und keine wiederherstellbare Struktur. Lediglich das wahre vollständige Original wird im Rückfall wieder sichtbar; die umgekehrte falsche Aussage bleibt unsichtbar.
- Die ergänzten gespeicherten Fälle entfernen eine alte Fallbackmarke bei gültigen Sätzen sowie bei Quellenentzug. Erfolgreiche vollständige Vergleiche behalten ihre geprüfte Satzstruktur. Die vorhandenen Frische-/Entzugskriterien bleiben erhalten und werden bei Projektion zusätzlich geprüft.

## Injection-Gegenprobe

Die sichtbare unveränderte Originalquelle darf ihre fremde Anweisung enthalten; der Satzmodellpayload bleibt geschwärzt und die behauptete Ausführung bleibt verworfen (`test_satzantwort.py:694-707`). Die neue Fortsetzung geht tatsächlich durch `ConversationStore.add_message` → `history` → `Agent.load_history` → `Agent.send` → synthetischen nächsten Provider, statt nur einen Hilfsstring zu untersuchen.

Sie verlangt neutralen gespeicherten Assistententext, keine Injection im geladenen Verlauf und im **tatsächlich aufgezeichneten nächsten Modellinput**, keine verwendeten/ausgeführten Traptools, keine neuen nutzbaren Memoryeinträge und unveränderte Claimsrevision (`735-748`). Das Traptool ist eine synthetische Funktion, keine externe Nachricht. Seine OUTWARD-Policy ist eine zusätzliche Grenze; die reine Ausführungslosigkeit wird daher nicht als alleiniger Nachweis der Neutralisierung gewertet. Die gespeicherten und tatsächlich modellseitigen Payloadassertions tragen den Nachweis.

## Ausführung am unveränderten Freeze

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:. /private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python -m pytest -q -p no:cacheprovider sidecar/tests/test_partial_answer_source_loss.py sidecar/tests/test_satzantwort.py sidecar/tests/test_zweites_tor.py
```

**100 bestanden in 8,43 s.** Log: `/private/tmp/kf-original-test-contracts-selected-20261101.log`.

Keine Vollsuite, echten Modelle, privaten Dateien, Netzaufrufe oder Rootänderungen.

## Isolierte Sabotagen, ohne gespeicherte Repositoryedits

Externer Runner: `/private/tmp/kf_original_contract_sabotage_20261101.py`. Jeder Monkeypatch gilt nur im eigenen Pythonprozess und wird beim Prozessende verworfen.

1. **Originalbody wieder entfernen:** `_zitate` wird vorübergehend mit `originaltext=False` aufgerufen; Links, Quellen und Gateverwerfung bleiben unverändert. `test_lexical_rejection_cannot_leave_only_old_planning_visible` wird erwartungsgemäß **rot**, konkret an `FIRST in text and UPDATE in text` (`test_partial_answer_source_loss.py:60`). Damit genügt ein bloßer vollständiger Quellenlink nicht zum Bestehen. Log: `/private/tmp/kf-original-contract-remove_originals-20261101.log`.
2. **Speicherneutralisierung umgehen:** Der Wrapper lässt den angezeigten Originaltext als Assistenteninhalt in `ConversationStore` speichern, indem ausschließlich die Neutralisierungsmarkierung für diesen Aufruf entfernt wird. Die neue Injection-Probe wird erwartungsgemäß **rot** an `stored.content == wma.NEUTRAL` (`test_satzantwort.py:737`); der echte schädliche Quelltext ist im Fehlvergleich sichtbar. Log: `/private/tmp/kf-original-contract-bypass_store_neutralization-20261101.log`.
3. **Zusätzliche Grenze hinter dem Laden:** Nach normalem `Agent.load_history` wurde versuchsweise dieselbe synthetische Injection direkt in den Agentverlauf angehängt. Die Probe bleibt **grün**, weil ein weiterer vorhandener Agent-Historyguard den kontaminierten Verlauf vor dem Modellcall verwirft. Eine reine Beobachtungsinstrumentierung bestätigt `EXISTING_HISTORY_GUARD_CLEARED_SYNTHETIC_INJECTION`; die tatsächlichen Modellinputassertions bleiben erfüllt. Das ist keine überlebende Injection und kein fehlgeschlagener erforderlicher Mutationstest. Log: `/private/tmp/kf-original-contract-contaminate_actual_agent_history-20261101.log`.

Die beiden geforderten Vertragsbrüche werden somit gezielt erkannt. Keine Erwartungswerte wurden für die Sabotagen oder für das Bestehen des normalen Laufs geändert.

## Grenzen

Freigegeben ist die Konsistenz und Sensitivität dieses engen synthetischen Testpatches. Kein neues Produktverhalten, keine reale Modellqualität, kein UI-/Mac-Ergebnis und keine Gesamtbackendfreigabe werden damit behauptet. Nach dem vereinbarten Scope sind keine weiteren Suchbereiche oder Kontrollen nötig.
