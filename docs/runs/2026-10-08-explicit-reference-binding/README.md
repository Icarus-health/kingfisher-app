# Originalbelege an ausdrücklich erfragte Vorgänge binden

Produktcode: `c3510908bb3d7522c5f9ab0ea2f5ec0599eb372a`, auf `b1436e9`.

## Reproduzierter Fehler und begrenzte Korrektur

Der [vorherige geschlossene Produktlauf](../2026-10-08-closed-model-memory/README.md) lieferte bei „Wer prüft die Ware im Auftrag KL-24?“ die fremde Notiz H02. Die Satzprüfung verwarf zwar die erfundene Auftragszuordnung, der Zitat-Rückfall zeigte aber weiterhin den unpassenden Originaltext. Ein gültiger Verweis und ein exaktes Zitat sind kein Relevanznachweis.

Ein deterministischer Schutz liest ausdrücklich typisierte alphanumerische Kennungen aus der **Originalfrage**, etwa „Auftrag ZX-29“, „Vorgang M731“ oder „Rechnung INV/203“. Das Modell erhält nur Quellen, deren voller Originaltext, Originaltitel oder aktuell zugeordnetes Projekt mindestens eine der erfragten Kennungen enthält. Die vollständige Kandidatenbasis und Abdeckung bleiben erhalten. Nach Personen-/Projekthilfen wird die endgültige S-Auswahl nochmals geprüft; gespeicherte Antworten durchlaufen denselben notwendigen Bindungstest. Ein gespeicherter Projektname allein genügt nicht: Der aktuelle Arbeitsbereich wird spät gelesen. Bestätigte K-Aussagen und ihre Konflikt-/Herkunftsprüfung bleiben außerhalb dieses S-Filters.

Nur typisierte Kennungen und unmittelbar koordinierte Vergleichskennungen zählen; eine nebenbei genannte Mailnummer darf die eigentliche Auftragsnummer nicht ersetzen. Vergleiche brauchen nicht jede Kennung in jeder Quelle. Bei unabhängigen Teilfragen, negierten Bereichen oder verbleibender Koordination wie „Auftrag ZX-29 und Urlaub“ entfällt der globale Filter konservativ. Er ist kein Sprachparser und keine automatische Identitätsverknüpfung.

Eine passende Kennung ist **notwendig, nicht hinreichend**: Eine Liefermeldung zu KL-24 sagt weiterhin nichts darüber, wer die Ware prüft. Dies muss die normale quellengebundene Auswahl erkennen. Die Korrektur erweitert keine Originale, Indizes, Freigaben oder Faktenprüfungen.

## Prüfungen und unabhängiges Review

24 neue Regressionen prüfen falsche/ähnliche Kennungen, richtige Belege, Titel, Projektzuordnung und -umbenennung, Vergleiche, unabhängige Themen, Modell-Sucherweiterungen und alte Antworten. Vor Produktänderung scheiterten fünf konkrete Verhaltensfälle, fünf Sicherheitskontrollen bestanden bereits. Die unabhängige Reviewkorrektur zur zusätzlichen Mailnummer und zur Projektumbenennung wurde ebenfalls zuerst rot reproduziert. Beim gezielten Abschalten des Schutzes ausschließlich im Testprozess scheitern 13/24 Kontrollen, elf Sicherheitsfälle bleiben grün; kein Produktcode wurde dafür zurückgesetzt.

**371 unterschiedliche betroffene Prüfungen bestanden**: 313 für Arbeitsgedächtnis, Quellen-/Gesprächs-HTTP und Sätze; weitere 64 für Agent, Diagnose und Projekte, davon sechs Überschneidungen. Unabhängiges Codereview des eingefrorenen Commits ohne blockierenden Befund innerhalb der beschriebenen Syntax. Nicht abgedeckt sind insbesondere rein numerische Kennungen und zusammengesetzte Typwörter wie „Auftragsnummer“/„Ticket-ID“; dort bleibt der bisherige Auswahlweg. Ungewöhnliche Beziehungen innerhalb mehrerer Vorgänge in einem Dokument benötigen weiterhin semantische Prüfung. Keine allgemeine Fehlerfreiheitsbehauptung.

## Echter lokaler Produktlauf

Dieselben 18 künstlichen Originale wie im vorherigen finalen Lauf werden neu über Dokument-HTTP aufgenommen, vom echten Modellworker eingeordnet, mit Themen/Entitäten versehen und dauerhaft eingebettet. Datenbanken und Bedeutungsdienst werden vor den Gesprächs-HTTP-Fragen geschlossen und neu geöffnet. Vorhandenes qwen3.5:4b und bge-m3 über `VerifiedLocalProvider`, kein Cloudaufruf, Download oder persönliches Original.

Alle 18 Quellen sind im Bedeutungsindex, ohne offenen Rest. Alle **23/23 Quellen-/Statuskontrollen** bestehen. RQ02 zeigt jetzt den passenden Nora-Beleg ohne unnötige Personenrückfrage. RQ04 erkennt, dass zur prüfenden Person in KL-24 keine belegte Angabe vorliegt; H02 wird nicht gezeigt und die gleichnamige Liefermeldung nicht zur Prüfzuständigkeit gemacht. Die vier Nichtwissensfälle sind genau RQ04, RQ16, RQ17 und RQ18. Eine gespeicherte Antwort wird nach einem weiteren Neustart und Quellenentzug ohne Modellaufruf gesperrt, ihr Original bleibt erhalten.

Der Lauf endet nach rund 252 Sekunden; der eigene Testserver und Client enden mit Exit 0. Maximal gemessenes eigenes Prozess-RSS: rund 6,25 GiB. Wie im vorherigen Vergleich wird ausdrücklich nach vier Testpaketen entladen. Dieser Stichprobenwächter ist keine harte RAM-/GPU-Grenze und die diagnostischen Pausen beweisen keine produktive Akkuqualität. Der kleine, bereits bekannte Kontrollbestand ist keine allgemeine persönliche Bestands- oder Großdatenabnahme. Die unabhängige Prüfung liest alle 23 Antworten gegen die Originale. Alle Fragen sind ausreichend beantwortet; **eine Zusatzbehauptung in RQ20 ist dennoch zu weit**: „Für Auftrag R-508 sind nur trockene Tücher erlaubt“ lässt „vor der Reinigung“ aus dem Original weg. Der folgende Lösungsmittelsatz beantwortet die Frage korrekt, heilt diese zusätzliche Verallgemeinerung aber nicht. Deshalb nur 22/23 Antworten ohne zu weite Zusatzbehauptung, keine Fehlerfreiheitsabnahme. Das ist die nächste gezielte Satzprüfungsarbeit. Alle neun erwarteten Personennennungen und 13 ausgegebenen Textspannen stimmen; Ort-/Organisationsfehltypen bleiben wie zuvor bestehen. Details in `independent-content-review.json`; die Rohberichte bleiben unverändert.

## Paket und Mac

Das netzlos mit 1 CPU/512 MiB geprüfte Paket enthält 264 Pythonquellen und 112 bytegleich erhaltene UI-Dateien. Der Smoke prüft Quellenabdeckung, den lokalen Unicode-Namensanker, falsche Vorgangsbelege, alte Antworten und Quellenentzug. Die Wheel-Prüfsumme und Dateifingerabdrücke stehen in `expected.json`, Einzelprüfungen in `package-smoke.json`.

Kein produktiver Modellwechsel, persönlicher Neubewertungslauf oder Importstart. Große Quellenabdeckung, Personen-/Organisationstypen, native Fensterbedienung sowie Tages-/Akkuabnahme bleiben offen. Der gesamte CoS ist nicht fertig abgenommen.

Mac-Installation am 8. Oktober: Backend `1.0.6-local.c351090` gesund auf Port 8890; alle 264 Pythonquellen und 112 UI-Dateien stimmen mit dem Paket überein. 344 Original-IDs samt Fingerabdrücken und 17 SQLite-Dateien erhalten; Zugänge, Modellrollen, Zeitplan und pausierte Aufnahme unverändert. Native Signatur und Programmdatei geprüft, Fensterbedienung weiterhin **nicht** geprüft. Vollständiger Rückweg unter `Kingfisher-Rueckweg/2026-10-08-vor-c351090-geprueft`.

Die native Speicherprüfung stoppte zunächst vor jedem Eingriff. Nur das unbenutzte alte bf396eb-Paket samt eindeutig zugehörigen Zwischenstufen wurde nach vollständiger OCI-/Schichtprüfung außerhalb Docker archiviert und ohne Erzwingen entfernt. Danach bestanden beide nativen Reservetests. Aktuelle Version, unmittelbare Rückwege sowie fremde Container/Volumes blieben erhalten. Details in `storage-relief.json`. Der Bedeutungsdienst bleibt mangels gestartetem Ollama unverfügbar; der Import wurde nicht fortgesetzt.
