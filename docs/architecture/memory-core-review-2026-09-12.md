# Review: Memory Core v0.1 und OpenViking

Stand: 12. September 2026. Ergebnis: **als Architektur- und Abnahmegrundlage
übernehmen, mit den nachfolgenden Präzisierungen. Keine Laufzeitfreigabe.**

## Prüfgegenstand und Entscheidung

Vollständig gelesen: [Memory Core und Sicherheitsvertrag v0.1](kingfisher-memory-sicherheitsvertrag-v0.1.md),
596 Zeilen, PR #34, ursprünglicher Head
`6f34f1566780ae522b720eebcb85f84c48bb1444` auf Basis
`a40071e281427a267d3530ede4fafb042c3011b7`.
SHA-256 der unveränderten Vorlage:
`2e342383f49cac4a94e940fdd5dedb0499fc2b3a76126674144f392544bfbcca`.

Der Vorschlag passt zur Produktvision: ein nachvollziehbarer Aufzeichnungsbestand,
getrennte Interpretation und Bestätigung, zeitlicher Verlauf, begrenzter Abruf,
Abdeckungsnachweis, unabhängig durchgesetzte Befugnisse und gemessene Entlastung.
Insbesondere die getrennten Zeitpunkte von Quellenbesitz und erkannter Aussage,
die Abhängigkeit vom gesamten Modellinput und das Vorgehen bei unbekanntem
Versandstatus präzisieren die bisherige Planung sinnvoll.

Übernommen wird die Zielarchitektur als Grundlage für konkrete Implementierungs-
und Prüfaufträge. Der Merge erlaubt keine neue Datenaufnahme, automatische Annahme
von Fakten, Migration, Modellausführung, Installation oder Außenaktion.
Die bestehende App bleibt in diesem PR unverändert.

## 1. Verhältnis zu bisherigen Verträgen

`CLAUDE.md`, `docs/08-gedaechtnisschichten.md` und `docs/10-verdichtung.md`
verlangen menschliche Annahme für bestätigten Bestand. KNOW-01 schafft dafür
keine Ausnahme: begrenzte Arbeitsinterpretationen sind ein eigener erkennbarer
Status, keine automatisch bestätigten Claims. Die betreffende Klasse muss zuerst
evaluiert und für ihren konkreten Zweck freigegeben werden.

Die Umsetzung muss diese Unterscheidung in Speicherung, Suche, Chat, Briefing und
Oberfläche gemeinsam tragen. Bis dahin bleiben die heutigen Regeln wirksam.
Eine Freigabe dieses Dokuments bestätigt keine darin erwähnte persönliche Tatsache.

Der lokale Gesprächsentwurf `docs/24-gedaechtnis-zielbild-entwurf.md` bleibt eine
ergänzende, bislang nicht versionierte Sammlung von Produktbeispielen. Seine
40 Fälle und Laufzeitannahmen sind frühere Vorschläge. Für die kommende technische
Abnahme verwenden wir den präziseren Umfang aus Abschnitt 13 von v0.1:
90 fachliche Fälle in getrennten Szenarien sowie mindestens 40 adversarielle
Abläufe. Keine der genannten Größen ist bereits eine bestandene Modellprüfung.

## 2. Präzisierung zu CHG-05/06: ältere Backups und spätere Löschung

Ein altes Backup enthält Löschentscheidungen aus späterer Zeit gerade nicht.
Das bloße Wiederherstellen seiner eigenen Löschmarker reicht deshalb nicht aus.
Der Restore-Vertrag wird für die spätere Umsetzung so konkretisiert:

- Lösch-/Widerrufsstand muss einen vom wiederhergestellten Datenstand getrennt
  abgleichbaren, versionierten Nachweis besitzen. Speicherort, Sicherung und
  Schlüsselwiederherstellung werden im Migrationsentwurf festgelegt.
- Vor Indexaufbau, Modellverarbeitung, Export und normalem Lesebetrieb werden
  spätere Entscheidungen auf den wiederhergestellten Bestand angewendet.
- Ist die Vollständigkeit dieses Nachweises unklar, bleibt der Restore isoliert;
  keine Zusicherung, dass gelöschte Daten nicht wiederkehren. Erst den Umfang
  klären, dann reguläre Nutzung freigeben.
- Der Prüfbestand muss enthalten: Backup erstellen → Inhalt löschen → altes
  Backup wiederherstellen. Nur Marker aus demselben alten Snapshot zu prüfen
  erfüllt T-DEL-01 nicht. Physische Backup-Aufbewahrung bleibt separat zu regeln.

Dies ist eine Architekturpräzisierung, keine Behauptung über die vorhandene
Recovery-Implementierung und kein bereits ausgeführter Restore-Test.

## 3. Präzisierung zu KNOW-01 und Abschnitt 13.4: Qualität pro Klasse

98 % Präzision und 95 % Erkennung sind vorgeschlagene Messziele, kein universeller
Freigabewert für folgenreiche Entscheidungen. Eine aggregierte Quote kann seltene,
aber schwere falsche Zusagen, Identitätsverwechslungen oder Beträge verdecken.

Version 1 beginnt wie KNOW-01 vorsieht mit Anfrage, Gesprächsgegenstand und
eindeutig datiertem Ereignis. Automatisch nutzbare Commitments werden dadurch
nicht mitfreigegeben. Für jede später ergänzte Klasse sind Zweck, Fehlerfolgen,
repräsentativer Prüfbestand, Nenner, Unsicherheit und Rückfallverhalten separat
festzulegen. Hypothetische/negierte Zusagen, falscher Sprecher und falsche Frist
sind verpflichtende Gegenfälle. Keine automatische externe Aktion allein wegen
bestandener Extraktion. In Zweifelsfällen bleibt der Befund Kandidat.

Für eine aktuelle Aussage wie "keine Zusage erfasst" gelten Abdeckung und Zeitstand;
sie darf nicht zu "du hast nichts zugesagt" verkürzt werden.

## 4. Gezielter Codeabgleich am Basisstand

Die Prüfpunkte R-01 bis R-05 wurden an `a40071e` nachvollzogen:

- `Agent.send()` setzt `_tainted` zurück, obwohl Verlauf erhalten bleiben kann;
  `load_history()` setzt die Markierung ebenfalls zurück. Eine Herkunftsprüfung
  muss daher auch fortgesetzte und geladene Gespräche erfassen.
- Quellen-/Personenkontext wird mit dem Systemprompt zusammengeführt. Eine
  Rollentrennung wäre nur eine Hilfsmaßnahme; die unabhängige Durchsetzung ist
  weiterhin erforderlich.
- `Policy` verwendet wortbasierte Constraints und hält ihre allgemeinen Pending
  Approvals in einem Dictionary. Andere fachliche Freigabepfade sind damit nicht
  pauschal beurteilt; vor Änderungen ist eine vollständige Pfadaufnahme nötig.
- Vorhandene Zitatvalidierung prüft keine semantische Folgerichtigkeit.

Das sind belegte Abweichungen zum Zielvertrag, kein demonstrierter Exploit und
kein vollständiger Sicherheits-Audit. Vor weiterer Freigabe agentischer Befugnisse
werden die durchgängigen Aufrufwege und Gegenproben priorisiert. Dieser reine
Dokumentations-PR repariert diese Stellen nicht.

## 5. OpenViking: passende Ideen, keine direkte Kernübernahme

Gelesener Repository-Stand:
`volcengine/OpenViking@0f77ab5625a5e2ead4f286d4e58ea77e05fcfdee`.
Reine Quellcodeprüfung: nichts installiert oder ausgeführt, keine Kingfisher-Daten
übergeben. Die folgende Bewertung ist begrenzt und kein Sicherheitszertifikat.

### Passende Teile

OpenViking organisiert Kontext unter `viking://` und lädt Abstract, Overview und
Detail bedarfsabhängig. Das passt zur geplanten Zugriffstiefe. Der Code in
`openviking/retrieve/context_assembler/budget.py` verteilt ein Kontextbudget zuerst
auf Kandidaten und vertieft anschließend; `hierarchical_retriever.py` bietet den
hierarchischen Suchpfad. Diese Ansätze sind konkrete Vergleichskandidaten.

Lokales Ollama ist laut README konfigurierbar. Benötigt werden auch ein Embedding-
Modell und ein VLM; die publizierte Memory-Auswertung verwendet laut README
Doubao-Modelle. Daraus folgt keine nachgewiesene Qualität oder Laufzeit mit unseren
lokalen Modellen auf M2 Max/32 GB.

### Unterschiede und Integrationsgrenzen

- `LICENSE` und SPDX-Köpfe des geprüften Stands nennen **AGPL-3.0**. Kein Fork,
  Codeimport oder Vertriebsmodell wird in diesem Review freigegeben. Die konkrete
  Lizenzverträglichkeit ist vor einer Übernahme separat zu klären.
- `openviking_cli/utils/config/memory_config.py:67–81` aktiviert Extraktion bei
  Session-Commit standardmäßig und verwendet standardmäßig eine eingeschränkte
  Python-DSL. Der Interpreter beschreibt keine freie Python-/Shell-Ausführung;
  das darf nicht als gefundene Codeausführungslücke behauptet werden.
- Das Extraktionsprotokoll erlaubt Create/Update/Delete und Verknüpfungen bestehender
  Erinnerungen. Diese modellgesteuerte Pflege darf nicht direkt Kingfishers
  bestätigten Bestand verändern. Abstammungsfelder sind im Code vorhanden; sie
  beweisen noch nicht unseren Zeit-, Rechte-, Widerrufs- und Restore-Vertrag.
- Serverkonfiguration bindet standardmäßig an `127.0.0.1`; ohne Root-API-Key wird
  der Dev-Modus gewählt, CORS ist standardmäßig `*`. Das ist keine passende
  ungeprüfte Konfiguration für eine Kingfisher-Integration.
- Die gelesenen Konfigurationen deaktivieren Tracing/OTel-Exporte, Body-Dumps und
  Usage-Reporter standardmäßig. Das ist kein pauschaler Beweis für ausbleibenden
  Netzwerkverkehr; Provider, Crawling, Erweiterungen und Installationshelfer sind
  zusätzliche Datenwege. Ein lokaler Betrieb braucht explizite Konfiguration und
  beobachtete Netzwerkgegenproben.

### Empfehlung

OpenViking vorerst als **optionalen, neu aufbaubaren Such- und Verdichtungsdienst**
evaluieren, nicht als autoritativen Memory Core. Ein Kingfisher-Adapter würde nur
für den Zweck erlaubte, versionierte Daten projizieren; Rückgaben bleiben
Kandidaten und werden vor Verwendung gegen den Kern geprüft. Keine automatischen
Session-Memory-Writes in bestätigte Kingfisher-Daten. Bot, fremde Skills und
Installationshelfer sind dafür nicht erforderlich.

Voraussetzung für einen späteren isolierten Vergleich: Lizenzentscheidung, fester
Stand, lokale Provider und Embeddings, authentifizierter begrenzter Zugang,
Netzwerkbegrenzung sowie Lösch-/Versionsabgleich. Zuerst synthetische Fälle, gleiche
Qualitäts- und Ressourcenmessungen wie für SQLite/FTS plus eigene Übersichten.
Erst ein messbarer Vorteil bei akzeptablem Zusatzaufwand begründet die Integration.

### Quellverweise des OpenViking-Reviews

- [README einschließlich Modelle der Memory-Evaluation](https://github.com/volcengine/OpenViking/blob/0f77ab5625a5e2ead4f286d4e58ea77e05fcfdee/README.md)
- [Lizenz](https://github.com/volcengine/OpenViking/blob/0f77ab5625a5e2ead4f286d4e58ea77e05fcfdee/LICENSE)
- [Budgetierte Kontextauswahl](https://github.com/volcengine/OpenViking/blob/0f77ab5625a5e2ead4f286d4e58ea77e05fcfdee/openviking/retrieve/context_assembler/budget.py)
- [Extraktionskonfiguration](https://github.com/volcengine/OpenViking/blob/0f77ab5625a5e2ead4f286d4e58ea77e05fcfdee/openviking_cli/utils/config/memory_config.py)
- [Eingeschränktes Extraktionsprotokoll](https://github.com/volcengine/OpenViking/blob/0f77ab5625a5e2ead4f286d4e58ea77e05fcfdee/openviking/session/memory/extraction_output_protocol/python_protocol.py)
- [Serverkonfiguration](https://github.com/volcengine/OpenViking/blob/0f77ab5625a5e2ead4f286d4e58ea77e05fcfdee/openviking/server/config.py)
- [Tracing-Konfiguration](https://github.com/volcengine/OpenViking/blob/0f77ab5625a5e2ead4f286d4e58ea77e05fcfdee/openviking_cli/utils/config/telemetry_config.py)

## 6. Reihenfolge der nächsten Freigaben

1. Daten-/Zustandsvertrag und komplette Aufrufwege aufnehmen, konkrete Migrations-
   grenzen bestimmen; keine vorschnelle Zusammenlegung vorhandener Datenbanken.
2. Sicherheitsgegenproben für Verlauf, Wiederanlauf, Lese-Datenflüsse und Freigaben
   definieren; gesperrte Wirkungen mit absichtlich falschem Modell prüfen.
3. Eine schmale Kette aus Quelle/Abdeckung, begrenzter Interpretation, Vorgang,
   Chatkorrektur und aktualisierter Ansicht implementieren und messen.
4. Optional OpenViking auf denselben Aufgaben vergleichen. Eine Adoption des
   Frameworks ist keine Voraussetzung für Schritte 1–3.

Nutzer-/Personenprofile, aktuelles Lagebild und Timeline bleiben Produktziele.
Der technische Vertrag reduziert diese Vision nicht auf ein reines Kontaktarchiv;
er legt Bedingungen fest, unter denen wir die jeweiligen Fähigkeiten freigeben.
