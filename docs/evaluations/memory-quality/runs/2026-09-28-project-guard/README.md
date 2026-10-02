# Projektgrenzen bei Originalquellen — 28. September 2026

Geprüfter Produktionscode: `46465369b2f0bd4d5e76a36b8f3ef6c324b66d59`.
Vorgänger: `105d0af` (Merge #115). Keine neuen Modelle, keine Cloud-Aufrufe.

## Problem und Verhalten

Das lokale Modell konnte eine Quelle zu einem anderen ausdrücklich genannten
Projekt liefern oder eine zweite Quelle zur gleichen Frage übergehen. Die
Auswahlanweisung allein verhinderte beides nicht. Eine nachgeschaltete Prüfung
verwendet nun vorhandene Projektzuordnungen und eindeutige `Projekt …`-Angaben
im Original. Sie blockiert erkennbare Abweichungen zum erfragten Projekt.
Bei einer einzelnen Sachfrage und gleichem belegten Gegenstand in zwei
verschiedenen Projekten erhält der Nutzer die vorhandene Vorgangsrückfrage,
auch wenn das Modell nur eine Quelle ausgewählt hat.

Es entstehen keine Projekte, Personenverknüpfungen oder bestätigten Fakten.
Originaltexte und Indizes bleiben unverändert. Die Prüfung kostet keinen
zusätzlichen Modellaufruf. Eine nachträgliche Projektzuordnung macht neue,
auf dem früheren Stand beruhende Antworten ungültig. Quellenentzug und
Korrektur bleiben über die vorhandene Frischeprüfung abgesichert.

## Lokale Modellprüfung

Mit unverändertem `qwen3.5:4b`, ohne semantische Suche, durch echte
HTTP-Aufnahme, Hintergrundklassifikation und Antwortweg mit produktiver
Werkzeugregistrierung:

- Bekannte sieben Ablaufprüfungen zunächst **7/7**, zuletzt **6/7**, zuvor nach #115 **5/7**.
  Letzter Fehlschlag: `conditional` lieferte die richtige Quelle vollständig,
  aber das Modell verlangte unnötig eine Personenentscheidung. Das wird als
  Fehlschlag gezählt, nicht durch Wiederholungen bis zum Erfolg ausgeblendet.
  Die Prüfungen für beide beauftragten Projektfehler sind in allen Läufen bestanden.
- Fünf neue, vor dem ersten Aufruf festgelegte Beispiele: **5/5**.
- Neue Beispiele: fremdes Zielprojekt, Bauabnahme mit zwei Projekten,
  mehrteiliger Projektname, ausdrücklicher Vergleich, Empfänger statt Projekt.
- Die letzte reine Gegenfall-Einschränkung (Personenname allein ist kein
  gemeinsamer Sachgegenstand) wurde anschließend mit beiden Sätzen erneut
  geprüft. Diese Wiederholung ist eine Regression, kein neuer Blindtest.

`results.json` enthält Prüfungen und synthetische Antworten; die vollständigen
lokalen Modellprotokolle liegen unter `work/project-acceptance-20260928/`.
Zum Nachvollziehen den Runner mit einem der `*-cases.json`-Sätze als
`holdout.json` in ein leeres Verzeichnis kopieren und aus dem Checkout mit
`PYTHONPATH=sidecar python <runner> --model qwen3.5:4b` starten.
Der Runner verweigert das Überschreiben bestehender Ergebnisse.

## Grenzen

Das ist ein zusätzlicher Schutz für automatisch gelesene Originalquellen,
keine allgemeine semantische Projekt- oder Entitätserkennung. Er erkennt
explizite, positiv formulierte Projektbezeichnungen und vorhandene
Zuordnungen. Freie Andeutungen, unbekannte Abkürzungen, negierte/verschachtelte
Bezüge und fehlende Kandidaten bleiben beim bisherigen Antwortweg. Die
Prüfung erfindet bei unklaren Bezügen keine dauerhafte Zuordnung.

Die ergänzende Rückfrage braucht eine eindeutige Sachfrage mit passendem
Hauptwort in beiden gefundenen Textstellen. Bekannte Projektnamen und ein
abschließender Namenszusatz können die Auswahl begrenzen. Ein anderer
Gegenstand, derselbe Projektbezug oder ein ausdrücklich verlangter Vergleich
lösen keine zusätzliche Projektrückfrage aus. Ein gemeinsamer Personenname
allein reicht nicht. Bestätigte K-Einträge sind nicht Gegenstand dieses Filters.

Die kleinen Beispiele belegen diese Verbesserungen, keine allgemeine
Fehlerquote. Die bekannten Suchlücken bei Umschreibungen sind weiterhin offen;
der frühere Wert 11/16 wird durch diesen Filter nicht verbessert.

## Automatisierte Regression

- Drei ursprüngliche Fehler vor dem Fix beobachtet: fremdes Projekt geliefert,
  ausgelassener Projektkonkurrent, Antwort trotz geänderter Projektzuordnung.
- Zwei zusätzliche Gegenfälle vor ihrer Korrektur rot: Empfänger fälschlich
  als Projekt verstanden; gemeinsamer Personenname zieht fremdes Thema hinzu.
- 15 neue Tests einschließlich HTTP-Aufnahme, Rückfrage und Quellenentzug.
- Vollständiger Lauf vor dem abschließenden App-Befund: **2447 bestanden**, zwei bestehende
  DeprecationWarnings (Starlette/httpx und AnyIO), 291 Sekunden.
- Ein früherer vollständiger Lauf wurde wegen der zusätzlichen Gegenfall-
  Korrektur bei 1144 bestandenen Tests abgebrochen; er ist kein Abschlussbeleg.
- Docker-Build einschließlich Weboberfläche erfolgreich. Das Image trägt
  den geprüften Produktionscommit als `org.opencontainers.image.revision`.

## Reale, gefüllte Mac-Test-App

Die isolierte Kopie auf Port 8892 wurde aktualisiert. Die ursprüngliche App auf
8891 und die vorherigen Testcontainer bleiben erhalten. Keine Neuinstallation
oder Löschung der Originaldaten. Automatische Modelle nach der Aufnahme
wieder pausiert; externe Konten in der Testkopie weiterhin deaktiviert.

Zwei per HTTP hochgeladene synthetische Quellen nennen eine Aufzugsprüfung für
Rosenbogen und Silberhof. Beim ersten Versuch war die zweite Quelle nach
40 Sekunden noch nicht eingeordnet. Der zweite Versuch mit längerem Warten
bestätigte die Aufnahme, deckte aber einen weiteren Antwortfehler auf: Mit
zusätzlichen Kandidaten aus der Testdatenbank verlangte das Modell eine
Personenentscheidung statt einer Projektentscheidung und ließ eine Quelle weg.
Dieser Fehlschlag wurde nicht als Erfolg gezählt.

Zwei weitere HTTP-Regressionsfälle reproduzierten den fehlerhaften Personen-
und Zeitstatus. Die Projektprüfung greift jetzt auch bei einer unbegründeten
Personenrückfrage für Dokumente ohne Absenderidentitäten; eine unbegründete
Zeitrückfrage wird vor der Projektprüfung normalisiert. Echte Absender-
Mehrdeutigkeiten bleiben beim bisherigen Personenweg.

Die identische Frage mit den unveränderten Quellen besteht auf dem endgültigen
Code: Beide Projektquellen und die Vorgangsrückfrage erscheinen. Eine Frage zum
unbelegten Projekt Tannenblick liefert keinen der Termine. Im Browser wurde die
Auswahl angeklickt: Die neue Antwort enthält nur Rosenbogen mit dem 8. Dezember.
Die frühere Rückfrage bleibt als Gesprächsverlauf sichtbar. Die Knöpfe heißen
noch nach Quelldateien; besser lesbare Projektbeschriftungen bleiben UX-Arbeit.

Die zwölf Entwicklungsfälle wurden nach diesem App-Befund erneut geprüft:
**11/12 bestanden**, einschließlich aller Projektfälle. Der offene
Statusfehler der Bedingungsfrage steht oben und in `results.json`. Die Aufnahmeverzögerung ist separat dokumentiert; diese Änderung
verspricht keine sofortige Verarbeitung eines größeren Rückstands.

Abschließender vollständiger Lauf auf `4646536`: **2449 bestanden**,
zwei bestehende DeprecationWarnings, 259,51 Sekunden.
