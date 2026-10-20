# Fassung 1.0.26: Gedächtnis-Durchsicht „wie ein guter Stabschef“

Stand 20.10.2026. Zielversion 1.0.26. Geprüft wurde ausschließlich mit synthetischen
Daten (Messlatte-Welt, Attrappen für IMAP, CalDAV und Microsoft Graph, künstliche
Kalenderdateien); keine persönlichen Daten, kein echtes Postfach, kein bezahlter
Modellaufruf. Die Abnahme am Mac steht aus.

## Inhalt und Reihenfolge

| PR | Paket | Kern |
|---|---|---|
| #77 | Einstieg | Einstieg auf 1.0.25 (Dokumentation) |
| #78 | Fristen | Deutsche Fristformulierungen ([Protokoll](../2026-10-19-fristen-formulierungen/README.md)) |
| #79 | CI | CI wieder grün (Python 3.10), Netzsperre der Microsoft-Tests, parallele Tests |
| #80 | 1 Akte | „Braucht dich“, Entscheidungen (Migration 23), Zeitstrahl, Richtung, Mailverläufe |
| #81 | 2 Abrufen | Umlaut-Umschrift, Zeitangaben mit Suche im Zeitraum, „Worauf warte ich noch?“ |
| #82 | 5 Ablage | Entscheidungen gelten für den Text der Quelle; Terminort zur Organisation |
| #83 | 3 Hereinholen | Neue Post trotz Pause, ehrliche Anmeldung mit „Neu anmelden“, neueste zuerst, keine Dubletten nach neuer Postfachkennung |
| #84 | 4 Kalender | Zeitzonen, Serien, Absagen aus CalDAV und Abo; Abo bis 25 MB |

#80 baut auf #78, #81 auf #80. Damit die Merges ohne Konflikt gelingen, werden diese
PRs mit „Create a merge commit“ gemergt (mit „Squash“ kollidieren je eine Zeile in
`akten.py` und `time_scope.py`; lokal nachgestellt).

## Prüfungen je Paket

Jedes Paket: volle Backend-Suite, neue Tests, die vor der Änderung rot waren,
Sabotageproben (Zusicherung absichtlich gebrochen, passender Test wird rot) und
unabhängige Reviews durch eigene Prüf-Agenten, deren Befunde vor dem Merge
eingearbeitet wurden. Bei #83 und #84 lief nach jeder Korrekturrunde ein weiteres
Review auf den Korrekturen, bis keine hohen Befunde und keine falschen Ergebnisse
mehr kamen. Einzelheiten stehen in den PRs.

| Paket | Volle Suite (Paketstand) | Sabotageproben | Review | Browser |
|---|---|---|---|---|
| 1 Akte (#80) | 7.377 bestanden | 16, alle gefangen | 14 Befunde, eingearbeitet | 1280/768/390 px, Tastatur, Fokus |
| 2 Abrufen (#81) | 7.437 bestanden | 16, alle gefangen | 18 Befunde, eingearbeitet | 1280/390 px |
| 5 Ablage (#82) | 7.263 bestanden | 13, alle gefangen | 9 Befunde, 7 behoben, 2 vermerkt | keine Oberflächenänderung |
| 3 Hereinholen (#83) | 7.371 bestanden | rund 100 in drei Runden, alle gefangen | 2 Runden: 1 hoher, 12 mittlere, 12 niedrige Befunde, alle behoben | 390 px, Pause, Neu anmelden, Fokus und Escape |
| 4 Kalender (#84) | 7.421 bestanden | vier Runden, alle gefangen bis auf zwei ohne beobachtbare Wirkung | 3 Runden mit 7, 11 und 11 Befunden, alle behoben; zuletzt 0 falsche Termine in 7.800 Zufallsregeln | keine Oberflächenänderung |

Auf dem Paketstand fiel jeweils nur `test_microsoft_anmeldung::test_ein_netzversuch_in_tests_wird_gefangen`
(Namensauflösung im Container); #79 behebt genau diesen Fall.

**Messlatte** (synthetische Welt, ohne Modell):

* Abrufen, 83 Fragen: erwartete Belege auf Rang 1 32 → 35 von 142, bis Rang 5 91 → 92,
  bis Rang 12 unverändert 112. Sieben Belege rücken nach vorn (einer von Rang 10 auf 3),
  drei um einen Rang zurück, keiner fällt aus den ersten fünf.
* Akten: 5 von 5 Fällen, 15 von 15 erwarteten Quellen im Verlauf, vor und nach den Paketen.
* Auf dem Gesamtstand gemessen: dieselben Zahlen, Beleg für Beleg gleich wie Paket 2 allein.

## Gesamtstand

Geprüft wurde der Baum dieses Release-Branches: alle acht PRs in ihrem Endstand,
zusammengeführt mit Merge-Commits, keine Konflikte. Das ist der Stand, der nach allen
Merges auf `main` liegt.

* Volle Backend-Suite unter **Python 3.10** (wie die CI): **7.731 bestanden, 0 fehlgeschlagen**, 3 übersprungen, 26 Unterfälle.
* Volle Backend-Suite unter Python 3.13: **7.731 bestanden, 0 fehlgeschlagen**, 3 übersprungen, 26 Unterfälle.
* Geprüfter Code-Stand: `583d7ea` (danach nur dieses Protokoll geändert).
* Oberfläche: `tsc` ohne Fehler, **763 von 763** Oberflächentests, Produktionsbau erfolgreich.
* Browser (echtes Chromium, synthetische Messlatte-Welt bzw. Attrappe, auf diesem Baum):
  Akte 24 von 24 Prüfungen (Braucht dich, Erledigt/Rückgängig, Zeitstrahl mit Tastatur,
  Fokus, 1280/768/390 px), „Worauf warte ich noch?“ und „Was habe ich zugesagt?“ mit
  Quellenlinks, Pause und „Neu anmelden“ (9 Bilder); Konsole jeweils ohne Fehler.

## Grenzen und offene Abnahme

* Nur synthetische Daten. Nicht geprüft: echte Postfächer, echte CalDAV-Server, echte
  Google- und Microsoft-Anmeldungen, das Mac-Update selbst.
* Einmalig nach dem Update: Akten werden neu berechnet (Akte 11); Termine werden neu
  eingeordnet; jede CalDAV- oder Abo-Serie wird von einer Episode zu Einzelterminen
  (die alte Episode wird entzogen); Entscheidungen, die bisher nur wegen nachgetragener
  Kontakte oder einer Projektzuordnung als veraltet galten, wirken wieder.
* Die Pause hält ab 1.0.26 nur ältere Mails und jede Modellarbeit an; neue Post,
  Termine und die Sicherung kommen ohne Modell weiter an. Der Import älterer Mails
  bleibt pausiert.
* Abnahme am Mac: eine Akte mit abgesagtem Termin ansehen, „Worauf warte ich noch?“
  fragen, Pause setzen und eine neue Mail empfangen, einen Google-Kalender über die
  iCal-Adresse prüfen.
