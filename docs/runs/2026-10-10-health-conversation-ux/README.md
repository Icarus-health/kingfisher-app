# Health-Verlauf und Gesprächsaufnahme

Ergänzung auf `feat/memory-feedback-20261010`, ausgehend von `cc4e845`.
Erweitert denselben Draft-PR #54, keine neue Gedächtnisarchitektur.
Nicht auf dem persönlichen Mac installiert.

## Health

Die vorhandene Gesundheitsseite lässt eigene Messangaben jetzt nach vollständiger
Messgröße und genauer Einheit filtern. Eingabevorschläge kommen nur aus dem
geladenen Ausschnitt, der Filter selbst erreicht den gesamten gespeicherten
Messbestand. Die Namen werden getrimmt und ohne Groß-/Kleinschreibung verglichen;
Einheiten bleiben nach dem Trimmen case-sensitiv (mV ist nicht MV). Keine
Synonymannahme, Einheitenumrechnung oder medizinische Bewertung.

SQLite wählt passende Kandidaten vor der Seiten-/Scanbegrenzung aus. JSON-Prüfung
verhindert dabei, dass eine beschädigte Textquelle den Filter zum Absturz bringt.
Jeder angezeigte Wert wird anschließend weiterhin über das vorhandene vollständige
Original-/Metadaten-/Head-Verfahren geprüft. Der Cursor ist an den Filter gebunden;
Wechsel in einen anderen Filter wird abgewiesen. Ungefilterte und historische
Cursorverträge bleiben unverändert. Originalwerte, Messzeiten und Quellen werden
durch das Filtern nicht geschrieben.

Bei mindestens zwei aktuellen Angaben derselben Messgröße und Einheit zeigt die
Seite eine Kurve des **geladenen Ausschnitts**, kein vollständiges Lebenszeitbild.
Punkte verlinken ihre datierten Einträge und deren Originalquellen. Frühere Seiten
bleiben erreichbar. Die Positionen richten sich nach Messzeit, nicht Aufnahmedatum.
Dezimaldifferenzen werden mit BigInt exakt gebildet, bevor grafische Verhältnisse
berechnet werden. Originalwerte, Kommata, führende Nullen und Zeitzonen bleiben
in Einträgen und Punktbeschriftungen erhalten. Zeitunterschiede bis Mikrosekunden
bleiben für Sortierung und horizontale Positionen erhalten. Bei unterschiedlichen
Messgrößen/Einheiten oder ungültigen Daten erscheint keine vermischte Kurve.

## Gespräch

Im bestehenden Gespräch steht **Datei oder Transkript aufnehmen** direkt unter
dem Titel. Erst Öffnen montiert den bisherigen Dateiimport. Text, SRT/VTT,
DOCX/PDF werden über dieselbe lokale Vorschau und ausdrückliche Speicherung als
Quelle aufgenommen; die Projektzuordnung ist weiterhin optional. Der vollständige
Quellenbestand wird in dieser kompakten Ansicht nicht zusätzlich geladen.

Diese Aufnahme ist kein automatischer Anhang an die laufende Modellnachricht.
Die Oberfläche erklärt den Unterschied und die anschließende Gedächtnissuche.
Audiodateien werden hier nicht transkribiert. Der bestehenden Quellenverwaltung
bleibt ihr bisheriges Verhalten erhalten. Schließen mit einer fertigen ungespeicherten
Dateivorschau verlangt ausdrückliches Verwerfen; Weiter bearbeiten erhält den Text.
Während Einlesen oder Speichern ist Schließen gesperrt.

Die Gesprächseingabe ist mehrzeilig. Enter fügt eine Zeile hinzu; Strg/⌘ + Enter
oder der Senden-Knopf sendet ausdrücklich. Die Suche auf Heute bleibt einzeilig.
Die vorhandene lokale Diktatfunktion trägt weiterhin nur einen bearbeitbaren
Entwurf ein. Aufnahme, gesperrter Zustand und laufende Sendung blockieren Senden.
Ein Sendefehler erhält den Entwurf. Die Fehlerhinweise stehen jetzt unmittelbar
über der Eingabe statt unabhängig davon über dem vergrößerbaren Textfeld.

## Prüfungen

- Health: vier neue Backendfälle scheiterten vor Umsetzung, danach bestanden.
  37 Health-Backendfälle bestanden. Filter erreicht passende ältere Werte hinter
  105 anderen Messungen; Einheiten und Cursor bleiben getrennt; Korrektur, Entzug,
  beschädigtes JSON, Kontrollzeichen und Feldlängen geprüft.
- UI: sieben neue Health-Fälle scheiterten vor Umsetzung; ein weiterer echter
  Mikrosekunden-Gegenfall reproduzierte das Reviewfinding und wurde korrigiert.
  Der gerenderte Kurvenfall prüft Ausschnittkennzeichnung, Originalwert,
  Punkt-/Eintragslink und Fortsetzung. Sechs Gesprächsfälle scheiterten vor
  Umsetzung; ein weiterer Review-Gegenfall belegte verlorene Dateivorschau bei
  Schließen. Beide Fehler vor finaler Fassung behoben.
- Finale gemeinsame Prüfung: **187 betroffene Backendtests, alle 545 UI-Tests,
  Typprüfung und Produktionsbuild bestanden**. Assetvertrag: 16 Dateien, 16 Icons.
  Kein neuer vollständiger Backend-Gesamtlauf. Vorhandene Starlette/httpx-,
  Node-MockTimers- und große JS-Chunk-Hinweise.
- Unabhängiges Health-Review: konkreten Mikrosekundenfehler gefunden; nach Fix
  kein verbleibender Blocker, 14 betroffene UI-Fälle bestanden. Reviewer führte
  zudem 37 Health-Backendfälle vor diesem reinen UI-Zeitfix aus.
- Unabhängiges Gesprächsreview: Vorschauverlust gefunden; nach Fix kein verbleibender
  Blocker, 29 Gesprächs-/Sprachfälle bestanden.

Komprimierte Logs und `verification.json` dokumentieren den Hauptlauf einschließlich
beider roten Review-Gegenfälle. Komponentenprüfungen mit Hook-Treiber und statischem
Rendering ersetzen keine echte native Bedien-/Layoutprüfung.

Keine zusätzliche Bibliothek, Schemaänderung, Anbieteraktivierung, bezahlte
Modellanfrage, Importfortsetzung oder Arbeit am persönlichen Datenbestand.
Die synthetischen Uploadtests lesen ausschließlich künstliche Textdateien.
Kein neues ARM-App-/Backend-Paket und keine Installation oder neue OS-Freigabe
in dieser Lieferung. Nächster Auslieferungsschritt: gekoppeltes Paket bauen,
persönliche Sicherung prüfen und danach den echten Mac-Ablauf abnehmen.
