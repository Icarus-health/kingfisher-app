# Durchgehender Alltagsablauf · 7. Oktober 2026

Ausgangsstand: `0a683ec`, Kingfisher 1.0.3. Fassung dieser Lieferung: 1.0.4.

## Verhalten

Heute zeigt Quellenlücken, Zeitpunkt und Aktualisierung direkt oben. Sichtbare Mails öffnen den vorhandenen Leser direkt. Eine begrenzte zweite lokale Modellprüfung bewertet Kandidaten im vollständigen Mailkontext: aktuelle Bitte, eigene Zusage mit bekannter Absenderidentität, fremde Zusage, Information, Marketing oder unklar. Ein wörtliches Zitat allein genügt nicht. Es bleiben Modellvorschläge.

Ein ausdrücklicher Klick übernimmt einen Vorschlag als lokale Aufgabe samt Originalbeleg; Datum, Projekt und wartende Person bleiben frei. Dieselbe direkte Übernahme ist über erneute Anfragen/Neustarts hinweg idempotent. Quellenänderungen werden erneut geprüft. Ein bearbeiteter Dialog bleibt unabhängig von wechselnden Heute-Leerzuständen erhalten. Versand bleibt im vorhandenen Freigabeablauf.

## Prüfung

- Betroffener Backend-Satz: 122 bestanden. Einschließlich Quellengleichheit, Widerruf während beider Modellaufrufe, Entzug der eigenen Absenderidentität, nachträglicher Kürzungsmarkierung, fehlerhafter Prüfung, Cache und direkter Aufgabenübernahme.
- Oberfläche: 292 Tests bestanden; Typecheck und Produktionsbuild bestanden. Bestehende Warnung über die Bundlegröße bleibt. Asset-Vertrag: 16 Dateien/15 Icons bestanden.
- Unabhängiger Review fand und reproduzierte fünf Fehler plus zwei Folgefälle. Korrekturen mit roten/grünen Regressionen; abschließender gezielter Review: 51 Backendtests bestanden, keine verbleibenden wichtigen Befunde in den korrigierten Stellen.
- Vollständige Backendregression: Ergebnis wird nach Abschluss ergänzt. Ein erster Sandboxlauf hatte gesperrte lokale Testsockets/Swift-Zugriffe sowie drei anzupassende Extraktions-Fixtures; der finale Lauf verwendet die erforderlichen lokalen Testrechte.
- Echtes installiertes lokales Modell `kingfisher-qwen3.5:9b-32k`, eigene Testinstanz auf Port 8893, ausschließlich acht erfundene Mails: drei konkrete Bitten angeboten, fünf Gegenbeispiele ohne eigene Aufgaben. Siehe `model-cases.jsonl`. Ein zuvor übersehener Kandidat wurde wegen seiner abstrakten Titelparaphrase abgelehnt; präzisere Tätigkeitsformulierung im Extraktionsprompt behebt dieses Beispiel. Keine Sonderbehandlung eines Betreffs oder Namens. Das ist ein kleiner Entwicklungssatz, keine allgemeine Präzisionsmessung. Frische Modellabrufe im abschließenden Lauf benötigten etwa 6–36 Sekunden; Cachetreffer etwa 0,07 Sekunden.
- Native Mac-Test-App: Heute meldet fehlenden Kalender ausdrücklich; Mail direkt geöffnet; Aufgabe mit einem Klick gespeichert; beide Übernahmeknöpfe danach gesperrt; Aufgabenliste zeigt genau die übernommene Aufgabe ohne Termin/Projekt; Quellenansicht enthält wörtliche Stelle und vollständige Originalmail. Zusätzlicher nativer Ausfalltest: verzögerter HTTP-200-Abruf entfernt alle Heute-Zeilen und meldet künstlichen Mailfehler; währenddessen eingegebener Aufgabentitel bleibt im offenen Dialog unverändert, danach ist die leere Fehleransicht sichtbar. Kein Entwurf wurde gespeichert. Screenshot und Accessibility-Ergebnis im Arbeitsgespräch geprüft.

## Grenzen und Bestand

Foreground höchstens drei Kandidaten; Hintergrund bis zu 31 pro Extraktionsschritt, gemeinsam geprüft. Vollständiger Prüfkontext höchstens 20.000 Zeichen, Gesamtpayload höchstens 40.000 Zeichen, Ausgabebudget höchstens 1.200 Token. Unvollständige oder zu große Kandidatengrundlagen werden nicht als erfolgreicher Aufgabencheck gespeichert. Ein längerer Segmentierungs-Test bleibt oberhalb des bisherigen 8.000-Zeichen-Ausschnitts; ein zusätzlicher über 20.000 Zeichen verlangt ausdrücklich keinen Erfolgscheckpoint. Große Datenbestände bedeuten viele einzelne Quellen; beliebig lange Einzelmails sind damit nicht vollständig abgenommen.

Die bestehende requests-v3-Auswertungsversion wird nicht angehoben. Alte erledigte Auswertungen und offene Kandidaten sind durch dieses Update nicht nachträglich geprüft; keine vollständige Neuauswertung und kein Datenreset. Originale und bestätigte Aussagen werden nicht umgeschrieben. Bestehende Quellenansichten bleiben der Einstieg für Wissensprüfung; eine neue allgemeine Kläransicht wird nicht hinzugefügt.

Reale Kalenderanmeldung und Postfachvollständigkeit sind keine Ergebnisse dieser künstlichen Prüfung. Im Ausgangspiloten fehlte die Kalenderverbindung. Mistral/OpenRouter bleiben vorbereitet und ausgeschaltet; keine echten Quellen wurden an Cloudmodelle übertragen und keine kostenpflichtigen Modellaufrufe ausgelöst.

## Auslieferung

Noch nicht veröffentlicht oder im produktiven Bestand installiert; nach vollständiger Regression über den bestehenden Release-/Updateweg ausliefern. Separate Testdaten und private Sicherungen gehören nicht ins Repository.
