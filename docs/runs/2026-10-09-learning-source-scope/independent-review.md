# Enges unabhängiges Review

Wiederverwendeter Reviewer `/root/review_core_acceptance_map`, nur lesend. Scope: Episode-/Proposal-Getter, Habits, Learning-Service/-Routes und neue Regressionstests. Keine Tests durch den Reviewer.

> Kein konkreter Gültigkeits-, Entzugs- oder Idempotenzfehler im Diff gefunden. Die neuen Getter filtern vor der Python-Deserialisierung, behalten die bisherigen Sortierfolgen und erfassen weiterhin alle passenden Zustände. Check-in-Wiederholungen suchen per exaktem Quellenbezug auch ignorierte und unmarkierte Legacy-Einträge; mehrere Habit-Tags bleiben getrennt je aktivem Habit auswertbar.
>
> Die verbleibende Grenze: `tagged_raw`, `by_source_ref` und `from_origin_prefix` filtern JSON-Felder in SQLite ohne passende Indexe. Unbeteiligte Dokumente werden nicht in Python geladen, aber SQLite kann sie beim JSON-Scan weiterhin untersuchen.

Nach diesem Review wurde die nicht mehr aufgerufene private Wochenzählung entfernt; die Anzeige zählt jetzt aus denselben Check-in-Datensätzen, die sie anzeigt. Der eingefrorene Endstand wurde anschließend mit allen 141 betroffenen Fällen und im fertigen Paket geprüft.
