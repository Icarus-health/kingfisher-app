# Personenunsicherheit ohne unterscheidbare Auswahl

Nur die gespeicherte Darstellung wird korrigiert. Der Seitenvergleich, seine Personenunsicherheit und alle gewählten Quellen bleiben unverändert. Wenn aktuelle Originalmetadaten keine unterscheidbaren Optionen liefern, zeigt der Verlauf einen kompakten Unsicherheitshinweis und aktuelle Originalverweise statt einer unbelegten „Welche der genannten Personen“-Frage mit vollständigen Mailtexten.

Künstliche Regression: sechs Quellen, zwei positive Seiten, davon eine Personenunsicherheit; Gesamtvergleich wählt nur die andere Seite. Die Seitenunsicherheit bleibt erhalten. Sowohl fehlende Teilnehmer als auch derselbe Teilnehmer in allen Quellen liefern keine unterscheidbaren Optionen. Beide Fälle schlugen vor der Korrektur an der Personenfrage fehl und bestehen danach. API und gespeicherter Verlauf erhalten beide Links; Originale bleiben vollständig abrufbar und unverändert. Quellenentzug entfernt die Antwort samt Links. Echte unterscheidbare Personenoptionen bleiben im bestehenden positiven Kontrollfall erhalten.

Gezielte Prüfung: `test_answer_clarification_projection.py`, `test_source_selection_pages.py`, `test_memory_clarification.py`: **83 bestanden** in 14,07 Sekunden. Ein vorhandener Starlette-Testclient-Hinweis.

Dies korrigiert keine fehlerhafte Modellentscheidung und ersetzt eine unklare Auswahl durch keine behauptete Antwort. Kein neuer Modellaufruf, keine Ich-Heuristik, keine Änderung an Fakten, Beziehungen, Aufgaben oder Fristen. Die reale Modell- und Mac-Abnahme bleibt getrennt.
