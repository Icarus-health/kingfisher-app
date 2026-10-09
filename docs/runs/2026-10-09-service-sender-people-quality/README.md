# Service-Absender in der Menschenansicht

## Problem und Änderung

Synthetische Absender `Example Software GmbH <cs-auto@software.example>` und
`Audio Shop <do_not_reply@audio.example>` wurden im Graphen ausdrücklich als
Personen markiert. Die Oberfläche behandelte außerdem fehlende oder unbekannte
Qualitätskennzeichnungen als Personen.

Die gemeinsame Postfachregel erkennt jetzt die Varianten `do_not_reply`,
`do-not-reply`, `do.not.reply` als technische Absender und `cs-auto`, `cs_auto`,
`cs.auto` als ungeklärte Servicepostfächer. Plus-Tags werden wie bisher entfernt.
Service-Anzeigenamen bleiben im Graphen lesbar, gelten aber nicht als menschliche
Namensaliase. Adresse, Kennung, Belegkanten und Originalquellen bleiben erhalten.
Die Oberfläche bietet ungekennzeichnete Einträge zur Prüfung an; ausdrücklich
bestätigte Identitäten bleiben sichtbar. Es gibt keine automatische Zusammenführung.

## Nachweise

Codefreeze: `32f4b0136f7d06a0fea93dc897f64edf506e39e7`; Basis:
`a42558fe0e55240f6f3ee300ce42c5515af702da`.

- Backend vor der Korrektur: 25 gezielte Tests fehlgeschlagen, vier
  persönliche Gegenbeispiele bestanden. Danach 30 neue Tests bestanden
  (zusätzliches persönliches Gegenbeispiel `mechanics`).
- Oberfläche: ein gezielter Test schlägt vor der Korrektur fehl; danach alle
  vier neuen Tests bestanden. Die Tests verwenden den tatsächlich konsumierten
  Filter, einschließlich unbekannter Kategorien und bestätigter Identitäten.
- 115 betroffene Graph-/Kontakt-/Zusammenführungs-/Fragetests bestanden;
  Pflichtprüfungen plus Sammelpostfach und Gedächtniskategorien: 202 bestanden;
  neue Servicefälle plus Arbeitsgedächtnis-Identität: 51 bestanden. Diese
  Läufe überschneiden sich; sie sind keine summierbare Gesamtsuite.
- Alle 423 Oberflächentests, Typprüfung und Produktionsbuild bestanden.
- Unabhängige Prüfung des Diffs: kein blockierender Befund.
- Assetprüfung: vorhandener Fehlalarm `expired` sowohl vor als auch nach dem
  Change reproduziert. Der Prüfer interpretiert ein Status-Array als Icon-
  Referenz. Keine neue Assetdatei oder visuelle Gestaltung geändert.

## Grenzen

Die Regeln sind bewusst eng. Ein Firmenname allein belegt weder Mensch noch
Organisation; diese Korrektur ist keine vollständige automatische
Personenerkennung. Bei mehreren Anzeigenamen desselben Servicepostfachs ist
die Graph-Beschriftung weiterhin die erste eingelesene Nennung, keine
bestätigte Identität. Originalquellen bleiben maßgeblich.

## Reale Bedienprüfung und Korrektur des Detailwegs

Die erste Installation `32f4b01` korrigierte die Listen, zeigte beim Öffnen
technischer Absender aber die bestehende unerreichbare Personenprofilseite.
Der Detailweg wurde deshalb vor dem Merge weiter korrigiert (Codefreeze
`af8e791bb55a4268597d2cef58106cc31e0315f5`).

Nur nach einem Personenprofil-404 kann eine lesende Absenderquellenansicht
folgen: frischer Graph, eindeutiger exakter Anzeigename und gleiche angeklickte
Kennung, bekannte Kategorie automatisch/prüfbedürftig, keine bestätigte
Identität. Die Quellen müssen aktuelle, genau belegte ausgehende Beteiligungen
an vorhandenen Episoden sein. Keine Namensergänzung, Zusammenführung,
Personenverdichtung oder Quellenänderung. Andere Fehler, fehlende Kennung,
Mehrdeutigkeit und fehlende gültige Quellen bleiben Fehler.

Acht weitere Oberflächentests: vor der Korrektur drei Fehler/fünf bestanden,
danach acht bestanden; anschließend alle 431 UI-Tests und Build bestanden.
Unabhängige Prüfung ohne Blocker. Python ist gegenüber `32f4b01` unverändert;
die Backend-Läufe wurden deshalb nicht unnötig wiederholt.

Native Mac-Prüfung am 9. Oktober 2026:

- Vorher Personen 112, automatisch 28, prüfen 31, alle 164.
- Nachher Personen 110, automatisch 27, prüfen 34, alle 164. Die Filter
  überlappen bei Duplikathinweisen; die Gesamtsicht bleibt vollständig.
- Beide betroffenen Service-Familien verlassen die Personenliste. Service
  unter Prüfen, technische Adresse unter automatische Absender sichtbar.
- Beide Einträge öffnen ihre Absenderquellen; jeweils eine Originalquelle
  geöffnet und erfolgreich geladen. Kennzeichnung als gespeicherte Quelle,
  keine bestätigte Personenidentität, keine Schreibaktionen.
- Abschließend Heute geladen, Uhr läuft, Importpause sichtbar, keine
  kodierten Mailheader im sichtbaren Text. Keine Nutzerentscheidung bestätigt.

Version `1.0.6-local.af8e791`, Image
`sha256:602b9e59d3565a12eefbcea0e6dbb4eafab41533272ba51ebd060978d5d79537`.
Alle 266 Python- und 112 UI-Dateien im tatsächlich laufenden Paket erneut
anhand der unabhängigen Soll-Prüfsummen verifiziert. Nativer Wrapper bleibt
unverändert. Zwei versiegelte Sicherungen angelegt, gleicher Datenbereich,
keine Migration: 344 Originale und 17 Datenbanken erhalten. Lokaler
Betriebsstatus nach der UI-Prüfung grün; Hintergrund weiterhin pausiert.

Eine zunächst zu kleine Docker-Speicherreserve hat das Update vor jeder
Veröffentlichung angehalten. Zwei ältere Sicherungsduplikate wurden erst
nach vollständigem Abgleich mit der bestehenden versiegelten Mac-Kopie
aus dem gestoppten Docker-Datenbereich ausgelagert (91.508.470 Bytes).
Nur die festgelegten Duplikate, niemals aktive Dateien oder die jüngste
Sicherung; externer Rückweg unverändert. Falscher Pfad, falsche Prüfsumme
und geänderte Quelldatei wurden mit Testdaten abgewiesen. Unabhängiger
Prüfer kontrollierte den Einmalweg; aktive Zeilen und Einstellungen danach
identisch, alter Dienst geprüft gestartet, Speicherreserve wieder grün.

## Verbleibende Grenze der Quellenansicht

Graph und Quellenabruf sind getrennte Momentaufnahmen. Eine inzwischen
ausgeschlossene Quelle kann noch im alten Verzeichnis stehen; ihre beim
Öffnen frisch geladene Quellkarte zeigt den Ausschluss beziehungsweise
fehlende aktuelle Zulassung. Die Ansicht bestätigt nichts und bietet
keine Wiederzulassung an. Technische und ungeklärte Quellen sind weiterhin
kein bestätigtes Menschenwissen.
Keine Modellaufrufe, Cloudkosten, Quellenlöschung oder CI-Neustarts.
