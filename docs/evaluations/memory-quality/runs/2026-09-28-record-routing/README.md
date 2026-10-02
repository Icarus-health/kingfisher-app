# Gedächtnisfragen nach Buchungen und Freigaben

## Fehler und Umfang

Die festgeschriebene Arbeitswochenfrage „Liegt jetzt eine Hotelbuchung für die Reise nach Bremen vor?“ umging den Belegpfad trotz gespeicherter Bestätigung. Der Frageanfang gehörte nicht zu den erkannten Formen. Das freie Modell erhielt keine Arbeitsgedächtnisbelege und verneinte die Buchung.

Ein begrenztes Muster in `memory_routing.py` erkennt jetzt Existenzfragen, deren erster Gegenstand eine Buchung, Buchungsbestätigung, Reservierung, Freigabe oder Zusage ist. Sie bleiben auch bei leerer Suche beleggebunden. Das bedeutet fehlende Belege, nicht den Beweis, dass etwas nicht existiert. Explizite gemischte Handlungsaufträge behalten den bestehenden Aktionsweg. Keine Modelländerung und kein neuer Modellaufruf allein für das Routing.

Die unabhängige Gegenprüfung fand „Gibt es eine Bestätigung für die Relativitätstheorie?“ als zu breit erfasste Allgemeinfrage. Der generische Begriff Bestätigung wurde entfernt und der Gegenfall als Regression aufgenommen. Dies ist eine begrenzte Verbesserung deutscher Frageformen, keine universelle Intent-Erkennung.

## Nachweise

- Vor Fix: 9 Regressionen rot, 8 Kontrollen grün. Erster Code `66ccbdf`: 82 betroffene Tests bestanden; vollständige Backend-Suite **2472 bestanden**, 2 bekannte DeprecationWarnings, 240,99 Sekunden.
- Letzte Eingrenzung `0ed3c2bc5a79c5df4c395d56b6ad7ad591fc2d06`: zusätzlicher Wissenschaftsgegenfall erst rot, dann **83 betroffene Tests bestanden**. Der bereits gestartete vollständige Lauf bezog sich auf den ersten Fixstand; kein zweiter vollständiger Lauf für das Entfernen dieses einzelnen Begriffes behauptet.
- Unveränderter synthetischer Wochenfallbestand auf `66ccbdf`: **8/11** statt 7/11 feste Beleg-/Statusprüfungen bestanden, Integritätsprüfungen bestanden. Die Hotelbestätigung wird gefunden. Personenmehrdeutigkeit, Hotelbelege zur Zugfrage sowie fehlender strukturierter Nichtwissen-Status bleiben offen. Keine allgemeine Genauigkeitszahl und keine vollständige CoS-Abnahme.
- Letzter Code als Docker-Image gebaut und in der bestehenden isolierten Testkopie auf 8892 bereitgestellt. Echte HTTP-Aufnahme einer synthetischen Buchungsbestätigung, lokale Einordnung und anschließende Frage: passender Originalbeleg, `working_reports`, erwartete Quellen-ID. `live-result.json` dokumentiert die Antwort. Automatik anschließend wieder pausiert. Ursprüngliche App auf 8891 sowie vorheriger Testcontainer erhalten.

## Produktstand

Siehe `docs/release/CORE-READINESS-2026-09-28.md` für den begrenzten Weg zur ersten alltagstauglichen Kernversion. Keine API-Ausgabe persönlicher Daten, kein JEV, kein neues Modell, keine CI-Neustarts.
