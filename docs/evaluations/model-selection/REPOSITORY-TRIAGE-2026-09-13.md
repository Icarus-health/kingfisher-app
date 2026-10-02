# Repository-Auswahl und nächster Prüfschritt

Stand: 13. September 2026. Dokumentationsreview mit einzelnen Code-Stichproben,
kein vollständiger Security-Audit. Keine Installation, Modell-Downloads oder
produktiven Datenzugriffe. Entscheidungen sind Kingfisher-spezifische Einschätzungen.

## Entscheidungen

- **Colibri: vorerst zurückstellen.** Inferenz-Engine mit diskbasiertem
  Expert-Streaming, kein persönliches Gedächtnis. Das GLM-Referenzbeispiel benötigt
  ca. 372 GB Modellplatz; dokumentierter kleiner 25-GB-Rechner erreicht kalt
  0,05–0,1 Token/s. Das ist keine Messung unseres M2 Max. Kleinere unterstützte
  Modelle haben andere Anforderungen. Für die erste alltagstaugliche CoS-Schleife
  rechtfertigt die Forschungslaufzeit den Wechsel von Ollama derzeit nicht.
  [Repository](https://github.com/JustVugg/colibri)
- **Maka: Architekturreferenz, kein Gesamtfork.** Ereignisprotokoll, daraus
  abgeleitete Kontextansichten und eine gemeinsame Ausführungsinstanz sind
  relevant. Ein Aktionsprotokoll ersetzt keine belegte, zeitlich gültige
  Personen-/Projektkenntnis. Electron/TypeScript-Gesamtübernahme würde unsere
  vorhandene Anwendung erheblich umbauen. Noch keine Apache-Veröffentlichung;
  Nightlies sind ausdrücklich Vorschauen.
  [Repository](https://github.com/apache/maka),
  [Architektur](https://github.com/apache/maka/blob/main/ARCHITECTURE.md)
- **VoiceStudio: später für lokale Sprachausgabe vergleichen.** Lokale Audio-API
  passt zum gesprochenen Morgenbriefing. Auf Apple Silicon ist laut Projekt die
  native Variante für GPU-Beschleunigung vorgesehen; veröffentlichte Docker-
  Images sind AMD64. Aktive Beta/Desktop-Umbau, AGPL-Anwendung und getrennte
  Modelllizenzen berücksichtigen. Vorzugsweise einen schmalen lokalen Audioadapter
  prüfen, nicht das gesamte Studio in Kingfisher integrieren.
  [Repository](https://github.com/debpalash/VoiceStudio)
- **Transformers: bei nachgewiesenem Bedarf als Bibliothek.** Relevant für
  spezialisierte Modelle und spätere Trainingsversuche; kein Agenten- oder
  Gedächtnisersatz. Kein Fork nötig, solange kein konkreter Upstream-Defekt die
  Integration blockiert. Für die Ollama-Baseline keine neue Abhängigkeit.
  [Repository](https://github.com/huggingface/transformers)

## Sicherheitsgrenzen der Sichtung

Maka dokumentiert eingeschränkte Sandbox-Abdeckung und eine durch Dateirechte
geschützte Klartext-Ablage für Zugangsdaten. Dies ist keine bestätigte Schwachstelle,
aber eine bewusste Architekturentscheidung, die wir nicht ungeprüft übernehmen.
[Security Policy](https://github.com/apache/maka/blob/main/SECURITY.md)

VoiceStudios Backend enthält Authentifizierungs- und Origin-Prüfungen; der
Bearer-Schutz hängt von der Konfiguration ab. Gelesen wurden ausgewählte Stellen
in `backend/main.py`, nicht sämtliche Routen/Startpfade oder Abhängigkeiten.
Daraus folgt keine Sicherheitsfreigabe für persönliche Daten oder LAN-Freigabe.
[Backend](https://github.com/debpalash/VoiceStudio/blob/main/backend/main.py)

Transformers empfiehlt Safetensors und Codeprüfung sowie feste Revisionen bei
`trust_remote_code=True`. Ungeprüften Modellcode nicht automatisch aktivieren.
[Security Policy](https://github.com/huggingface/transformers/blob/main/SECURITY.md)

## Nächster sinnvoller Entwicklungsblock

Zuerst die Messung belastbar machen, anschließend vorhandene Modelle vergleichen.
Die Prüfung von `scripts/evaluate_calendar_context.py` bestätigt: Es benutzt den
echten Agenten samt deterministischen Kalenderantworten. Solche erfolgreichen
Antworten mit null Modellaufrufen sind Anwendungsevidenz, keine Modellqualifikation.

1. Separate synthetische Modellprüfung vorbereiten, ohne Datenspeicher und ohne
   ausführbare Werkzeuge. Den tatsächlich gesendeten Kontext und erfolgreichen
   Modellaufruf erfassen; fehlende Antwort/Timeout als Fehler erhalten.
2. Gleiche Fälle auf zwei Ebenen prüfen: einmal mit vorgegebenem korrektem Kontext
   direkt am Modell, einmal durch Kingfishers Kontextabruf. So unterscheiden wir
   Abruf-, Modell- und Integrationsfehler.
3. Zunächst vorhandene Modelle verwenden und die leere Qwen-4B-Antwort untersuchen.
   Modellkennung/Digest, Parameter, Thinking, Kontextbudget und Laufzeitversion
   aufzeichnen. Keine neuen Downloads aus dieser Repository-Sichtung ableiten.
4. Kernfälle: zwei Mainz-Bezüge; neuere Absage; namensgleiche Personen;
   Gedankenexperiment statt Überzeugung; widersprüchliche Quellen; veralteter
   Kalender; unerledigte Terminvorbereitung; eingeschleuste Anweisung;
   Entwurf ohne Versand; unklarer Empfänger; fehlgeschlagenes Werkzeug;
   Kontextwechsel in einer Folgefrage. Synthetische Namen verwenden.
5. Kriterien vorab festlegen: Quellenrichtigkeit, Zeitbezug, Identität,
   angemessene Rückfrage, Aktionsgrenzen, Latenz. Kritische Fehler nicht mit
   Durchschnittswerten verrechnen. Natürliche Antworten benötigen menschliche
   Prüfung; JSON-Format und Werkzeugargumente zusätzlich maschinell prüfen.
6. Erst danach einen neuen Modellkandidaten vergleichen und die beste belegte
   Kombination in einen vollständigen Alltagspfad integrieren: Nachricht →
   Gedächtnis → Briefing/Rückfrage → Entwurf → konkrete Nutzerfreigabe.

Noch nicht ausgeführt: neuer Modellbenchmark, Integration der vier Repositories,
neue Audiofunktion oder Sicherheitsfreigabe. Der nächste Block benötigt keinen
Architekturwechsel und kein Fine-Tuning.
