# Kingfisher Core Icons v1

Diese 24 Symbole sind die verbindliche Kernbibliothek für die erste Kingfisher-Version. Jede Funktion verwendet ausschließlich eine vorhandene Datei.

- `outline/`: helle Linienvariante für Navy-, Petrol- und andere dunkle Flächen.
- `filled/`: dunkelblaue Linienvariante für warmweiße und helle Flächen.
- Standardgröße: 20 oder 24 px. Nicht strecken; keine eigene Strichstärke ergänzen.
- Kein Emoji, keine externe Icon-Bibliothek und kein generiertes Ersatzsymbol.

## Funktionale Zuordnung

- Orientierung: `house`, `search`, `calendar-days`, `folder`, `file-text`, `network`
- Kommunikation: `message-circle`, `mail`, `users-round`, `bell`
- Intelligenz und Bereiche: `brain`, `settings`
- Aktionen: `plus`, `pencil`, `check`, `trash2`, `download`, `link`, `funnel`, `eye`
- Rückmeldung: `clock3`, `circle-alert`, `triangle-alert`, `info`

## Fehlende Symbole

Fehlt ein Symbol, hält der Coding-Agent an und meldet einen `ASSET-REQUEST`. Er darf weder eine Bibliothek nachladen noch ein Icon erzeugen.

## Beispiel

Eine dunkle Sidebar verwendet `outline/bell.svg`. Dieselbe Benachrichtigungsfunktion auf einer hellen Karte verwendet `filled/bell.svg`.
