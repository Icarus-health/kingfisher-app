# Mistral-Quellenpakete mit Aufgabenprüfung

## Problem und Änderung

Die bisherige ausdrückliche Cloud-Quellenverarbeitung klassifiziert Originale und
extrahiert Kategorien/Entitäten. Sie untersucht jedoch keine Bitten und Aufgaben.
Damit konnte sie die lokale Aufgabenverarbeitung beim großen Erstbestand nicht
ersetzen. Mistral-Pakete können jetzt die bestehende Aufgabenerkennung und deren
semantische Gegenprüfung im selben genehmigten Quellenumfang verwenden.

Die Vorschau speichert `include_tasks`. Alte Vorschauen und Aufträge behalten
`false`; weder Start noch Fortsetzen können diesen Umfang erweitern. Die
Oberfläche fordert bei einer neuen Mistral-Vorschau die Aufgabenprüfung an und
nennt sie vor der Zustimmung. Die anderen Anbieter bleiben unverändert.

Der bestehende TaskDetector bearbeitet ausdrücklich ausgewählte IDs ohne globale
Wiedervorlage, Cursor oder Vorschlagsbereinigung. Er verwendet denselben
Mistral-Zugang, dasselbe dauerhafte Geldbudget und eine vorher sichtbare Obergrenze
für alle Abschnitts-, Extraktions- und Gegenprüfungsaufrufe. Es gibt keinen
lokalen Modell-Fallback. Quellenstand, Kontakte, Freigabe und Zugang werden vor
Übertragung und Speicherung erneut geprüft. Ergebnisse sind weiterhin Vorschläge;
es werden keine Aufgaben automatisch übernommen.

Die lokale Beleg-/Fristprüfung und die Unterscheidung zwischen Termin und Bitte
bleiben bestehen. Eine Quellenklassifikation allein genügt weder für den neuen
Aufgabenabschluss noch dafür, eine Mail beim nächsten Paket zu überspringen.
Auch die Bulk-Schranke verlangt jetzt einen vollständigen Pilot mit passendem
Prüfumfang; ein alter Quellenpilot schaltet keine erstmalige Aufgabenprüfung von
bis zu 1.000 Mails frei. Ein unabhängig reproduzierter Reviewbefund führte zu
dieser zusätzlichen Korrektur.

Eine zuvor ausdrücklich abgelehnte Aufgabe wird bei reiner Kontextänderung nicht
erneut vorgeschlagen, wenn Quellen-ID, Textfassung und Zitat unverändert sind.
Der Regressionstest änderte dafür tatsächlich die Kontaktmetadaten und wies eine
neue Auswertung nach; ein beliebiger zusätzlicher Tag wäre kein ausreichender Test.

## Grenzen

- Aufgabenprüfung zunächst nur für vollständige Mailnachrichten bis 20.000
  Zeichen. Größere Quellen und Anhänge bleiben mit sichtbarer Aufgabenlücke
  erhalten; ihre schon gespeicherte Quellen-/Personeneinordnung geht nicht verloren.
- Kein automatisches Nachladen von Elternmails oder anderen Quellen.
- Ein belegter Abschluss beweist Verarbeitung, nicht richtige Modellentscheidung.
  `quality_verified` bleibt ausdrücklich `false`.
- Bei ungültiger Gegenprüfung, fehlendem Fortschritt oder Budgetänderung gibt es
  keinen falschen vollständigen Abschluss und keine automatische Wiederholung.
- Die bestehende CLI-Quellenprobe bleibt absichtlich ein Quellen-/Kategorientest
  ohne Aufgabenqualität. Für die spätere echte Mistral-Abnahme muss der kombinierte
  Prüfweg mit eingefrorenem Goldstandard verwendet werden.

## Prüfungen

Nur künstliche Quellen und simulierte Anbieterantworten über HTTP MockTransport.
Keine persönlichen Quellen, echten Anbieteraufrufe oder API-Kosten. Die echte
Mistral-Qualität und Geschwindigkeit sind ohne Schlüssel noch offen.

- Neue Aufgabenpaket-Tests: vollständiger Ablauf, Termin als Information,
  Quellenbindung, Kostenbuchung mit künstlichen Tokenzahlen, alter Umfang,
  Widerruf/Entzug während Anfrage, unvollständige Gegenprüfung, Bulk-Aufgabenlücke,
  erhaltene Ablehnung, lange Mail, mehrere Abschnitte, konkurrierende Lease,
  Budgetänderung, leere Auswahl, SQLite-Migration und drei Pilot-Scope-Fälle.
- Vorherige Fehler wurden zuerst nachgewiesen: fehlender Previewparameter,
  wiederkehrende abgelehnte Aufgabe und unzulässige Bulk-Freigabe.
- Unabhängiges Abschlussreview: 18 neue Tests bestanden; Pilot-Befund geschlossen,
  keine weiteren offenen Reviewblocker im geprüften Diff.
- TypeScript/Produktionsbuild und Assetvertrag bestanden. Bekannte Warnungen:
  großes Frontend-Bundle und Starlette/httpx-Testclient-Abkündigung.

Die genauen Endstände der betroffenen Regressionen stehen in `validation.json`.
Keine neue native Bedienabnahme und kein Mac-Update. Der Großimport bleibt pausiert.
