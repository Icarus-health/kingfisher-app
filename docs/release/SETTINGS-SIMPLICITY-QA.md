# Einstellungen vereinfachen

Referenz: system-overview-canonical-source-v1.png (vor der Veröffentlichung entfernt), Ansicht 14. Die Vorlage zeigt kompakte Integrationszeilen. Die lokale Umsetzung ergänzt vorhandene Einrichtungsabläufe und beansprucht keine vollständige visuelle Abnahme.

Bereits eingerichtetes Modell: Name sichtbar, Bearbeitung über „Modell verwalten“. Ohne Einrichtung bleibt das Formular offen. Ein Modellname bedeutet eingerichtet, nicht frisch geprüfte Verbindung. Kalendersynchronisationsstand bleibt sichtbar; einzelne Kalender und Zugriffsdetails werden auf Wunsch geöffnet. Trennen liegt in den Zugriffsdetails. Blätter-Schaltflächen erscheinen bei Dateilisten nur, wenn mehrere Seiten vorhanden sind.

Playwright mit isolierter App und simuliertem Einrichtungsstatus prüft kompakte Darstellung und erneutes Öffnen der vollständigen Bedienelemente, keine Browserfehler. Screenshot mit Originalübersicht verglichen; Typografie und Abstände angeglichen. Build und Assetmanifest bestanden. Keine echten Modelle oder Kalenderkonfigurationen im Test geändert.

Ergänzende Prüfung am 7. September: frischer Docker-Bestand mit aktivem
Sitzungsschutz und dem auf dem Mac installierten Ollama-Modell `qwen3.5:4b`.
Ein absichtlich nicht installiertes Modell wird gespeichert, der tatsächliche
Verbindungstest schlägt verständlich fehl. Die Überschrift zeigte zunächst
fälschlich noch das vorherige Modell. Sie übernimmt jetzt die aktive gespeicherte
Konfiguration unmittelbar nach dem Speichern, unabhängig vom Testergebnis.
Der gleiche Browserablauf reproduzierte den Fehler vor der Änderung und bestand
danach; anschließende Auswahl und Verbindung des echten Modells erfolgreich.
Screenshot des Fehlerzustands auf Lesbarkeit geprüft, Build bestanden.
Die Modelländerungen betrafen ausschließlich den getrennten Testbestand.

Registry-Profile: bestätigte Beziehungen und Aussagen stehen vor der Verwaltung. Namens-/Quellenwerkzeuge liegen in „Profil verwalten“; die Anzahl gleichnamiger Einträge bleibt im geschlossenen Zustand sichtbar. Isolierter Browsertest prüft geschlossenen Zustand, Öffnen, Umbenennen, Persistenz nach Reload und Erreichbarkeit/Abbruch der Quellenlösung. Screenshot visuell geprüft; Build und Assetmanifest bestanden.
