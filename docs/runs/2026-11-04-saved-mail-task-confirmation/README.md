# Gespeicherte Mail → Aufgabe mit Frist, Person und Projekt

Geprüfter Implementierungsstand: `484dc1ccb73f7b8db5519c657daf83fcb0c47896`, Basis `1b5a262`.
Begrenztes P3-Paket, keine allgemeine Gedächtnis- oder Modellabnahme.

## Problem und Verhalten

Die gespeicherte Mailansicht übernahm Aufgaben stets ohne Frist und wartende Person. Außerdem fehlten beim Anlegen die aktuellen eigenen Kontoadressen: Eine eigene Zusage konnte dadurch die eigene Person statt des Empfängers als Bezug erhalten.

Der vorhandene Aufgabenweg liefert jetzt auch hier seine geprüfte Frist und Bezugsperson. Beides steht vor der Bestätigung in einer kompakten Zeile. Die Änderung von Datum und „Warte auf“ liegt aufklappbar darunter; Aufgabe und Projekt bleiben direkt bearbeitbar. Eine unveränderte Datumsauswahl erhält die belegte Uhrzeit. Ein ausdrücklich neu gewählter Tag gilt bis 23:59 Uhr. Bezugsperson und wartende Person sind unterschiedliche Angaben.

Aktuelle eigene Kontoadressen gehören zur Bestätigungsgrundlage und werden beim Anlegen verwendet. Ändern sie sich, muss die Grundlage erneut geprüft werden. Auch ein unverändert übernommener Formularvorschlag bleibt nach einem Speicherfehler als Entwurf erhalten. Eine neue Zuordnung nach erneuter Abfrage kann ihn nicht still ersetzen. Wiederholung verwendet weiterhin die bestehende idempotente Aufgabenübernahme.

Der gemeinsame Fristauflöser verwendet die bestehende strenge Fristerkennung statt jede Datumsnennung als Frist anzunehmen. Ein Besprechungsdatum in einem anderen Satz wird dadurch nicht zur Aufgabenfrist. Die breitere Zeiterkennung bleibt als Unsicherheitssignal erhalten: Nicht eindeutig gebundene Zeitangaben müssen geprüft werden, statt eine Aufgabe automatisch ohne Frist anzulegen. Historische bzw. ungeprüfte Fristen werden in der Mailansicht nicht vorbefüllt. Modellangaben überdecken kein geprüftes leeres Ergebnis.

## Nachweise

| Prüfung | Ergebnis |
| --- | --- |
| Betroffene Backendtests (Mailworkflow, Aufgabenübernahme, Entzug, Fristprüfung, Automatik und Datumsparser) | 332 bestanden, 20,14 s |
| Gesamte Frontendtests dieses Branches | 1.039 bestanden, 12,03 s |
| TypeScript / Produktionsbuild / Diffprüfung | bestanden |
| Unabhängiges Review von `1b5a262..aba5ee3` | keine kritischen, zwei wichtige Befunde; beide korrigiert |
| Gerenderte Bedienprobe mit künstlichen Mails | 18 Prüfungen bestanden; keine Provideraufrufe |

Neue Gegenproben wurden vor der jeweiligen Implementierung fehlschlagen gesehen. Das unabhängige Review fand (1) verlorene Erkennung ungebundener Zeitangaben und (2) stille Änderung eines zunächst unbearbeiteten Entwurfs nach Speicherfehler und Kontextwechsel. Die drei Backendfälle und der Frontendfall wurden jeweils erst rot und nach der Korrektur grün geprüft. Anschließend liefen die oben genannten Suiten vollständig. Kein zweites Review als Ersatz für diese Gegenproben.

Bestehende Hinweise: Starlette/httpx-Abkündigungswarnung in pytest; großer JavaScript-Chunk im Build. Beides wurde nicht als behoben ausgegeben.

## Bedienprobe

Die echte `MailReader`-/`SavedMailWorkflow`-Oberfläche lief auf einem getrennten lokalen Testserver mit künstlichen API-Antworten, Zeitzone Europe/Berlin. Browser-Plugin nicht verfügbar; vorhandenes Playwright/Chrome verwendet, keine neue Browserabhängigkeit installiert. Geprüft bei 390, 900, 1.280 und 1.440 Pixeln sowie CSS-Zoom 200 % (kein nativer Browserzoom).

| Verhalten | Ergebnis |
| --- | --- |
| Richtige Seite, sinnvoller Inhalt, kein Frameworkfehler | bestanden |
| Person und genaue Uhrzeit vor Bestätigung; Detailfelder zunächst zugeklappt | bestanden |
| Aufklappen mit Tastatur, Datum/Warteperson/neues Projekt gemeinsam ändern | bestanden |
| Quellenstand wechselt: vorhandene Eingaben bleiben, Bestätigung gesperrt bis erneute Prüfung | bestanden |
| Speicherfehler und Wiederholung: identische Nutzdaten, Erfolg sichtbar | bestanden |
| Speicherfehler ohne vorheriges Bearbeiten: alte Vorgaben bleiben nach neuem Quellenstand erhalten | bestanden |
| Historische Mail ohne automatische Frist; Quellenentzug entfernt Bestätigung | bestanden |
| Keine horizontalen Überläufe; schmaler Bestätigungsknopf erreichbar | bestanden |
| Keine unerwarteten Konsolenfehler | bestanden; HTTP 500/409 absichtlich simuliert |

Screenshots wurden lokal geprüft. Der erste Ganzseitenscreenshot enthielt eine Capture-Wiederholung unterhalb des sichtbaren Bereichs; DOM-Prüfung zeigte genau einen Root und einen Hauptbereich. Für die visuelle Bewertung wurden danach Viewport-Aufnahmen einschließlich der schmalen Bestätigungsansicht verwendet. Die anfänglich zu enge Testauswahl für das Projektfeld wurde auf die tatsächliche einzelne Combobox korrigiert; keine Produktänderung dafür.

## Entscheidungen und verbleibende Abnahme

- Vorhandene Parser und Aufgabenidentität wiederverwenden. Preis der konservativen Fristbindung: ungewohnte Formulierungen landen häufiger in der Prüfung; sie werden nicht still als fristfrei übernommen.
- Dieses Paket verbessert gespeicherte Mails. Es ersetzt weder eine Prüfung des gesamten Postfachs noch Kalender-/Briefingabnahme. Native Macinstallation, normaler Updateweg, VoiceOver und tatsächliche Alltagsnutzung bleiben getrennte Nachweise.
- Keine neue Modellbewertung aus synthetischen Tests ableiten. Kein bezahlter Aufruf, keine Weitergabe persönlicher Quellen, keine Änderung der persönlichen App. Mistralqualität und Kosten müssen nach Einrichtung separat mit begrenzter Probe gemessen werden.
- Der Großimport bleibt pausiert. Die Funktion benötigt beim Blättern keine Modellarbeit.

## Reproduktion

Backend (Pythonumgebung mit Sidecar-Abhängigkeiten):

```sh
PYTHONPATH=sidecar python -m pytest -q sidecar/tests/test_local_mail_workflow.py sidecar/tests/test_local_mail_workflow_nonreentrant.py sidecar/tests/test_task_candidates.py sidecar/tests/test_task_candidate_retention.py sidecar/tests/test_task_deadline_review.py sidecar/tests/test_task_review.py sidecar/tests/test_aufgaben_frist_sicherheit.py sidecar/tests/test_aufgaben_von_selbst.py sidecar/tests/test_fristen.py sidecar/tests/test_fristen_formulierungen.py
```

Frontend in `app/kingfisher`: `npm test`, `npm run typecheck`, `npm run build`.

## Nachtrag: Wartezeit der synthetischen Importprüfung

Im GitHub-Lauf `41882043160` scheiterte der Python-3.12-Job ausschließlich an der Fünf-Sekunden-Wartezeit von `test_bulk_accepts_101_sources_after_pilot_and_uses_larger_budget` (10.034 weitere Tests bestanden, zwei übersprungen). Dieser Test und die Importimplementierung waren gegenüber `main` unverändert. Der Python-3.10-Job bestand.

Eine lokale Gegenprobe mit 30 ms zusätzlicher Verzögerung je künstlicher Providerantwort reproduzierte denselben Abbruch nach 5,17 s. Der beobachtete Worker beendete anschließend alle 101 Quellen mit genau 202 Antworten nach 9,29 s. Nur dieser große Test erhält deshalb bis zu 30 Sekunden Wartezeit; die anderen Aufrufe behalten fünf Sekunden. Produktzeitlimits, Anfragebudgets und Ergebnisprüfungen bleiben unverändert.

Dieselbe verzögerte Gegenprobe bestand danach in 9,57 s einschließlich aller vorhandenen Vollständigkeits- und Budgetprüfungen. Die gesamte betroffene Datei `sidecar/tests/test_cloud_memory.py` bestand mit 50 Tests in 9,42 s. Diese künstliche Verzögerungsprobe ist weder eine Erklärung der genauen CI-Auslastung noch ein Nachweis realer Cloudgeschwindigkeit. Der frühere rote CI-Lauf wird dadurch nicht als grün ausgegeben.
