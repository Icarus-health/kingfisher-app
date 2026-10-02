# Postfachprobe: Arbeitsstand bei großem Postfach

Synthetisch, ohne Chatmodell, ohne Netz. Skript:
`scripts/probe_working_memory_scale.py`, Test:
`scripts/test_probe_working_memory_scale.py`.

## Aufbau

Ein reproduzierbares Postfach (Seed 20260925) aus geschäftlichen Mails mit
Begrüßung, Füllabsätzen, einer Lieferangabe und Gruß. 40 Nadeln haben eine
eindeutige Kombination aus Person, Projekt und Gegenstand. Alle übrigen Mails
sind Ablenker, die jeweils zwei dieser drei Merkmale mit einer Nadel teilen.
Die Einordnung wird ohne Modell nachgebildet, je Absatz ein Abschnitt, wie ihn
die lokale Einordnung liefert. Gefragt wird je Nadel „Wann liefert <Person>
<Gegenstand> für <Projekt>?“.

## Ergebnis auf `05c71ca`

| Mails | Aufnahme | Einordnung ohne Modell | Suche Median / p95 | Datenbank | Nadel in Top 12 | Nadel beim Modell | Antworten „begrenzt“ |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 200 | 0,2 s | 0,8 s | 4 / 5 ms | 6,4 MB | 40/40 | 40/40 | 40/40 |
| 1000 | 1,1 s | 4,7 s | 10 / 15 ms | 32,4 MB | 40/40 | 40/40 | 40/40 |
| 3000 | 2,9 s | 19,7 s | 40 / 50 ms | 95,9 MB | 40/40 | 40/40 | 40/40 |

Rohdaten: [`lexikalisch-05c71ca.json`](lexikalisch-05c71ca.json).

## Was daraus folgt

1. **Suche und Auswahlgrenzen halten.** Auch bei 3000 Mails findet die
   Wortsuche jede Nadel unter den ersten zwölf Treffern, und sie kommt nach dem
   Kontextbudget beim Auswahlmodell an. Die Suche bleibt unter 0,1 s. Die Fragen
   hier nennen Person, Gegenstand und Projekt wörtlich; das ist der günstige
   Fall. Umschreibungen misst die Umschreibungsprobe (`../paraphrase/`).
2. **Der Suchindex ist zu groß.** Rund 32 KB je Mail, bei 10 000 Mails also etwa
   320 MB, für wenige hundert Kilobyte Text. Aufgeschlüsselt (500 Mails): Die
   Tabelle `working_memory_tokens` belegt mit ihren beiden Indizes rund 19 MB,
   die Mails selbst 0,75 MB. Ursache: Jedes Wort und jede Wortendung steht als
   64-stelliger Hex-Hash mit 64-stelliger Item-ID dreifach auf der Platte.
   Vorschlag: ganzzahlige Schlüssel und eine Tabelle ohne Zeilen-ID mit
   Primärschlüssel (Wort, Item). Das spart geschätzt eine Größenordnung, ohne
   Suchverhalten und ohne Klartext im Index.
3. **„Begrenzt“ ist bei großem Postfach der Normalfall.** Jede Frage enthält
   ein häufiges Wort („liefert“), die Wortsuche hat damit mehr als zwölf Treffer
   und markiert die Antwort als begrenzt. Für Gesprächsantworten ist das nur
   ein interner Vermerk. Die Antwortvorschläge für Mails verwerfen aber jede
   begrenzte Auswahl (`mail_reply_suggestions.py`). Bei einem echten Postfach
   bekämen sie damit praktisch nie Gedächtnisbelege. Das ist vor der Nutzung
   mit echten Postfächern zu klären.
4. **Die Modellzeit dominiert das erste Einordnen.** Ohne Modell dauert es
   rund 7 ms je Mail. Mit Modell zählt nur dessen Zeit je Quelle. Auf dem
   Zielrechner einmal messen und mit `--sekunden-je-quelle` hochrechnen, etwa:
   `python scripts/probe_working_memory_scale.py --sizes 1000 10000
   --sekunden-je-quelle 4 --output docs/evaluations/memory-quality/scale/mac-<commit>.json`.

Eine Entscheidungsgrundlage, keine Produktabnahme.
