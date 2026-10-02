# Kontextbeleg pro Antwort

Stand: 2026-09-02

Kingfisher darf nicht nur eine passende Antwort erzeugen. Es muss später auch
erklärbar bleiben, welche Gedächtnisaussagen dafür verwendet wurden.

## Vertrag

- Das Selbstmodell bleibt der autoritative Bestand. Der Kontextbeleg kopiert
  keine Wahrheit in ein zweites Gedächtnis.
- Vor jedem Modellaufruf wird ein begrenzter, deterministischer Ausschnitt
  ausgewählt. Der Selektor funktioniert ohne Modell und ohne semantischen
  Zusatzindex.
- Bindende Grenzen werden immer berücksichtigt. Dazu kommen Aussagen, die zum
  aktuellen und zu den letzten beiden Nutzerbeiträgen passen, sowie höchstens
  zwei stabile Profilpunkte.
- Ersetzte, widerrufene und abgelaufene Aussagen werden nicht als aktuelle
  Wahrheit verwendet. Relevante veraltete oder widersprüchliche Aussagen
  werden ausdrücklich als solche gerahmt.
- Die Schutzbedarfsgrenze des Modellanbieters gilt vor der Auswahl und nochmals
  unmittelbar vor dem Versand. Nicht freigegebene Inhalte werden nur gezählt,
  nie in den Kontext kopiert.
- Pro Antwort werden Aussage-ID, Wortlaut, Art, Zustand, Auswahlgrund,
  Quellenverweis, Evidenzzeitpunkt und Confidence zusammen mit der Nachricht
  in SQLite gespeichert.
- Der gespeicherte Beleg ist ein Snapshot. Eine spätere Änderung am
  Selbstmodell verändert nicht rückwirkend die Begründung einer alten Antwort.

## Austauschbarkeit

Der heutige Selektor arbeitet mit nachvollziehbarer Wort- und Tag-Überlappung.
Ein späterer semantischer oder graphbasierter Selektor darf ihn ergänzen oder
ersetzen, solange derselbe Kontextbeleg entsteht und alle Regeln oben erhalten
bleiben. Ein semantischer Index bleibt Hilfsmittel zum Wiederfinden und wird
nie zur autoritativen Wissensquelle.

## Oberfläche

Der genehmigte Gesprächsscreen zeigt im vorhandenen Kontextbereich die Punkte
des zuletzt gespeicherten Belegs. Er fragt nicht mehr den gesamten aktuellen
Gedächtnisbestand ab. Dafür wurde keine neue Karte, kein Dialog und keine neue
Komponentenvariante eingeführt.
