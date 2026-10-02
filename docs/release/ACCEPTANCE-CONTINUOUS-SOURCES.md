# Abnahme 09: fortlaufende Quellenaufnahme

Stand: 8. September 2026. **15 von 20 Abnahmepunkten erfüllt = 75 %.**
Dies ist eine Abnahme der beschriebenen Quellenaufnahme, keine Zeitprognose
und keine vollständige visuelle Produktabnahme.

## Echte Mailquelle auf dem Mac

Der Nutzer hat ein ALL-INKL-Postfach ausdrücklich ausgewählt und dessen
Passwort selbst in Kingfisher gespeichert. Die Prüfung verwendete den echten
lokalen Docker-Bestand, keine simulierte Mailantwort. Zugangsdaten und
Mailinhalte werden hier nicht veröffentlicht.

- Der authentifizierte Posteingangsabruf lieferte eine echte Nachricht.
- Der erste ausgewählte Aufnahme-Lauf speicherte 50 neue Nachrichten als
  Quellen und meldete Erfolg ohne Fehler.
- Eine bereits aufgenommene Nachricht wurde über den normalen Aufnahme-Endpunkt
  zweimal erneut abgerufen: dieselbe Episoden-ID, jeweils `new=false`.
- Der automatische Zeitplan wurde auf 15 Minuten gesetzt. Nach einem echten
  Containerneustart blieben Kontenauswahl, Zugang, Erfolgsstatus und Zeitplan
  erhalten. Eine erneute Aufnahme derselben Nachricht blieb ohne Dublette.
- Ein weiterer Lauf nach dem Neustart nahm weitere 50 Nachrichten auf,
  statt mit den ersten Nachrichten von vorn zu beginnen. Der nächste
  automatische Lauf war terminiert. Der bestehende Cursor setzt die
  schrittweise Aufnahme mit maximal 50 Nachrichten je Lauf fort.
- Es wurden keine E-Mails versendet. Die bestehende Modellnutzung im Zeitplan
  blieb ausgeschaltet; Mailaufnahme bedeutet keine automatische Bestätigung
  von Wissensaussagen.

## Kalender und ausgewählter Ordner

Die fortlaufende Aufnahme freigegebener Mac-Kalender und deren stabile
Instanz-Identitäten wurden bereits geprüft. Im aktuellen Nutzerbestand ist
auch nach dem Neustart der ausgewählte Mac-Kalender erreichbar.

Der ausdrücklich neu angelegte Eingangsordner ist aktiviert. Sein leerer
Erstlauf war fehlerfrei. Text/VTT, Unterordner, Dateifassungen, Entzug,
Dubletten, Teilausfall, Pause und Neustart sind mit synthetischen Quellen
im isolierten Docker und einem tatsächlichen Mac-Ordnerhelfer geprüft:
[FOLDER-SYNC-QA.md](FOLDER-SYNC-QA.md). Testdateien wurden nicht in den
persönlichen Eingangsordner gelegt. Die gemeinsame Quellen-Lebenszyklusabnahme
steht in [ACCEPTANCE-SOURCES.md](ACCEPTANCE-SOURCES.md).

## Grenzen / nächste Schritte

Ein zweites, vom Nutzer ausgewähltes Gmail-Konto ist zur Einrichtung
vorbereitet, aber noch nicht authentifiziert. Das ersetzt keine Abnahme des
bereits erfolgreich geprüften ALL-INKL-Kontos und wird nicht als fertig gemeldet.

Die vollständige visuelle Abnahme (Punkt 16), befüllte Personen-/Projektakten
(Punkt 07), Docker-Desktop-Abnahme sowie übrige offene Punkte der Roadmap
bleiben separat offen. Vorhandene Nachrichten werden schrittweise eingelesen;
100 aufgenommene Nachrichten bedeuten keine vollständige Postfachmigration.
