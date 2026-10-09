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

Mac-Abnahme und Paketnachweise folgen separat nach der Installation.
Keine Modellaufrufe, Cloudkosten, Quellenlöschung oder CI-Neustarts.
