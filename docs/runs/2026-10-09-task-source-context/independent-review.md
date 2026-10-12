# Unabhängige enge Prüfungen

Ein günstiger getrennter Agent prüfte Konzept und Diff; keine Modell-/Cloud-/persönlichen Zugriffe und keine Änderungen. Das erste Review benannte den persistenten Scan-Cursor und die notwendige erneute Prüfung vor dem Commit. Die finale Kontextbindung wird vor dem zweiten Modellschritt und nach dessen Rückkehr verglichen; eine Änderung mit anschließend wiederhergestellten Kontakten bleibt am Generationswechsel erkennbar.

Das Codereview fand einen echten Altbestands-Bypass: task_context=None übersprang den gültigen Quellenbezug. Drei Negativtests für ersetzten Quellenkopf, ersetzte Anhang-Elternfassung und einen tatsächlich entwerteten Berichtigungsbezug reproduzierten ihn. Die Korrektur verlangt nun den gültigen Bezug auch für Altvorschläge, nur ein fehlender Hash bleibt manuell prüfbar.

Weitere gezielte Reproduktion fand doppelte offene Vorschläge bei Übergang von alter zu gebundener Prüfung und erneutes Anbieten angenommener Aufgaben nach Kontaktänderung. Beides ist korrigiert: Ersetzung teilt die Abschluss-Transaktion, bestätigte Episoden-/Digest-/Zitatbindung wird nicht neu angeboten. Ein absichtlich gebrochener Checkpoint lässt den alten offenen Vorschlag unverändert erhalten.

Abschließendes Read-only-Review des festen Commits d0733c6 bestätigte die Bypass-Korrektur, Bindung und Transaktionsfolge ohne weiteren konkreten Fehler im engen Umfang. Es ersetzt keine Modell- oder persönliche Alltagsabnahme. Alte gültige ungebundene offene Kandidaten bleiben bewusst manuell annehmbar, im Briefing als prüfbedürftig markiert; erst eine passende neue Analyse ersetzt den alten Vorschlag.
