# Abschlussreview Mailaufnahme, 08.10.2026

Basis `0c0245031f75b6b9016afafdd54b4a17c2a974b9`, aktueller Arbeitsdiff in `work/memory-activation-20260923`. Keine persönlichen Inhalte oder laufenden Dienste gelesen; Ollama und echte Aufnahme unverändert. Nur synthetische temporäre Daten. Reviewer änderte keinen Produktcode.

## Verifikation

`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts /tmp/kingfisher-review-20261006-venv/bin/python -m pytest sidecar/tests/test_mail_intake_lane_progress.py sidecar/tests/test_mail_intake_wait.py -q -p no:cacheprovider`

**9 bestanden in 1,73 s**, eine bestehende Starlette/httpx-Deprecationwarnung. Die sechs Lane-Tests waren auf dem vorherigen Stand mit fünf erwarteten Assertionfehlern rot; siehe `mail-intake-lane-progress-red-20261008.log`. Die Gegenproben nutzen echte Intake-/EpisodeStore-/Retry-/mail_stand-Logik und ersetzen lediglich den Mailserver.

- History-Zähler `filtered/filtered_by` bleiben nun im gleichen Umfang wie `total/captured`; `live_filtered/live_filtered_by` stehen separat.
- `live_failed` wird aus der neuen Lane geliefert. `MailIntake.tsx` berücksichtigt es für den Retryknopf und addiert für Filter-Retry beide Lane-Zahlen.
- History-Wartebedingung und Abrufsteuerung verwenden denselben `_history_backlog`-Query (höchstens 201 Ergebnis-IDs, ohne Originaltext). Der verschachtelte Store-Lock ist ein RLock. Der Patch ändert die bestehende Schwelle, Priorität oder Nachanalyse nicht.
- `waiting_analysis`/`wartet` sind durch Backend, API-Typ, Fortschritt, Einrichtungsanzeige, Heute-Lernanzeige und Technikansicht geführt. Explizite globale Pause überschreibt Warten; Kontopause bleibt separat. Der globale Pause-/Weiter-API-Test besteht.
- `/memory?view=status` wird in `MemoryAreaModel.memorySectionFromSearch` als Statusansicht gelesen; `MemoryGraph` rendert dafür `MemoryStatus` mit „Verarbeitung & Verlauf“.

## Im Review gefundener und nachgeprüfter Restfall

`app/kingfisher/src/Einrichtung/einlesen.ts:22–24` im ersten Reviewstand: Nach Retry einer neuen Mail ist der Altbestand vollständig gelesen, `live_pending=1`, `stand.zustand='liest'`. Fortschrittslogik meldete korrekt `capture`, Heute-Lernanzeige übernahm korrekt „Noch eine Mail neu einzulesen“. `einlesenStand` gab dagegen „Alle 1 Mails sind gelesen“ aus, weil es nach seinen Sonderzuständen nur den Altbestand verglich. Unabhängig mit den echten TypeScript-Funktionen reproduziert und an Root übergeben. Der ergänzte Test `setup keeps pending new mail visible after its retry` war beim ersten gezielten Node-Lauf entsprechend rot (vier andere Tests grün).

**Nachprüfung nach Root-Fix:** `einlesenStand` übernimmt nun bei `livePending > 0` und Serverzustand `liest` den vorhandenen Satz. `node --experimental-strip-types --test app/kingfisher/tests/intake-wait.test.mjs`: **5/5 bestanden**; zuvor rot gesehener fünfter Test ist grün. `git diff --check` ohne Befund. Kein verbleibender bestätigter Funktionsfehler im geprüften Diff.

## Separater nächster Blocker: Angaben zu Anhängen

`sidecar/icarus_memory/mail_intake_routes.py:56,123` liefert weiterhin pauschal `attachments_supported:false`; `app/kingfisher/src/MailIntake.tsx:174` sagt „Anhänge bleiben außen vor“. Der reale Abruf bevorzugt bereits `message_mit_anhaengen` (`mail_intake.py`), `mail_ingestion.py:82–90` nimmt vorhandene Anhänge auf. `anhaenge.py:30–37,47–62` beschreibt begrenzte PDF-/Bildverarbeitung mit je Anhang eigenen Lesezuständen sowie Seiten-/Zeichenlimits. Die pauschale Nichtunterstützung bildet diesen tatsächlichen Teilumfang nicht ab. Später separat einen ehrlichen Anhangs-/Parserstatus durch API und Anzeige führen; keine pauschale Vollständigkeitsbehauptung als Ersatz. In diesem Patch bewusst nicht geändert und kein OCR-/PDF-/Modelllauf ausgeführt.

Grenzen: kein gesamter Backend-/UI-Testlauf durch diesen Reviewer, keine Browser- oder Liveabnahme; diese führt Root durch. Der geteilte Query begrenzt Ergebnismenge, belegt für sich keine konstante Laufzeit auf beliebig großem Bestand. Bei vielen bereits eingeordneten Zeilen und noch offener History kann die zusätzliche Statusabfrage den gesamten Metadatenbestand durchlaufen, bevor sie 0 liefert. Kein Laufzeitbenchmark ausgeführt, deshalb keine bezifferte Regression oder neue Architekturmaßnahme daraus abgeleitet. Kalender-/Aufgabenfehler werden im vorhandenen Morning-Vertrag separat dargestellt; kein zusätzlicher reproduzierter Anschlussblocker in diesem eng begrenzten Review.
