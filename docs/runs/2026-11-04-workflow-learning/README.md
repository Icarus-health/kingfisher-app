# Wiederholte Arbeitskorrekturen: kontrollierter Lernweg

Stand: 04.11.2026. Teilpaket P2 auf der geprüften Oberfläche aus PR119; keine vollständige Produkt- oder Modellabnahme.

## Verhalten

Eine eigene Antwortkorrektur kann ausdrücklich als Arbeitsweise markiert werden. Erst mindestens drei verschiedene passende Aufträge führen zur begrenzten lokalen Prüfung. Ihr Ergebnis bleibt ein inaktiver Ablaufvorschlag. Fakten-, Namens-, Datums- und reine Tonkorrekturen sind kein Arbeitsablauf. Die bestehenden Kategorien, Beispiele, Versionsprüfung und Aktivierung werden weiterverwendet. Quellen, Akten und bestätigte Fakten bleiben unverändert.

Vorschläge zeigen ihre eigenen Ausgangskorrekturen mit Gesprächslinks. Lernfreigabe und Vorschlagsstatus sind nach erneutem Öffnen erreichbar. Die Rücknahme braucht nur die Kennung, bewahrt die ursprüngliche Fehlermeldung und macht abhängige Vorschläge beziehungsweise aktive Verfahren ungültig. Ablehnungen werden nicht aufgrund derselben Belege erneut angeboten.

## Review und Tests

Ein unabhängiges Review fand zwei relevante Lücken: Änderungen am bestehenden Skillkatalog während der Modellprüfung waren nicht gebunden; der Rücknahmezugang ging beim erneuten Öffnen verloren. Beide sind behoben. Die drei zunächst fehlschlagenden Backend-Regressionsfälle sind grün; ergänzende UI- und HTTP-Fälle prüfen Wiederöffnung, Rücknahme, Wiederholung, Fehlerbehandlung und ausgeblendete veraltete Korrekturtexte.

- 204/204 betroffene Backendtests bestanden (37,20 s).
- 1033/1033 Oberflächentests bestanden (13,77 s).
- TypeScript/Vite-Build und Assetvertrag bestanden (11 Dateien, 14 Icons).
- Bestehende Hinweise: TestClient/httpx-Abkündigung und große Vite-Ausgabedatei.

Befehle: `python -m pytest sidecar/tests/test_workflow_learning.py sidecar/tests/test_procedure_model.py sidecar/tests/test_procedure_runtime.py sidecar/tests/test_procedures.py sidecar/tests/test_procedure_categories.py sidecar/tests/test_procedure_choice.py sidecar/tests/test_chat_procedure_choice.py sidecar/tests/test_mail_procedure_choice.py sidecar/tests/test_rueckmeldung.py sidecar/tests/test_complete_recovery.py -q`, im UI-Verzeichnis `npm test` und `npm run build`, danach `python3 scripts/check_asset_manifest.py`.

## Bedienprüfung

Getrennter lokaler Testbestand, ausschließlich künstliche Nachrichten, simulierter Modellanbieter. IAB bei 1280 × 720 und 900 × 800. Geprüft: drei Korrekturen markieren und speichern; Vorschlag nach Neuladen wiederfinden; drei Herkunftsgespräche öffnen; Lernfreigabe zurücknehmen; veralteten Vorschlag erneut öffnen. Danach ist Übernehmen deaktiviert und die Herkunftskorrekturen sind ausgeblendet. Keine relevanten Browserwarnungen oder Fehler im geprüften Lauf.

Das echte Mac-Testfenster enthielt noch einen ungespeicherten künstlichen Entwurf. Das automatische Freigabesystem blockierte daher sein Neuladen. Ohne weitere Freigabe blieb dieser Zustand unverändert; keine neue native Abnahme behaupten.

## Grenzen

Keine echten Qwen-Aufrufe in dieser Bedienprüfung, keine Cloudaufrufe, kein persönlicher Bestand und kein Großimport. Die lokale Modellqualität, Ressourcenlast, Schlaf-/Prozessabbruch, VoiceOver, 200%-Zoom und eine Alltagswoche sind damit nicht abgenommen. Drei ähnliche Korrekturen sind eine konservative Schwelle, kein Beweis einer universell richtigen Regel. Persönlicher Kommunikationston bleibt im vorhandenen Kontaktstil; es entsteht kein Skill je Aktenname. Dieses Teilpaket ist noch nicht in der persönlichen Mac-App installiert.
