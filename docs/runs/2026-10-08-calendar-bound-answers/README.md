# Kalendergrenzen in belegten Antworten

## Reproduzierter Fehler

Aus der einzigen künstlichen Quelle „Die Zusage gilt nur bis30.09.2026.“ akzeptierte die gemeinsame Satzprüfung sowohl „Die Zusage gilt ab30.09.2026.“ als auch „Die Zusage gilt aktuell.“. Werteprüfung des Datums allein erkannte weder die umgedrehte Richtung noch die weggefallene Gültigkeitsgrenze. Der unabhängige Prüfer reproduzierte zusätzlich den Satz-/Verlässlichkeitsweg ohne zugewiesenes Prüfmodell. Ein aktives Modelltor ist eine zusätzliche Prüfung; sein mögliches Verhalten wurde dadurch nicht gemessen.

## Korrektur

Der vorhandene Datumsparser erhält seine Zeichenpositionen, ohne Datumserkennung oder Jahresauflösung zu verändern. Erkannte explizite Operatoren an einem einzelnen Kalenderdatum werden mit dem Quellentext verglichen; Titel, Import- und Anzeigedaten liefern keine Grenze. Bei einer ausdrücklich formulierten Gültigkeit (`gilt`, `gültig` und erkannte Varianten) müssen die datierten Grenzen des über Inhaltswörter zugeordneten Quellsatzteils erhalten bleiben. Stärkere inhaltliche Übereinstimmung hat Vorrang; gleich gut passende Satzteile sind Alternativen. Historische Formulierungen („galt“) werden dadurch nicht pauschal zur vollständigen Datumswiederholung gezwungen. Unbekannte Modifier bleiben an ihren Wortlaut gebunden. Nur geprüfte gleichwertige Formen werden normalisiert.

Der vorhandene Antwortweg verwirft solche Sätze und fällt auf das Originalzitat zurück. Gespeicherte alte Satzantworten werden beim Wiederöffnen mit derselben gemeinsamen Prüfung erneut geprüft; dafür wird kein Modell gestartet. Originale, Modellrollen und Datenbankschemata bleiben unverändert.

## Prüfstand

- Erste9 Fehlerfälle RED;11 positive Kontrollen bereits bestanden. Danach131 gemeinsame Guardtests bestanden.
- Echter `prepare`-/Render-Weg und gespeicherte Wiederöffnung ergänzt. Sabotage mit ursprünglichem Produktcode:12 erwartete Fehler,11 positive Kontrollen bestanden. Änderung anschließend wiederhergestellt.
- Zwei zusätzliche Normalisierungs-Kontrollen („nur bis“/„bis“, „erst ab“/„ab“) zunächst RED, dann korrigiert.25 neue Fälle bestanden.
- Frühere17 tatsächlich erzeugte Einzelsätze mit künstlichen Quellen erneut geprüft:keine Änderung der bisherigen Urteile. `historical-replay.json` ist ausdrücklich kein neuer Modell- oder Abruflauf.

Das unabhängige Review fand einen echten Fehlalarm: Der unbefristete Betriebsbereich einer Lizenz wurde wegen eines anderen befristeten Testbereichs verworfen; außerdem fiel eine korrekt kopierte zweite Gültigkeitsaussage durch. Drei zusätzliche Kontrollen zunächst RED, anschließend korrigiert.174 Guard-/Antworttests bestanden. Der ursprüngliche vollständige Backendlauf wurde gezielt unterbrochen, weil der Reviewbefund eine Codekorrektur verlangte; er ist kein Abschlussnachweis. Erneute unabhängige Reproduktion bestätigt die ursprünglichen Fehler als verworfen, beide Review-Gegenbeispiele und historische/imperative/Frist-Kontrollen als bestanden.139 fokussierte Tests unabhängig bestanden; keine weiteren wichtigen Befunde im begrenzten Diff. Der abschließende vollständige Backend-Lauf läuft. Lieferung bleibt bis zu dessen Ergebnis offen.

## Grenzen

Keine allgemeine Wahrheits-, Aktualitäts- oder Ereigniszuordnungsprüfung. Unerkannte relative Ausdrücke und kompakte Datumsbereiche haben hier keinen neuen Vertrag. Inhaltswörter können in komplizierten Satzklammern mehrere Ereignisse verbinden; bei Zweifeln bleibt das Original maßgeblich. Ein korrekt erhaltenes altes Datum beweist weder eine heute noch offene Aufgabe noch eine aktuelle Berechtigung. Reale Modellqualität und native Alltagsbedienung bleiben getrennte Abnahmen.
