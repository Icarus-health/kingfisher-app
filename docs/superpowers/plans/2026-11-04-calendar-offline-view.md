# Kalender: geladene Termine bei einem Providerfehler behalten

Begrenztes P3-Paket auf main `1b5a262`. Vorangegangener Zielturn lieferte PR122; hier wird dessen unabhängiger Branch nicht verändert. Aktuelle persönliche Leseprobe: 18 Termine aus zwei sichtbaren Quellengruppen, fünf nachgewiesene Spiegelgruppen, keine ähnlichen unzusammengefassten Paare im Zweiwochenfenster. Kein Termin geändert.

## Vertrag

Fällt ein einzelner Kalenderanbieter aus, bleiben seine bereits geladenen Termine im selben Zeitraum als ausdrücklich ungeprüfte Vorschau sichtbar. Frische andere Kalender bleiben aktuell. Ein erfolgreich leer gelesener Kalender ersetzt die alte Liste; nur ein ausdrücklich gemeldeter Quellenausfall darf alte Einträge erhalten. Entfernte Kalender, geänderte Zugänge und geänderte Mac-Kalenderfreigaben entwerten alte Vorschauen. Ein anderer Zeitraum darf keine alten Termine übernehmen.

Der Server liefert pro Antwort einen undurchsichtigen Lesekontext, die ausgefallenen Quellen und den Lesezeitpunkt. Dies erweitert den bestehenden Kalenderweg; kein zweites Gedächtnis, keine Provider- oder Modellaufrufe zusätzlich zum vorhandenen Kalenderabruf. Die Oberfläche hält ausschließlich ihre bereits geladene Ansicht vor; daraus werden keine Kalenderaktionen oder Vorbereitung gestartet. Eine erneute erfolgreiche Abfrage ersetzt die Vorschau.

Dies ist die Fehlerbehandlung einer offenen Kalenderansicht, kein persistenter Offlinekalender nach App-Neustart. Vorhandene Mac-Snapshots und Terminoriginale bleiben unverändert; ein persistenter Anzeigeweg bleibt P3/P5-Arbeit und wird mit dieser Lieferung nicht als erledigt markiert.

## Schritte

- [x] Providerfehler/erfolgreich leer/Entzug/Quellenwechsel/In-flight-Änderung im Backend reproduzieren.
- [x] Antwortgebundene Lesemetadaten liefern, unveränderte Modell- und Gedächtniswege beibehalten.
- [x] Quellenweise Vorschau in derselben Ansicht mit Alter und gesperrten Aktionen; echte Gegenfälle für Spiegelkopien und Zeitraumwechsel.
- [x] Betroffene Tests, vollständige UI-Suite, unabhängiges Review und künstliche gerenderte Bedienprüfung.
- [ ] GitHub-Lieferung; native Prüfung und normale Installation bleiben getrennt.

## Review Focus

Quellenänderung während eines langsamen Abrufs; getrennter Kalender taucht aus der Vorschau wieder auf; erfolgreiche leere Liste gilt fälschlich als Ausfall; alte Spiegelkopie bekommt Rechte der frischen Kopie; Zeitraumwechsel übernimmt fremde Daten; stale-Eintrag startet Vorbereitung oder Schreiben; Fehler einer Quelle überschreibt den Status einer parallelen Abfrage.
