# Deutsche Fristformulierungen

Stand: 19.10.2026. Zielfassung 1.0.26. Nur künstliche Sätze; keine private Mail, kein Modell, keine Cloud.

## Umfang

`fristen.py` findet Datumsangaben und entscheidet, welche davon eine Frist ist. Laut den
Protokollen vom 19.10. blieben komplexere deutsche Formulierungen oft ohne abgeleitete Frist.
Diese Runde erweitert beides, ohne das Grundprinzip aufzugeben: Eine falsche Frist ist schlimmer
als keine.

* **Neue Angaben:** Binnenfristen („innerhalb von 14 Tagen“, „binnen zwei Wochen“, „innerhalb eines
  Monats“), Fristen vor einem Ereignis („spätestens 24 Stunden vorher“, „drei Werktage vor Ihrem
  Termin“, immer ohne Datum) und Wochentag mit Datum („bis Freitag, den 11. September“).
* **Neue Bindungen:** mehr Handlungen (zahlbar, Zahlungsziel, begleichen, unterschreiben, widerrufen,
  Bescheid geben …), trennbare Verben, Modalverb mit Handlung am Satzende, „muss bis … eingegangen
  sein“, benötigte Unterlagen, „zu“-Infinitiv nach Bitte oder Zusage, verbundene Fristen („A bis …
  und B bis …“), „bis einschließlich“, „bis zum Ablauf des“.
* **Neue Ausschlüsse:** ein Zustand nach dem Datum („geschlossen“, „gültig“, „verfügbar“), ein
  gemeldeter Eingang ohne Modalverb („sind bis 18.09. eingegangen“), „nicht vor Montag“, „nicht zu
  betreten“, ein Bedarf an beliebigen Dingen („Wir brauchen das Auto bis …“).
* **Akten:** `AKTEN_VERSION` 10. Zwischengespeicherte Akten werden nach dem Update mit den neuen
  Regeln neu berechnet. Originale, Bezüge und bestätigte Entscheidungen bleiben unverändert.

## Messung

Entwickelt wurde an eigenen Beispielen (in `sidecar/tests/test_fristen_formulierungen.py`). Gemessen
wurde an zwei Prüfsätzen, die zwei getrennte Hilfsagenten nach einer festen Anleitung geschrieben
und annotiert haben, ohne Einblick in den Code: [`pruefsatz_1.py`](pruefsatz_1.py) (60 Sätze) und
[`pruefsatz_2.py`](pruefsatz_2.py) (70 Sätze). Nachrechnen:
`PYTHONPATH=sidecar python docs/runs/2026-10-19-fristen-formulierungen/messen.py`.

| Messung | Fassung 1.0.25 | Diese Änderung |
|---|---|---|
| Prüfsatz 1, erste Messung (blind) | 6 von 36 Fristen richtig, 24 von 24 ohne Frist richtig, 2 Sätze mit falschem Kalendertag | 18 von 36, 24 von 24, 0 |
| Prüfsatz 1, nach der zweiten Runde (nicht mehr blind) | – | 35 von 36, 24 von 24, 0 |
| Prüfsatz 2 (blind, danach keine Änderung) | 8 von 40, 30 von 30, 2 | **25 von 40, 30 von 30, 0** |

Nach der ersten Messung wurden die Fehler aus Prüfsatz 1 angesehen und allgemeine Regeln ergänzt.
Prüfsatz 1 ist danach kein unabhängiger Nachweis mehr. Die belastbare Zahl ist die von
Prüfsatz 2: Er wurde erst nach Abschluss der Regeln einmal gemessen, und danach wurde nichts mehr
geändert.

Alle vier falschen Kalendertage der Fassung 1.0.25 kamen aus „bis Montag, den 14. September“: Die
alte Regel nahm den nächsten Montag (7.9.) statt des genannten Datums. Passen Wochentag und Datum
nicht zusammen („Dienstag, den 17. September“, ein Donnerstag), bleibt die Frist jetzt ohne Datum
sichtbar.

Zusätzlich 30 eigene Gegenproben, die einer Frist ähneln (Abbuchung, Öffnungszeit, Vergangenes,
„In zwei Wochen beginnt die Anmeldung“): alle ohne Frist, auch im Test.

## Was offen bleibt

Die 15 Fehler in Prüfsatz 2 fallen in diese Gruppen:

* „zu“-Infinitiv mit Wörtern dazwischen („ist bis 24.09. an die Gerichtskasse zu zahlen“, „beim
  Prüfungsamt einzureichen“).
* Ihr-Formen und fehlende Verben: „Meldet … an“, „widersprechen“, „nachweisen“, „einchecken“,
  „Berufung einlegen“.
* Unscharfe Angaben werden zwar erkannt, aber nicht als Frist gebunden: „zeitnah“, „umgehend“,
  „Anfang Oktober“, „in KW 40“.
* Aufzählungen nach einem Doppelpunkt („Zählerstände bis übermorgen melden, Schlüssel bis zum
  30.09. abgeben“): Nur die erste Frist wird gefunden.
* Zwei Fristen in einem Satz, die zweite nach „brauchen wir … :“.

Keine dieser Lücken erzeugt eine falsche Frist; die Angabe bleibt im Original. Eine nächste Runde
braucht einen neuen, noch ungesehenen Prüfsatz.

## Prüfungen

* `test_fristen_formulierungen.py`: 102 Fälle, darunter 30 Gegenbeispiele, Ende-zu-Ende über die
  Personenakte und der Neuaufbau einer alten zwischengespeicherten Akte.
* Bestehende Tests der Fristen, Datumsrollen, Quellenfristen, Akten, Satzprüfung und Lint
  (394 Tests) unverändert bestanden.
* Sabotageproben: Jede neue Zusicherung wurde absichtlich gebrochen. Alle elf werden von Tests
  gefangen: Wochentag passt nicht zum Datum; Zustand nach dem Datum; gemeldeter Eingang als Pflicht;
  Binnenfrist mit Ereignis aufgelöst; Werktage gezählt; „nicht vor“; „nicht zu“; Bedarf an
  beliebigen Dingen; Verb am Satzende ohne Modalverb (erst nach einem zusätzlichen Gegenbeispiel);
  Komma nach dem Einschub; Akten-Cacheversion nicht erhöht.
* Vollständige Backend-Suite: siehe PR.

## Grenzen

Die Sätze sind erfunden und von einem Modell annotiert; einzelne Annotationen sind diskutabel
(etwa „zeitnah“ als Frist). Die Zahlen gelten für diese Prüfsätze, nicht für ein echtes Postfach.
`fristen.py` bleibt eine begrenzte Grammatik ohne Modell, kein allgemeiner Parser. Aus einer Frist
entsteht weder Zuständigkeit noch Aufgabe; Fristen ohne festes Datum bleiben wörtlich. Der
pausierte Großimport ist davon nicht berührt. Das Mac-Update und eine Probe mit eigenen aktuellen
Mails stehen aus.
