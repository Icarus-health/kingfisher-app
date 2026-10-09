# Enges unabhängiges Review

Wiederverwendeter Reviewer `/root/review_core_acceptance_map`, nur lesend. Er prüfte vor dem finalen Datums-Commit; keine Tests durch den Reviewer. Die folgende Zusammenfassung ist sein Bericht über bereits geprüften Code, keine Bestätigung des finalen Gesamtlaufs.

> Neu aufgenommene Live-Mail wird mit Episode und Intake-Fortschritt atomar zur Aufgaben-Wiedervorlage vorgemerkt. Der kurze `rechecks_only`-Lauf versucht höchstens zwei Quellen und liest höchstens 20 Queue-Zeilen; er überspringt den historischen Scan und die globale `expire_sources()`-Prüfung. Briefing, Kandidatenanzeige und Übernahme prüfen den aktuellen Quellenbezug weiterhin frisch.
>
> Zeitplan-, Modell-, Pause-, Last-, Parallelitäts- und Restore-Sperren bleiben wirksam. `RestorePending` verhindert den Jobstart, wird nun aber im Worker-Loop abgefangen, damit der Scheduler-Thread weiterläuft. Die vier Health-Zeitstempel verwenden den ISO-Helfer mit unveränderter Parse-Semantik.

Der erste Review fand, dass der kurze Lauf trotz begrenztem Modellbudget global alle offenen Vorschläge prüfen würde. Deshalb überspringt `rechecks_only` sowohl diese globale Prüfung als auch den normalen Scan. Die reguläre vollständige Prüfung bleibt bestehen. Anschließend zeigte ein eigener Regressionstest, dass eine Wiederherstellungssperre vor Methodeneintritt den Scheduler-Thread beenden konnte; die Sperre bleibt wirksam, die Ausnahme wird nun im Loop abgefangen. Beide Korrekturen wurden gezielt geprüft.

## Gesamtlauf-Nachtrag: RAM-Testvertrag

Der Reviewer prüfte den einzigen Fehler des zweiten vollständigen Laufs eng und nur lesend, ohne eigene Tests:

> Die geplante Testkorrektur erhält das Sicherheitsverhalten und kaschiert keine Runtime-Abweichung: Bei 8 GB gemeinsamem Arbeitsspeicher weist `memory_plan_gb` nach 6 GB Reserve nur 2 GB Modellbudget aus. Nach Ausschluss von `tev1:0.8b` ist daher eine leere Ausweichliste korrekt. Der separate Linux-Fall mit 8 GB dediziertem GPU-Speicher prüft weiterhin die bisherige Reihenfolge unter dem dort geltenden 85%-GPU-Budget.
