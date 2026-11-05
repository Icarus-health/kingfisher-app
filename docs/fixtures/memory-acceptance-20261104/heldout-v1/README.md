# Unabhängiger synthetischer P1-Abnahmesatz, 4. November 2026

Status: vor der ersten Ausführung eingefroren, **nicht ausgeführt**. Die Anlage dieses Satzes verwendet keine Modelle, persönlichen Daten, Produktimplementierung oder Modellantworten. Alle Personen, Organisationen, Inhalte und Adressen sind erfunden; Adressdomains enden auf `.example`.

## Umfang und Grenze

- 100 unterschiedlich formulierte Mailoriginale in zehn zusammenhängenden Episoden, 40 vorab festgelegte Abruffragen.
- Zusätzlich 10 native Originale: zwei MIME-Mails mit ihren echten PDF-Anlagen (vier Originale inklusive Anlagen), zwei ICS-Stände eines Termins, eine Textnotiz, zwei bereitgestellte Texttranskripte, ein DOCX. Dazu sieben zusätzliche Fragen.
- Neun separat zu startende Zustandsphasen mit elf Fragen: Versionswechsel, Entzug nach früherer Antwort, Gruppenwiderruf, bestätigte Erledigung, bestätigte Eigentümerkorrektur, aufgehobene Frist, unvollständige Aufnahme, Duplikat und Kalenderabsage.
- 35 logische Aufgaben/Verpflichtungen im Mailteil und neun weitere im nativen Teil. Der Nenner für eindeutige aktive Verpflichtungen wird in `reference.json` vor dem Lauf festgelegt; historische, unklare und aufgehobene Fälle bleiben separat zwingend zu prüfen.
- Eigene gesendete Mails tragen `folder: "Sent"`. Zeitbasis ist fest **2026-11-04 16:00 Europe/Berlin**; spätere Phasen nennen ihren eigenen Zeitpunkt. Quellzeit und Importzeit sind getrennt.

Der Mailteil alleine ersetzt keine Abnahme der PDF-, DOCX-, Kalender- oder Transkriptaufnahme. Die beiden Transkriptdateien sind bereits vorhandener Text: Sprachaufnahme, Spracherkennung und Sprechertrennung werden damit nicht getestet. Die native Absage N06 wird erst nach N05 importiert. Eine erfolgreiche Mailbody-Simulation zählt niemals als bestandene Anlagenprüfung.

## Dateien

- `sources.json`: kanonische Eingaben ohne Sollwerte. Mailfelder enthalten ausschließlich Originalmetadaten und -texte. Native Einträge verweisen auf tatsächliche Dateien unter `native/`; Eltern-/Anlagenbeziehung bleibt erhalten.
- `catalog.json`: Adapterformat des bestehenden Intake-Katalogs für die 100 Mails/40 Fragen. `expect`, `people`, Frageerwartungen und alle übrigen Goldwerte dürfen nie an ein Modell übergeben werden. Grenzen stehen absichtlich auf null: Eine spätere Ausführungsfreigabe/Begrenzung gehört in ein separates Laufmanifest, nicht in die eingefrorenen Quellen.
- `reference.json`: semantische Sollwerte einschließlich Aufgabeninhaber, Quellenbelege, zeitlicher Bedeutung, negativer Fälle, Mehrdeutigkeit und Qualitätsgates. Originalzitate sind gegen die Quellen zu lesen. Konkrete Fristen dürfen nur auf diese Quelle und gültige Version gestützt werden.
- `state-phases.json`: unabhängige Zustandszweige ab benannter Basis. Kein Modell- oder Ergebnisdatensatz.
- `freeze.json`: SHA-256 jedes Eingabe-/Referenzartefakts. Vor jeder Ausführung vollständig prüfen; Laufresultate außerhalb dieses Ordners speichern.

Die alte Katalogprüfung ist nur ein mechanischer Anschluss: Sie kann höchstens einen eigenen Kandidaten pro Quelle prüfen und stellt Eigentümer, mehrere Aufgaben, Zustandsauflösung oder die Qualität freier Antworten nicht ausreichend fest. `required` und `allowed` liefern die eingefrorene Belegreferenz; allein deren Treffer sind kein semantischer Erfolg. Die Antwort muss alle relevanten Aspekte korrekt wiedergeben und darf keine weiteren unbelegten Tatsachen behaupten. `contains` bleibt absichtlich leer: Wortgleichheit wäre kein Ersatz für die Bewertung. Eine Nachbewertung darf semantische Paraphrasen zulassen, jedoch die faktischen Sollwerte nicht nachträglich absenken.

Datum ohne Uhrzeit bleibt fachlich Datum ohne Uhrzeit. Nur der Kompatibilitätsadapter setzt für solche Daten `23:59` an; das ist keine Uhrzeit aus der Quelle. Direkte Ereigniszeiten, historische Fristen, unverbindliche Wünsche und aktuelle Abgabetermine müssen getrennt bleiben. Ein unbekannter Termin darf nicht mit der Importzeit, einer Besprechung oder einer benachbarten Aufgabe gefüllt werden.

## Vorab festgelegte Bewertung

Der Masterplan fordert null beobachtete kritische Personen-/Inhaberwechsel, erfundene Fristen und unbelegte Erledigung sowie mindestens 95 % Aufgaben-/Fristerkennung und mindestens 95 % korrekte belegte Abrufantworten. Für den Mailabruf sind mindestens 38/40 korrekt nötig, zusätzlich null kritische erfundene Angaben. Native sieben Fragen und die elf Zustandsfragen separat ausweisen; ein nicht ausgeführter Teil bleibt offen. Kein Durchschnitt darf einen kritischen Fehler verdecken.

Alle unzweideutigen aktiven Aufgaben zählen, auch undatierte und die Aufgaben anderer Personen; den eigenen Aufgabenanteil zusätzlich ausweisen. Die Aufgabe darf als Vorschlag erkannt werden, ohne automatisch aktiviert oder erledigt zu werden. Rückfrage/Abstention, Auslassung, falscher Vorschlag und korrekter Vorschlag getrennt zählen. Bei wirklich mehrdeutiger Frage ist eine ehrliche Rückfrage oder eine vollständige Darstellung der unterscheidbaren Möglichkeiten zulässig. Zwei Adressen allein beweisen nicht zwei Menschen; die expliziten Identitätsbelege in E02 entscheiden. Echte Informationsabwesenheit und eine nicht gelesene/entzogene Quelle sind verschiedene Ergebnisse.

## Unabhängigkeit und Wiederverwendung

Es wurde zuerst nach vorhandenen Holdouts gesucht. Die bekannten Formate umfassen Intake development 24/16, unabhängige Abrufkontrolle 14/23, Paraphrase 16/36, Workweek 9/11 sowie kleine alte 2–10-Fall-Sätze. Keiner erfüllt die geforderten 100 Quellen und 30 Fragen als unbenutzte Gesamtabnahme. Deshalb wurden **null alte Quellen oder Fragen** kopiert. Der separate Pilot enthält 10 andere Quellen/5 andere Fragen und zählt nicht zum Holdout. Der Pilot und seine eventuellen Ergebnisse ändern diesen Satz nicht.

Gelesen wurden die Qualitätskriterien des Masterplans und bestehende Fixtureformate/Bestandsmetadaten. Einige frühere Fixture-READMEs enthielten Ergebniszusammenfassungen; das ist offengelegt und bedeutet, dass der Autor nicht gegenüber jedem historischen Fehlerthema blind war. Keine Produktimplementierung und keine Modellantwort wurden für diese Erstellung gelesen. Themen stammen aus dem Masterplan, Texte und Sollwerte sind neu verfasst. Unabhängige Referenzprüfung vor einer Ausführung ist erwünscht; notwendige Goldkorrekturen müssen als neue Version eingefroren werden, nicht nachträglich in diesem Satz verschwinden.

## Durchführungsgrenze

Kein Modell-, Cloud-, GUI-, Docker- oder persönlicher Datenzugriff fand zur Erstellung statt. Statische Kontrollen prüfen nur Dateiformat, Referenzkonsistenz und Prüfsummen. Sie sind keine Qualitätsmessung des Produkts und keine Bestätigung, dass ein Importpfad diese Eingaben unterstützt. Ausführung, Modellfreigabe, Ressourcengrenze und Kostenquittung übernimmt der übergeordnete Lauf separat.
