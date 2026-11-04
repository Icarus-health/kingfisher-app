# Wiederholte Arbeitskorrekturen: kontrollierter Lernweg

Stand: 04.11.2026. Teilpaket P2 auf der geprüften Oberfläche aus PR119; keine vollständige Produkt- oder Modellabnahme.

## Verhalten

Eine eigene Antwortkorrektur kann ausdrücklich als Arbeitsweise markiert werden. Erst mindestens drei verschiedene passende Aufträge führen zur begrenzten lokalen Prüfung. Ihr Ergebnis bleibt ein inaktiver Ablaufvorschlag. Fakten-, Namens-, Datums- und reine Tonkorrekturen sind kein Arbeitsablauf. Die bestehenden Kategorien, Beispiele, Versionsprüfung und Aktivierung werden weiterverwendet. Quellen, Akten und bestätigte Fakten bleiben unverändert.

Vorschläge zeigen ihre eigenen Ausgangskorrekturen mit Gesprächslinks. Lernfreigabe und Vorschlagsstatus sind nach erneutem Öffnen erreichbar. Die Rücknahme braucht nur die Kennung, bewahrt die ursprüngliche Fehlermeldung und macht abhängige Vorschläge beziehungsweise aktive Verfahren ungültig. Ablehnungen werden nicht aufgrund derselben Belege erneut angeboten.

## Review und Tests

Ein unabhängiges Review fand zwei relevante Lücken: Änderungen am bestehenden Skillkatalog während der Modellprüfung waren nicht gebunden; der Rücknahmezugang ging beim erneuten Öffnen verloren. Beide sind behoben. Die drei zunächst fehlschlagenden Backend-Regressionsfälle sind grün; ergänzende UI- und HTTP-Fälle prüfen Wiederöffnung, Rücknahme, Wiederholung, Fehlerbehandlung und ausgeblendete veraltete Korrekturtexte.

- Zunächst 204/204 betroffene Backendtests; nach den echten Modell- und Reviewkorrekturen 220/220 bestanden (36,23 s).
- 1033/1033 Oberflächentests bestanden (13,77 s).
- TypeScript/Vite-Build und Assetvertrag bestanden (11 Dateien, 14 Icons).
- Bestehende Hinweise: TestClient/httpx-Abkündigung und große Vite-Ausgabedatei.

Befehle: `python -m pytest sidecar/tests/test_workflow_learning.py sidecar/tests/test_procedure_model.py sidecar/tests/test_procedure_runtime.py sidecar/tests/test_procedures.py sidecar/tests/test_procedure_categories.py sidecar/tests/test_procedure_choice.py sidecar/tests/test_chat_procedure_choice.py sidecar/tests/test_mail_procedure_choice.py sidecar/tests/test_rueckmeldung.py sidecar/tests/test_complete_recovery.py -q`, im UI-Verzeichnis `npm test` und `npm run build`, danach `python3 scripts/check_asset_manifest.py`.

## Bedienprüfung

Getrennter lokaler Testbestand, ausschließlich künstliche Nachrichten, simulierter Modellanbieter. IAB bei 1280 × 720 und 900 × 800. Geprüft: drei Korrekturen markieren und speichern; Vorschlag nach Neuladen wiederfinden; drei Herkunftsgespräche öffnen; Lernfreigabe zurücknehmen; veralteten Vorschlag erneut öffnen. Danach ist Übernehmen deaktiviert und die Herkunftskorrekturen sind ausgeblendet. Keine relevanten Browserwarnungen oder Fehler im geprüften Lauf.

Das echte Mac-Testfenster enthielt noch einen ungespeicherten künstlichen Entwurf. Das automatische Freigabesystem blockierte daher sein Neuladen. Ohne weitere Freigabe blieb dieser Zustand unverändert; keine neue native Abnahme behaupten.

## Echte lokale Lernprobe und Korrekturen

Die getrennte Probe verwendet zwei feste künstliche Gruppen mit je drei Korrekturen,
denselben Qwen9B-Digest und den tatsächlichen Produkttransport. Keine eigenen Mails,
Cloudaufrufe oder Änderungen an der persönlichen App. Wiederholbarer Aufruf:

```sh
python scripts/probe_workflow_learning.py /tmp/kingfisher-learning-new.json
```

Der vorhandene Alias `kingfisher-qwen3.5:9b-8k` wird vor und nach Aufrufen geprüft.
Mindestens 55 % Startreserve, Stopp unter 25 % oder bei Speicherdruckstufe 4;
höchstens vier Modellaufrufe und drei Minuten insgesamt. Vorhandene Ausgabedateien
werden nicht überschrieben. Die Probe aktiviert und entzieht einen Vorschlag nur
innerhalb ihres eigenen temporären künstlichen Bestands.

| Lauf | Beobachtung |
|---|---|
| 1–2 | Speichergrenze erreicht; keine Qualitätsabnahme. Modell lieferte zusätzlich fehlendes Spec bzw. nicht abrufbare Auswahlbeispiele. |
| 3 | Ressourcen eingehalten und Mailablauf richtig; Modell verwandelte aber konkrete Namens-/Datumsfehler in einen falschen Skill-Vorschlag. |
| 4 | Derselbe Mailablauf richtig; Fakten-Gegenfall ohne Modellarbeit abgewiesen. |
| Abschluss | Nach zusätzlichen Reviewkorrekturen beide Fälle bestanden: 22,33 s für Vorschlag, Annahme, passenden Abruf, privaten Gegenfall und Entzug; 0,43 s für die drei Faktenkorrekturen ohne Modellaufruf. Insgesamt 22,96 s, geringste freie Reserve 28 %, höchster Speicherdruck 2. |

[Vergleich mit fehlgeschlagenen Läufen, Antworten und Codeprüfsummen](qwen-learning-comparison.json).
Der endgültige Antworttext wurde zusätzlich gelesen: Er enthält die wiederholten
Prüfschritte und keine erfundenen Personen oder Daten. Das ist eine schmale
Lernprobe, keine repräsentative Abnahme des ganzen Gedächtnisses oder der Mac-Bedienung.

Die Reparatur erlaubt höchstens eine Ergänzung einer unvollständigen oder nicht
abrufbaren Synthese im selben unverlängerten 60-Sekunden-Budget. Ein gemeinsames
„prüfe“ oder derselbe Auftragskontext genügt nicht als Wiederholungsbeleg. Konkrete
Datums-, Adress- und bestimmte Faktenformulierungen bleiben außerhalb automatisch
gelernter Verfahren. Diese konservative Vorprüfung ist keine allgemeine
Entitätserkennung; unterschiedliche Formulierungen desselben Ablaufs können zu
keinem Vorschlag führen. Nutzerprüfung und Herkunft bleiben deshalb erforderlich.

Das zusätzliche unabhängige Review reproduzierte zwei Umgehungen: ältere gespeicherte
Vorschläge und elliptische Fakten wie „morgen statt heute“. Die permanenten
Regressionen waren zunächst rot und sind grün. Bereits gespeicherte automatische
Verfahren werden auch vor Wiederverwendung, Aktivierung und Auswahl geprüft;
ihre Historie bleibt unverändert. Die neue Lernprüfung verwendet einen eigenen
Cache-Schlüsselstand. Die zusätzliche Überprüfung der begrenzten Nachbesserung
bestätigte Quellentzug im zweiten Aufruf, Werkzeugabwehr und engere Zeitfristen.

Offener Leistungsbefund: Die bestehende nachgelagerte Ollama-Retention-Anfrage
läuft in diesen Proben nach drei Sekunden in einen Timeout, obwohl die eigentliche
Antwort erfolgreich war. Das ist gemessen; eine Ursache für die früheren
Speicherausschläge ist damit nicht bewiesen. Der Transport wurde deshalb hier
nicht spekulativ umgebaut.

## Grenzen

Keine echten Qwen-Aufrufe in dieser Bedienprüfung, keine Cloudaufrufe, kein persönlicher Bestand und kein Großimport. Die schmale Modellprobe oben ersetzt keine repräsentative lokale Modellqualität, Dauerlast-, Schlaf-/Prozessabbruch-, VoiceOver-, 200%-Zoom- oder Alltagswochen-Abnahme. Drei ähnliche Korrekturen sind eine konservative Schwelle, kein Beweis einer universell richtigen Regel. Persönlicher Kommunikationston bleibt im vorhandenen Kontaktstil; es entsteht kein Skill je Aktenname. Dieses Teilpaket ist noch nicht in der persönlichen Mac-App installiert.
