# Profilverwaltung: gemeinsame Abnahme

8. September 2026. Ergebnis: bestanden im Umfang von SDR-011 und Roadmap-Punkt 08.
Referenz: Systemübersicht, Screen 06. Desktop: 1521 × 1034.
Browser plugin nicht verfügbar; vorhandenes Playwright gegen den tatsächlich
gebauten Docker-Container auf 127.0.0.1:8892. Synthetischer isolierter Bestand,
keine erzeugten Personen oder Belege in den Nutzerdaten.

## Funktionsnachweise

- Gleichnamige per Link vergleichen; Name ändern und nach Neuladen lesen.
- Quellenkennung lösen abbrechen/bestätigen; andere Identität bleibt unverändert.
- Aussage, Ziel, Kontext und Zeitraum ändern. Gleichnamige auch in der Prüfung
  eindeutig. Ungültiger Zeitraum verhindert Fortfahren; Ortszeit korrekt gespeichert.
- Prüfphase schreibt nichts. Bestätigung erzeugt neuen Stand; ersetzter Stand bleibt.
- Widerruf abbrechen lässt aktiven Stand erhalten; Bestätigung und Neuladen zeigen
  Widerruf. Originalquelle des ersetzten Standes bleibt im Verlauf lesbar.
- Kontrolliert ausgelöste HTTP-503-Fehler bei Namensänderung und Profilladen:
  Meldung sichtbar, Wiederholen gegen das echte Backend erfolgreich.
- 19 gezielte Backendtests (test_claim_correction.py, test_memory_corrections.py)
  decken neue Korrekturbelege, Konflikte, ungültige Änderungen ohne Schreibwirkung,
  Identitäten, Herkunft und Korrekturverlauf ab. Build und Assetmanifest bestanden.

## Sichtprüfung und Abweichungen

Kompakte Übersicht, Namensbearbeitung, Speicherfehler, Quellenlösung, ungültiger
Zeitraum, abschließende Korrekturprüfung, Ladefehler und Historie geprüft.
Keine horizontale Überbreite, abgeschnittenen Felder oder Framework-Overlays;
keine JavaScript-Laufzeitfehler. Kontrollierte HTTP-Fehler sind Testinjektionen.
Ungestaltete blaue Links und zu große Zwischenüberschriften korrigiert.
Paarweise Felder verkürzen das Formular; lange Inhalte bleiben regulär scrollbar.
Die Formulare ergänzen die Referenz gemäß SDR-011; die Gesamtakte ist hiermit
nicht als vollständig referenzgetreu abgenommen. Mobile bleibt zurückgestellt.

Belege im Aufgabenordner outputs/: controls-compact.png, controls-rename.png,
controls-rename-error.png, controls-unlink-review.png, controls-invalid-period.png,
controls-load-error.png, correction-identity-review.png, correction-history-source.png.
Prüfskripte: controls-visual-qa.cjs, identity-joint-qa.cjs,
correction-identity-qa.cjs, correction-final-qa.cjs.
