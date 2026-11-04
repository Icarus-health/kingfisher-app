# Unabhängiger synthetischer P1-Abnahmesatz V2

Stand: 4. November 2026. **Vor der ersten Heldout-Ausführung eingefrorene Reviewkorrektur; noch nicht ausgeführt.** Quellen und Goldreferenzen stammen von einem KI-Agenten. Kein Testmodell und keine Modell-API wurden zur Konstruktion oder Revision des Satzes ausgeführt. Es wurden keine Erwartungen anhand eines Modelllaufs geändert.

Alle Personen, Organisationen, Inhalte und Adressen sind erfunden. Domains enden auf `.example`. Die Szenariozeit bleibt **2026-11-04 16:00 Europe/Berlin**; spätere Zustandsphasen nennen ihre eigene Zeit. Quellzeit und Importzeit sind getrennt.

## Vorgänger und unveränderte Originale

V1 bleibt im benachbarten Ordner `heldout` unverändert erhalten. SHA-256 seines `freeze.json`:

`99f1a7e11818a737095ff125a91fea156fcf85a51a5902c5275490739e35fb96`

V2 ändert ausschließlich Goldwerte, Metadaten und Dokumentation. Alle 100 Mailtexte einschließlich ihrer ursprünglichen Umschlagdaten und alle zehn nativen Dateien sind bytegleich zu V1 erhalten. Native Dateien werden kopiert, nicht erneut erzeugt; auch MIME-Grenzen, PDF-Inhalte und DOCX-ZIP-Bytes bleiben gleich. Die einzige Korrektur an kanonischen Quellmetadaten ist N03 `source_at`: 12:00 statt 11:00 Uhr, entsprechend dem unveränderten EML-Original. Die 40 Basisfragen bleiben unverändert.

## Vollständiger vorab geprüfter Änderungsumfang

1. **T45, E02-03:** Jona soll beide ausdrücklich bestätigten Werkstatt-Adressen von Deniz den bisherigen Absprachen zuordnen. Diese konkrete Kontaktdatenpflegebitte wird als Aufgabe ohne Frist erfasst, getrennt vom Identitätsbeleg. Der Legacy-Katalog erhält dafür einen passenden eigenen Kandidaten; dies autorisiert keine automatische Kontaktdatenänderung.
2. **T46, E06-01:** Evelyn übernimmt den Satz für Sedge nach der Caption-Freigabe. Keine eigene Frist. Die Caption-Frist von Jona darf nicht übernommen werden. **E06-07 bestätigt dieselbe T46** und erzeugt keine zweite Aufgabe.
3. **T47, E06-02:** Lucie übernimmt den Druck für Roseau. Keine belegte Druckfrist; Jonas Maquette-Frist wird nicht übertragen.
4. **T48, E06-03:** Inés übernimmt den Materialeinkauf für Junco. Keine belegte Einkaufsfrist; Jonas Frist für die Materialliste wird nicht übertragen.
5. **Getrennte Bewertungsdimensionen:** Handlungserkennung, Eigentümer samt Unklarheit, Frist samt Unklarheit und Präzision sowie Status werden für jede der 48 logischen Verpflichtungen ausdrücklich annotiert. T25 zählt in der Erkennung: Handlung und Jona als Inhaber sind klar, nur die Frist bleibt zwischen zwei Daten offen. T31 zählt als erkennbarer Vorschlag mit ausdrücklich unbestätigter, quellenberichteter Zuständigkeit. T43 zählt mit klarer Handlung, unbekanntem Sprecher und belegtem Datum ohne Uhrzeit. Keiner dieser Fälle verschwindet wegen einer unklaren Dimension aus dem Erkennungsnenner.
6. **Historische und aufgehobene Fälle:** T23 bleibt historisch ungeklärt, T28 aufgehoben und nicht erledigt. Beide zählen nicht automatisch als aktuelle Aufgaben. Beide müssen separate Pflichtprüfungen bestehen; sie dürfen nicht durch einen guten Durchschnitt verdeckt werden.
7. **N03-Zeitmetadaten:** `source_at` in kanonischem Quellenverzeichnis und nativer Annotation wird auf `2026-11-03T12:00:00+01:00` gesetzt. Die EML-Datei selbst bleibt unverändert.
8. **Native Phasengrenze:** Die Basis umfasst N01–N05 und N07–N10, ausdrücklich **vor Import von N06**. NQ02 prüft ausschließlich diesen Stand und benötigt N02 für die Lizenzfrist sowie N05 für den bestätigten Termin. S09 importiert anschließend N06; SQ11 benötigt N06 für die Absage und N02 für die unverändert bestehende Lizenzbogenpflicht. Kein Nach-Absage-Befund wird ohne die Absagequelle verlangt.
9. **Identitätsbelege:** Die Dana-Aussage erhält E02-01 und E02-02 zusätzlich zu E02-07 als Belege der beiden konkreten Adressen und ihrer ausdrücklich verschiedenen Personen. Die Abgrenzung von Werkstatt-Deniz und Schach-Deniz erhält E02-03 zusätzlich zu E02-05. Gleicher Name oder verschiedene Adressen allein beweisen weder Gleichheit noch Verschiedenheit.
10. **Autorschaft und Methodik:** Präzisiert auf KI-Agentenautorschaft und keine Testmodell-/API-Ausführung zur Konstruktion; keine pauschale Behauptung „ohne Modelle“. Der Validator prüft neue Nenner, Dimensionen, Belege, Phasen, die Metadatenkorrektur und die Unverändertheit der Originale. Sein Bericht liegt separat außerhalb dieses eingefrorenen Ordners.

Es gibt keine weiteren Quelländerungen, zusätzlichen Abruffragen, Modellresultate oder nachträglichen Anpassungen an Ausgaben. Bestehende Aufgaben- und Quellen-IDs bleiben erhalten; nur T45–T48 kommen hinzu. Neue Felder für die Dimensionsbewertung ändern nicht die zugrundeliegenden Originalaussagen.

## Umfang und Phasen

- 100 neu formulierte Mails in zehn Episoden, 40 vorab festgelegte Abruffragen, darunter acht Mails aus `Sent`; Deutsch, Englisch, Französisch und Spanisch.
- Zehn native Originale: zwei MIME-Mails mit ihren echten PDF-Anlagen, zwei ICS-Stände eines Termins, eine Textnotiz, zwei bereitgestellte Texttranskripte und ein DOCX. Das sind neun native Basisoriginale plus der später importierte Absagestand N06. Sieben native Fragen werden an der Basis geprüft.
- Neun unabhängige Zustandszweige mit elf Fragen: Versionswechsel, Quellenentzug nach früherer Antwort, Gruppenwiderruf, bestätigte Erledigung, bestätigte Eigentümerkorrektur, aufgehobene Frist, unvollständige Aufnahme, Duplikat und Kalenderabsage.
- Insgesamt 48 logische Verpflichtungen: 39 im Mailteil, neun im nativen Teil. Zusätzliche Belege werden nicht als neue Aufgabe gezählt.

Der Mailteil allein beweist keine PDF-, DOCX-, Kalender- oder Transkriptaufnahme. Beide Transkripte sind bereits vorhandener Text; Audioaufnahme, Spracherkennung und Sprechertrennung werden nicht getestet. Eine Mailbody-Simulation zählt niemals als bestandene Anlagenprüfung. Native Fragen und Zustandsfragen sind separat auszuweisen; nicht ausgeführte Phasen bleiben offen.

## Vorab festgelegte Bewertung

**Aktuelle Handlungserkennung:** 37 Mail-Aufgaben beziehungsweise 46 Aufgaben nach tatsächlicher Mail- und nativer Aufnahme. T25, T31 und T43 zählen mit ihrer tatsächlichen Unsicherheit. Mindestens 95 % müssen erkannt werden: mindestens 36/37 im Mailteil beziehungsweise 44/46 insgesamt. Ein zutreffender Vorschlag zur Prüfung zählt; eine vollständig übergangene Aufgabe zählt als Auslassung. Den eigenen und den fremden Aufgabenanteil zusätzlich getrennt ausweisen.

**Eigentümer:** Die 46 Erkennungsfälle umfassen 44 quellenbekannte Eigentümer, eine ausdrücklich unbestätigte Quellenzuordnung (T31) und einen unbekannten Sprecher (T43). Korrekte Zuordnung, ausgelassene Angabe, falsche Zuordnung und verlorene Unklarheit getrennt zählen. Quellenbericht ist nicht Nutzerbestätigung. Jona ist bei T25 eindeutig; bei T43 darf keine der anwesenden Personen willkürlich gewählt werden.

**Frist und Präzision:** Unter den 46 Erkennungsfällen haben 35 eine belegte Frist, zehn keine genannte Frist und einer eine ausdrücklich mehrdeutige Frist (T25). Die festen IDs und ihre Datum-/Uhrzeitpräzision stehen in `reference.json`. Belegte Fristen, korrekt offen gehaltene Fristen, Mehrdeutigkeit, Auslassungen, Präzisionsfehler und erfundene Fristen getrennt zählen. Ein Datum ohne Uhrzeit ist keine Quellenangabe von 23:59 Uhr; diese Uhrzeit kommt ausschließlich im Legacy-Adapter als Normalisierung vor. Eine Handlungsreihenfolge oder ein Ereignistag darf nicht zur neuen Abgabefrist werden.

**Status:** Offen, teilweise erledigt, unvollständig, unbestätigt, historisch ungeklärt und aufgehoben getrennt prüfen. Lesebestätigung, Zustellung, vergangener Kalendertermin und Absage sind keine Erledigung. T23 und T28 sind zwingende separate Gates. Die ausdrücklich definierten Unklarheitsfälle müssen ebenfalls korrekt bleiben.

Zusätzlich zur Handlungserkennung die Quote vollständig korrekter Vorschläge über denselben Nenner ausweisen, mit weiterhin mindestens 95 % als Ziel. Ein vollständig korrekter Vorschlag hat Handlung, Eigentümer beziehungsweise Unklarheit, Frist beziehungsweise Unklarheit/Präzision und Status richtig. Getrennte Kennzahlen sollen Fehler sichtbar machen, keine falschen Rollen, Fristen oder Zustände entschuldigen.

**Abruf:** Mindestens 38/40 korrekte, belegte Mailantworten. Semantisch richtige Umschreibungen sind zulässig. Bei echter Mehrdeutigkeit sind eine ehrliche Rückfrage oder vollständig unterscheidbare Möglichkeiten zulässig. Informationsabwesenheit, eine nicht gelesene Anlage, unvollständige Aufnahme und entzogene Belege sind verschiedene Befunde.

**Kritische Fehler:** Null beobachtete Personenwechsel, falsche Aufgabeninhaber, erfundene Fristen, unbelegte Erledigungen oder kritische erfundene Abruffakten. Jeder einzelne kritische Fehler blockiert die Abnahme unabhängig von Durchschnittswerten. Jede ausgegebene konkrete Frist muss an der passenden Originalstelle und gültigen Quellversion geprüft werden.

## Dateien und Ausführung

`sources.json` enthält Eingaben ohne Goldwerte; native Einträge verweisen auf die tatsächlichen Dateien. `catalog.json` bleibt ein Anschlussformat für den bisherigen Mailrunner. Dessen Grenzen stehen weiterhin auf null; spätere freigegebene Laufgrenzen gehören in ein separates Manifest. `expect`, `people`, Bewertungsdimensionen und sonstige Sollwerte dürfen niemals in Modellanfragen gelangen.

`reference.json` enthält die semantische Referenz einschließlich `task_dimensions`, `dimension_scoring_protocol`, der festen Nenner und `native_baseline`. `state-phases.json` enthält unabhängige Folgephasen. Der ältere Grader prüft höchstens einen eigenen Kandidaten pro Quelle und reicht daher weder für Drittaufgaben noch für Mehrfachaufgaben oder freie Antworten aus. Wortgleichheit und Treffer auf Quellen-IDs ersetzen keine semantische Bewertung.

`freeze.json` nennt alle Artefaktprüfsummen, den Vorgängerhash und den Zeitpunkt der V2-Fixierung. Vor jeder Ausführung vollständig prüfen. Ergebnisse außerhalb dieses Ordners speichern. V1 und V2 nach einem Ergebnis nicht überschreiben. Die unabhängige Kontrolle dieser Referenz erfolgte vor einem Heldout-Modelllauf.

## Unabhängigkeit und bestehende kleine Sets

Kein vorher gefundener unbenutzter Gesamtsatz erfüllte mindestens 100 Quellen und 30 Fragen. Inventarisierte Altformate: Intake development 24/16, unabhängige Abrufkontrolle 14/23, Paraphrase 16/36, Workweek 9/11 sowie kleinere 2–10-Fall-Sätze. Null alte Quellen oder Fragen wurden übernommen. Der getrennte Pilot zählt nicht zum Holdout und wurde nicht zur Anpassung dieser Erwartungen benutzt.

Gelesen wurden die Qualitätskriterien des Masterplans sowie alte Fixtureformate und Bestandsmetadaten. Frühere README-Dateien enthielten auch Ergebniszusammenfassungen und kurze Antwortfragmente; gegenüber allen historischen Fehlerthemen bestand daher keine vollständige Blindheit. Für Konstruktion und Revision wurden keine Produktimplementierung, vollständigen Modellantworten oder Antworten dieses Heldouts ausgewertet. Keine persönlichen Daten, Netz-, Cloud-, GUI- oder Dockerzugriffe fanden für diese Arbeit statt. Statische Prüfungen belegen nur die Konsistenz des Satzes, keine Produktqualität und keine Unterstützung der Importpfade.
