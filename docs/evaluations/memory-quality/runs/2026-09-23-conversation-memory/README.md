# Gesprächsaufnahme und gemeinsamer CoS-Arbeitsstand — 23.09.2026

Normale neue Nutzerbeiträge werden einzeln als CHAT-Originalquelle mit Nachrichtenzeit und stabiler Herkunft aufgenommen. Die bereits eingeschaltete lokale Verarbeitung wird geweckt; Einstellungen werden nicht geändert. Ein ausdrückliches „Merke dir“ ist für die Arbeitsnutzung nicht erforderlich. Bestätigte Aussagen und Aufgaben entstehen dabei nicht automatisch. Der bisherige ausdrückliche Merke-Pfad verwendet dieselbe Quelle und erhält seine Personen-/Themen-/Projektmetadaten.

Reine, als Gedächtnisabruf geroutete Fragen bleiben im Gespräch gespeichert, werden jedoch nicht in die Quellenbericht- oder Originaltextsuche aufgenommen. Eine Frage ist kein Beleg für ihre Antwort. Normale gemischte Beiträge bleiben von der Modellklassifikation abhängig; die Unterscheidung ist keine allgemeine Sprachgarantie.

Quellenausschluss und Quellenänderung entwerten abhängige Antworten über mehrere Gesprächsschritte, Vorschauen, automatisch erzeugte Titel und ausstehende Freigaben. Der globale und der gesprächsbezogene Freigabeweg prüfen dieselbe Grundlage. Eine Wiederzulassung der Quelle belebt alte Antworten/Freigaben nicht wieder. Unvollständig belegte frühere Gesprächsantworten werden konservativ zurückgehalten. Alte Gesprächsbestände werden nicht nachträglich vollständig eingelesen.

Die Tagesübersicht zeigt begrenzt neu aufgenommene, automatisch eingeordnete Quellen aus den letzten 24 Stunden. Terminvorbereitung nutzt die gleiche Einordnung für ausdrücklich ausgewählte Projekt-/Personenquellen. Aufnahmereihenfolge ist keine Wahrheitsentscheidung, Namensgleichheit keine Zuordnung, eine bedingte Aussage keine feste Aufgabe. Originale und Korrektur sind über die vorhandene Quellenansicht erreichbar.

## Prüfung mit lokalem Modell

Vier neue synthetische Gesprächsangaben wurden über den HTTP-Gesprächsweg aufgenommen und mit dem vorhandenen lokalen `qwen3.5:4b` klassifiziert und ausgewählt: bedingte Lieferung, Bitte ohne Zusage, Aufbewahrungsort nach Neustart sowie explizite Datumsänderung. Alle vier Fragen enthielten die erwartete Quelle und vollständige entscheidende Einschränkung; keine fremde Quelle wurde ausgewählt. Acht echte lokale Modellaufrufe pro Durchlauf. Keine privaten Nutzerdaten.

Die allgemeine Chatbestätigung war ein kontrollierter Testanbieter; echte Modellaufrufe betreffen Einordnung und Auswahl. Die Hintergrundfunktion wurde in diesem Modelltest direkt aufgerufen, ihr tatsächlicher Thread und die Bedienung wurden separat im Browser geprüft. Es ist ein kleiner Integrationstest mit eingefrorenen Erwartungen, kein allgemeiner Qualitätsprozentsatz. Der erste Durchlauf bleibt als Entwicklungsnachweis archiviert; der zweite prüft zusätzlich den korrigierten Fragenfilter und dass der Abruf nach dem nächsten Hintergrundlauf gültig bleibt. Die Korrektur machte bereits richtige Entwicklungsfälle nicht zu einem neuen unabhängigen Benchmark.

Beide Durchläufe behielten die Bedingung und fehlende Zusage bei. Im abschließenden Lauf blieben Daten nach Neustart abrufbar, die Suchfragen verursachten keine zusätzliche Klassifikation, Quellenentzug entfernte den synthetischen Testcode aus altem Verlauf, Vorschau und neuem Abruf, das Original blieb erhalten. Keine neuen Claims oder Aufgaben.

## Abschließende Prüfungen

- Produktcode `818b582`: `PYTHONPATH=sidecar:scripts python -m pytest sidecar/tests scripts -q` — **2273 Tests und 4 Untertests bestanden**, 191 Sekunden. Zwei bekannte Starlette/httpx-Abkündigungswarnungen; keine Fehler.
- Oberflächen-Build einschließlich TypeScript und Assetprüfung bestanden (14 Dateien, 17 freigegebene Icons). Unabhängige Prüfung der gemeinsamen Quellenprojektion fand keine weiteren konkreten Blocker.
- Echter Browserdurchlauf in isolierten synthetischen Daten: neue Gesprächsangabe, tatsächlicher Hintergrundthread, Abruf mit vollständiger Bedingung, lesbare Quelle in der Tagesübersicht, Ausschluss einschließlich altem Gespräch, explizite Projektauswahl im Termin, sichtbare Kennzeichnung „Bedingte Aussage“, Quellenfenster über die 15-Sekunden-Aktualisierung hinweg, Verwerfen der Einordnung und Wechsel des Kontextes. Keine Browserwarnungen/-fehler. [Prüfprotokoll](browser-verification.json).
- Dabei behoben: nach Neuladen verschwundene Quellenkontrollen, doppelt übersetzte Einordnungslabels und zu schmale Quellenkarte. Eine unvollständige alte Testquelle wurde auf den echten Aufnahmeweg umgestellt; die strengere Produktionsprüfung wurde nicht gelockert.

## Grenzen

Keine vollständige CoS-V1-Abnahme: Antwortentwürfe greifen noch nicht auf diesen zusätzlichen Arbeitsstand zu. Allgemeine Personen-/Projektauflösung, paraphrasierte Suche, lange/unvollständige Quellen und die Langzeitqualität sind weiterhin getrennte offene Punkte. Die Terminansicht übernimmt ausschließlich bereits ausdrücklich zugeordnete Quellen. Automatische Verarbeitung setzt die vorhandene aktivierte lokale Modellprüfung voraus.
