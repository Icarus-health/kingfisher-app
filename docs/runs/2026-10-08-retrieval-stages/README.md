# Getrennte Abrufdiagnose – noch keine Qualitätsverbesserung

Basis: zusammengeführter CoS-Stand `30593d4`, installierter Produktcode `da5b0e6`. Der eingefrorene Katalog und seine früheren Berichte bleiben unverändert.

Die bisherige Kennzahl `retrieved_expected` prüfte tatsächlich angezeigte Quellen, nicht Suchkandidaten. Version 2 der Diagnose erhält dieses Feld kompatibel, benennt seine Bedeutung ausdrücklich und ergänzt Kandidatenfund, Auswahl, Anzeige und erste fehlende Stufe getrennt. Fehlt `working_answer.basis`, ist der Kandidatenfund **unbeobachtet**, nicht als leer gemessen. Begrenzte Rohantworten des Modells werden nur im synthetischen Werkzeug samt Pending-/Fehlerzustand erfasst.

Vier neue Stufenregressionen und zwei Modellprotokollregressionen schlugen vor der Implementierung erwartungsgemäß fehl. Abschließende betroffene Datei: **19 bestanden**. Das echte Agentenverfahren mit künstlichem Offlineanbieter und Quellenentzug bleibt enthalten. Keine Produkt-/Datenbankänderung, keine neue Mac-Installation erforderlich.

## Befund aus dem unveränderten echten Bericht

- Zwei Fragen haben die erwarteten Kandidaten, aber keine ausgewählten/angezeigten Quellen: Dachreparatur und Berichtsfreigabe. Ohne rohe Modellantwort bleibt Modellentscheidung gegenüber nachträglichem Guard ungeklärt.
- Eine Frage hat Kandidat und Auswahl; der Satzschritt liefert `nichts`: Anmeldung zum Workshop, gefragt als Seminar.
- Fünf Fragen haben keine gespeicherte Abrufspur: Serverausfall, Zugangskarte, Lieferantenverträge, Bildlizenz und Urlaubsvertretung. Daraus kann nicht bewiesen werden, dass die Suche null Kandidaten fand.
- Die direkt formulierten Fragen zu denselben Originalen sind Vergleichsfälle aus demselben Katalog, **keine unabhängige Kontrollmenge**.

## Lokaler Messversuch ohne Ergebnis

Ein getrennter lokaler Ollama-Dienst sollte bge-m3-Scores für 16 Umschreibungen, 16 direkte Vergleiche, vier nicht beantwortbare Fragen und vier zusätzliche nahe Negativfragen messen. Die Startversuche scheiterten mit HTTP 500 beim Metal-Kontext. Ein abschließender expliziter CPU-Versuch (`num_gpu=0`, `num_ctx=2048`, 45-Sekunden-Limit) bestätigte CPU-Offload 0/25, scheiterte nach etwa 1,3 Sekunden weiterhin beim Erzeugen der Metal-Command-Queue. **Keine Scores, Ränge oder Schwellenempfehlung.** Dienst beendet, keine Downloads, Cloud abgeschaltet, fremde Dienste unverändert. Private Daten wurden nicht genutzt.

Nächster Schritt ist ein funktionierender isolierter lokaler Lauf mit Stufenspur, nicht eine Wortliste oder ungemessene Schwellenabsenkung. Der Mac war beim nativen Fenstertest gesperrt; eine Ursache des Metal-Fehlers ist damit nicht bewiesen. Offene Produktqualität bleibt dieselbe wie im vorherigen Liefernachweis.
