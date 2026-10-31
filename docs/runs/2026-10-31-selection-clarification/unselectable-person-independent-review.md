# Unabhängige enge Prüfung – nicht auswählbare Personenrückfrage

**Ergebnis: kein weiterer Befund im geprüften Delta.** Die nachgewiesene Darstellungsstörung ist behoben; die fachliche Seitenunsicherheit wird weiterhin unverändert erhalten. Keine Aussage, dass die ursprüngliche Formularfrage damit inhaltlich beantwortet wäre.

Geprüft: Commit **914f303218f2d276185cc0b337180c21f95a8250** gegen `184fca4`, Arbeitsbaum `/private/tmp/kf-skill-categories-20261031`. Inhaltlich geprüft wurde der Produkt-/Testdelta in `working_memory_answers.py` und `test_answer_clarification_projection.py`. Der Commit enthält außerdem zwei Dokumentationsänderungen (`docs/fassungen/1.0.37.md` und das Root-Prüfprotokoll); deren Inhalt gehört nicht zu dieser engen unabhängigen Codeprüfung. Arbeitsbaum vor/nach Prüfung sauber; `git diff --check 184fca4..914f303` bestanden. Keine Repo-/Teständerungen durch diesen Reviewer, keine realen Modelle, Netzwerkzugriffe oder privaten Dateien.

## Delta und Sicherheitsgrenze

- `working_memory_answers.py:1340–1347` erkennt ausschließlich `status=unclear`, `uncertainty=person` und tatsächlich leere quellenabgeleitete Auswahloptionen. Dann wird der vorhandene kompakte Quellenlinkmodus verwendet.
- `:1367` lässt in genau diesem Zustand den pauschalen Personenfragesatz aus. Andere Personenrückfragen, Scope-/Zeit-/Widerspruchsfragen und der gesamte Auswahlweg sind unverändert.
- `source_selection_pages.py` und die nachgelagerte Bindung der Seitenunsicherheit/Referenzmenge sind im Delta unberührt. Kein Überschreiben durch Gesamtvergleich oder vermeintlich eindeutiges „ich“.
- Aktuelle Originale bleiben über die bisherigen Quellenlinks zugänglich. `render` und `project_message` verändern weder gespeicherte Antworten noch Quellen oder Claims. Ungültige Grundlagen führen weiterhin zu unavailable statt zu alten Verweisen.

## Ausgeführte Prüfung

58 gezielte bestehende/neue Tests aus:

```
sidecar/tests/test_answer_clarification_projection.py
sidecar/tests/test_working_memory_choices.py
sidecar/tests/test_source_selection_pages.py
```

Ergebnis: **58 passed, 1 warning in 13.04s**. Warnung: bestehende `StarletteDeprecationWarning` zu httpx/TestClient. Keine Testfehler. Enthalten: die beiden neuen Fälle ohne Teilnehmer bzw. mit gleichem Absender, echte Personenauswahl mit Klick und Wiederöffnen, Quellenentzug/Metadatenänderung sowie Seitenfehler-/Frische-/Zeitgrenzen. Kein Volltestlauf.

Zusätzlich das schon vor der Änderung erstellte unabhängige Offline-Repro erneut ausgeführt:
`/private/tmp/kf-page-uncertainty-readonly-20261101.py`.

```
Seite 1: source_reports[S3]
Seite 2: needs_person_choice[S6]
Gesamt: source_reports[S3]
```

Weiterhin: `working_unclear`, `uncertainty=person`, beide Quellenverweise, keine erfundenen Auswahloptionen, genau drei geskriptete Auswahlaufrufe. Darstellung jetzt **212 statt vorher 2532 Zeichen**, kein vollständiger Mailkörper, kein Satz „Welche der genannten Personen …“. Das zeigt reine Darstellungskorrektur bei unverändertem unsicheren Ergebnis. Es ist kein Modellqualitätsnachweis.

## Zusätzliche unabhängige Kontrollen

Skript: `/private/tmp/kf-person-projection-independent-controls-20261101.py`; vier eigene Offline-Store-/Render-Szenarien, alle bestanden:

1. **Zwei echte unterschiedliche Absender:** zwei quellenbelegte Optionen und bisheriger Personenfragesatz bleiben erhalten; Originalanzeige unverändert. `working_unclear`, zwei Links.
2. **Gleicher Absender, anschließend Quellenmetadaten ändern:** zunächst kompakt, zwei Links; nach Änderung working_unavailable. Originalkörper bleiben unverändert.
3. **Bestätigter claim_basis neben automatischen Quellen:** beständig bestätigte Aussage bleibt vollständig sichtbar und verlinkt (drei Links insgesamt). Bei nicht geklärtem Claimkonflikt greift weiterhin working_conflict ohne Links.
4. **Read-only-Wiederöffnungsprojektion:** wiederholtes project_message liefert dieselbe kompakte Darstellung, lässt Eingaben/Antwort/Claimrevision unverändert. Nach Entzug einer Quelle verschwinden alle alten Links und Status wird working_unavailable.

Je Szenario genau **ein** geskripteter Auswahlaufruf; Rendern, Wiederöffnen, Metadaten- und Entzugsprüfung benötigen keinen weiteren Modellaufruf. Diese Skripte instanziieren keine echten Modellanbieter und verwenden nur eigene temporäre synthetische Stores.

Gesamtumfang: 58 Tests plus fünf kleine Offline-Szenarien (ein Seitenrepro, vier Zusatzkontrollen), deutlich unter der Grenze von 100 gezielten Fällen. Die RED-Vorgeschichte der neuen Root-Tests wurde als Root-Nachweis gemeldet; dieser Reviewer hat das alte Produkt nicht mutiert und beansprucht keinen eigenen RED-Lauf.

## Verbleibende Grenze

Die Auswahl zweier Formularquellen und die abweichende Seitenbewertung bleiben eine echte Modell-/Quellenauswahlgrenze. Aus einem eigenen Mailkopf, „ich“ in der Frage oder „im Anhang“ folgt hier keine automatisch bewiesene Rücksendung. Die Korrektur lässt deshalb Unsicherheit bestehen und macht sie verständlicher, ohne eine unbelegte Antwort zu erzeugen.
