# Kingfisher — Weg zum täglichen lokalen Produkt

Stand: 2026-09-03. Diese Reihenfolge ergänzt die Icarus-Fundamente; sie ersetzt
sie nicht. Jede sichtbare Oberfläche bleibt an die kanonischen Kingfisher-
Screens und das Asset Manifest gebunden.

## 1. Täglicher Kernfluss abschließen

- Morning Briefing, Gespräch, lokales SQLite und der Gespräch-zu-
  Gedächtnisvorschlag laufen bereits additiv auf dem Icarus-Sidecar.
- Noch vor einer Produktfreigabe: Docker neu bauen, `/today` und ein echtes
  konfiguriertes Modellgespräch ausführen, Verlauf nach Container-Neustart
  prüfen und die neue Vorschlagskarte am kanonischen Desktop-Viewport visuell
  abnehmen.
- Fehler, fehlender Modellzugang und unvollständige Quellen bleiben sichtbar;
  sie dürfen nie durch Platzhalter oder scheinbare Antworten ersetzt werden.

## 2. Gesprächsgeführtes Gedächtnis

- Der Gesprächsmoment ist implementiert: Nur eine eindeutige Nutzerbitte wie
  `Merke dir: …` darf das Modell einen *strukturierten Vorschlag* formulieren
  lassen. Der Server prüft diese Absicht selbst; er akzeptiert keinen stillen
  Modellaufruf als Speicherauftrag.
- Die schon vorhandene Karte erhält dabei nur echte Kandidaten mit Quellzitat;
  Bestätigung, Ablehnung und Konfliktersetzung sind bereits persistente,
  testbare Aktionen.
- Bestätigte Entitätsaussagen werden in einem späteren Gespräch als Kontext
  verwendet und zusammen mit der Antwort protokolliert. Dieser Kontext geht
  ausschließlich an einen lokalen Modellanbieter; ein externer Anbieter erhält
  ihn nicht automatisch.
- Vor der Produktfreigabe mit einem real konfigurierten Modell prüfen: Person,
  Thema und bereits vorhandenes Projekt müssen jeweils einen korrekten,
  nachvollziehbaren Vorschlag ergeben. Ein unbekanntes Projekt wird bewusst
  nicht automatisch angelegt.
- Das gemeinsame Entitätsverzeichnis ist als reine Lese-API
  `GET /api/v1/memory/entities` vorhanden: stabile Referenz, lesbarer Name,
  Typ, Herkunft und Verbindungszahl stammen ausschließlich aus dem gerade
  berechneten Graphen. Ein Label oder eine Beziehung wird niemals aus einem
  unbestätigten Satz als Fakt übernommen.

## 3. Personen und Projekte als Arbeitskontext

- Die read-only Projektionen für Personen und Projekte sind über die
  kanonischen Profilrouten mit dem Graphen verbunden. Knoten im Graphen öffnen
  ihre stabile Profilreferenz; es gibt keinen zweiten CRM-Speicher.
- Profile zeigen nur belegte Verbindungen: Gespräche, Dokumente, offene
  Punkte, Projektbezug, letzter Kontakt und aktuelle beziehungsweise ersetzte
  Wissensstände.
- Aufgaben und Zeitlinien bleiben abgeleitete Arbeitshinweise; sie sind keine
  stillen Behauptungen über Menschen oder Projekte.
- Die befüllte visuelle Abnahme von Screen 06/07 bleibt offen, bis eine
  ausdrücklich freigegebene Quelle echte Person- und Projektknoten liefert.

## 4. Täglich nutzbare lokale Quellen

- Die vorhandenen Icarus-Adapter für Aufgaben, Kalender, Mail und lokale
  Dokumente einzeln, opt-in und nur lesend an den Morning-Briefing-Komponisten
  anschließen.
- Pro Quelle: sichtbare Rechte, Herkunft, Teilfehler, Widerruf und ein echter
  Testnachweis. Keine Sammelimporte und keine Cloud-Datenbank.
- Wetter bleibt standardmäßig aus und verlangt die bereits vereinbarte
  Orts- und Koordinatenfreigabe.

## 5. Abschluss für einen installierbaren Alltagstest

- Ein sauberer Docker-Start mit eigener `.kingfisher.env`, eigenem Volume und
  Loopback-Port; keine Berührung vorhandener Icarus-Instanzen.
- Sicherung, Wiederherstellung und Export/Import des lokalen Bestands an
  echten Beispieldaten nachweisen.
- Eine kurze lokale Update-Anleitung. Ein automatischer Updater ist bewusst
  später: Erst wenn Versionierung, Sicherung und Rückkehrweg ausreichend
  belastbar sind.

## Spätere, bewusst getrennte Arbeit

- Onboarding für neue Nutzer und optionaler Import freigegebener Ordner.
- Vollständige Gesprächsliste, mobile Variante und die übrigen Navigationen.
- Native macOS-Hülle erst bei echten Systemrechten wie Mikrofon, Bildschirm
  oder Schlüsselbund; bis dahin bleibt Docker die schlankere lokale Form.
