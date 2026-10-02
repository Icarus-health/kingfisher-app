# Memory Quality Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Execute within the user's authorized scope; do not start downloads, private-data exports or unattended runs.

**Goal:** Fehler beim Gedächtnisabruf von Fehlern bei der Antwortinterpretation im bestehenden Agentenpfad reproduzierbar unterscheiden.

**Architecture:** Ein ausschließlich synthetischer Evaluationsrunner verwendet die bestehenden Stores, `Agent.send()` und den vorhandenen `Provider.complete()`-Vertrag. Ein delegierender Provider zeichnet die tatsächlich übergebenen Nachrichten auf; Rubriken bewerten Abruf und Antwort getrennt. Keine Änderungen an Produktionsprompts, Datenbanken, Routing oder Freigaben in diesem Paket.

**Tech Stack:** Python 3.12 lokal, pytest, bestehende SQLite-Stores, bestehender OpenAI-kompatibler Ollama-Adapter; keine neue Bibliothek.

**Spec:** [MEMORY-FIRST-ROADMAP.md](../../release/MEMORY-FIRST-ROADMAP.md), Paket M0. M1–M5 sind nachgelagerte Pakete und werden hier nicht als implementiert behandelt. Bestehender Memory-Core-Vertrag und dessen Reviewpräzisierungen gelten weiterhin.

## Global Constraints

- Keine neue Graphdatenbank, kein zweiter Personenbestand, keine komplette Neuentwicklung aller Stores ohne nachgewiesene Lücke.
- Keine neuen Downloads oder Trainingsläufe im heutigen Planungspaket.
- Jede Wiederholung und jeder Fehlschlag bleibt sichtbar; kein Auswählen des besten Versuchs.
- Null beobachtete Fehler sind kein Beweis für eine Fehlerwahrscheinlichkeit von null.
- Cloud bleibt optional und zweckgebunden; kein stiller Versand als Ausweg aus einem lokalen Qualitätsproblem.
- Dieses Umsetzungspaket verwendet ausschließlich synthetische Daten und lokale Loopback-Endpunkte; keine produktiven Konto-, Profil- oder Konfigurationsdateien lesen.
- Der deaktivierte `experimental_calendar_recall`-Pfad bleibt deaktiviert. Nicht zum Bestehen der Baseline einschalten.

---

## Fortschritt am 13. September 2026

Fortsetzung 14. September: Task 1 (18 Entwicklungsfälle), Task 2 (Recorder),
Task 3 (isolierter Fixturebuilder mit Wiederöffnung) und Task 4 (begrenzter CLI-Runner)
sind implementiert. [Methode und Grenzen](../../evaluations/memory-quality/BASELINE.md).
Die fachliche Auswertung echter Modellantworten steht noch aus; die Implementierung
allein erfüllt M0 nicht vollständig. Docker-/Backup- und allgemeine
Verlaufswiederherstellung gehören weiterhin zu den nachgelagerten Paketen.
Die folgende Checkliste beschreibt den ursprünglichen Auftrag; abschließende
Verifikations- und Reviewnachweise stehen in der Baseline.

## Start und Geltungsbereich

Basis dieser Planung: `4a42b22927bd2382b7f74bc2a5ac2fe5d793fc18` plus der Planungs-PR.
Vor Beginn `git status --short`, `git fetch origin`, aktuellen Head und Arbeitskopie
prüfen. Neuer sauberer Branch vom integrierten Stand; fremde Änderungen erhalten.

Zuerst Dokumente lesen:
- `docs/evaluations/model-selection/cos-diagnostic-2026-09-13/README.md`
- `docs/evaluations/model-selection/calendar-recall-experiment/README.md`
- `docs/architecture/memory-core-review-2026-09-12.md`
- `sidecar/tests/test_context.py` und `sidecar/tests/test_calendar_answers.py`

Der neue Runner heißt `scripts/probe_memory_pipeline.py`. Er bleibt ein Prüfwerkzeug,
kein Werkzeug, das Kingfisher eigenständig ausführen kann. Bestehenden nativen
Modellrunner nicht umdeuten: dessen Ergebnisse bleiben ein anderer Versuchsaufbau.

## Dateiverantwortung

| Datei | Verantwortung |
|---|---|
| `scripts/memory_probe_support.py` (neu) | Trace-Provider, Fall-/Ergebnisvalidierung, Zeiten und technische Bewertung |
| `scripts/memory_probe_fixtures.py` (neu) | Frische synthetische Stores, genaue Beleg-IDs, Aktionen vor/nach einer Runde |
| `scripts/probe_memory_pipeline.py` (neu) | CLI, lokale Modellprüfung, einzelne Fälle, exklusive Ergebnisdatei |
| `scripts/test_memory_probe_support.py` (neu) | Recorder-/Bewertungs-/Fehlervertrags-Tests ohne Netzwerk |
| `scripts/test_probe_memory_pipeline.py` (neu) | Fixtures und Runner gegen Fakeprovider; Isolation und Erhaltung alter Versuche |
| `docs/evaluations/memory-quality/development-cases-v1.json` (neu) | Entwicklungsfälle, erwartete Identitäten/Belege, Rubrik; keine Holdout-Daten |
| `docs/evaluations/memory-quality/BASELINE.md` (neu) | Methode, Einschränkungen, erste Rohresultatverweise und Fehlerentscheidungen |

`agent.py`, `context.py`, `providers.py`, `claims.py`, `episodes.py` und `server.py`
werden in M0 gelesen, nicht funktional geändert. Ein im Test gefundener Produktfehler
bekommt einen separaten Fix nach der unveränderten Baseline.

## Task 1: Reproduzierbare Fälle und Bewertung festlegen

**Files:** Create `development-cases-v1.json`, `memory_probe_support.py`, `test_memory_probe_support.py`.

**Interfaces:** `validate_case(case: dict) -> None` wirft bei ungültigem Fall `ValueError`.
`score_retrieval(expected: set[str], forbidden: set[str], actual: set[str]) -> dict`
liefert Mengen als sortierte Listen und Zähler, kein semantisches Gesamturteil.

Fallformat (Entwicklungsbeispiel; Quelle und Aussage getrennt):

```json
{
  "id": "identity-separation-01",
  "scenario_id": "two-alex-01",
  "split": "development",
  "fixture_mode": "prepared_memory",
  "clock_utc": "2026-09-13T07:00:00Z",
  "question": "Welche Adresse hat Alex Winter?",
  "sources": [
    {"id": "S1", "text": "Alex Winter im Einkauf: alex@firma-a.invalid", "source_type": "email"},
    {"id": "S2", "text": "Alex Winter an der Schule: winter@schule-b.invalid", "source_type": "email"}
  ],
  "entities": [
    {"id": "person:alex-a", "kind": "person", "label": "Alex Winter"},
    {"id": "person:alex-b", "kind": "person", "label": "Alex Winter"}
  ],
  "assertions": [
    {"id": "C1", "subject_ref": "person:alex-a", "predicate": "email", "value": "alex@firma-a.invalid", "source_id": "S1"},
    {"id": "C2", "subject_ref": "person:alex-b", "predicate": "email", "value": "winter@schule-b.invalid", "source_id": "S2"}
  ],
  "expected_source_ids": ["S1", "S2"],
  "forbidden_source_ids": [],
  "required": ["Konkrete Rückfrage, welche der beiden Personen gemeint ist"],
  "forbidden": ["Identitäten zusammenführen", "Adresse willkürlich auswählen"],
  "severity": "critical_identity"
}
```

- [ ] Test schreiben: doppelte Source-IDs, unbekannte erwartete IDs und Überschneidung
  von expected/forbidden müssen `ValueError` ergeben. Ebenso unbekannte subject_ref-/
  source_id-Verweise in assertions sowie doppelte Entity-/Assertion-IDs. `split=holdout` im Entwicklungs-
  runner ebenfalls ablehnen. Fixturedefinitionen akzeptieren nur Inline-Text und definierte Operationen, kein
  Python/eval. Ein Pfad innerhalb eines Quellentexts wird niemals als Datei geöffnet.
- [ ] Test für Bewertung schreiben und rot laufen lassen:

```python
def test_missing_context_cannot_be_reported_as_model_failure():
    from memory_probe_support import score_retrieval
    result = score_retrieval({'S1', 'S2'}, {'S3'}, {'S1'})
    assert result['missing'] == ['S2']
    assert result['forbidden_seen'] == []
    assert result['expected_count'] == 2
    assert result['found_count'] == 1
```

- [ ] Mengenbewertung implementieren: missing=`expected-actual`, forbidden_seen=
  `forbidden & actual`, unexpected=`actual-expected-forbidden`; sortiert ausgeben.
  Kein relevanter Sollbeleg bedeutet Recall `None`, nicht pauschal 100 %.
- [ ] Die sechs Themen des bisherigen `CASES`-Bestands in getrennte Quellen überführen:
  mehrdeutiges Mainz, neue Absage, gleiche Namen, Gedankenexperiment, Anweisung im
  Quellentext, veralteter Kalender. Jeder Fall bekommt zwei Varianten (Paraphrase,
  entscheidende Folgefrage/Zustandsänderung): 18 Entwicklungsfälle, nicht 18 unabhängige
  Szenarien. Varianten bleiben über scenario_id zusammengehalten.
- [ ] Für Kalenderfälle feste Zeit/Timezone in Snapshot und Frage aufeinander abstimmen;
  relative Wörter wie „heute“ nicht versehentlich gegen den realen nächsten Tag bewerten.
  Laufuhr getrennt von fachlicher Uhr protokollieren. Kein globaler Uhr-Patch in Produktion.
- [ ] Tests ausführen: `.venv/bin/python -m pytest scripts/test_memory_probe_support.py -q`.
  Anschließend Dateien prüfen und committen. Die 300/90/40-Sammlung ist hiermit noch nicht erstellt.

## Task 2: Tatsächlichen Providerinput und Fehler erfassen

**Files:** Modify `memory_probe_support.py`, `test_memory_probe_support.py`.

**Interfaces:** `RecordingProvider(delegate)` erfüllt `Provider` mit `name`, `model`,
`is_local` und `complete(messages, tools) -> Reply`. `calls` ist eine Liste von Dicts.
Jeder Eintrag besitzt request, started_monotonic, elapsed_seconds, status und reply
oder error_type. Nutzlasten sind tiefe Kopien; Keys/HTTP-Header gehören nicht ins Trace.

- [ ] Recorder-Test zuerst schreiben:

```python
from icarus_memory.providers import Reply

class MutatingProvider:
    name = 'synthetic'
    model = 'stub'
    is_local = True
    def complete(self, messages, tools):
        messages[0]['content'] = 'changed by delegate'
        return Reply(text='Testantwort', model=self.model)

def test_records_payload_before_delegate_mutation():
    from memory_probe_support import RecordingProvider
    provider = RecordingProvider(MutatingProvider())
    provider.complete([{'role': 'user', 'content': 'original'}], [])
    assert provider.calls[0]['request']['messages'][0]['content'] == 'original'
    assert provider.calls[0]['status'] == 'returned'
```

- [ ] Rot prüfen; dann delegierenden Wrapper implementieren. `copy.deepcopy()` vor
  Delegation; `time.monotonic()` vor/nach Aufruf; Ausnahme mit Typ erfassen und erneut
  auslösen. Keine rohen HTTP-Ausnahmen mit potentiellen Secrets exportieren.
- [ ] Tests ergänzen: Providerfehler bleibt erhalten, mehr als eine Runde hat mehrere
  Traceeinträge, `is_local` wird nicht fälschlich immer True, Werkzeuge werden nur
  beschrieben und vom Wrapper nie ausgeführt. Fakeprovider mit Fehler verwenden.
- [ ] Leere Antwort, ToolCall und Abbruch als technische Zustände getrennt behandeln.
  Nicht vorhandene Token-/Finish-Reason-Metadaten im vorhandenen `Reply` bleiben `null`
  mit Grund, nicht geschätzt. Gesamtdauer und Summe der Providerzeiten erfassen; die
  Differenz ist **Nicht-Provider-Zeit**, kein isolierter Beweis für reine Suchzeit.
- [ ] Tests erneut ausführen und committen. Keine Veränderung von Modellparametern
  oder Produktionsprompts als Teil dieses Schritts.

## Task 3: Bestehenden Agenten mit isolierten Stores prüfen

**Files:** Create `memory_probe_fixtures.py`; modify `test_probe_memory_pipeline.py` (neu).

**Interfaces:** `build_fixture(case: dict, root: Path, provider: Provider) -> ProbeFixture`.
`ProbeFixture` ist eine Dataclass mit `agent: Agent`, `source_ids: dict[str,str]`
(physische Episoden-ID → Fall-ID), `claim_ids: dict[str,str]` (Claim-ID → Fall-ID)
und `close() -> None`. Alle Datenpfade liegen unter root. Keine App-Konfiguration laden.

- [ ] Test schreiben, der zwei Fixtures mit separaten `tmp_path`-Unterordnern aufbaut
  und sicherstellt, dass weder Quellen noch Audit-Zeilen zwischen ihnen auftauchen.
- [ ] Vorhandenen Aufbau aus `sidecar/tests/test_context.py::_knowledge_agent`
  nachvollziehen und als eigenen Fixturehelper umsetzen: `EpisodeStore`, `ProposalStore`,
  `ClaimStore`, `KnowledgeService`, `SelfModelStore(MemoryBackend())`, `AuditLog`, `Policy`.
  `Agent(..., tools={}, provider=provider, knowledge=claims, episodes=episodes,
  max_rounds=1)` verwenden. Entitäten vorher mit
  `claims.entities.create(kind, label, explicit_id=id)` aus dem Fall anlegen; der
  Rückgabewert ist ein Dict. Namen nie als eindeutigen Entity-Schlüssel verwenden.
  `assertions` explizit über KnowledgeService und zugehörige Episodenbelege anlegen;
  Aussage/Zitat des Beispiels ist der volle Text der genannten Quelle. Andere Fälle
  geben nötigenfalls eigene genaue Aussage/Zitatfelder an, die gegen diese Quelle
  validiert werden. Keine automatische Extraktion als unsichtbarer Fixtureschritt.
  Keine produktiven Volume-/HOME-Pfade öffnen.
- [ ] Quellen als separate Episoden mit synthetischer Provenance anlegen. Der Modus
  `prepared_memory` nutzt ausdrücklich vorgegebene bestätigte Testaussagen und deren
  echte Evidenzstellen. Keine externe Mail als angeblich ausdrückliche Nutzeraussage
  umetikettieren. Vorbereiteter Zustand prüft Abruf/Antwort, nicht Extraktionsqualität.
- [ ] Nach `agent.send(question)` die tatsächlich gelieferten Claim-IDs und über deren
  Evidenzen die Source-IDs auflösen; mit der Provider-Nutzlast abgleichen. Keine bloße
  Wortsuche nach einem Namen als Beleg für korrekten Quellabruf zählen. Zusätzliche
  systematische und situative Daten getrennt markieren.
- [ ] Direkte Kalenderantworten (`answer_mode=calendar_data`) ausdrücklich als
  modellfreien Pfad erfassen. Null Provideraufrufe sind dort kein Transportfehler und
  kein Beweis für Modellkompetenz. Kalenderfälle verwenden den vorhandenen
  `calendar_context`-Callback und die Struktur aus `test_calendar_answers.py`.
- [ ] Zustandstest: Quelle → bestätigte Aussage → Abruf → Quellenentzug → erneuter
  Abruf; kein Inhalt aus entzogener Quelle im Providerinput. Neustarttest mit denselben
  SQLite-Dateien, jedoch neuer Agent-/Storeinstanz. Nicht nur dieselbe Pythoninstanz
  erneut aufrufen. Erwartete ID-Listen pro Phase getrennt auswerten.
- [ ] Referenzkontext-Diagnose zusätzlich anbieten: exakt die vorab definierten erlaubten
  Quellen im Datenblock, gleicher Provider und gleiche Frage. `mode=reference_context`
  im Ergebnis; nicht als Agenten-/Rechteprüfung werten. Attack-Quellen nur synthetisch,
  keine Tools und kein Zugriff auf persönliche Dateien. Zwei Modi nicht vermischen.
- [ ] Fakeprovider-Tests beider Modi ausführen. Erst nach bestandener Isolation committen.

## Task 4: Begrenzter Live-Runner und auswertbarer Bericht

**Files:** Create `probe_memory_pipeline.py`; modify `test_probe_memory_pipeline.py`;
create `docs/evaluations/memory-quality/BASELINE.md` nach tatsächlichem Lauf.

**CLI-Vertrag:**

```sh
PYTHONPATH=sidecar .venv/bin/python scripts/probe_memory_pipeline.py \
  --model qwen2.5:14b --case identity-separation-01 --repeat 1 \
  --mode agent --output /tmp/kingfisher-memory-baseline-attempt-01.json
```

`--model` muss installiert sein; nur `http://127.0.0.1:11434/v1` zulassen.
`--mode` ist `agent` oder `reference_context`; Standard `agent`. `--repeat` 1–3 für
fachliche Entwicklungsdiagnosen. Kein beliebiger URL-/Shell-/Konfigurationsparameter.

- [ ] CLI-Tests schreiben: vorhandene Ausgabedatei nicht überschreiben, fehlendes Modell
  ohne Pullversuch ablehnen, unbekannter Fall ohne Modellaufruf, Wiederholung außerhalb
  1–3 ablehnen. Tests laufen mit injiziertem Fakeclient, nicht gegen Ollama.
- [ ] `main(argv=None)` implementieren: Argumente validieren; Ergebnisdatei exklusiv
  (`open('x')`, danach chmod 0600); temporäre Stores je Versuch; endlich begrenzte
  HTTP-Zeiten und keine automatischen inhaltlichen Retries. Der bestehende Adapter
  bleibt für Request-/Response-Abbildung maßgeblich. Für den isolierten Diagnoseprozess
  seinen HTTP-Client mit `trust_env=False`, `follow_redirects=False` und explizitem
  Timeout ausstatten; nicht allein auf NO_PROXY vertrauen. Ein Test mit gesetztem
  HTTP_PROXY muss belegen, dass keine Anfrage dort landet. Diese Transportbegrenzung
  als Unterschied zum normalen App-Betrieb dokumentieren; keinen globalen Proxy- oder
  Providerwechsel in der laufenden App vornehmen. Bei Abbruch bisherigen
  Versuch als incomplete erhalten. Kein Weiterlaufen als Hintergrunddienst.
- [ ] Modellmetadaten vor/nach Lauf prüfen: Name, Gewichts-Digest, Ollama-Version,
  Konfigurationshash, Git-Commit, Fallhash, Provider/Modus und Zeitpunkte. Keine rohe
  Modellkonfiguration veröffentlichen; benutzerdefinierte Systemprompts könnten privat
  sein. Unbekannte effektiv gesetzte Laufzeitparameter als unbekannt dokumentieren.
- [ ] Unterstützungs- und Runner-Tests ausführen:

```sh
PYTHONPATH=sidecar .venv/bin/python -m pytest \
  scripts/test_memory_probe_support.py scripts/test_probe_memory_pipeline.py \
  scripts/test_evaluate_cos_models.py sidecar/tests/test_context.py \
  sidecar/tests/test_calendar_answers.py -q
```

- [ ] Erst einen lokalen Fall ausführen. Nach Kontrolle von Isolation, Ausgabe und
  Laufzeit die 18 Entwicklungsfälle je Modus höchstens einmal starten. Das sind
  höchstens 36 Versuche; Provideranzahl pro Versuch ausweisen. Kein Modellwechsel
  während paralleler Alltagsnutzung erzwingen. Zeitbudget für die Sitzung vorher prüfen.
- [ ] Im Bericht jede Antwort anhand der Rubrik bewerten: `pass`, `fail` oder
  `review_required`; Fehlerstufe und Schweregrad, erwartete/erhaltene Source-IDs,
  Zeiten, technische Ausfälle und hilfreiche Rückfrage angeben. Fehlender Kontext
  kann mit zusätzlichem Modellfehler koexistieren, deshalb mehrere Labels zulassen.
- [ ] Mindestens zwei bewusst falsche synthetische Antworten zur Kontrolle der Rubrik
  bewerten: vermischte Alex-Adresse, unbelegtes „Mail versendet“. Keine Quote ohne Nenner.
- [ ] Kein P95-Versprechen aus 18 Fällen. Warm-/Kaltzustand bei diesem ersten Lauf
  als beobachtet oder unbekannt kennzeichnen. Die 100er-Lastmessung bleibt M3.
- [ ] Erst nach Prüfung ausschließlich synthetische Berichte ins Repository übernehmen.
  Bericht nennt den nächsten kleinsten reproduzierten Fix; kein automatisches Umschalten
  auf ein angeblich bestes Modell. Code-/Dokureview, passende CI, PR und Integration.

## Selbstreview dieses Plans

M0-Abdeckung: Task 1 definiert Fälle/Rubriken, Task 2 tatsächliche Nutzlast/Zeiten,
Task 3 isolierten Agentenpfad und Fehlerlokalisierung, Task 4 reproduzierbaren Versuch
und nachvollziehbaren Bericht. M1–M5 und die vollständige 300/90/40-Qualifikation sind
bewusst nicht als Folge dieses kleinen Runners erfüllt. Der Plan liefert noch keine
Implementierung, bestandenen Tests oder Messergebnisse.

Wichtigster Schutz gegen Selbsttäuschung: vorbereitete Claims, direkter Referenzkontext,
modellfreie Kalenderantworten und echter Import→Interpretation→Antwort werden als
unterschiedliche Versuchspfade bezeichnet. Ein guter Einzelpfad qualifiziert nicht
alle anderen. Erst mit den Ergebnissen wird die nächste Änderung ausgewählt.
