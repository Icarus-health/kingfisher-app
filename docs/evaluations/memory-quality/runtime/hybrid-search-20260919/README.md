# Lokale hybride Gedächtnissuche: begrenzter Entwicklungsvergleich

Datum: 19. September 2026. Implementierung `7d9270017196de1f430848c46b6377428eb3d42d`,
auf M2c `e7f2d72`. Opt-in am Agenten; die private App und ihr Standardabruf sind
unverändert. Keine Produkt-, Modellantwort- oder allgemeine Suchqualifikation.

## Übernahme aus WeKnora

Kleine Python-Adaption der Reciprocal Rank Fusion mit k=60: Stichwort- und
Bedeutungstreffer stimmen über Rangplätze ab, statt inkompatible Rohscores zu
addieren. Herkunft, fixer Quellcommit und MIT-Hinweis stehen in
[weknora.md](../../../../third-party/weknora.md).
Kein weiterer Dienst, keine neue Bibliothek, kein Modelldownload.

Die zusätzliche Suche verwendet einen ausdrücklich vorbereiteten, flüchtigen
Snapshot von höchstens 128 Aussagen. Vor dem Embedding müssen ihre Originalbelege
gültig sein. Im Snapshot liegen Vektoren, IDs und Signaturen statt einer zweiten
Wissensablage. Vor Nutzung werden Aussageprojektion und Generationen sämtlicher
Belege erneut abgeglichen; der Agent führt danach seine kanonische Quellen- und
Zeitprüfung aus. Ähnlichkeit verleiht keine Speicher- oder Aktionsrechte.

Ein anderer Modellstand, Modellfehler, unbrauchbare Vektoren oder entfallene
Bedeutungstreffer lassen den bisherigen lexikalischen Abruf verfügbar. Externe
Chatmodelle erhalten weder diese Wissensschicht noch lösen sie Embeddings aus.
Abbrüche durch KeyboardInterrupt bleiben Abbrüche. Der Prompt benennt den begrenzten
Suchumfang und stellt klar, dass fehlende Treffer keine Abwesenheit belegen.

## Messung

Zehn vor dem ersten Modellaufruf festgelegte deutsche Entwicklungsfälle, jeweils
mit neun synthetischen Quellen; sieben positive Fälle und drei Negativkontrollen.
Jedes Paar nutzt denselben vorbereiteten SQLite-Bestand und dieselben Quell-IDs,
aber einen frischen Agenten ohne übernommenen Gesprächsverlauf. Die Fälle wurden
nach Betrachtung der Ergebnisse nicht verändert.

Reales lokales Embedding-Modell: `bge-m3:latest`, Digest
`7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab`.
Transport ausschließlich `127.0.0.1:11434`, ohne Umgebungsproxy, Redirects,
Modell-Pull oder private App-Konfiguration. `truncate=false` verhindert stilles
Kürzen von Modellinputs. Gewichte vor/nach Aufrufen kontrolliert.

Der produktive Agent liefert den Kontext an einen aufzeichnenden Testanbieter;
der vorhandene unabhängige Recorder gleicht vollständige Projektionen gegen
Originalquellen ab. **Es wird keine Chatantwort generiert oder semantisch bewertet.**

| Fall | Exakter Soll-Kontext: Stichwörter | Exakter Soll-Kontext: Hybrid |
|---|---|---|
| Finanzierung anders formuliert | Nein, kein Treffer | Ja |
| Verkehrsmittel anders formuliert | Nein, kein Treffer | Ja |
| Personalplanung anders formuliert | Nein, kein Treffer | Ja |
| Reparaturfrist anders formuliert | Nein, kein Treffer | Ja |
| Gleichnamige, ungeklärter Kontext | Ja, beide Datensätze | Ja, beide Datensätze |
| Einkauf ausdrücklich ausgewählt | Nein, zusätzliche Schuladresse | Nein, zusätzliche Schuladresse |
| Versandstatus | Nein, zwei zusätzliche Quellen | Nein, zwei zusätzliche Quellen |
| Fahrradfarbe unbekannt | Ja, leer | Ja, leer |
| Finanzierung widerrufen | Ja, leer | Ja, leer |
| Finanzierung abgelaufen | Ja, leer | Ja, leer |

**4/10 → 8/10 exakt passende Quellmengen** in dieser kleinen vorbereiteten Sammlung.
Alle acht erwarteten Quellenzuordnungen in den sieben positiven Fällen werden mit
Hybrid geliefert; Stichwörter liefern vier davon. Beide Varianten haben weiterhin
Zusatztreffer in zwei Fällen. In beiden Läufen und Varianten: keine verbotenen
Quellen und keine Abweichungen zwischen ausgewiesenem und tatsächlich geliefertem
Kontext. Das beweist weder eine korrekte Personenauflösung noch eine korrekte Antwort
auf „abgeschickt?“; es misst ausschließlich die übergebene Quellenmenge.

Rohdaten einschließlich tatsächlicher Provider-Nutzlasten:

- [Erster vollständiger Lauf, 157ed82](hybrid-development-157ed82.json)
- [Wiederholung nach Reviewkorrekturen, 7d92700](hybrid-development-7d92700.json)

Beide Läufe enthalten alle 20 geplanten Vergleichsarme und liefern dieselben oben
genannten Quellmengen. Die Wiederholung prüft die korrigierte Implementierung;
es handelt sich nicht um 20 unabhängige Fälle. Gemeinsamer Datensatzhash:
`889ac4ae05fb5f62353358c56e0cc50c64b8447a20c6d153e294ec08c8f542cf`.
Einzelzeiten stehen in den Rohdaten. Der erste Lauf benötigte rund 24–40 ms je
Hybridabruf plus einmalige Vorbereitung pro Fixture (erster Modellaufruf 2,36 s,
folgende etwa 0,14–0,22 s). Das sind kleine lokale Diagnosen ohne Chatgenerierung,
keine Alltag-, Last- oder P95-Messung.

## Prüfung und Grenzen

Unabhängiges Code-Review von `157ed82` fand zwei P2-Probleme: Adapter-Timeouts
konnten den lexikalischen Rückfall unterbrechen; der Runner verlangte ein nicht
überall vorhandenes Ollama-Metadatenfeld. Beide wurden mit zunächst fehlschlagenden
Regressionstests behoben. Zusätzlich ist die Bedeutungssuche bei ausdrücklich
aktiviertem Hybridabruf für kurze Fragen wie „KI?“ erreichbar. Erneute unabhängige
Prüfung von `7d92700`: keine wesentliche Regression, 29 fokussierte Tests bestanden.

Vollständige lokale Python-3.12-Prüfung nach den Korrekturen: **1.786 Tests bestanden**
(Sidecar sowie die bisherigen drei und der neue Diagnose-Testblock), zwei bestehende
Deprecation-Warnungen. Die GitHub-Matrix prüft zusätzlich Python 3.10, UI und Container;
deren Status ist im zugehörigen PR separat sichtbar.

Das Paket ist bewusst keine allgemeine Hintergrundindexierung. Der Snapshot muss
explizit erstellt und nach relevanten Änderungen neu aufgebaut werden; ein alter
Snapshot kann keine erneute Quellenzulassung selbst erteilen. Der Adapter ist für
die Diagnose mit endlichen HTTP-Zeitgrenzen ausgelegt, nicht für eine zugesagte
Antwortlatenz im Produkt. Ein Docker-/Browserlauf der neuen zuschaltbaren Suche
und die breite fachliche Abnahme stehen aus. Der bekannte Schutz gegen die
Wiederbelebung alter Quellenfreigaben durch Backup-Restore bleibt offen.

Nächster fachlicher Schritt: präzise Kontextwahl bei gleichnamigen Personen und
ähnlichen Vorgängen prüfen; anschließend größeren, unabhängig vorbereiteten
deutschen Vergleich einschließlich tatsächlich generierter Antworten durchführen.
Keine Anpassung der Relevanzschwelle anhand dieser zehn Fälle und keine automatische
Aktivierung in der privaten App allein aufgrund dieses Ergebnisses.

Reproduktion auf einem passenden lokalen Entwicklungsrechner:

```sh
PYTHONPATH=sidecar .venv/bin/python scripts/probe_hybrid_memory.py --output /tmp/new-hybrid-result.json
```

Die Ausgabedatei muss neu sein. Der Runner beendet weitere Fallstarts nach fünf
Minuten; endliche laufende HTTP-Anfragen können anschließend noch auslaufen.
Er schreibt Zwischenergebnisse und unterscheidet unvollständige/fehlgeschlagene
Läufe von abgeschlossenen. Ein technischer Abschluss ist kein fachlicher Pass.
