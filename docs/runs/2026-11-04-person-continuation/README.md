# Personenwahl: widersprüchliche Zusätze

Der abschließende unabhängige Review von PR #117 fand eine weitere stille
Fehlauswahl: Nach „Wo erreiche ich Alex Winter aus dem Einkauf?“ konnte ein
nachfolgendes „Diese Zuordnung ist unbestätigt“ übergangen werden. Ebenso wurden
„respektive aus der Schule“ und eine nachträgliche ausdrückliche Korrektur nicht
zuverlässig als offene Personenauswahl behandelt.

Ursache war die Prüfung auf eine begrenzte Liste verbotener Fortsetzungen. Die
Auswahl akzeptiert jetzt nur vollständige bekannte Fortsetzungen für Kontakt,
Aufgabenhandlung, Frist, Feedback oder Preis. Unbekannte Zusätze und weitere
Sätze führen zur bestehenden Rückfrage. Verneinte Aufgabenhandlungen bleiben
möglich; es werden weder Personen zusammengeführt noch Quellen verändert.
Komplexe gültige Fragen können weiterhin eine zusätzliche Personenwahl brauchen.

## Prüfung

- Vier neue Fälle über den echten `Agent.answer_memory`-Weg: zunächst vier
  erwartete Fehler, 25 bestehende Kontrollen bestanden. Nach der Korrektur
  verlangen alle vier Fragen eine Auswahl mit beiden getrennten Kontakten,
  bevor ein Modell aufgerufen wird.
- 173 betroffene Tests bestanden in 39,21 Sekunden: Personenfragen,
  Personenabgrenzung, Abruf, Kennzeichnung, expliziter Suchkontext und
  Arbeitsgedächtnisidentität. Eine bestehende Starlette/httpx-Warnung.
- Unabhängiger begrenzter Nachreview: 29 Tests bestanden; der wichtige Befund
  ist behoben, keine weitere kritische oder wichtige Beanstandung in dieser
  Korrektur.
- Weitere 147 Tests für Originalantwort, Rückfrage, Gesprächsrouting und
  Kontextrelevanz bestanden in 21,97 Sekunden, eine bestehende Warnung.
- Im getrennten nativen Mac-Testfenster am 04.11.2026 um 14:26 Uhr die Frage
  mit nachträglicher Korrektur zur Schule eingegeben und gesendet. Beide
  Kontakte erschienen als auswählbare Rückfrage. Null Modellaufrufe, keine
  Cloudaufrufe. Dies bestätigt die tatsächliche Fenstereingabe für diesen Fall;
  es ist noch kein Update der normalen App.

Diese Offlineprüfung verwendet künstliche Kontakte und einen begrenzten
Modell-Ersatz für den Antwortpfad. Sie ist kein zusätzlicher Qwen-Qualitätslauf
und kein Nachweis einer bereits installierten neuen App. Die vorherigen echten
Modellläufe bleiben unter ihren jeweiligen Code-Prüfsummen dokumentiert.

## Vollständige CI: Vertragsabgleich

Der vollständige Lauf auf `60efc1e` zeigte unter Python 3.10 und 3.12 jeweils
9 Fehler, 9.965 bestandene und 2 übersprungene Tests. Die Fehler wurden lokal
reproduziert: 9 fehlgeschlagen, 116 bestanden. Es waren nicht aktualisierte
Erwartungen an die ergänzten `entity_errors`, zwei Testersatzfunktionen ohne
`focus_query`, ein Zugriff auf das frühere `text`-Feld statt `originalsaetze`
und ein Anführungszeichen-Prüfer, der eine reguläre Zeichenklasse als Prosa
interpretierte.

Die Tests prüfen jetzt die vollständigen neuen Verträge. Insbesondere muss
weiterhin eigene Belegsubstanz vorliegen und die fremde Zusage fehlen; die
Quellen- und Widerrufsprüfungen wurden nicht abgeschwächt. Das Suchmuster
verwendet für dasselbe öffnende Anführungszeichen eine äquivalente Unicode-Escape.
Unabhängiger Diff-Review bestätigte unveränderte Schutzprüfungen und identisches
Musterverhalten. Anschließend bestanden alle 179 Tests der betroffenen fünf
Dateien in 30,87 Sekunden, mit einer bestehenden Warnung. Ein grüner vollständiger
Lauf auf dem abschließenden Commit ist weiterhin Voraussetzung für die Freigabe.
