# SDR-015 — Ruhige Gestaltung in der gesamten App

Status: vom Product Owner am 27. September 2026 beauftragt.

## Auftrag

Nach Freigabe und Umsetzung der zweiten Heute-Variante (SDR-014) lautet der
Folgeauftrag: „Super also einmal durch die ganze App“. Die ausgewählte
Gestaltung wird auf die bestehenden Arbeitsbereiche übertragen. Maßstab sind
große, deckende Leseflächen, schlichte Eleganz und gut erkennbare Aktionen.

## Umfang

- Gemeinsame Materialwerte in `CalmUI.css`: warme helle Flächen, dunkle
  Blauflächen, dezente Ränder und Schatten, Inter für Arbeitsüberschriften,
  gerundete Schaltflächen und sichtbarer Tastaturfokus.
- Die bereits freigegebene Landschaft bleibt hinter den Arbeitsbereichen
  durchgehend sichtbar. Eine dezente Aufhellung beruhigt sie auf Detailseiten.
  Karten und Lesebereiche bleiben vollständig deckend.
- Aufgaben einschließlich Projektwahl, Entscheidungen, Zielen und Formularen;
  Kalender in Liste, Woche, Monat und Jahr sowie Vor- und Nachbereitung;
  Gedächtnis mit Akten, Profilen, Graph, Prüfungen und Verlauf; Nachrichten
  einschließlich Lesefläche und Antwortentwurf; Gespräche und Historie;
  sämtliche vorhandenen Einstellungsbereiche und Briefing-Flächen.
- Das Gedächtnis verwendet auch im hellen Modus helle Aktenflächen. Die
  Seitenleiste bleibt dunkel und behält die freigegebenen Piktogramme.
- Die eigenen geometrischen Zeichen aus SDR-014 werden für die internen
  Gedächtnisfilter und Mail-/Kalenderüberschriften ergänzt. Es entstehen keine
  neuen Bild- oder Fontdateien; das Asset-Manifest und die Drive-Originale
  bleiben unverändert. Dies erweitert ausdrücklich den SVG-Umfang von SDR-014.
- Neue Überschrift in der Gesprächshistorie; beschriftete Schaltfläche für ein
  neues Gespräch; vollständige Aufgabentitel statt einzeiliger Kürzung.

## Grenzen

Speicherung, Quellenprüfung, Vorschläge, Bestätigungen, Senden und die
Verbindungslogik bleiben unverändert. Keine neuen Konnektoren und keine
externen Datenzugriffe werden durch diese Gestaltungsänderung eingerichtet.
Die bestehenden schmalen Gedächtnisansichten bleiben erhalten; die übrige
Desktop-App setzt weiterhin mindestens 1280 Pixel Breite voraus.

## Prüfung

Die Browserprüfung verwendet den lokalen Sidecar mit ausschließlich
synthetischen Daten. Die Mailansichten nutzen ausdrücklich als solche
gekennzeichnete UI-Fixtures. Geprüft werden Hauptansichten in Hell/Dunkel,
1280-Pixel-Desktop, schmaler Gedächtnisverlauf, wesentliche Unteransichten und
reversible lokale Abläufe. Zusätzlich werden die bereits geprüften
Heute-Abläufe erneut ausgeführt. Native Tauri-/Safari-Darstellung und reale
Mac-Verbindungen bleiben Teil des Gerätetests am 28. September 2026.
