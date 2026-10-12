# Bestätigte Aufgaben: spätere Mail im Verlauf sichtbar

Code `a5787c88914400151769dae714dfd74c9ea8a0c3`, 11.10.2026. Persönlich während der Prüfungen weiterhin `1.0.6-preview.bfe555e`; große Mailaufnahme pausiert. Kein Cloudaufruf, Modellstart oder Rollenwechsel.

## Verhalten und Grenzen

Wird nach dem Festhalten einer offenen Aufgabe eine weitere Mail in demselben kontogebundenen Header-Verlauf erfasst, erscheint im Heute-Überblick ein Prüfhinweis mit direkter Originalansicht. Auch Antworten auf Antworten, Geschwisterantworten und später importierte Vorgänger werden verbunden. Maßgeblich ist die Erfassungszeit, nicht ein scheinbar aktuelles Versanddatum. Es gibt keine automatische Absage-, Frist-, Personen- oder Statusentscheidung. Aufgabe und Verlauf bleiben unverändert; ausdrücklich erledigen oder bearbeiten bleibt möglich.

Die Prüfung liest nur aktuelle, nicht ausgeschlossene Mail-Metadaten. Grenzen für Aufgaben, Header, Treffer, Erweiterungsstufen und ein gemeinsames SQLite-Arbeitsbudget führen zu einem ausdrücklich unvollständigen Prüfstatus. Das ist keine feste Laufzeitgarantie und keine semantische Vollständigkeit. Nicht klassifizierte Quellen erzeugen keine erfundene Mailwarnung. Bestätigte Mailaufgaben haben Nutzerherkunft; die Einordnung richtet sich deshalb nach ihrer verknüpften Originalquelle.

Die neue Originalansicht verwendet `originalOnly`: keine Einordnungs-/Beziehungsleser, die bisher beim Öffnen interne Nachläufe auslösen konnten; keine Bearbeitung. Auch Anlagen/Berichtigungen bleiben darin lesend. Quelldatum und Erfassungsdatum werden getrennt gezeigt, fehlende Zeitpunkte bleiben unbekannt. Alte explizit geöffnete Originale bleiben mit ihrem Quellenstatus nachvollziehbar. Zwei kollidierende React-Schlüssel der normalen Quellenansicht sind zusätzlich berichtigt.

## Ausgeführte Prüfungen

- 156 betroffene Backendtests, zusätzlich 13 Dateiimporttests bestanden. 19 neue Backendfälle darunter; echter HTTP-Übernahmeweg mit Nutzerherkunft, transitive Zuordnung, Kontentrennung, Rücknahme/Quellgeneration, Grenzen und Handler-Aufräumen.
- 557 UI-Tests bestanden, Typprüfung, Build, Assetvertrag und Anführungszeichenprüfung erfolgreich. Der Build meldet weiterhin ein großes JS-Bündel. Der erste UI-Lauf vom Repository-Wurzelverzeichnis hatte acht Vite-Testumgebungsfehler; Rohprotokoll erhalten. Der vollständige Lauf vom erforderlichen UI-Verzeichnis ist grün.
- Vorher/Nachher-Gegenproben im getrennten alten Quellarchiv: ein Backendfall und vier UI-Fälle scheitern erwartungsgemäß ohne Änderung. Produktcode wurde dafür nicht temporär verändert.
- Unabhängiger enger statischer Review fand mehrere echte Gegenfälle, die vor dem finalen Lauf korrigiert wurden. Abschluss ohne weiteren Blocker. Der Reviewer hat keine eigenen Tests, Modelle oder persönlichen Daten verwendet. Danach nur abschließende Leerzeile/Leerzeichen in zwei Python-Dateien bereinigt; die dokumentierten Review-Hashes gehören zum Stand unmittelbar davor.
- Tatsächliche Komponenten im Browser gegen einen getrennten SQLite-Dienst mit künstlichen Daten: Vorschau/Abbruch ohne Speicherung, ausdrücklicher Dateiimport mit exaktem Text/Projekt/Herkunft, Neuladen, Duplikat, ungültige Datei und Ausschluss. Nach frischem Prozess erhalten. Keine neue bestätigte Aussage, Einordnung pausiert.
- Heute → später erfasste Mail öffnen: Original sichtbar, kein Schreibaufruf, kein Beziehungsnachlauf, unveränderte Aufgabe, keine Browserfehler, Desktop und 390 px ohne horizontalen Überlauf. Nach Neustart derselbe Hinweis und dieselben Originale. Ein zusätzlicher ausdrücklich künstlicher Teilfehler auf der echten Backendantwort prüft den sichtbaren unvollständigen Prüfstatus samt Aufgabenlink.

`verification.json` enthält die Prüfzahlen und Grenzen; `document-flow-proof.json`, `restart-proof.json`, `task-ui-proof.json` und `task-coverage-ui-proof.json` die tatsächlich ausgeführten Abläufe. Screenshots und Rohprotokolle liegen daneben. Die Treiber verwenden den damaligen absoluten Checkout-Pfad sowie die bereits vorhandene gebündelte Playwright-Laufzeit; für einen anderen Checkout müssen diese Pfade angepasst werden. Dienst und Browser blockieren ausgehende Verbindungen. Der Datenspeicher selbst wird nicht eingecheckt.

Dies ist kein nativer Dateiauswahldialog-, persönlicher Kalenderfenster- oder persönlicher Gedächtnisqualitätsnachweis. Das neue Paket wird gesondert geprüft; `main` und die öffentliche Updatequelle werden hier nicht verändert.

## Wiederholung in einem eigenen temporären Verzeichnis

Die beigefügten Treiber mit `backend.py`, `vite.config.mjs`, `index.html` und den zwei `main-*.tsx`-Einstiegen in ein neues temporäres Verzeichnis kopieren. Absolute Checkout-/Runtimepfade bei Bedarf anpassen. Kein persönliches env/Volume verwenden. Erst `main-documents.tsx` als `main.tsx` setzen, Backend mit Sidecar-PYTHONPATH starten und Vite auf Port 18765 starten; `check.mjs` ausführen. Danach `seed_task.py` im selben getrennten Datenverzeichnis ausführen, Backend neu starten, `main-task.tsx` als `main.tsx` setzen und `check-task.mjs` sowie `coverage-ui.mjs` ausführen. Beide Server beenden; `restart.py` prüft den gespeicherten Bestand in einem frischen Prozess. Die Treiber verwenden ausschließlich die zwei reservierten Prüfports 18764/18765, niemals den persönlichen Dienst auf 8890.
