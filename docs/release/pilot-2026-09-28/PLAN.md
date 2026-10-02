# Begleiteter Alltagspilot

Freigegebener Umfang: Gedächtnis, E-Mail, Kalender und Aufgaben. Der Nutzer startet mit Gegenprüfung in bisherigen Programmen. Neue echte Eingaben und Korrekturen müssen auch nach Updates erhalten bleiben. Ein einmaliger leerer Pilotbestand ist erlaubt; vorhandene Bestände bleiben als Rückfallkopie erhalten. Kein erneuter automatischer Reset. Ein separates App-Fenster ist zurückgestellt.

## Technische Abnahme

1. Die drei offenen Arbeitswochenfälle reproduzieren, gezielt beheben, unabhängige Gegenprüfung und unveränderten lokalen Modelllauf durchführen. Keine allgemeine Fehlerfreiheit aus elf Fragen ableiten.
2. Einen gemeinsamen synthetischen Ablauf durch Postfach, Quellen, Aufgaben, Projekt, Kalender, Briefing, Gespräch und Neustart prüfen. Tatsächliche externe Kontoanbindung und Versand bleiben gesonderte Abnahmen.
3. Aktuelles Docker-Image bauen, Wiederanlauf und Sicherung/Wiederherstellung auf getrennten Beständen prüfen. Danach einen einmalig leeren, dauerhaft benannten Pilotbestand bereitstellen und Startweg dokumentieren. Kein Testskript darf spätere Nutzerdaten löschen.

Zusätzlich: größere synthetische Bestände mit dem vorhandenen Lasttest prüfen. Dieser misst Index/Suche ohne Modell-Einordnung und ist kein Vollnachweis beliebiger großer Archive.

## Nach technischer Bereitstellung

- Konten nacheinander verbinden: zwei Gmail-Konten und ein ALL-INKL-Konto; mehrere Kalender, ein beobachteter Kalender ohne Schreibzugriff. Zugangsdaten werden durch den Nutzer eingegeben, nicht in Git gespeichert.
- Erst kleine, ausgewählte Bestände und dann größere Mengen importieren; Fortschritt, Fehler und Antwortbelege gegenprüfen.
- Mehrere echte Arbeitstage sind eine offene Produktabnahme. Sie werden nicht durch synthetische Testtage ersetzt.
- Externe Nachrichten/Einladungen nur mit konkret sichtbarer Freigabe; keine Übernahme der alleinigen Fristenverantwortung während des Piloten.
