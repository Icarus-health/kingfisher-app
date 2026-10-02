# Aufnahme und Quellenstatus – 28. September 2026

## Gelieferte Änderung

Gespeicherte Dateien wurden bislang ohne verlässliche Unterscheidung zwischen Speicherung und automatischer Einordnung angezeigt. Uploads, die während eines gewöhnlichen Automatiklaufs eintrafen, mussten außerdem hinter zusätzlichen Modellaufgaben warten.

Die Dateiliste und geöffnete Originalquellen zeigen jetzt einen aus dem aktuellen Original abgeleiteten Einordnungsstatus. Sichtbare Ansichten aktualisieren ihn alle fünf Sekunden ohne neue Modellaufrufe. „Automatisch eingeordnet“ bestätigt weder sachliche Wahrheit noch vollständige Auffindbarkeit. Leere Ergebnisse, ausgeschlossene/verworfene Quellen, Pause und Fehler bleiben unterscheidbar.

Der bestehende einzelne Scheduler bedient vor optionalen Modell-Nebenaufgaben eine begrenzte Upload-Gruppe. Laufende Modellaufrufe werden nicht unterbrochen. Pausen, Abschaltung, Warteschlangengrenzen und Sicherungen bleiben erhalten. Ein Upload während einer bereits laufenden langen Nebenaufgabe kann weiterhin warten; dies ist keine allgemeine Latenzgarantie.

Projektauswahl-Schaltflächen verwenden eindeutige, explizite Projektnamen aus derselben Originalquelle statt technischer Dateinamen. Daraus entsteht keine automatische Projekt- oder Personenzuordnung.

## Verifikation

Geprüfter und lokal bereitgestellter Code: `55e9bca9f772213c5a00396e77aa96a3876c3b54`, Basis `fff3fa7cc9c97e2c6646fb61b35ecd6b806d9f53`.

- Vollständige Backend-Suite: **2455 bestanden**, 2 bestehende DeprecationWarnings, 246,59 Sekunden. Weitere **235 Diagnoseskript-Tests** bestanden. UI-Produktionsbuild, Docker-Build und Asset-Vertrag (16 Dateien, 15 Icons) bestanden; `git diff --check` sauber.
- Neue Regressionen zunächst rot, anschließend grün: Status-Lebenszyklus einschließlich leerer/zu umfangreicher Quelle, Upload-Vorrang vor Nebenaufgaben, Pause während laufender Arbeit und lesbare Projektauswahl.
- Ein bestehender Duplikat-Upload-Test verglich GET und Create vollständig. Wegen des zusätzlichen, ausschließlich lesend abgeleiteten Status vergleicht er jetzt den GET-Zustand vor/nach Upload. Der Schutz gegen Quellenumschreibung bleibt erhalten.
- Gefüllte lokale Testkopie: zwei synthetische Quellen in **1,55 und 13,43 Sekunden** eingeordnet; beobachtete Folgen `processing → complete` bzw. `queued → processing → complete`. Originaltexte blieben exakt erhalten. Diese Messung lief auf `46f075c`, dessen Aufnahme-/Status-/Scheduler-Code identisch mit dem ausgelieferten Stand ist. Der damalige experimentelle Antwortvertrag wurde anschließend entfernt.
- Endgültiger Stand erneut per HTTP und Browser geprüft: frische Projektfrage bietet Abendhain/Birkenufer; Bedingungsfrage liefert den Originaltext mit fehlender Freigabe. Die Browser-Auswahl Abendhain zeigt nur die passende Quelle; Dateiliste und aufgeklappte Quelle zeigen den Einordnungsstatus. Rohantworten: `shipping-live-answers.json`.
- Bereitstellung ausschließlich in bestehender isolierter Testkopie auf Port 8892. Automatik nach dem Aufnahmeversuch wieder pausiert; ursprüngliche App auf Port 8891 nicht umgestellt. Keine Cloud-Modelle, Downloads, externen Sendungen oder erneuten CI-Läufe.

## Bewusst nicht übernommen

Eine experimentelle Erweiterung sollte Personen-Rückfragen durch zusätzliche Modellzitate begründen. Das lokale 4B-Modell verwendete Bedingungen bzw. Rollen als Personenalternativen und übersah zwei unterschiedliche Personen innerhalb einer Quelle. Eine verschärfte Validierung erzeugte zudem einen Auswahlfehler im bekannten Bedingungsfall. Deshalb wurde der gesamte neue Antwortvertrag zurückgenommen; die kompakten Fehlresultate bleiben in `results.json` dokumentiert. Aus grünen Unit-Tests wurde keine Produktfreigabe abgeleitet.

Mit dem ursprünglichen Antwortvertrag und den neuen Oberflächen-/Aufnahmeänderungen bestand das bereits installierte `qwen2.5:14b` lokal **7/7 bekannte Fälle und 1/2 zusätzliche Fälle**. Auch dieses Modell erkannte die nötige Personen-Rückfrage bei zwei Personen in derselben Quelle nicht. Die vollständigen synthetischen Eingaben, Modellantworten, Gewichte, Quellenintegritätsprüfungen und Runner liegen in `larger-known` und `larger-independent`. Beide Runner erwarten `PYTHONPATH=sidecar`, laufendes lokales Ollama und schreiben nur in ein neues Ergebnisverzeichnis; vorhandene Ergebnisdateien sind gegen Überschreiben geschützt.

Dies ist kein allgemeiner Genauigkeitswert und kein ausreichender Beleg für einen globalen Modellwechsel. Standard bleibt `qwen3.5:4b`; unnötige und fehlende Personen-Rückfragen bleiben offen. Nächster Qualitätsblock: Personenmehrdeutigkeit innerhalb einer Quelle und Bedingungen getrennt an unveränderten Gegenbeispielen bewerten, bevor eine neue Entscheidungsregel oder Modellkonfiguration übernommen wird.

GitHub-CI auf PR #117 wurde nicht gestartet: Die Job-Annotation bestätigt fehlgeschlagene Account-Zahlungen bzw. erreichtes Ausgabenlimit. Keine CI-Wiederholung veranlasst; die Übernahme stützt sich auf die genannten lokalen Nachweise, nicht auf grüne Actions.
