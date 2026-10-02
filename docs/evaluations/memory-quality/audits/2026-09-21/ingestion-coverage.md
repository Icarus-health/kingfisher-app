# Intake, Verdichtung und Abdeckung – 21.09.2026

Basis: isolierter Checkout `work/memory-audit-20260921`, Ausgangscommit `7e397db`. Die Prüfung begann lesend. Zwei eng begrenzte Fehler wurden danach auf ausdrücklichen Auftrag des koordinierenden Agents behoben. Keine Produktionsdaten, Netzabrufe, Modellaufrufe, Downloads, Commits oder Pushes. FakeProvider liefert ausschließlich synthetische Antworten; Speicher, HTTP-Routen und Zustandsübergänge sind echt.

## Ergebnis

Der Nachweis für vorbereitete Claims trägt bereits wesentlich weiter als der Nachweis für alltägliche Rohquellen. Ein importiertes Dokument ist gespeichert und direkt durchsuchbar, gelangt aber über die vorhandene allgemeine Verdichtung in das **Selbstmodell**. Die beleggebundene Gedächtnisantwort liest dagegen ausschließlich **bestätigte Entitätsclaims**. Die getestete Kette Upload → echte Verdichtung → Vorschlag → Nutzerannahme führt deshalb noch nicht zu einer Antwort auf den gespeicherten Fakt. Sichere Zustimmung und beleggebundene Antworten sind vorhanden; die zusammenhängende Aufnahme- und Abrufkette bleibt offen.

## Tatsächliche Datenwege

| Eingang | Gespeicherte Darstellung | Ableitung/Annahme | Abruf |
|---|---|---|---|
| Datei-Upload | `server.py:3467-3520`: PDF/DOCX-Vorschau; anschließend ausschließlich übermittelter UTF-8-Body als DOCUMENT-Episode, Herkunft `upload:filename` | `consolidation.py:325-379`: Modellvorschläge vom Typ ASSERTION; `453-478`: ausdrückliche Annahme erzeugt Selbstmodell-Assertion | Rohe Episode: `episodes.py:740-748`/`tools.py:620-641`; Selbstmodell im normalen Chat-Kontext. Kein Eintrag im ClaimStore allein durch diesen Weg |
| Freigegebener Ordner | `ingest.py:284-330,493-575`: Normalisierung, Digest, stabile Source-Key-Referenz, Importbericht; Quellenänderungen über `source_versions.py` | Derselbe Consolidator; unabhängige Aufgabenerkennung | Direkte Episodensuche und Dateiwerkzeug; keine allgemeine semantische Rohquellensuche im Evidence-Antwortpfad |
| Mail | `connectors/mail.py:163-180,319-332`: bevorzugt ein Plaintext-Part, sonst HTML→Text, höchstens 20.000 Zeichen; `mail_ingestion.py:12-33`: MESSAGE-Episode, Account/UID-Key, Kürzungstag | Consolidator plus unabhängiger `TaskDetector` mit 8.000-Zeichen-Segmenten und persistentem Fortschritt | Rohe Episode sowie explizite Mailwerkzeuge. Aufgaben werden Vorschläge, nicht automatisch Wissen |
| Gespräch | `server.py:2674-2693`: Nutzer-/Assistentenbeiträge im ConversationStore | Erst ein konkreter Gedächtnisvorschlag erzeugt über `2378-2419` eine Episode und KNOWLEDGE-Proposal; Annahme über `2801-2822` | Gesprächsverlauf separat; akzeptierte KNOWLEDGE-Proposal gelangt in ClaimStore |
| Fachlicher Wissenskandidat | `server.py:3830-3868`: strukturierte Felder + Episode/Zitat/Digest über KnowledgeService | Explizite Annahme erzeugt ClaimStore-Eintrag | `agent.py:318-341,467-479`: Evidence-Antwort nutzt ausschließlich diese bestätigten Claims |

Die Probe-Fixtures überspringen den schwierigen Rohtext→Aussage-Schritt: `scripts/memory_probe_fixtures.py:119-138` lesen fertige `case['assertions']`, rufen `service.propose(...)` und unmittelbar `service.accept(...)` auf. Das ist korrekt als Prepared-Memory-Test, kein Nachweis echter Intake-Extraktion.

## Behobene Fehler

### I-01 / P1: Fehlerhafte Verdichtungsantwort verbrauchte die Rohquelle

- Ausgangsfehler: `_parse_candidates` gab für unlesbares JSON oder falsches Schema `[]` zurück (Ausgangsfassung `consolidation.py:523-530`). `_propose_from_episodes` setzte die Episode anschließend immer auf `consolidated` (`360`). `episodes.pending` berücksichtigt ausschließlich `new` (`episodes.py:717-719`). Die Quelle verschwand damit ohne Fehler aus der erneuten Verarbeitung.
- Bezug: COV-01/COV-03, docs/08 Übergang Rohmaterial→Vorschlag.
- Änderung: `consolidation.py:516-552` unterscheidet ungültige Antwort, ungültige Vorschlagsliste, defekte Pflichtfelder und unbekannte Art vom gültigen Nullbefund. `ProviderError` nutzt den bestehenden Fehlerpfad (`334-338`); Quelle bleibt NEW, keine partiell erzeugten Vorschläge. Gültiges `[]` oder `{"vorschlaege":[]}` bleibt erfolgreich.
- Tests: `tests/test_verdichtung.py` prüft schlechten JSON-Output, fehlende/falsche Strukturen, falsche Pflichtfeldtypen, teilweise defekte Ergebnisliste, erfolgreichen nächsten Lauf und unveränderten echten Nullbefund. HTTP liefert weiterhin den bestehenden 200-Bericht mit `errors` und erhält die Quelle als `new`.
- Vorher: `consolidation-red.log`: 9 gezielt fehlschlagende Regressionen, 2 gültige Nullbefunde bestanden. Nachher: `consolidation-final.log`: **106 bestanden**, Verdichtung plus bestehende Episode-Support-Tests. Zwei Bibliotheks-Deprecation-Warnungen (Starlette/httpx, anyio).
- Grenze: Keine semantische Vollständigkeitsbehauptung. Zitate, die nicht im Quelltext vorkommen, bleiben wie bisher ausgeschlossen. Keine neue Jobarchitektur oder Chunking der allgemeinen Verdichtung.

### I-02 / P1: Gekürzte Mail wurde als abgeschlossene Quellenabdeckung ausgewiesen

- Ausgangsfehler: Mail-Limit bei 20.000 Zeichen (`connectors/mail.py:35,319-328`); `remember` persistiert `source:truncated` (`mail_ingestion.py:29`). `MemoryAnalysis` kann korrekt nur den gespeicherten Ausschnitt verarbeiten (`memory_analysis.py:134,155-160`). Der frühere Coverage-Code ignorierte das bekannte Kürzungsflag und zählte `completed`, sobald `offset==total` war.
- Synthetischer Ausgangsnachweis: Eine Zusage nach Zeichen 20.000 und ein Anlagentext fehlen in der Episode. Trotzdem: Job completed/20000 von 20000, Coverage completed=1, partial=0, kein sichtbarer Quellkürzungszähler. Siehe **before-only** `ingestion-reproduction-before-coverage-fix.json`.
- Bezug: COV-01, COV-02, COV-03, T-COV-01/T-COV-02.
- Änderung: `memory_routes.py:20-55` liest ausschließlich das Kürzungsflag zusätzlich zur bisherigen Metadatenauswahl. Fertig ausgewertete, gekürzte Quellen zählen nun als `partial`. Neues Feld `truncated_sources` zählt gekürzte verfügbare Quellen innerhalb der ausgewiesenen Stichprobe. `detail` nennt Zahl und Ursache. Jobzustände bleiben unverändert, wodurch kein endloses erneutes Lesen desselben Ausschnitts entsteht; pending/running/failed bleiben echte Arbeitszustände.
- Nachweis nach Änderung: `ingestion-reproduction-after.json`: identischer 20.000-Zeichen-Ausschnitt, Job weiterhin completed, **partial=1, completed=0, truncated_sources=1**, konkrete Meldung zur fehlenden Originalfortsetzung. `coverage.truncated` behält seine bisherige Bedeutung „Stichprobe gekappt“; es ist kein Quellkürzungsflag.
- Tests: `coverage-red.log` zeigt den Ausgangsfehler; `coverage-green.log`: **21 bestanden** (Memory-Routen, segmentierte Analyse und Mailaufnahme), darunter echte Aufnahme→TaskDetector→Coverage sowie ausbleibender erneuter Job nach einem abgeschlossenen Ausschnitt. Zwei gleiche Bibliotheks-Deprecations.
- UI-Prüfung: `app/kingfisher/src/MemoryStatus.tsx:54-56` zeigt Coverage-Zähler und serverseitige scope/detail. Es leitet keine separate Vollständigkeitsbehauptung aus Job=completed ab. `server.py:861` zeigt als Laufstatus weiter „N Quellen geprüft“; dies beschreibt den ausgeführten Lauf, nicht sichere semantische Vollständigkeit. Root ergänzt bei Bedarf den additiven TypeScript-Typ.
- Grenze: Der fehlende Mailrest oder eine Anlage wird dadurch nicht wiederhergestellt. Dafür ist ein eigener vollständiger Quellen-/Darstellungspfad notwendig.

## Offene Kernlücken, reproduziert oder unmittelbar aus dem Datenpfad belegt

### I-03 / P1: Intake und Evidence-Antwort sind noch getrennte Gedächtnispfade

- Stellen: `agent.py:318-341,467-479`; `consolidation.py:453-478`; `server.py:3510-3519`.
- Synthetischer realer Ablauf: Upload „Aurora Kontakt: Kira arbeitet bei Beispiel.“; direkte `episodes.search('Kira')` findet die Episode. `answer_memory('Wo arbeitet Kira?')` ist unknown, Modell wird nicht aufgerufen. Danach echter Consolidator erzeugt einen belegten Vorschlag, `accept` speichert die Assertion; Ergebnis Selbstmodell=1 und ClaimStore=0. Die gleiche Gedächtnisfrage bleibt unknown.
- Evidenz: `ingestion-reproduction-after.json`, Abschnitt `raw_to_memory_answer`. Keine vorbereitete Claim-Injektion in dieser Probe.
- Vertrag: RET-03 verlangt einen Ausweg aus fehlender Vorsortierung. Die direkte Originalsuche existiert als `/episodes?q=...` und Chatwerkzeug, ist aber kein ergänzender Abruf des aktuell beleggebundenen Fragepfads. Dass die Antwort ihre Unsicherheit nennt, ist korrekt; es löst den praktischen Erinnerungsfehler nicht.
- Nächster sinnvoller Kernschritt: Quelle als unbestätigten Beleg direkt finden und ihren fehlenden Analyse-/Bestätigungsstand kenntlich machen; keine automatische Erklärung als Wahrheit und keine bloße neue UI.

### I-04 / P2: Uploads gleicher Inhalte verlieren weitere Fundstellen und Projektzuordnungen

- Stellen: `server.py:3510-3519` ruft `episodes.record` ohne `source_key`; `episodes.py:472-489` entdoppelt dann nur Body-Digest. Datei/Projekt/Herkunft des zweiten Uploads tragen nicht zur Identität bei.
- Reproduktion: one.txt/Projekt One und two.txt/Projekt Two mit gleichem Body liefern dieselbe ID und den ersten Dateinamen/das erste Projekt; zweites Projekt hat keine Quelle. `ingestion-reproduction-after.json`, Abschnitt `upload_second_location`.
- Kein versehentlicher neuer Testfehler: `tests/test_document_upload.py:33-41` verlangt dieses Verhalten explizit. Es ist ein Altentwurf, der mit dem neueren SourceRecord-/SourceVersion-Vertrag und RET-01 kollidiert. Eine neue Identitätsregel für Wiederholung versus zweite Fundstelle muss entschieden und migriert werden; hier kein stiller Umbau.

### I-05 / P2: Originaldarstellungen und Parserlücken sind nicht vollständig im Kern erfasst

- Mail: `_body` wählt den ersten passenden Textpart und überspringt benannte Anlagen (`connectors/mail.py:163-180`). Roh-MIME und Anlagenmanifest sind nicht Bestandteil der Episode (`mail_ingestion.py:23-31`). Die synthetische Anlage fehlt vollständig; es gibt nur den allgemeinen Hinweis „fehlende Anlagen sind nicht enthalten“.
- DOCX: `document_text.py:19-22,37-61` liest ausschließlich `word/document.xml` und traversiert den Hauptteil. Header, Footer, Fuß-/Endnoten und sonstige Teile werden weder aufgenommen noch als fehlende Teile markiert. Die synthetische Reproduktion mit BODY_ONLY/HEADER_ONLY/FOOTNOTE_ONLY liefert nur BODY_ONLY.
- Upload: Preview liefert extrahierten Text; die endgültige Aufnahme erhält nur `filename` und `body` (`server.py:3475-3482,3492-3519`). Originalbytes, Parserrevision und Darstellungsmanifest sind nicht gespeichert. PDF meldet leere OCR-Seiten immerhin explizit im Body (`pdf_text_worker.py:24-43`); das ist eine hilfreiche Teilabsicherung.
- Ordner: Markdown-Frontmatter wird normalisiert, nur bekannte Metadaten werden übernommen (`ingest.py:309-329`). Der Dateipfad bleibt als Herkunft, ein unveränderlicher Original-Bytebestand samt Parsermapping aber nicht in der Episode.
- Bezug: SourceVersion/Representation sowie COV-01/COV-02. Für Wiederherstellung nach Modell-/Parserwechsel ist diese Grenze erheblich; die bestehenden Claims lassen sich aus gespeichertem Bestand neu projizieren, ungespeicherte Originalteile jedoch nicht rekonstruieren.

## Weitere Abdeckungsgrenzen

- Coverage ist ausdrücklich nur die Analyse auf Aufgabenvorschläge für aufgenommene MESSAGE-/DOCUMENT-Episoden (`memory_routes.py:18-24,52`). Es ist weder die Vollständigkeit angebundener Konten noch ein Fortschrittsnachweis fachlicher Wissensverdichtung. Es fehlen konkrete Parser-/Anlagenstände, synchronisierte Zeiträume, Claim-Extraktionsstände und Indexrevisionen pro Quellversion (COV-02).
- Episodensuche ist eine direkte SQL-LIKE-Suche im vollständigen gespeicherten Body, standardmäßig nach Neuigkeit limitiert (`episodes.py:740-748`). Das ist ein vorhandener Ausweg für genau bekannte Wörter, kein semantischer Fallback für die Gedächtnisantwort. Die Suche enthält keinen total/next_cursor/truncation-Nachweis; das Werkzeug listet nur ID/Titel/Datum (`tools.py:620-628`).
- Positiv: TaskDetector besitzt eigenständige persistente Analysefortschritte; 8.000-Zeichen-Segmente überlappen, das Ergebnislimit wird als Fehler statt Nullbefund behandelt (`memory_analysis.py:41-49,98-101`). Der bestehende Langquellen-Test `test_memory_analysis.py:58-78` injiziert jedoch schon die vollständige Episode und kann den vorgeschalteten 20.000-Zeichen-Mailverlust allein nicht finden.

## Wiederholbare Befehle

Arbeitsverzeichnis: `work/memory-audit-20260921`. Interpreter:
`python`.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts python -m pytest -q -p no:cacheprovider sidecar/tests/test_verdichtung.py sidecar/tests/test_episode_support.py --basetemp=docs/evaluations/memory-quality/audits/2026-09-21/pytest-consolidation-rerun
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts python -m pytest -q -p no:cacheprovider sidecar/tests/test_memory_routes.py sidecar/tests/test_memory_analysis.py sidecar/tests/test_mail_ingestion.py --basetemp=docs/evaluations/memory-quality/audits/2026-09-21/pytest-coverage-rerun
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts python docs/evaluations/memory-quality/audits/2026-09-21/reproduce-ingestion.py
```

`reproduce-ingestion.py` charakterisiert den aktuellen Stand und enthält keine Assertions, die den behobenen Coverage-Fehler verlangen. Ausgangsnachweise sind mit `before` beziehungsweise `red` gekennzeichnet. Die Suite wurde absichtlich nicht vollständig gestartet; Root übernimmt den abschließenden Gesamtlauf. `git diff --check` war sauber.
