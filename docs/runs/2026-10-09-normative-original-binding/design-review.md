# Begrenztes Designreview: Bindung normativer Quellen

Stand: `8394ff5169e28e0cc70bd48e818db123e2efb7f7`. Keine Produktänderungen oder Modellaufrufe.

Der Ansatz schließt die nachgewiesenen frei formulierten Vertauschungen N02/N06 strukturell: Bei einer erkannten normativen Quelle darf der Kandidat nur eine vollständige Originaleinheit aus einem tatsächlich zitierten aktuellen Quellkörper wiedergeben. Das belegt Wortlaut und Herkunft, nicht automatisch Wahrheit, Aktualität, Vollständigkeit oder Verbindlichkeit der Quelle.

## Vor der Umsetzung festzulegen

- **Ein gemeinsamer Vertrag für Auswahl und Prüfung.** Vollständige Einheiten und deren Vergleich müssen denselben Helfer verwenden. `_originalstellen` und `_bedingung_verloren` segmentieren heute verschieden; `_regeltext` sowie der Legacy-Adapter entfernen `!?`. Der neue Vergleich darf nur Leerraum, Groß-/Kleinschreibung und einen optionalen endgültigen Punkt normalisieren; `ß` und `ss`, Fragezeichen und Zitatzeichen bleiben verschieden. Vorhandene semantische Hilfsfunktionen dürfen ihre bisherige Bedeutung behalten.
- **Abkürzungen nicht als Satzende ausgeben.** Der bestehende Helfer bietet aus „Die Messsonde darf z. B. nach der Kalibrierung eingesetzt werden.“ tatsächlich „Die Messsonde darf z.“ an; aus „Schraube Nr. 7 …“ bietet er ein Objektfragment. Im Zweifel ein größeres Originalstück behalten oder auf Quellenzitate zurückfallen, statt unvollständige Stücke zu IDs zu machen. Kein allgemeiner deutscher Satzparser ist erforderlich, aber diese üblichen Punktformen dürfen keine angeblich vollständige Freigabe erzeugen.
- **Mehrsatz-Zitate verlieren den Rahmen.** Nur Zitatzeichen an Satzenden zu erhalten reicht nicht: Der innere Satz einer alten, verworfenen Anweisung enthält keine Anführungszeichen. N22 demonstriert das. Ein solches Zitat zusammenhalten oder die betroffene normative Quelle konservativ im Zitatmodus belassen; nicht den inneren Satz als eigenständige Erlaubnis anbieten.
- **Sichtbarkeit und Zitierung getrennt prüfen.** Ein vollständiges Original im versteckten `pruef_text` ist noch keine dem Antwortmodell angebotene Stelle. IDs ausschließlich aus vollständigen sichtbaren Einheiten. Der Legacy-Pfad darf kein unangebotenes verborgenes Original ergänzen. Die zentrale Prüfung verwendet ausschließlich die tatsächlich zitierten Belege, nicht alle im Pool vorhandenen Quellen.
- **Kein Umgehen beim Wiederöffnen.** Dieselbe neue zentrale Bindung muss alte gespeicherte `roh`/`text`-Antworten prüfen, unabhängig von damaligem Modell-Ja oder `vom_programm`. Unzulässige alte Paraphrasen fallen auf Quellen zurück; Originale werden nicht gelöscht. Gültige Originalstellen, Quellenentzug und aktive Zweitprüfer-Metadaten benötigen eigene Kontrollen.

## Konkrete Kompatibilitätsrisiken

1. `pruefe_satz` ersetzt relative Zeitangaben vor der zentralen Prüfung durch Datumstext. Eine neue wörtliche Bindung kann deshalb eine korrekt wiedergegebene Pflicht mit „morgen“ zurückweisen. Kein pauschaler Ausnahmeweg für programmgenerierte Texte; konservativer Zitatmodus ist sicher, muss aber als Nutzbarkeitsänderung sichtbar gemessen werden.
2. `_wandel_saetze` erzeugt Erläuterungen aus Quellenmetadaten. Wenn diese normative Belege zitieren, stehen die Erläuterungen nicht wörtlich im Quellkörper und können jetzt zum Zitatmodus führen. `vom_programm` darf die Bindung nicht still umgehen.
3. Ein erweitertes `bedingte_regeln_fuer_antwort` würde auch `_quelle_fehlt` verändern: Nach einer einzigen Verwerfung müssten womöglich sämtliche normativen Regeln wiedergegeben werden. Neuer Erkennungshelfer und bestehende Vollständigkeitslogik sollten nicht unbeabsichtigt gekoppelt werden.
4. Wenn irgendein vorgelegter normativer Beleg die ganze Anfrage in den ID-Modus versetzt, laufen auch die gewöhnlichen Faktenbelege derselben Anfrage dort durch. Das ist ein vertretbarer konservativer Vertrag, aber eine reine Faktenanfrage muss den bestehenden Textvertrag behalten. Dies explizit testen statt „gewöhnliche Fakten unverändert“ pauschal zu behaupten.
5. Bestehende API-Verträge bleiben nötig: strenge echte Integer-IDs, keine Zusatzfelder, keine unbekannten oder doppelten IDs; Legacy-Verwerfungszahlen bleiben ehrlich; leere/zu große Angebote erzeugen keine angeblich fehlende Information; exakte ID-Stellen durchlaufen weiterhin Aktualitäts- und zweite Modellprüfung.

## Bewusste Grenzen

L01 ist eine wörtliche Erlaubnis mit einer Einschränkung im Folgesatz. L02 ist eine wörtliche Erlaubnis in einem historisch nicht freigegebenen Entwurf ohne Zitatzeichen. Einzelne vollständige Sätze können beide Fälle weiterhin unvollständig darstellen. Diese Fälle sind im Katalog als dokumentierte Grenzen und ausdrücklich **nicht als Freigabeforderungen dieses Inkrements** eingefroren. Gleiches gilt für die optional noch nicht vereinbarte Erkennung von „erforderlich“.

Die Bezeichnung „Originalstelle“ ist gerechtfertigt, wenn die Bindung stimmt. Sie rechtfertigt keine neue Behauptung „aktuell erlaubt“, „Bedingung erfüllt“ oder „semantisch verifiziert“.

## Eingefrorene Evidenz

- `/private/tmp/kingfisher-normative-source-holdouts-20261009.json`: 8 unveränderte bekannte Negativkontrollen, 25 neue Kontrollen einschließlich 9 positiver/gewöhnlicher Vergleichsfälle und 2 dokumentierter Grenzen; zusätzlich 10 strukturelle API-/Speicher-/Sichtbarkeitskontrollen.
- SHA256: `a53217e6a52aa5a6c55728cc5ccc6d12ba21317a53538a391adbda970db4a361`.
- `/private/tmp/kingfisher-normative-source-baseline-20261009.json`: deterministische Baseline und tatsächliche vorhandene Splitter-Ausgaben; keine Modelle. Die bekannten fünf Fehlfreigaben sind unverändert reproduziert. Die Goldwerte wurden nach der Ausführung nicht geändert.
