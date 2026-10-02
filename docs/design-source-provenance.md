# Herkunft der kanonischen Designquelle

- Quelle: Google-Drive-Ordner `Kingfisher`
- Freigegebener Ordner: (intern)
- Übernommen am: 2026-09-01
- Umfang: 97 Dateien aus den freigegebenen Brand-, Icon-, Media-, Foundation-,
  Komponenten-, Screen- und Coding-Package-Ordnern
- Ausgeschlossen: `Review` und `Concepts`

Alle 97 Dateien wurden nach dem Abruf bytegenau gegen die von Google Drive
gemeldeten Dateigrößen geprüft. Das Coding Package und die Approved-Dateien
liegen unverändert unter `design-source/`. Die maschinenlesbare Allowlist ist
`design-source/07_Coding_Package/KINGFISHER-ASSET-MANIFEST-v1.json`.

## Verbindliche Doppelablage

Google Drive und GitHub haben absichtlich unterschiedliche Rollen:

- **Google Drive `Kingfisher`** bleibt die Quellenablage. Jedes freigegebene
  Bild, Icon, Font und jeder kanonische Screen muss dort weiterhin verfügbar
  sein.
- **`design-source/` im Repository** ist die eingefrorene, reproduzierbare
  Implementierungskopie. Docker-Builds dürfen niemals auf eine Live-Abfrage
  von Drive angewiesen sein.

Eine Datei darf nur in das Asset Manifest aufgenommen oder darin ersetzt
werden, wenn die zugehörige Drive-Datei beziehungsweise ihr freigegebener
Drive-Ordner dokumentiert ist. Für jeden künftigen Asset-Release werden
Drive-Referenz, verfügbare Drive-Revision und SHA-256 im Release-Protokoll
festgehalten. GitHub ist damit ein prüfbarer Build-Stand, aber nie das einzige
Archiv der visuellen Originale.

## Ergänzung vom 2026-09-02

Der Product Owner hat die V3-Vorschau und deren kleinste Asset-Ergänzung
ausdrücklich freigegeben. Manifest 1.1 ergänzt ausschließlich fünf bereits in
`03_Media/Approved` abgelegte Dateien sowie die drei in der Vorschau
abgenommenen Steuericons `microphone`, `arrow-up` und `pause`. Die
Entscheidung ist in
`docs/screen-deviations/SDR-002-approved-v3-controls-and-media.md`
dokumentiert. Die ursprünglichen 97 Dateien bleiben unverändert erhalten.

Manifest 1.2 ergänzt keine Datei. Es schreibt ausschließlich die verbindliche
Doppelablage mit dem Kingfisher-Drive-Ordner fest.

## Ergänzung vom 2026-09-27

Der Product Owner hat die zweite finale Today-Variante ausgewählt und deren
Umsetzung beauftragt. Manifest1.3 ergänzt drei eigenständige Bildmotive und die
gewählte kanonische Today-Vorlage. Drive-IDs, Dateigrößen und SHA-256 stehen in
`docs/release/ASSET-RELEASE-2026-09-27.md`; Umfang und Abweichungen in SDR-014.
Die früheren Quellen bleiben unverändert.
