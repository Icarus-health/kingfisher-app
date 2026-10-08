# Gedächtnisbereiche und getrennte Absenderidentität

## Ergebnis

Auf dem Mac installiert und im echten nativen Fenster geprüft:
**1.0.6-local.160cfd7**, Quellstand `160cfd78231534c94f3fc6d62c485d033e1c4c9c`.
Die vorherige App, Einstellungen und das kalte Datenvolume sind außerhalb des
Repositorys gesichert. Kein neuer universeller Mac-Build oder öffentlicher
Release; das bestehende native Programm wurde mit neuer Versionsangabe erneut
lokal signiert. Der Container stammt aus einem sauberen Git-Archiv.

## Absender und erwähnte Menschen

Die entfernte Einordnung darf nur `mentioned` liefern. Eine dennoch gelieferte
Modell-Absenderrolle wird verworfen. Der tatsächliche Absender kommt weiterhin
getrennt aus den Mailkopfdaten. Auch ein exakt gleicher Name im Text beweist
keine gemeinsame Identität: Signaturen, Zitate und gleichnamige andere Personen
werden nicht automatisch mit dem Mailabsender verschmolzen. Der lokale
Einordnungspfad bleibt unverändert. Allgemeine Servicepostfächer werden auch
bei ausschließlich vorliegenden Kontaktkopfdaten nicht als Menschen übernommen.

Die erste Implementierung dieses Nachtrags beförderte gleichnamige Nennungen
anhand des Mailkopfs. Das unabhängige Review fand den Gegenfall einer zitierten
anderen Person mit gleichem Namen. Die Regression wurde zunächst rot geprüft;
die automatische Beförderung ist vollständig entfernt. Neue synthetische Tests
prüfen außerdem Teilnamen, Empfänger/CC, kodierte Mailköpfe, Kontaktdaten ohne
Teilnehmerliste, gefälschte Rollen und allgemeine Postfächer.

## Vier Bereiche

Der Einstieg in Gedächtnis zeigt **Arbeit & Projekte**, **Privat & Familie**,
**Gesundheit** und **Finanzen & Verträge**. Eine Quelle kann mehrere Hinweise
haben. Weitere Themen, unzugeordnete Quellen und offene Einordnungen bleiben
unter **Weitere Hinweise** erreichbar. Bestehende Ansichten für Menschen,
Projekte, Organisationen, Orte, Themen, Entscheidungen und Dokumente sowie
Prüfung und Verarbeitungsverlauf bleiben erhalten.

Automatische Themenhinweise sind ausdrücklich ungeprüft; manuelle Zuordnungen
werden als solche angezeigt. Hinweise führen zur schreibgeschützten
Originalquelle. Die Ansicht liest nur aktuelle, nicht entzogene Rohquellen und
Hinweise mit passendem Fingerabdruck. Das Öffnen löst weder Einordnung noch
Modellaufrufe aus und verändert keine Originale, Fakten oder Suchfilter.

Die API liefert standardmäßig 50, höchstens 100 Quellen je Seite. Der Client
hält nur die aktuelle Seite und Cursorpositionen, keine wachsende Sammlung von
Quellentexten. Zahlen und leere Zustände gelten ausdrücklich für die aktuelle
Seite. **Die Filter sind keine vollständige corpusweite Bereichssuche**: Weitere
passende Quellen können auf anderen Seiten liegen. Seitennavigation folgt der
Aufnahme in den Bestand, nicht dem Quelldatum; bekannte Quelldaten bleiben an
jeder Quelle sichtbar, fehlende Daten werden nicht zu heute.

Migration 19 ergänzt `health`, ohne `corpus_version`, Originale, bestehende
Ableitungen oder manuelle Korrekturen zu ändern. Eine eigene vorhandene
Gesundheitskategorie bleibt erhalten. Ist eine bestehende Taxonomie bereits
mit 64 Kategorien voll, wird nichts gelöscht: Der betroffene Bereich wird
explizit als nicht verfügbar angezeigt. Alte Quellen erhalten nicht durch
bloßes Öffnen neue Gesundheitshinweise; dafür ist eine bewusste Nachprüfung
nötig. Wiederherstellung älterer v18-Sicherungen ist synthetisch geprüft.

## Echte begrenzte Nachprüfung

Dieselben sieben bereits freigegebenen Originalmails wie im vorherigen Lauf
wurden erneut mit `gpt-6.1-sol` geprüft. Zweck **Nachprüfung**, kein neuer Pilot,
keine neuen Quellen und kein anderer Empfänger.

| Messung | Vorherige Nachprüfung | Aktueller Nachtrag |
| --- | ---: | ---: |
| Quellen durchgesehen | 7 | 7 |
| Grundeinordnung vollständig | 7 | 7 |
| Beide Schichten vollständig | 3 | 7 |
| Abgewiesene Absenderrollen | 4 | 0 |
| Modellanfragen | 21 | 22 |

Der lokale Abschnittsplan umfasst 22 Anfragen; alle wurden benötigt. Das
bestehende generische technische Auftragslimit wird weiterhin als 4.000
angezeigt, nicht als die Zahl der für diese sieben Quellen geplanten Anfragen.
Das bleibt eine bekannte Unklarheit der Cloud-Auftragsanzeige.

Die aktuelle Prüfung fand **42 Arbeitsgedächtnisbereiche, 55 Entitätsbereiche
und 48 Themenbereiche**: alle 145 liegen im jeweiligen Original und geben dessen
Text exakt wieder. Alle sieben Originaldokumente stimmen mit dem Vorherstand
überein; sämtliche Modell-Entitätsrollen sind `mentioned`. Die zwei persönlichen
Anliegen bleiben als Bitte erhalten; die vier zuvor auffälligen automatischen
Bedienaufforderungen bleiben ohne Bitte. In einer langen Kaufbestätigung
entfallen elf isolierte Preis-/Versandzeilen aus dem Werbeteil; Kaufgegenstand,
Bestellbelege und tatsächliche Gesamtsumme bleiben als Quellenbefunde vorhanden.
Das ist ein begrenzter Inhaltsvergleich, kein Vollständigkeits- oder
Faktengenauigkeitsnachweis für beliebige Nachrichten.

Die ursprüngliche, nicht repräsentative 100-Mail-Probe bleibt mit 48 vollständigen
Quellen und offenen Fällen historisch unverändert. Ein erfolgreicher Nachprüflauf
schaltet den Bulk-Gate nicht frei. **Kein großer Import wurde gestartet.**
Auch in der neuen Übersicht sind fragwürdige alte Themenzuordnungen sichtbar;
sie wurden nicht still korrigiert oder als richtige Fakten übernommen.

## Installation und Bedienprüfung

Vor dem Austausch lief die Migration an einer getrennten Kopie des echten,
kalten Bestands ohne Netzwerk: Schema 18 auf 19, Originale und vorhandene
Kategorien-, Entitäts-, Quellen- und Korrekturzeilen unverändert. Vor dem letzten
reinen Oberflächennachtrag wurde der inzwischen erfolgreich nachgeprüfte
Schema-19-Bestand erneut vollständig gesichert und getrennt validiert.

Abschließend: **340 Originalquellen mit unveränderten Digests**, **17 SQLite-Dateien
mit erfolgreichem quick_check**, bestehende ChatGPT-Verbindung und Einstellungen
erhalten. Lokale Modellauswertung bleibt ausgeschaltet; der Mailabruf ist nicht
pausiert. Datenvolume und ausschließlich lokale Portbindung bleiben gleich.

Im nativen Fenster geprüft: vier Tabs, leerer Bereich, neu gespeicherte
Gesundheitshinweise, mehrfache Themenzuordnung, Weitere Hinweise,
Originalquelle öffnen/schließen, nächste/vorherige Seite und bestehende
Menschenansicht. Die abschließenden Navigationstexte und der neue Einstieg
wurden nach dem letzten Update erneut kontrolliert. Keine Browser-Konsole des
nativen Webviews verfügbar; kein vollständiger Console-Test behauptet.

## Automatisierte Prüfungen

- 144 betroffene Backendtests bestanden: Senderrollen, Kategorien, Bereiche,
  Cloudjobs, Erwähnungen, Sicherung und Wiederherstellung.
- 35 zusätzliche Migrations-/Bezugstests bestanden; davon überschneiden sich
  die acht Bereichstests mit dem ersten Lauf.
- 113 weitere Migrations-, Mailintake-, Suchindex-, Projektlink- und
  Updatesicherungstests bestanden. Versionsverträge sind auf Schema 19
  angepasst; ursprüngliche Inhalts- und Rollback-Prüfungen bleiben erhalten.
- 367 Frontendtests und Produktionsbuild bestanden. Bestehende Warnungen zu
  Starlette/httpx und der Größe des JavaScript-Bündels bleiben.
- Unabhängiges Review nach der Senderkorrektur und dem expliziten
  Taxonomie-Kapazitätsfall fand keinen weiteren konkreten Fehler im Diff.

Der vollständige breite Backendlauf endete nach rund 13 Minuten mit **5.146
bestandenen, neun fehlgeschlagenen und einem übersprungenen Test**. Acht Fehler
waren beim Sammeln des Laufs noch geladene Erwartungen an Schema 18 oder die
alte Taxonomienummer. Die angepassten Inhalts-/Versionsverträge bestehen in den
oben genannten gezielten Läufen; die erneute Ausführung aller neun Fehlfälle
ergibt **acht bestanden, ein weiterhin fehlgeschlagen**.

Verbleibend ist `test_datumstext.py::test_kein_weiterer_z_leser_ausser_den_benannten`:
Der statische Vertrag findet eigenständige ISO-Z-Konvertierung in
`calendar_actions.py`, `calendar_window.py` und `server.py`. Derselbe Test wurde
in einem getrennten sauberen Archiv des Ausgangsstands `9a8e67c` ausgeführt und
scheitert dort identisch. Diese Dateien sind in diesem Nachtrag unverändert.
Keine vollständig grüne Gesamtsuite behauptet. Ein zunächst in der Sandbox
begonnener Lauf wurde wegen gesperrter lokaler Testserver abgebrochen; der oben
gezählte Volltest erlaubte die lokalen Test-Sockets. Keine GitHub-CI-Wiederholung.

Aus vollständiger technischer Verarbeitung, gültigen Textbereichen und der
begrenzten Inhaltsprüfung wird kein fehlerfreies Gedächtnis abgeleitet.
