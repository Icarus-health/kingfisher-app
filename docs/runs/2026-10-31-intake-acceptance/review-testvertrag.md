# Unabhängiges enges Review: Test-only-Abgleich des zweiten Prüftors

31.10.2026, Worktree `/private/tmp/kf-skill-categories-20261031`. Ausschließlich Diff von `sidecar/tests/test_zweites_tor.py` gegen `d971dc4` und die betroffene Testdatei geprüft.

**Urteil: Kein Befund. Der Testabgleich bildet die bewusst geänderte q09-Regel korrekt ab; er macht die Prüfung nicht durch Weglassen des Gegenfalls grün.**

Der zentrale Teilverwerfungstest enthält weiterhin die echte Rollenvertauschung `FALSCH` und den korrekten Satz `RICHTIG`. Er verlangt jetzt zutreffend Originalfallback statt Restprosa. Die falsche Behauptung muss im Rendertext fehlen; das richtige Original, sein Quellenrahmen und genau der zugehörige Quellenlink müssen vorhanden sein. Verwerfungszahl, Prüferzustand, Modellname und exakter Verwerfungsgrund bleiben geprüft. Zusätzlich werden Vollständigkeitsgrund, fehlende wiederherstellbare Satzstruktur sowie die zwei Prüferaufrufe einschließlich ihrer Satzreihenfolge explizit kontrolliert. Der falsche Satz wurde weder aus dieser Fixture entfernt noch nachträglich als gültig erklärt.

Die Speicherung-/Verlässlichkeits- und Alterstests verwenden nun separat `nur_richtig`, weil nur eine vollständig bestandene Antwort noch den Satzmodus erreicht. Die relevanten Sicherheitsassertionen bleiben erhalten: fehlendes Prüfer-Ja sperrt, ungültiger Torzustand sperrt, die gespeicherte Verlässlichkeitsstufe wird beim Öffnen neu berechnet, ein späterer Stichtag stuft den Beleg ab, Legacy-Antworten bleiben lesbar, und der alte Einzelbeleg trägt unverändert den Hinweis samt Jahr. Diese Trennung isoliert den geprüften Sachverhalt, statt seine Erwartungen abzuschwächen.

Der neue JSON-Roundtrip-Test deckt den anderen Speicherpfad ausdrücklich ab: Die gespeicherte Teilverwerfung bleibt Originalfallback; richtige Quelle sichtbar, falsche Aussage abwesend, keine Satzstruktur. Nach Quellenentzug wird `working_unavailable` mit leeren Links ausgegeben; weder richtige noch falsche Behauptung wird wiederhergestellt. Die Prüferaufrufzahl bleibt bei zwei, also keine verdeckte erneute Modellprüfung beim Anzeigen oder Entziehen.

Die bisherige Assertion über den gerenderten Satzmodus-Hinweis „1 Satz verworfen (Prüfmodell)“ entfällt folgerichtig im nun geltenden Originalmodus. Das ist eine bewusste Änderung der Darstellungsannahme; die persistierten Gründe und Zählungen sind weiterhin exakt geprüft. Dieser Testpatch behauptet nicht, dass der Originalrenderer denselben Hinweis anzeigt.

**Unabhängig ausgeführt: 13 Tests bestanden.** Nur dieses Modul, mit `PYTHONDONTWRITEBYTECODE=1` und deaktiviertem Pytest-Cache; keine Modelle, Netzaufrufe, privaten Daten oder Produktedits. Die gemeldeten CI-/575er-Gruppenergebnisse wurden nicht als eigene Ausführung gezählt. Die endgültige Vollsuite/CI bleibt der nächste getrennte Nachweis nach Freeze.
