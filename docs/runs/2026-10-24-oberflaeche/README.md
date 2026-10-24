# Oberfläche: ruhig, groß, auf einen Blick (23.–24.10.2026)

Auftrag des Nutzers nach zwei Wochen Test: „UI aber auch UX immer noch ein Graus.“ Dann: „Gehe einmal komplett alles
durch, jede einzelne Funktion und Oberfläche: große Flächen, wenig geschrieben, sehr adaptiv, Verständnis auf einen Blick,
optische Wertigkeit – als hätte Apple das Programm geschrieben.“

Keine neue Funktion, keine neue Ansicht, keine neue Route (Ziellinie, `docs/65-ziellinie.md`). Alle Proben mit der
synthetischen Welt der Messlatte (Lea Hartmann, Stichtag 29.09.2026), keine persönlichen Daten.

## Ablauf

1. **Rundgang vorher** über alle Hauptseiten bei 1280 und 390 px. Befund: Die Seiten waren nicht hässlich, sondern voll –
   Bedienelemente, Erklärsätze, Aufklapper und Absicherungsprosa, die niemand braucht, um das zu tun, wofür er kam;
   dasselbe mehrfach (Heute und Briefing, zwei Monatskalender, zwei „Neues Gespräch“); mehrere gefüllte Knöpfe je
   Ansicht; der Eisvogel dreimal auf Heute.
2. **Inventar**: 196 Oberflächen in zehn Bereichen (Routen, Reiter, Unteransichten, Dialoge, Einrichtungsschritte,
   Lade-, Leer- und Fehlerzustände). Jede ist in einem der Pakete unten abgehakt.
3. **Aufräumen U1–U3**: Heute ist das Briefing (eine Seite statt Seite und Schublade); Aufgaben zeigen Aufgaben statt
   Bedienelemente; übrige Seiten ohne Handbetrieb und Doppelungen.
4. **Gestaltungsgrundlage F** (`app/kingfisher/src/Grundlage.css`, Bausteine in `src/grundlage/`, beschrieben in
   [`16-gestaltung.md`](../../16-gestaltung.md#grundlage-vom-23102026)): Systemschrift des Macs, Typo-Skala mit großem
   Titel, Abstände im 4er-Raster, gruppierte Flächen mit Haarlinien, Segmentsteuerung, drei Knopfstufen, Ziele ab 44 px,
   Leerzustand, Landschaft nur noch im Kopf von Heute.
5. **Flächenpakete P1–P5** über jede Oberfläche: Heute und Gespräche; Aufgaben und Entwicklung; Gedächtnis, Akte,
   Prüfen und Welt; Nachrichten und Kalender; Einstellungen, Einrichtung und Gesundheit.

## Was sich für den Menschen ändert

- Jede Seite hat einen großen Titel, höchstens eine Zeile darunter und genau einen gefüllten Knopf.
- Listen sind ruhige weiße Gruppen mit ganzen, anklickbaren Zeilen; Reiter sind eine Segmentsteuerung, die auf dem
  schmalen Fenster rollt statt umzubrechen.
- Leere Bereiche sagen einen Satz oder verschwinden; niemand muss mehr „aktualisieren“ drücken.
- Nachrichten wie in Apple Mail, Kalender wie in Apple Kalender, Einstellungen wie die Systemeinstellungen.
- Sicherheitszusagen blieben vollständig: Freigabekarten, Belege, Rückgängig, Einwilligungssätze und der Satz, was den
  Rechner verlässt. Zwei Grenzsätze, die beim Kürzen verloren gingen, sind zurück und mit Test abgesichert
  (`tests/zusagen-nach-kuerzen.test.mjs`).

## Nebenbei behoben

- Der Einrichtungsschritt „Dieser Rechner“ stürzte ab (Verweis auf ein unbekanntes Ziel).
- Die eigene Person bekam in ihrer Akte einen Kreis-Vorschlag (`kreis.py`, mit Test).
- Die Ortskarte schob bei 390 px die Seite über den Rand.
- Die CI auf main war seit #92 rot: `Mitteilungen.swift` übersetzte unter Linux nicht (FoundationNetworking).
- `scripts/probe_seiten_ui.py` lief schon vorher nicht mehr durch; jetzt läuft jeder Befund-Abschnitt für sich.

## Vorher und nachher

| Ansicht | Bild |
| --- | --- |
| Heute, 1280 | [heute-1280.jpg](heute-1280.jpg) |
| Heute, 390 | [heute-390.jpg](heute-390.jpg) |
| Aufgaben, 1280 / 390 | [aufgaben-1280.jpg](aufgaben-1280.jpg), [aufgaben-390.jpg](aufgaben-390.jpg) |
| Nachrichten | [nachrichten-1280.jpg](nachrichten-1280.jpg) |
| Kalender | [kalender-1280.jpg](kalender-1280.jpg) |
| Gedächtnis | [gedaechtnis-1280.jpg](gedaechtnis-1280.jpg) |
| Akte einer Person | [akte-1280.jpg](akte-1280.jpg) |
| Einstellungen, 1280 / 390 | [einstellungen-1280.jpg](einstellungen-1280.jpg), [einstellungen-390.jpg](einstellungen-390.jpg) |
| Gespräche | [gespraeche-1280.jpg](gespraeche-1280.jpg) |
| Prüfen | [pruefen-1280.jpg](pruefen-1280.jpg) |

## Prüfungen

Siehe Beschreibung des PR (#94) für die Zahlen auf dem letzten Stand. Jedes Paket hat Sabotageproben für seine neuen
Zusicherungen gemacht (zusammen über 80); alle wurden rot und danach zurückgesetzt.

## Offen

- **Abnahme am Mac im nativen Fenster.** Die Systemschrift San Francisco ist im Container nicht zu sehen (dort Inter).
- Bausteinwünsche aus den Paketen an die Grundlage: Umlegeschalter, `Gruppe` mit Zahl und Aktion im Kopf, `Zeile` als
  Knopf und mit eigenem Bedienelement links, Unterkopf für Unteransichten, Karte zur Bestätigung, feine Rastermaße für
  den Kalender. Heute lokal gebaut, aus `--g-*`-Werten.
- Kleine Reste: Tagesziele in der Jahresansicht 26 px; im Akte-Kopf nimmt das Bild bei 390 px viel Breite; graue
  Ladebalken unter der Fehlermeldung, wenn die Zugänge nicht laden; Projektprofile ohne Inhalt nicht fotografiert (die
  synthetische Welt hat keine Projekte); drei lokale Werte in `Workspace.css` (`.memory-decision`).
