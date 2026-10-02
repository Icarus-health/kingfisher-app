# Gedächtnisstruktur: vorhandener Code und nächste Verbindung

Stand: 13. September 2026, nach PR #40. Dies ist eine Bestandsaufnahme und
Präzisierung der bestehenden Memory-first-Roadmap, keine neue parallele Architektur.

## Die vorhandenen Ebenen

| Ebene | Bestehende Implementierung | Bedeutung und Grenze |
|---|---|---|
| Originalbelege | `episodes.py` / EpisodeStore | Quelle, Text, Herkunft, Digest und Quellenzustand. Ein Archiv ist kein Widerruf. |
| Identitäten | `entities.py` / EntityRegistry | Stabile IDs und Quellenzuordnungen; gleiche Namen sind keine gleiche Person. |
| Belegte Aussagen und Beziehungen | `claims.py` / ClaimStore, KnowledgeService | subject_ref, target_ref, scope_ref, Evidenz, Gültigkeitsintervall, Vorgänger und Abhängigkeiten. Ein vorbereiteter Claim ist kein Nachweis korrekter automatischer Extraktion. |
| Verlauf | `memory_history.py` | Fachliche Gültigkeit und damaliger Kenntnisstand getrennt; paginierter Abruf. Noch keine vollständige Lebenszeitleiste. |
| Nutzerkontext | SelfModelStore und `context.py` | Regeln, Präferenzen und Identität mit begrenzter Kontextauswahl. Kein vollständig automatisch gepflegtes Lebensprofil. |
| Personenüberblick | `person_digest_context.py`, `person_digests.py` | Begrenzte Quellen, Zitate und Fingerprint; verwerfbarer Cache, keine neue Wissenswahrheit. |
| Gesprächsabruf | `Agent._knowledge_context_items`, `knowledge_context.py` | Belegketten werden vor Übergabe geprüft; höchstens fünf Wissensaussagen nach Wortüberschneidung aus bis zu 5.000 Kandidaten. Kein allgemeiner hierarchischer oder semantischer Abruf. |

Dateinamen beziehen sich auf `sidecar/icarus_memory/`. Die Kontaktansicht ist eine
Projektion dieser Daten, keine zweite Kontakt-Datenbank.

## Was für das gewünschte Schichtengedächtnis noch fehlt

Die entscheidende Lücke liegt zwischen dem Personenüberblick und dem Gesprächsabruf:
Es existiert noch kein durchgängiger Weg, der zuerst passende Organisationen,
Projekte oder Personen findet, ihre erlaubten aktuellen Übersichten prüft und bei
Bedarf gezielt zu Aussagen und Originalbelegen hinabsteigt. Mehr Kontext pauschal
ins Modell zu laden beseitigt diese Lücke nicht.

Die vorhandene Graphstruktur muss dafür mehrere belegte Beziehungen pro Person
tragen dürfen. Eine Person gehört nicht exklusiv in einen Ordner unter einer
Organisation. Frühere Arbeitgeber, private Bekanntschaften und aktuelle Projekte
brauchen jeweils ihren eigenen Beziehungskontext und Zeitraum. Eine thematische
Gruppierung beweist noch keine organisatorische Zugehörigkeit.

Eine Verdichtung soll künftig eine **ersetzbare Sicht** auf erlaubte Aussagen sein:
IDs der verwendeten Aussagen/Quellen, fachlicher Zeitraum, Kenntnisstand,
Abdeckungsgrenze und Aktualitätsnachweis bleiben nachvollziehbar. Bei Korrektur oder
Quellenentzug wird die Sicht unbrauchbar und gegebenenfalls neu aufgebaut. Das
Original bleibt erreichbar, soweit es noch gespeichert und für den Zweck erlaubt
ist. Details werden nicht durch immer neue Zusammenfassungen endgültig ersetzt.

## Konkrete Grenzen vor einer Erweiterung

1. Chat und Personenverdichtung besitzen derzeit unterschiedliche Belegprüfungen.
   Der Chat erlaubt archivierte Originale und prüft die ganze Kette einschließlich
   Gültigkeit, Digest und Zitat. Die Personenverdichtung lässt archivierte Quellen
   aus, führt historische Aussagen gesondert und hat eine eigene rekursive Prüfung.
   Diese Unterschiede müssen explizit getestet und nach Zweck getrennt werden;
   historische Ansichten dürfen nicht unbesehen einen Nur-aktuell-Filter übernehmen.
2. Die Wortauswahl und Kandidatenbegrenzung können relevante Beziehungen übersehen.
   Das ist ein Abrufproblem vor dem Modell. Ein größeres Modell allein löst es nicht.
3. Eine korrekt zitierte Zusammenfassung kann trotzdem falsch interpretiert sein.
   Schema, Zitatprüfung und fachliche Modellbewertung bleiben verschiedene Prüfungen.

## Neue Gegenprobe: Abhängigkeiten nach Wiederöffnung

`scripts/test_memory_probe_agent.py` ergänzt einen synthetischen Test über drei
abhängige Aussagen. Der letzte Satz passt zur Frage; sein ursprünglicher Beleg
enthält den Suchnamen nicht. Ablauf:

- Vor dem Schließen erreicht die letzte Aussage den tatsächlichen Providerinput.
- Nach Schließen und Wiederöffnen aller SQLite-Stores und neuem Agenten bleibt
  derselbe belegte Zusammenhang abrufbar (positive Kontrolle).
- Der ursprüngliche Beleg wird ausgeschlossen. Nach erneutem Schließen und
  Wiederöffnen erscheint die abhängige Aussage weder in der Auswahl noch im
  tatsächlichen Providerinput. Der gespeicherte Satz bleibt als Historie erhalten.

Verifikation: 89 fokussierte Tests aus `test_memory_probe_agent.py`,
`test_memory_probe_support.py`, `test_context.py` und `test_memory_history.py`
bestanden, zwei bekannte Dependency-Warnungen. Fakeprovider, keine Inferenz,
keine privaten Daten, keine Produktcodeänderung. Wiederöffnung der Stores ist
kein Docker-Neustart, kein Restore eines alten Backups und keine Prüfung geladener
Gesprächsverläufe oder aller Verdichtungscaches.

## Nächster Entwicklungsschritt

M0 weiter vervollständigen: Fälle für Beziehungsketten, gleichnamige Personen,
Zeiträume, Korrektur, Quellenentzug und fehlende Quellen anhand des tatsächlichen
Inputs prüfen. Danach M1: Beleg-/Aktualitätsregeln für Chat und Verdichtung mit
expliziten historischen Modi absichern. Erst auf dieser Grundlage M2: begrenzten
Abruf über Organisation/Projekt/Person und Originalbelege anschließen. Die
[Memory-first-Roadmap](../release/MEMORY-FIRST-ROADMAP.md) bleibt maßgeblich;
die alte Funktionsquote wird durch diesen Nachweis nicht erhöht.
