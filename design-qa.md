# Gestaltungskontrolle · freigegebene Variante 3

final result: passed

Geprüft am 15.10.2026 im Codex-Browser an der isolierten lokalen Laufzeit `http://127.0.0.1:8893`; ausschließlich künstliche Quellen und deterministische Provider. Dies ist eine Prüfung der Umsetzung und Bedienung, keine persönliche Mac-Abnahme.

## Vergleichsgrundlage

- Visuelle Wahrheit: [ausgewählte dritte Bildausgabe](docs/runs/2026-10-15-nordic-workspace/00-vorlage-variante-3.png), ursprünglich `exec-8f0dc99a-3b34-4786-995c-547d3bf1f954.png`.
- Umsetzung: [Dokumentarbeitsplatz](docs/runs/2026-10-15-nordic-workspace/01-dokumente.png).
- Quelle: 1487 × 1058 px; Umsetzung: 1440 × 1024 px, CSS-Fenster 1440 × 1024, DPR 1, Zoom 1. Die Quelle wird proportional in 1440 × 1024 eingepasst; der Gesamtvergleich zeigt beide bei halber Größe. Die Originale bleiben erhalten.
- Zustand: Gedächtnis → Dokumente → Arbeit → Projektplan Polarstern. Der Bildentwurf enthält beispielhafte PDF-Bilder und fünf Einträge; der geprüfte Bestand hat zwei echte synthetische Quellen in diesem Ordner. Kein pixelgenauer Inhaltsvergleich dieser unterschiedlichen Quellenbestände behauptet.
- [Gesamtvergleich in einer gemeinsamen Bilddatei](docs/runs/2026-10-15-nordic-workspace/07-vergleich.jpg).
- [Gemeinsame Detailansicht für Schrift, Navigation, Kopf und Liste](docs/runs/2026-10-15-nordic-workspace/08-vergleich-detail.jpg). Zusätzlich Originalgröße des rechten Quellentextes sowie 390-px-Ansicht geprüft.

## Befunde und Korrekturrunden

1. Erste Umsetzung: Kopf blieb durch geerbtes `align-items:start` schmal; freigegebene helle Symbolstriche waren auf Papier kaum sichtbar. Kopf auf volle Breite gestellt, Symbole auf dunkle Striche angepasst. Der anfängliche Bildausschnitt hatte eine harte senkrechte Fotokante; Hintergrundgröße auf `cover` korrigiert. Abschließender Gesamt- und Detailvergleich zeigen diese Fehler nicht mehr.
2. Folgeprüfung: Aufgaben erbten große äußere Karten und kräftige Reiter. Gemeinsamen flachen Arbeitsplatz, unterstrichene Reiter und kompakte Projektsteuerung umgesetzt. Einstellungen erhielten fehlendes Innenpadding, Personenprofile weniger ineinander verschachtelte Rahmen. [Aufgaben](docs/runs/2026-10-15-nordic-workspace/02-aufgaben.png), [Einstellungen](docs/runs/2026-10-15-nordic-workspace/03-einstellungen.png), [Profil](docs/runs/2026-10-15-nordic-workspace/04-personenprofil.png).
3. Unabhängiges Codereview: zwei P2, keine P1. Automatisch geöffnete Quelle hatte keine stabile Auswahl-ID; Importvorschau wurde beim Gedächtnis-Tabwechsel ausgehängt. Beide reproduziert, mit zwei zuvor fehlschlagenden Regressionen korrigiert. Zusätzlich Seitenwechsel gesondert abgesichert. In der Browserprüfung bleiben Vorschau/Projekt und Suchzustand erhalten; die Datei wurde ausdrücklich aufgenommen und wiedergefunden.
4. Responsive Prüfung: Bei 900 px überragte die geerbte Mindesthöhe den verbleibenden Platz. Auf `min-height:0` korrigiert; Hauptinhalt misst danach 816 px bei 84 px Kopfnavigation und 900 px Fensterhöhe. Bei 1280 × 360 waren die unteren Navigationsziele zu weit unten; kurze Navigation zeigt nun Uhr, alle Ziele und Einstellungen ohne diesen Überhang. [Kurze Mailansicht](docs/runs/2026-10-15-nordic-workspace/06-mail-kurzes-fenster.jpg).
5. Schlussvergleich: frühe Aufnahmen unmittelbar nach Größenwechsel waren weich gerastert. Nach stabiler Browserdarstellung neu aufgenommen; Abschlussbilder und Detailvergleich verwenden die scharfe 1440-px-Aufnahme. Keine weitere visuelle P0/P1/P2-Differenz offen.

## Die fünf Gestaltungsflächen

- **Schrift:** vorhandenes Inter, System-Fallbacks; gemeinsame Gewichtung, 32-px-Seitenköpfe, 25-px-Dokumenttitel, 16-px-Originaltext mit 1,75 Zeilenhöhe. Umbruch und Fokus auch bei 390 px lesbar. Keine zweite neue Schriftfamilie.
- **Rhythmus und Layout:** dunkle 220-px-Navigation, ruhiger Kopf, klar getrennte Ordner/Liste/Quelle; keine Quelle für jede Zeile aufgeklappt. Bei ≤1100 px eigener Leser mit sichtbarem Rückweg. Gleiches Papier, Reiter und Knopfsystem in den übrigen Ansichten.
- **Farben:** heller kühler Grund, weiße Leseflächen, dunkle Tinte und blaue Auswahl/Fokuskante; deckende Arbeitsflächen auch bei dunkler Systemeinstellung. Warnungen und deaktivierte Zustände bleiben eigenständig.
- **Bilder:** vorhandene freigegebene Eisvogel-, Landschafts- und Symbolassets. Keine neuen nachgezeichneten Logos oder PDF-Bilder. Landschaft hinter dekorativen Köpfen und Navigation, nicht hinter dem Originaltext. Schrift und Markenbild in abschließenden Aufnahmen scharf.
- **Inhalt:** echte Quellenmetadaten statt erfundener Dateigrößen oder Personenverbindungen. Quelldatum und Erfassungszeit bleiben unterscheidbar; das Listendatum trägt kein irreführendes Erfassungslabel. Bestand, Projektnamen und verfügbare Aktionen kommen aus der Laufzeit.

## Sichtbar geprüfte Bedienung

- Dokumente: Ordner und Unterordner, Suche im vollständigen Bestand, Projektfilter, Seitennavigation; eine Quelle öffnen, Escape/Rückknopf und Fokus auf markierter Zeile. Nach Projektprofil-Rückkehr sind Suchabfrage und dieselbe Quelle erhalten. Listenposition bleibt beim schmalen Rückweg erhalten.
- Datei: künstliche Textdatei wählen → Polarstern zuweisen → Menschen → Dokumente → Vorschau/Projekt erhalten; Schließen fragt vor Verwerfen; Weiter bearbeiten → ausdrücklich aufnehmen → schließen → suchen → Original lesen → Projekt und zurück.
- Aufgaben: Detail öffnen, Notiz ändern und speichern, schließen; Projektliste und Board mit denselben vorhandenen Aufgaben aufrufen.
- Gespräche: Entwurf mit Shift+Enter; anderes Gespräch und zurück bewahren Entwurf und Zeilenumbruch.
- Nachrichten: gespeicherte historische Mail suchen/lesen; Zurück bewahrt die Suche. Liste und Leser bleiben auch bei 1280 × 360 eigenständig bedienbar; historische Quelle wird nicht als heutige Aufgabe ausgegeben.
- Kalender: Woche mit vorhandenen überlappenden Terminen und Wechsel in Monatsansicht. Keine Terminänderung.
- Menschen, Bereiche, Heute und Einstellungen visuell geprüft; Profil und Rückweg bedient. Keine Konto-, Modell- oder Cloudfreigabe ausgelöst.
- Größen: 1440 × 1024, 1280 × 900, 900 × 900, 390 × 844 und 1280 × 360. Kein horizontaler Seitenüberlauf in den geprüften Abläufen; mobile Originalansicht und Rückweg funktionieren. [390-px-Original](docs/runs/2026-10-15-nordic-workspace/05-dokument-390.jpg).
- Browserkonsole nach dem Durchlauf: keine erfassten Warnungen oder Fehler.

## Bewusste Grenzen und P3

- Die bestehende Originalansicht zeigt gespeicherten Text, keine binäre PDF-Seitenvorschau. Die im Bildentwurf gezeigten Dateibilder, Größen und Personenbezüge werden nicht erfunden. Dies ist eine bewusste Produktgrenze dieser Lieferung.
- Quellenkontrolle bleibt sichtbarer als im generierten Bild; unbekannte bzw. historische Angaben werden nicht für eine ruhigere Ansicht weggelassen.
- P3: weitere Verdichtung der Quellenmetadaten und des mobilen Ordnerbereichs kann nach persönlicher Nutzung bewertet werden. Dies blockiert keinen geprüften Ablauf.
- Der Import bleibt bei Tabwechsel innerhalb des Gedächtnisses erhalten; damit wird kein allgemeiner dauerhaft gespeicherter Datei-Entwurf über App-Neustarts zugesagt.
- Keine vollständige WCAG-Abnahme, keine reale Mail-/Kalender-Providerabnahme, kein Modellqualitätsnachweis. Der pausierte Großimport wird nicht gestartet.

## Implementierungscheckliste

- [x] Gewählte Bildausgabe eindeutig zugeordnet; Originalassets wiederverwendet.
- [x] Dokumentarbeitsplatz und gemeinsame Gestaltung umgesetzt.
- [x] Reviewbefunde korrigiert und durch Verhaltenstests belegt.
- [x] Sichtbare Hauptabläufe, Rückwege und schmale/kurze Fenster geprüft.
- [x] 710/710 UI-Tests, TypeScript/Produktionsbuild, Assetvertrag und Diff-Prüfung bestanden.
- [ ] Persönliches Mac-Fenster und reale Daten nach gesondertem Update prüfen.
