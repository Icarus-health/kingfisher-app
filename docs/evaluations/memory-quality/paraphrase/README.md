# Umschriebene Fragen an den Arbeitsstand

Wie oft findet die heutige Quellensuche (`WorkingMemoryStore.search`) eine
Quelle, wenn die Frage andere Wörter benutzt als die Quelle? Das ist die
Entscheidungsgrundlage dafür, ob sich eine Bedeutungssuche für Quellenberichte
lohnt, bevor ein neuer Vektorindex gebaut wird.

Katalog: `catalog.json`. 16 erfundene Quellen; zu jeder eine direkte Frage mit
Wortüberschneidung und eine Umschreibung ohne gemeinsames Inhaltswort; dazu
vier unbeantwortbare Fragen. Vor der Messung eingefroren. Keine privaten Daten,
kein Chatmodell. Die Einordnung ist deterministisch (ein Abschnitt je Quelle),
damit nur die Suche gemessen wird.

## Ergebnis der heutigen Suche

Gemessen auf dem Suchcode von `main` (`985f6ec`); Datei
`lexikalisch-main-985f6ec.json`.

| Fragen | gefunden (unter den 12 Kandidaten) | auf Platz 1 |
| --- | --- | --- |
| direkt (16) | 16 | 15 |
| umschrieben (16) | 3 | 3 |
| unbeantwortbar (4) | 0 Fehlkandidaten | – |

Die drei gefundenen Umschreibungen treffen über zufällige Überschneidungen
(„achten“, „Tag“/„Freitag“, „Bericht“ im Titel). Ohne sie wäre es 0 von 16.
Direkte Fragen und das Nicht-Finden bei fehlender Quelle funktionieren.

**Befund:** Wer anders fragt, als die Quelle formuliert ist, bekommt heute in
der Regel „keine Information“, obwohl die Information vorliegt. Das ist der
größte verbleibende Qualitätsmangel des Gedächtnisses im Alltag.

## Auf dem Mac nachmessen

```
python scripts/probe_working_memory_paraphrase.py --embedder bge-m3 \
  --output docs/evaluations/memory-quality/paraphrase/bge-m3-$(git rev-parse --short HEAD).json
```

Nutzt nur das bereits installierte `bge-m3:latest` über den lokalen
Ollama-Dienst, lädt nichts herunter und überschreibt keine Datei. Es misst vier
Arme: lexikalisch, semantisch (Ähnlichkeit ≥ `--threshold`, Vorgabe 0,55),
gemischt (wörtliche Treffer zuerst, dann semantische) und **produktiv**: genau
der Weg, den Kingfisher mit eingeschalteter Bedeutungssuche geht
(`WorkingMemorySemantic`).

## Wann sich der Umbau lohnt

Vorschlag für die Entscheidung, bevor Code für einen Vektorindex entsteht:

- gemischt findet mindestens 12 von 16 Umschreibungen unter den 12 Kandidaten,
- direkte Fragen bleiben bei 16 von 16,
- unbeantwortbare Fragen bekommen höchstens bei einer Frage Kandidaten; die
  anschließende beleggebundene Auswahl muss dann weiterhin „keine Information“
  ergeben.

Erst dann lohnt ein abgeleiteter Vektorindex neben dem bestehenden Wortindex,
mit denselben Regeln wie heute: kein neues Wahrheitslager, Entzug und
Berichtigung entwerten auch die Vektoren, kein Download.

## Einschalten

Die Bedeutungssuche für Quellenberichte ist gebaut und standardmäßig aus.
Erfüllt der Arm **produktiv** die Kriterien oben, in `.kingfisher.env`
`ICARUS_MEMORY_SEMANTIC=1` setzen und Kingfisher neu starten. Wieder aus:
Zeile entfernen und neu starten. Es bleibt nichts zurück; die Vektoren liegen
nur im Speicher und werden aus dem aktuellen Bestand neu berechnet.

## Grenzen

16 synthetische Paare sind klein und von einem Entwickler formuliert, keine
repräsentative Alltagsquote. Die Schwelle 0,55 ist ein Startwert, keine
kalibrierte Größe. Das Skript prüft nicht, ob die spätere Auswahl durch das
Modell richtig entscheidet, nur ob die richtige Quelle überhaupt ankommt.
