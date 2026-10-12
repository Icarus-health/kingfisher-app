# Persönlicher Kernablauf auf dem Mac

12. Oktober 2026. Geprüfte Installation: `1.0.6-preview.b7cd321`. Der Nutzer hat den entsperrten Mac, das vorhandene Qwen9B und die Prüfung von Mail, Gedächtnis, Aufgaben und Kalender ausdrücklich freigegeben. Dies ist ein begrenzter tatsächlicher Bediennachweis, keine vollständige Alltags- oder Gedächtnisabnahme.

## Tatsächlich geprüft

| Bereich | Beobachtung | Ergebnis |
|---|---|---|
| Native Sitzung | Alte Sitzung beendet, installierte App frisch geöffnet. Der bewusste native Knopf startet das vorhandene Ollama. | Neuer Fensterstart geprüft; kein Modelldownload. |
| Lokale Antwortwahl | `kingfisher-qwen3.5:9b-32k` über „Speichern und verbinden“ ausgewählt. Bereitschaftstest 6,5 Sekunden. Zusätzlich tatsächliche wirksame Rollen lesend geprüft: Frage und Antwort verwenden diese lokale Wahl; kein Ollama-Cloudweg. | Verbindung bestanden; keine Aussage über Antwortqualität. |
| Mail aufnehmen | Eine gewöhnliche vergangene Veranstaltungsmail geöffnet und ausdrücklich als Quelle gemerkt. Originaldatum und heutige Erfassung erscheinen getrennt. | Original als Rohmaterial erhalten, kein bestätigter Fakt daraus gemacht. |
| Aufgabe aus Mail | Eine ausdrücklich als Funktionstest bezeichnete Aufgabe ohne Fälligkeit gespeichert. Seitenwechsel, direkter Originalbeleg, Abschluss und Anzeige unter „Erledigt“ geprüft. | Eine Testaufgabe samt Quelle erhalten; keine erfundene Frist, kein Versand. |
| Gedächtnisfrage | Zwei lokale Fragen zur gerade gespeicherten Mail, eine ausführliche und eine kurze Kontrollfrage. Beide Antworten melden `selection_failed` und enthalten keinen Beleg. | **Nicht bestanden.** Je rund 37 Sekunden: Frage ca. 6, Suche 0,3–0,4, Auswahl ca. 30 Sekunden. |
| Kalender | Nach neuer Sitzung zunächst ausstehende Freigabe; Anfrage über Kingfisher geöffnet. macOS-Einstellungen zeigen bestehenden Vollzugriff. Danach frische Anzeige mit drei ausgewählten Kalendern. Die zwei heutigen Termine samt Beginn/Ende im tatsächlichen Mac-Kalender und in Kingfisher verglichen. | Heutiges Zeitfenster stimmt überein. Kein Nachweis sämtlicher Konten, Serien oder Zeiträume. |
| Pausierter Betrieb | Mailaufnahme und Hintergrundverarbeitung bleiben in der UI pausiert; globale Pause zusätzlich per Produkt-API geprüft. Abschließend meldet Ollamas `/api/ps` keine geladenen Modelle. | Großen Import nicht fortgesetzt. Keine Akku- oder Tagesmessung daraus ableiten. |

Die Diagnose der Antworten enthält jeweils 16 Einträge in `basis` und 64 Einträge in `candidate_signature`; Bedeutungssuchstatus `partial`. Diese Felder beweisen weder vollständige Suche noch die Eignung der Kandidaten. Der Auswahlfehler ist reproduziert, seine Ursache noch nicht abschließend belegt. Eine bloße Erhöhung von Zeitlimits oder vorsichtig klingende Nichtantwort wäre keine Abnahme des Abrufs.

Persönliche Mailtexte, Screenshots, Belegkennungen, Einwahldaten und Zugriffsschlüssel werden hier nicht veröffentlicht. Die Quelle, die abgeschlossene Testaufgabe und das lokale Testgespräch bleiben auf dem Mac erhalten. Keine Mail versendet, Kalendertermine verändert, Cloudverarbeitung gestartet oder Originale gelöscht. Kingfisher wurde in der geprüften Kalenderansicht hinterlassen.

## Gefundener Zeitzonenfehler und vorbereitete Korrektur

Die Heute-Terminkarte zeigte die richtige lokale Uhrzeit, ihr Briefing-Satz jedoch die zwei Stunden frühere UTC-Uhrzeit. Der Morning-Endpunkt löst die Nutzerzone korrekt auf; sein verschachtelter Dashboard-Aufruf verwendete für den Satz erneut die Containerzeit. Ein interner Datenhelfer gibt nun dieselbe aufgelöste Zeit an beide Ansichten weiter; die öffentliche Dashboard-Signatur bleibt unverändert.

Der unabhängige Review fand zusätzlich eine dadurch betroffene Aufgabenlücke um Mitternacht. Vollständig zeitzonenbehaftete Fälligkeiten werden jetzt vor dem Tagesvergleich in die Briefing-Zone umgerechnet. Reine Datumsangaben und zeitzonenlose Angaben behalten ihren geschriebenen Tag.

Neue tatsächliche Endpunktfälle waren vor der jeweiligen Korrektur rot: Sommer, Winter, Kalender-Tageswechsel sowie lokale Heute-/Morgen-/Gestern-Abgrenzung bei UTC-Fälligkeiten. Enger unabhängiger Abschlussreview ohne verbleibenden konkreten Befund; dieser Review führte keine eigenen Modell- oder Liveprüfungen aus.

Root-Nachprüfung:

```text
PYTHONPATH=sidecar /private/tmp/kingfisher-question-model-venv-20261011/bin/python -m pytest -q sidecar/tests/test_briefing_zeitzone.py sidecar/tests/test_urteil.py sidecar/tests/test_briefing.py sidecar/tests/test_briefing_task_candidates.py sidecar/tests/test_morning_source_dates.py
53 passed, 1 warning in 5.40s
```

Bestehende Starlette/httpx-Abkündigungswarnung; kein vollständiger Backend- oder UI-Neulauf. Finaler Laufzeit-/Testdiff vor Dokumentation SHA-256: `8628a69ccc9b26e3ac3c06f206d5b8690d74c00778720c902bdb278bb34abe16`.

**Die Zeitzonenkorrektur ist Quellcode, noch kein neues geprüftes oder installiertes Paket.** Auf dem Mac bleibt `b7cd321`. Vor weiterer Freigabe: den konkreten lokalen Auswahlfehler beheben und nachmessen, anschließend ein gemeinsam geprüftes Paket mit Sicherung installieren und denselben persönlichen Weg erneut prüfen. Kein Main-Merge, öffentlicher Updater oder GitHub-CI-Neustart.
