# Nicht verfügbare lokale Antwortwahl: Einrichtung direkt sichtbar

11. Oktober 2026. Code `675ad8054d980313cca84c4b91a2523f5e3c2302`, bestehender Draft #54. Reine UI-Korrektur; **noch nicht persönlich installiert**. Die installierte App bleibt auf dem separat geprüften Paket `1.0.6-preview.45cb1c8`. Neuer nativer Fensternachweis bleibt offen: Computersteuerung fand den Mac wieder gesperrt.

## Beobachteter Fehler und Verhalten

Die Karte „Lokale KI“ klappte beim Laden bereits zu, sobald `setup.status.model` einen Namen enthielt. Auch ein fehlendes Modell oder gestopptes Ollama hatte diesen Namen; der ausführliche gemeldete Grund und vorhandene Alternativen blieben hinter „Modell verwalten“ verborgen.

Die anfängliche Entscheidung berücksichtigt jetzt die bestehende kanonische `lokale_ki`-Aussage: `keins`, `fehlt` und `nicht_erreichbar` öffnen die Einrichtung. Bereite lokale und eingerichtete Cloudantworten bleiben zunächst kompakt. Manuelles Schließen bleibt möglich. Keine neue Readiness-Definition, kein automatischer Modellwechsel oder Download; Speichern, Verbindungstest und Quellenstart brauchen weiter ihre eigenen Aktionen.

## Tatsächlicher gerenderter Gegenfall

Browser plugin not available; vorhandenes Playwright, tatsächliche React-Komponente auf `http://127.0.0.1:18762`, künstliche abgefangene HTTP-Antworten. Keine persönliche App, echte Backendkonfiguration, Mail, Kalender, Cloud oder Modellinferenz.

Auf Baseline `c4b6079` scheiterten genau die beiden Fälle „fehlt“/„nicht erreichbar“ am erwarteten sichtbaren Formular. Drei Erhaltungskontrollen bestanden: kein Modell offen, bereit/Cloud kompakt. Final bestehen alle fünf Zustände. Schließen/erneut öffnen funktioniert; im fehlenden Zustand ist das vorhandene Qwen9B ausdrücklich auswählbar, der manuelle Altmodell-Eingang verschwindet und „Auswahl geändert. Bitte verbinden.“ erscheint. **Kein schreibender API-Aufruf**, keine automatische Rollenänderung. Verbindungstaste in diesem Lauf bewusst nicht betätigt; deren vorhandener separater Verbindungsnachweis bleibt historisch.

| Prüfung | Ergebnis |
| --- | --- |
| URL/Titel und sinnvolle Anzeige | bestanden |
| Framework-Fehleroverlay | keines |
| Konsolenwarnungen/-fehler | keine |
| Erstansicht, Schließen/Öffnen, Auswahl | bestanden |
| Screenshot 1100×850 / 390×844 | erfasst und visuell gelesen; kein horizontaler Seitenüberlauf |
| Gesamte bestehende UI-Suite | 551 bestanden |
| Typprüfung, Produktionsbuild, Assetvertrag | bestanden |

Bestehende Bundlegrößenwarnung über 500 kB bleibt. Kein neuer Backend-Gesamtlauf für diesen UI-only-Diff. Unabhängiges enges statisches Review ohne konkreten Blocker; Reviewer führte den Renderer nicht aus. Testserver und Testbrowser anschließend beendet.

## Belege und Grenzen

`before.json`, `final.json`, `verification.json`, Treiber/Hostdateien und komprimierte Logs binden den engen Nachweis. Screenshots liegen außerhalb Git unter `/private/tmp/kingfisher-model-recovery-ui-20261011/final-fehlt.png` und `final-mobile.png`. Der erste Treiber wartete im Zustand „keins“ auf den falschen Hinweistext und wurde berichtigt. Ein zusätzlicher Lauf vermischte Status-Retry und sofortige Auswahl und wartete auf einen bereits überholten Text; der finale Lauf prüft Erstansicht und Auswahl ohne diesen gleichzeitigen Retry. **Status-Retry/Mehrfachinteraktionsrennen sind damit nicht allgemein abgenommen**; kein entsprechender Produktfix behauptet.

Diese Änderung macht einen bestehenden Erholungsschritt zugänglich. Sie installiert keine fehlenden Modellgewichte, löst nicht den noch unklaren nativen Dateidialog und beweist keine persönliche Gedächtnisqualität. Gepaarte Lieferung mit nächstem geeigneten Paket und persönlicher Bedienweg bleiben offen; großer Import weiterhin pausiert.
