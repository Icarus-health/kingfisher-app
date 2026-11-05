# Mailaufnahme-Lücken bei Gedächtnisantworten sichtbar machen

Geprüfter Code: `9ecbc10d916740b2b92d9fe3a757c2ec39013d57`, 05.11.2026.

Die tatsächliche App-Probe hatte drei inventarisierte Mails: eine eingelesen,
eine noch offen und eine fehlgeschlagen. Die vorhandene Antwort gab eine
Bedingung mit Quellenbezug wieder. Sie behauptete weder, dass keine Frist
existiert, noch dass das ganze Postfach geprüft sei. Sie zeigte aber die bekannte
Aufnahmelücke nicht; dafür musste der Nutzer auf eine andere Seite wechseln.

Jetzt erhalten geeignete allgemeine Gedächtnisantworten eine kompakte lokale
Statuszeile. Sie unterscheidet fehlende Aufnahme, fehlende Einordnung und einen
nicht verlässlich prüfbaren Umfang. Bekannte Aufnahmelücken haben Vorrang vor
bekannten Analyselücken; bekannte Lücken haben Vorrang vor einer zusätzlichen
allgemeinen Unsicherheit. Das behauptet weder Relevanz noch Inhalt unbekannter
Mails. Auch ohne Hinweis gilt das Gedächtnis nicht als vollständig.

Der Hinweis wird aus dem aktuellen lokalen Bestand beim Senden, Wiederholen
und Öffnen berechnet, mit begrenzter SQL-Arbeit und ohne Provider, Connector,
Wartungsarbeit oder Schreibzugriff. Bereits belegte Aussagen und ihre Quellen
bleiben erhalten. Ausdrückliche Originalquellenfragen und die eigenständige
Aufgabenstatus-Anzeige behalten ihren engeren Umfang. Die Oberfläche zeigt den
Hinweis auch bei strukturierten Antworten außerhalb eingeklappter Belege.
ConversationStore und Modellhistorie bleiben frei von diesem aktuellen Hinweis;
ein ausdrücklich gespeicherter Feedback-Snapshot ist davon getrennt.

## Nachweise

- [Anforderungen](requirements.md), [chronologischer Autorbericht](author-report.md).
- [Erstes unabhängiges Review](review01.md) und [Nachreview](fix01-review.md):
  Der Mischfall mit unbekanntem Archiv oder deaktiviertem Zweitkonto ist
  korrigiert. Kein kritischer oder wichtiger Befund offen.
- Vor dem Review 176 Backendfälle, 14 UI-Fälle und TypeScript bestanden. Nach
  der eng begrenzten Korrektur 70 betroffene Backendfälle bestanden; UI und
  Gesprächsprojektion sind unverändert. Die Zahlen überschneiden sich.
- [Maschinenlesbare Validierung](validation.json); veröffentlichte Protokolle
  entfernen ausschließlich Leerzeichen am Zeilenende. Rohprotokolle sind im
  Autorbericht angegeben. Bestehende Starlette-TestClient-Warnung dokumentiert.

Der damalige kleine Befund zur Rückmeldungsablage wurde anschließend im
[separaten P2-Paket](../2026-11-05-feedback-intake/README.md) tatsächlich
reproduziert und behoben. Die ursprünglichen Reviewberichte dokumentieren den
damaligen Stand; der spätere Fix erhält den sichtbaren Snapshot und trennt den
technischen Hinweis ausschließlich für den Regressionsexport.

Keine reale Modellqualität, native Klickprüfung oder vollständige P1-Abnahme
wird aus diesen technischen Tests abgeleitet. Keine persönlichen Quellen,
Cloudaufrufe, Kosten, App-Installation oder Fortsetzung des Großimports.

Die getrennten [MIME- und Antwortverknüpfungsproben](../2026-11-05-mime-replay/README.md)
verwenden den unveränderten vorherigen Codecommit. Sie belegen tatsächliches
Wiederlesen und gespeicherte Kontotrennung, nicht semantische Aufgabenqualität.

## CI correction: central source eligibility

The full CI runs for published `f4be125` exposed a duplicated source predicate in the intake-gap query. Both Python 3.10 and 3.12 reported one failure in `test_geltende_quelle`, 10,293 passing tests, two skips and 26 passing subtests. The correction consumes `sql_nachricht` plus `sql_aktuelle_fassung`, keeping message scope and current version while respecting the central ignored-state and parent-withdrawal policy. The source-authority guard was not relaxed.

On an isolated archive of `c70acac` with only this correction applied, Python 3.12 passed 77 source/intake tests and three targeted parent-lifecycle cases. Independent scoped review approved the change; the existing TestClient deprecation warning remains. UI, Mac build and container CI on the prior published head passed. No CI rerun was triggered; a future published revision still requires its own result. No actual model, private mailbox, native window or bulk import was used in this correction.
