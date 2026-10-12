# Getrennter Hindsight-Vergleich

> Für die Ausführung: kleine sequenzielle Messungen im bestehenden Checkout; unabhängige Fallprüfung durch einen günstigeren Agenten.

**Ziel:** Mit dem vorhandenen lokalen Qwen prüfen, welche Hindsight-Bausteine Kingfishers Abruf zuverlässiger und schneller machen können.

**Architektur:** Zwei getrennte künstliche Datenspeicher, gleiche Originale und Modellgewichte. Aufnahme, reine Suche und modellgestützte Antwort getrennt messen; unterschiedliche Antwortformate ausdrücklich kennzeichnen. Kein Austausch des Produktgedächtnisses.

**Technik:** Eingefrorener Kingfisher-Code f75ccad, Hindsight 0.10.3 in eigener Python-Umgebung, Qwen9B und vorhandenes bge-m3, optional kleiner lokaler Reranker.

**Auftrag:** Aktuelle ausdrücklich freigegebene Vergleichsprüfung des Nutzers.

## Grenzen

- Nur künstliche Quellen; keine persönlichen Datenbanken, Cloudanbieter oder echten Zugriffsschlüssel.
- Keine Änderung der laufenden App, ihrer Konfiguration, Konten oder Importpause.
- Keine neuen großen Sprachmodelle. Einmalige kleine Testabhängigkeiten und Gewichte gesondert protokollieren.
- Ein Modellaufruf zur Zeit, feste Zeitlimits, Token-/Aufrufzahlen und kalte/warme Zustände erfassen.
- Docker-Reserve erhalten; eigener temporärer Host-Datenspeicher.

## Prüfstellen

Gleiche Namen; Änderung/Absage; Bedingungen statt Zusagen; Quellenzeit statt Erfassungszeit; fehlende Informationen und tatsächlich entzogene Originale. Kündigungs-/Absagebelege sind relevante historische Quellen, keine zu löschenden Treffer.

## Ausführung

1. [x] Gemeinsamen kleinen Quellen-/Fragenkatalog vor dem ersten Lauf festlegen; erwartete Original-IDs und Aussagegrenzen getrennt führen.
2. [x] Hindsight isoliert starten, lokale Modellidentität und sämtliche Inferenzziele prüfen. Kingfisher-Originalbestand bleibt unberührt.
3. [x] Gleiche automatische Aufnahme, Suche und Antworten messen; Fehler und Abbrüche als Ergebnisse erhalten. Enger Reranker-Versuch nur am Testadapter.
4. [x] Ergebnis mit Einzelbelegen und Grenzen dokumentieren; Testdienste stoppen. Nur belegte, kleine Übernahmevorschläge, keine neue Produktarchitektur.

Der Nutzer hat die Ausführung bereits ausdrücklich freigegeben; zusätzliche Planfreigabe ist für diese getrennte Prüfung nicht erforderlich.

Ergebnis: docs/runs/2026-10-12-hindsight-comparison/README.md. Keine Produktintegration; native Hindsight-Antworten nach zwei vollständig gemessenen Fällen begrenzt. Testdienste beendet.
