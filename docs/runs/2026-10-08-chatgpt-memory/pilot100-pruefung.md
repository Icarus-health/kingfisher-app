# Abschlussprüfung der echten 100-Quellen-Probe

Geprüft am 08.10.2026 auf dem installierten Mac, Code `e882740`, Modell
`gpt-6.1-sol`. Ausschließlich vorhandene Ergebnisse gelesen: keine zusätzlichen
Modellanfragen, keine Änderungen am persönlichen Gedächtnis, kein großer Lauf.
Die private Prüffassung der Originale liegt außerhalb des Repositorys. Dieser
Bericht enthält keine Originaltexte, Adressen, Zugangsdaten oder Quellen-IDs.

## Entscheidung

**Der große Lauf bleibt gesperrt.** Der Test ist technisch beendet, aber weder
vollständig noch als verlässliche Ende-zu-Ende-Gedächtnisfunktion abgenommen.

| Messung | Ergebnis |
| --- | ---: |
| Durchgesehene Quellen | 100 |
| Beide Einordnungsschichten vollständig | 48 |
| Ungültige Entitätsbelege in der Kategorienphase | 37 |
| Zurückgestellt wegen Verarbeitungsgrenzen | 15 |
| Arbeitsgedächtnis vollständig | 99 |
| Arbeitsgedächtnis zurückgestellt | 1 |
| Tatsächliche Modellaufrufe | 219 / 400 |
| Laufdauer | rund 41 Minuten |

Die 15 zurückgestellten Quellen sind unterschiedlich: zwölf überschreiten die
Kategoriengrenze von 24 Absätzen, obwohl ihre Texte nur etwa 2.700 bis 5.500
Zeichen lang sind. Zwei Anhänge überschreiten die Kategorien-Textgrenze; eine
weitere Quelle ist bereits als unvollständig markiert. Bei 14 dieser 15 ist das
Arbeitsgedächtnis trotzdem vollständig. Der gespeicherte Fehlerabschnitt
`source` unterscheidet diesen Fall noch nicht von einem Fehler vor der ersten
Einordnung.

Bei den 37 ungültigen Entitätsantworten wurden keine neuen Themen oder Entitäten
gespeichert. Der Fehlercode `invalid_entity_evidence` unterscheidet fehlende,
mehrdeutige, doppelte oder unbelegte Absenderbelege noch nicht. Ohne die verworfene
Modellantwort ist die jeweilige genaue Ursache nicht nachträglich nachweisbar.
Eine bestimmte Einzelursache für alle 37 wird deshalb nicht behauptet.

## Originale und Wiederfinden

- Alle 100 Quellen entsprechen weiterhin den vor dem Lauf freigegebenen
  Fingerabdrücken. Der Bestand enthält weiterhin 340 Originalquellen; SQLite
  `quick_check` besteht.
- 187 gespeicherte Entitätsstellen, 93 Themenstellen und 888
  Arbeitsgedächtnisstellen haben gültige Originalbereiche und passen zum
  jeweiligen gespeicherten Einordnungsfingerabdruck. Dies ist ein technischer
  Belegtest, keine Messung semantischer Vollständigkeit.
- Acht gezielte lokale Wortsuchproben fanden jeweils die vorab bestimmte
  Originalquelle unter höchstens zwölf Abschnittstreffern. Auch zusätzliche
  Quellen wurden geliefert; drei Suchen meldeten weitere abgeschnittene
  Ergebnisse. Das ist kein Nachweis hoher Präzision, freier Umformulierungen
  oder einer richtig formulierten Antwort. Es wurden keine Antwortmodelle
  gestartet.
- Das native App-Fenster zeigt den tatsächlichen Abschlussstand 100/100,
  48 vollständig und 52 offen sowie den Hinweis, dass diese Probe den großen
  Lauf nicht freigibt.

Die Auswahl war eine Speicherseite, keine repräsentative Zufallsstichprobe.
Sie enthält Mails und Anhänge mit Quelldaten von 2015 bis 2026, viele automatische
Nachrichten und 96 bereits archivierte Quellen. Der Kategorienstand und die
Suche durch alte Quellen sind deshalb getrennt vom täglichen Aufgabenfluss zu
bewerten.

## Inhaltliche Prüfung

Eine unabhängige Prüfung der gespeicherten Entitätsausgaben fand keine eindeutige
Verwechslung eines Unternehmens/Servicepostfachs mit einer Person. Alle 18
gespeicherten Absenderbelege passen zum jeweiligen Absender-Anzeigenamen.
Fehlende Menschen, Namensauflösung und Beziehungen sind damit nicht abgenommen.
Ein Name mit HTML-Zeichenkodierung und OCR-bedingte Namensabstände bleiben als
Originalzitat sichtbar; das ist noch keine saubere Personenidentität.

Die geschichtete Inhaltsstichprobe des Arbeitsgedächtnisses zeigt konkrete
Nutzbarkeitsmängel:

- Werbe-, Bewertungs- und Bedienaufforderungen werden teilweise als `request`
  gespeichert. Das darf nicht automatisch zu einer Aufgabe des Nutzers werden.
- Signaturmaterial wird teilweise als `historical` eingeordnet; manche klare
  Benachrichtigungen oder Aussagen werden unnötig `uncertain`.
- Ein rund 1.370 Zeichen langer Rechnungsabschnitt wird insgesamt als
  `commitment` behandelt, obwohl nur ein Teil die Zusage trägt.
- Alle vier gespeicherten `commitment`-Stellen beschreiben Zusagen oder
  Abrechnungsaussagen des Mailabsenders. Die Art allein benennt keinen
  Verantwortlichen und darf nicht als eigene Zusage des Nutzers dargestellt
  werden.

In den geprüften Negationen wurde keine Umkehrung der Aussage gefunden.
Die Stichprobe ist keine vollständige Wahrheits- oder Recall-Messung aller
888 Abschnitte und ersetzt keine Prüfung der Antworten im Nutzerfluss.

## Gezielte Folgearbeit

1. Fehlerphase und sichere Unterursachen dauerhaft unterscheiden, ohne private
   Modellantworten in allgemeine Protokolle zu schreiben.
2. Kategorien/Entitäten über begrenzte Abschnitte verarbeiten und wiederholte
   Namen eindeutig belegen. Quellenprüfung und Vollständigkeitsgate erhalten.
3. Werbe-/Bedienmaterial von persönlichen Anliegen trennen sowie Zusagen nach
   Urheber unterscheiden; übergroße Belegabschnitte gezielt verbessern.
4. Danach nur die offenen Fälle erneut freigeben und eine breitere, bewusst
   zusammengestellte Probe einschließlich Antwort- und Aufgabenfluss prüfen.

Es wurden für diese Prüfung keine zusätzlichen Pakete gestartet, keine
GitHub-Prüfungen wiederholt und keine Daten stillschweigend bereinigt.

## Gezielte Korrektur nach Freigabe

- Der ausdrücklich freigegebene ChatGPT-Pfad kann Kategorien nun abschnittsweise
  verarbeiten: höchstens 60.000 Zeichen und 120 Originalabsätze je Quelle,
  höchstens 12.000 Zeichen/24 Blöcke je Anfrage und 4.000 Zeichen je Textfragment.
  Die Quelle bleibt unverändert. Lokal berechnete Positionen zeigen weiterhin
  in ihren Volltext. Alle Abschnittsergebnisse werden vor einem gemeinsamen
  Schreibvorgang validiert; ein Fehler hinterlässt keine neuen Teilbelege.
- Wiederholte Namen brauchen eine explizite, geprüfte Vorkommensnummer.
  Eindeutige ältere Antworten bleiben kompatibel. Mail-Anzeigenamen mit RFC2047-
  Zeichenkodierung werden als Headertext dekodiert; das führt keine Identitäten
  zusammen. Die bisherigen lokalen Positionsantworten bleiben auf ihrem Pfad.
- Die quellweite Aggregation ist auf 128 Entitäts- und 192 Themenbelege begrenzt.
  Die Grenze je einzelner Modellantwort bleibt bei acht beziehungsweise zwölf.
  Auch diese Limits bedeuten, dass keine vollständige Erkennung aller Namen
  behauptet werden kann. Das bestehende Gesamtbudget des Cloudauftrags steigt
  nicht; ein umfangreicher Auftrag kann weiterhin sein Budget erreichen.
- Der Cloudauftrag speichert nur geschlossene Fehler-Unterursachen, keine
  verworfenen Modelltexte. Die additive Schemaänderung bewahrt bestehende
  Fehlerdatensätze. Altdaten bekommen `unspecified`; unbekannte frühere Ursachen
  werden nicht nachträglich erfunden. Die Fehlerphase unterscheidet künftig
  Grundauswertung von Kategorien/Personen und setzt bei einem reinen
  Kategorienfehler eine erfolgreiche Grundeinordnung nicht zurück.
- Die Anweisung für das Arbeitsgedächtnis trennt persönliche Anliegen von
  Werbe-, Bewertungs- und Navigationshinweisen; Signaturen sind kein alter
  Nachrichteninhalt. Zusagen-Zitate tragen „Urheber in Quelle prüfen“ und der
  Antwortauftrag verbietet, allein aus Art oder äußerem Absender eine Zusage
  des Nutzers abzuleiten. Dies sind Anweisungen und sichtbare Hinweise, kein
  technischer Beweis semantisch richtiger Modellantworten. Der große
  1.370-Zeichen-Abschnitt bleibt eine bekannte Grenze der Blockgranularität.

Prüfung vor Installation: 325 betroffene Backendtests, 362 Frontendtests und
TypeScript-/Produktionsbuild bestehen. Neue Regressionen wurden zuerst rot
ausgeführt. Der rein lokale Abschnitts-Vertragstest auf den 15 zuvor begrenzten
Originalen erreicht 14; die als unvollständig markierte Quelle bleibt abgewiesen.
Dabei wurde kein Modell befragt. Die ursprüngliche 48/100-Probe bleibt ein
datierter Befund und wird durch diese Tests nicht nachträglich als bestanden
bezeichnet.

## Übersichtliche Bereiche

Empfohlene Bereichsansichten: Arbeit & Projekte, Privat & Familie, Gesundheit
sowie Finanzen & Verträge. Menschen, Organisationen, Orte und Zeitverlauf bleiben
quer dazu erreichbar. Mehrfachzuordnung ist erlaubt; eine neue Ansicht soll
keine Kopien oder weitere verpflichtende Ablagearbeit erzeugen. Bestehende
Kategorien werden in dieser Korrektur nicht stillschweigend umbenannt oder
migriert. Neue Kategorien ändern keine Originale; eine rückwirkende Zuordnung
braucht aber eine gezielte Neuauswertung der betroffenen Ableitungen.

## Installation und begrenzte echte Nachprüfung

Auf dem Mac ist `1.0.6-local.0b56993` installiert. Der erste Start scheiterte
am vollen 60-GiB-Datenträger der lokalen Docker-Umgebung, nicht an einer
Quelleneinordnung. App, private Konfiguration und kaltes Datenvolume waren
bereits gesichert. Ausschließlich unbenutzte alte Kingfisher-Programmbilder
wurden zusätzlich in zwei überprüfte lokale Archive gesichert und danach aus
Docker entfernt: 66 Bilder, rund 3,1 GB Archivdaten. Keine Container oder
Datenvolumes wurden gelöscht. Danach waren rund 3,1 GiB wieder frei; die neue
App läuft ohne Neustartschleife. Die Archive und die vorherige App bleiben als
Rückweg außerhalb des Repositorys erhalten.

Vor und nach der Nachprüfung: 340 Originalquellen mit unveränderten Digests,
17 SQLite-Dateien mit erfolgreichem `quick_check`, ChatGPT-Zugang erhalten.
Die lokale Modellauswertung bleibt ausgeschaltet, die bestehende Mailpause
unverändert. Der Mailabruf ist weiterhin nicht pausiert.

Sieben gezielt ausgewählte, bereits für ChatGPT freigegebene Quellen wurden
mit `gpt-6.1-sol` als **Nachprüfung**, nicht als neuer Pilot, verarbeitet. Der
lokale Abschnittsplan erlaubte höchstens 22 Anfragen; tatsächlich waren es 21.
Keine neue Quelle, kein anderer Anbieter und kein großer Import. Das bestehende
technische Auftragslimit der Nachprüfung wird im Fenster weiterhin als 4.000
angezeigt; es ist nicht die Zahl der für dieses Paket geplanten Anfragen.

| Messung | Ergebnis |
| --- | ---: |
| Quellen durchgesehen | 7 |
| Grundeinordnung vollständig | 7 |
| Beide Schichten vollständig | 3 |
| Kategorienphase: unbelegte Absenderrolle | 4 |
| Modellanfragen | 21 |
| Gespeicherte Originalbereiche geprüft | 111 |

Eine zuvor wegen vieler Absätze zurückgestellte automatische Mail kann jetzt
in beiden Schichten verarbeitet werden. Vier Kategorienantworten scheitern
weiterhin am geschlossenen Belegtest `entity_sender`. Die erfolgreichen
Grundeinordnungen bleiben erhalten; die Kategorienphase wird deshalb nicht
als bestanden gezählt. Die verworfenen Modellantworten werden nicht gespeichert,
somit ist die jeweils betroffene behauptete Entität nicht nachträglich belegbar.

Bei vier ausgewählten automatischen Nachrichten sind die früheren
Bedien-/Serviceaufforderungen nicht mehr als `request` gespeichert. Zwei
persönliche Bitten bleiben als solche erhalten. Das ist ein positiver
Stichprobenbefund, keine Garantie für alle Benachrichtigungen oder Aufgaben.
Die 111 gespeicherten Stellen passen zu den Originalbereichen. Die ursprüngliche
100er-Probe und ihre Sperre bleiben unverändert; drei vollständige Nachprüfungen
schalten den großen Lauf nicht frei.

Im nativen Fenster wurden Fortschritt, gesperrte parallele Startaktionen und
aufgeklappte Hinweise geprüft: „Themen und Personen offen. Die Zuordnung zum
Absender ist nicht belegt. Die gespeicherte Grundeinordnung bleibt erhalten.“
Die Quellenansicht bleibt erreichbar. Ein unabhängiges Code-Review der
Korrektur fand keinen konkreten Blocker im geprüften Umfang. Die verbliebene
Absenderrollen-Zuordnung ist der nächste gezielte Qualitätsfall; eine vollständig
brauchbare Personenauflösung und Antwortqualität werden weiterhin nicht behauptet.
