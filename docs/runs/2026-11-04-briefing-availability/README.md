# Tagesbriefing: Ausfälle und verspätete Antworten

## Beobachtete Fehler

Eine bereits geladene Tageslage blieb bei einem fehlgeschlagenen Nachladen ohne
Warnung stehen. Ein alter paralleler Abruf konnte außerdem eine nachweislich
abbestellte Weltquelle wieder anzeigen. Nach Verlassen der Ansicht konnte eine
späte Antwort erneut einen Hintergrundtimer anlegen.

Die tatsächliche Tagesbriefing-Route übersah einen Teilausfall der
Kalendersammlung: Ein gesunder leerer Kalender neben einem ausgefallenen
Kalender ergab einen vermeintlich vollständig leeren Tag. Die Morning-Route
versprach zudem den nächsten Termin innerhalb einer Woche, erhielt durch ihr
eigenes Abfragefenster aber nur einen Tag. Ein Termin in drei Tagen fehlte dort,
obwohl dieselbe Kalenderquelle ihn in der Wochenansicht lieferte.

## Begrenzte Korrektur

- Ein fehlgeschlagenes Nachladen kennzeichnet den letzten Stand und bietet
  direkt „Erneut versuchen“. Ein unvollständig geprüfter leerer Tag behauptet
  nicht, dass nichts anliegt. Gespeicherte Inhalte bleiben lesbar.
- Nur die neueste laufende Anfrage darf den angezeigten Stand ersetzen.
  Automatische Takte häufen keine Abrufe an; nach dem Verlassen werden weder
  Zustände geschrieben noch neue Timer gestartet. Stilles Nachladen und
  Wiederholen verändern nicht den Logbuch-Marker „letzter Blick“.
- Das Tagesbriefing verwendet Termine und Fehler desselben Kalenderabrufs.
  Erreichbare Termine und lokale Fristen bleiben bei einem Teilausfall erhalten.
  Die öffentliche Terminlesefunktion für Mitteilungen behält ihren bisherigen
  Fehlervertrag bei Totalausfall.
- Die Morning-Route fordert das vorhandene, auf sieben Tage begrenzte Fenster
  an. Künftige Termine werden weiterhin nicht als heutige Termine ausgegeben.

## Prüfung

Nur künstliche Daten, keine Anbieter- oder Modellaufrufe. Die sieben neuen
Frontendfälle prüfen reale Komponentenhandler mit kontrollierten Antworten
und Timern, keine Browserbedienung. Die Backendfälle nutzen die tatsächlich
registrierten API-Routen und echte lokale Teststores/Kalendersammlung.

- Erste fünf Frontend-Gegenproben vor der Korrektur: **5 fehlgeschlagen**.
  Danach sieben Fälle einschließlich verzögerter Fehler und Abrufbegrenzung
  bestanden. Angrenzender UI-Lauf: **59 bestanden**.
- Vollständige UI: **1.114/1.114 bestanden**. Produktionsbuild bestanden;
  bestehende Bundlegrößenwarnung unverändert.
- Zwei ursprüngliche Backend-Reproduktionen fehlgeschlagen. Im erweiterten
  ersten Satz vier Fehler und zwei erfolgreiche Gegenkontrollen. Zusätzlich
  zeigte eine neue Gegenprobe die versehentliche Änderung des Fehlervertrags
  für Mitteilungen; vor Abschluss korrigiert.
- Betroffene Backend-Suite: **151 bestanden**. Die sieben neuen Routen- und
  Kompatibilitätsfälle sind darin enthalten; Zahlen werden nicht addiert.

Gezielt wiederholen:

```sh
python -m pytest sidecar/tests/test_briefing_calendar_availability.py -q
cd app/kingfisher
node --experimental-strip-types --test tests/tageslage-refresh.test.mjs tests/daily-flow.test.mjs
npm test
npm run build
```

Die zugehörigen Quellprüfsummen und unabhängigen Review-Ergebnisse stehen in
`validation.json`. Native Bedienprüfung und persönliches Update bleiben offen.
Die neue Fassung ist weder Modellqualitätsnachweis noch Alltagsabnahme. Der
Großimport bleibt pausiert. Der ausstehende Zugang zum getrennten nativen
Produkt-Testfenster wird nicht über einen anderen Browser umgangen.
