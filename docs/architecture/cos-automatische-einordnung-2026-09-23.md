# CoS: automatische Einordnung, gezielte Rückfragen

Stand: 23. September 2026. Produktentscheidung aus der aktuellen Nutzerpräzisierung. Zielverhalten und nächste Lieferung; keine Behauptung, dass die Automatik bereits vollständig implementiert oder qualifiziert ist.

## Auftrag

Kingfisher soll erlaubte Informationen selbst erfassen, einordnen, verbinden, aktualisieren und wiederfinden. Der Nutzer bestätigt nicht jeden Eintrag einzeln. Bei einer entscheidungsrelevanten Unsicherheit oder einem möglichen Fehler fragt Kingfisher konkret nach, nachdem die vorhandenen erlaubten Quellen geprüft wurden. Weniger dringliche Fragen werden gesammelt. Erkennbare Fehlerauslöser sind prüfbar; das System kann nicht zuverlässig jeden eigenen Bedeutungsfehler erkennen.

Die Festlegung präzisiert KNOW-01 und OPS-04 des [Memory-Core-Vertrags](kingfisher-memory-sicherheitsvertrag-v0.1.md). Die ältere Regel „Verdichtung schlägt vor“ betrifft weiterhin den menschlich bestätigten Bestand; sie darf die automatische, quellengebundene Arbeitsnutzung nicht dauerhaft auf eine manuell abzuarbeitende Vorschlagsliste beschränken.

## Arbeitsweise

| Situation | Zielverhalten |
|---|---|
| Eindeutige Nachricht, belegter Sprecher, passender Vorgang | Automatisch erfassen, einordnen und verbinden; Quelle und Einordnung getrennt erhalten. Keine Einzelbestätigung. |
| Eindeutig berichtete Frist oder Statusänderung | Als quellengebundenen aktuellen Arbeitsstand nutzen, soweit die betreffende Interpretationsklasse qualifiziert ist. Änderungen versionieren; in Antworten bei Bedarf „laut Nachricht von …“. |
| Bedingung, Bitte, Absicht oder Zusage | Den jeweiligen Zustand einschließlich Bedingung erhalten. Eine Bitte erzeugt keine Zusage; eine bedingte Zusage bleibt bedingt. |
| Widerspruch oder unklare Person/Frist | Zuerst passende erlaubte Originale und ihren Zusammenhang prüfen. Eine explizite, eindeutig zugeordnete Korrektur kann den Arbeitsstand aktualisieren. Bloßes Neuestsein reicht nicht. Bleibt die Frage entscheidungsrelevant: kurze Rückfrage mit Alternativen und Quellen. |
| Nicht dringliche Unsicherheit | Als offen erhalten und gesammelt zur Klärung anbieten. Sichere, unabhängige Arbeit geht weiter. |
| Rechte, persönliche Grenzen oder außenwirksame Aktion | Bestehende konkrete Freigaben bleiben eigenständig. Eine automatisch gemerkte Information ist keine Erlaubnis zum Versand oder zur Änderung von Rechten. |

Beispiel: „Anna schickt den Entwurf Freitag, wenn die Freigabe vorliegt.“ Kingfisher ordnet die Aussage dem belegten Vorgang zu und merkt die Bedingung. Ist die Freigabe noch unbekannt, bleibt sie offen; die Aussage wird nicht zu einer unbedingten Lieferzusage. Eine Rückfrage wird nötig, wenn diese Unklarheit eine konkrete Planung oder anstehende Entscheidung beeinflusst. Quelle und Nachrichtenzeit müssen die Auflösung von „Freitag“ tragen.

## Speicher- und Antwortvertrag

Herkunft, Interpretation und Bestätigung sind getrennte Eigenschaften. Automatisch eingeordnete Information wird niemals als vom Nutzer bestätigt ausgegeben. Sie braucht einen eigenständig nutzbaren Arbeitsstatus: in Suche, Antwort, Übersicht und Korrektur verfügbar, mit passenden Einschränkungen statt einer Bestätigungsaufforderung bei jedem Abruf. Ein bloß gespeicherter Kandidat, den der Abruf ignoriert, erfüllt diesen Auftrag nicht.

Eine Quelle belegt, was berichtet wurde; daraus folgt nicht automatisch die Wahrheit des Berichts. Das System erhält Sprecher, Personenbezüge, Aussageart, Bedingungen, zeitliche Gültigkeit und Originalstelle. Ungewisse Identitäten bleiben getrennt. Quellenentzug und Nutzerkorrektur wirken auf Arbeitsstand, Antworten und Ableitungen. Eine klare Nutzerkorrektur wird gezielt umgesetzt; nur ihre entscheidenden Unklarheiten werden zurückgefragt.

Keine Freischaltung durch die Selbsteinschätzung „99 % sicher“ eines Modells. Automatische Nutzung wird je Interpretationsklasse anhand unabhängiger Fälle geprüft. Niedrige Qualität einer Klasse beschränkt diese Klasse, nicht die gesamte Quellenaufnahme oder jede Routinearbeit.

## Nächste konkrete Lieferung

Eine zusammenhängende, synthetische Korrespondenz automatisch in einen abrufbaren Arbeitsstand überführen: Anfrage, bedingte Zusage, eindeutig datiertes Ereignis und spätere explizite Änderung. Die bestehende Aufgabenanalyse lässt bedingte Aufträge aktuell bewusst weg; sie bleibt ein Aufgabenpfad. Der neue Arbeitsstand muss Bedingungen aufbewahren, ohne daraus unbedingte Aufgaben zu machen. Vorhandene Originale, stabile Referenzen, Prüfgrenzen und Versionswege wiederverwenden; keine zweite Personenverwaltung.

Die Abnahme umfasst die ganze Kette: Quelle aufnehmen → automatisch einordnen → Frage beantworten → Änderung einarbeiten → gegebenenfalls gezielt nachfragen → Korrektur und Quellenentzug → Neustart. Keine einzelnen Annahmeklicks für die eindeutigen Routinefälle. Gegenfälle: gleichnamige Personen, Zitat einer alten Nachricht, unklare relative Frist, fehlende Anlage, Bedingung, widersprüchlicher Absender und Aufforderungen zur Regeländerung im Quelltext.

Getrennt messen: korrekt ohne Rückfrage erledigte Fälle, notwendige Rückfragen, unnötige Rückfragen, übersehene wichtige Informationen, falsche Zuordnungen und falsche verbindliche Aussagen. Weder „fragt immer nach“ noch „übernimmt immer alles“ besteht diese Abnahme. Die bisherigen technischen Testzahlen ersetzen diese Prüfung nicht.

## Aktueller Ausgangspunkt

`f749d9e` / PR #63 schützt vor bereits erfassten möglichen Widersprüchen. PR #62 erschließt begrenzt Originaltexte ohne angenommene Claims. Der gemeinsame automatisch eingeordnete und abrufbare Arbeitsstand ist noch zu bauen und zu qualifizieren. Diese Produktentscheidung nimmt keine persönlichen Daten an und aktiviert keine zusätzlichen Quellen oder Außenaktionen.
