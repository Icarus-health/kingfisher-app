# Rückmeldungen bleiben trotz wechselnder Importanzeige prüfbar

Geprüfter Code: `f98944a8d1d0e1e9ca6c70839d1b9703062d971a`, 05.11.2026.

Der authentifizierte Ablauf Gespräch → „Stimmt nicht?“ → Rückmeldungsablage →
Prüffallexport zeigte einen echten Fehler: Eine identische fachliche Antwort
wurde vom bestehenden wörtlichen Matcher nicht mehr gefunden, sobald der
angehängte Mailaufnahmehinweis wechselte oder verschwand.

Der vollständige angezeigte Snapshot und seine Quellen bleiben erhalten.
Die Regressionserwartung entfernt ausschließlich den durch serverseitige
Metadaten belegten letzten technischen Zusatz. Sie berücksichtigt auch den
Fall, dass die Speichergrenze mitten im Zusatz liegt. Gleichlautender echter
Quellentext, Altbestand ohne Metadaten und einzelne strukturierte Aussagen
behalten ihr bisheriges Verhalten. Keine Migration oder automatische
Skillaktivierung; das Lernen bleibt ausdrücklich freizugebender Vorschlag.

## Nachweise

- [Anforderungen](requirements.md), [Autorbericht](author-report.md),
  [erstes Review](review01.md), [Nachreview](fix01-review.md).
- Erstes Review fand den Abschneidefall; dieser wurde reproduziert und korrigiert.
  Finales unabhängiges Spezifikations- und Qualitätsreview bestanden.
- 94 betroffene Offlinefälle vor dem Review; nach der Korrektur 35 gezielte
  Rückmeldungs-/Aufnahmefälle bestanden. Überschneidende Testzahlen werden
  nicht addiert. Bestehende Starlette-TestClient-Warnung bleibt offen.
- [Validierung](validation.json). Protokolle sind künstlich und lediglich am
  Zeilenende von Leerraum bereinigt; Rohpfade stehen im Autorbericht.

Die Prüfung bestätigt den vorhandenen wörtlichen Fehlervergleich, keine
semantische Gleichheit umformulierter Antworten. Vollständige P2-Abnahme,
reale Modelle, native Bedienung und persönliche Aktualisierung bleiben offen.
Keine privaten Quellen, Netzwerk-/Modellaufrufe, Kosten oder Großimport.
