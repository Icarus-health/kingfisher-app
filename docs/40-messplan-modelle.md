# Messplan: Modelle auf dem Zielgerät wählen

Stand: 30. September 2026. Gilt für einen Mac mit 32 GB gemeinsamem Speicher
(M2 Max); andere Geräte nach `model_recommendation.stufe_fuer`.

Welche Modelle Kingfisher benutzt, entscheidet die Messlatte, nicht die
Beschreibung auf der Modellseite. Dieser Plan sagt, was in welcher Reihenfolge
zu messen ist und woran man den Gewinner erkennt.

## Was zählt, in dieser Reihenfolge

1. **Falsche Aussagen** (Stufe Antwort, „falsch“ in der Bewertung). Null ist
   die Linie. Ein Modell, das schneller ist, aber einmal lügt, verliert.
2. **Antwortzeit**: Median unter 8 Sekunden (`Antwortzeit im Ziel` im Bericht),
   gemessen mit der Satzantwort (Rolle `antwort` zweimal: Auswahl und Sätze).
3. **Belege und vollständige Fragen** (Stufe Abruf, mit Modell für die Rolle
   `frage`: Paraphrasen und Umschreibungen kommen erst dann in die Suche).
4. **Stufe Akten** (`python -m messlatte akten`), sobald die Einordnung mit
   dem Hintergrundmodell läuft.

## Die Kandidaten (Ollama, Stand der Bibliothek 30.09.2026)

| Rolle | Vorauswahl im Katalog | Vergleich messen | Nicht dafür |
|---|---|---|---|
| `frage` | `qwen3.5:4b` (bis 24 GB) bzw. `qwen3.5:9b` | `lfm2.5:8b` (8B, 1B aktiv, für Ausgabeformat gebaut); `tev1:4b` nur für den Label-Anteil | `functiongemma` (nur Funktionsaufrufe) |
| `antwort` | auf 32 GB `gemma4:12b` (dicht, 8 GB; der Speicherbedarf des Orchesters entscheidet, siehe unten), ab 64 GB `qwen3.6:35b` (MoE, 3B aktiv) | `qwen3.6:35b` auch auf 32 GB (Lauf A); `qwen3.8:27b` (dicht, neu) | Cloud-Modelle nur mit Einwilligung je Rolle |
| `hintergrund` | auf 32 GB `nemotron-3.5-lightning:30b` (MoE, 3B aktiv, 23 GB nachts mit Einbettung), ab 64 GB `qwen3.6:35b` | `qwen3.6:35b` auch auf 32 GB (Lauf A, braucht nachts rund 29 GB) | dichte 27B-Modelle: gründlich, aber nachts doppelt so langsam |
| `einbettung` | `bge-m3` | `qwen3-embedding:0.6b`, `qwen3-embedding:4b`, `nomic-embed-text-v2-moe`, `snowflake-arctic-embed2`, `paraphrase-multilingual` | ein Wechsel baut den Bedeutungsindex neu |
| `pruefung` (zweites Tor der Satzprüfung, immer lokal) | `bespoke-minicheck:7b` ab 16 GB (für Faktenprüfung gebaut: „stützt die Quelle den Satz?“), `tev1:0.8b` auf 8 GB | `tev1:4b`; `nimble:9b` („decision models“: Klassifikation, kein Text) | als Antwortgeber |
| Einordnung nachts (Runde 2) | Regeln, dann `hintergrund` | `nuextract:3.8b` (zieht Datum, Betrag, Name, Frist aus Text), `functiongemma` nur für Funktionsaufrufe | als Antwortgeber |

Die Tag-Namen sind von der Modellseite übernommen und nicht gegen `ollama pull`
geprüft. Meldet Kingfisher beim Laden „unbekannt“, den Namen auf
`https://ollama.com/library/<modell>` nachsehen und im Katalog korrigieren.

**Speicher am Tag:** `antwort` + `frage` + `pruefung` + `einbettung` sind gleichzeitig
geladen (die Prüfung läuft bei jeder Antwort), nachts `hintergrund` + `einbettung`. Die Rechnung und was Kingfisher
daraus macht steht unter „Speicherbedarf des Orchesters“ weiter unten; nach den
Katalogwerten kommt `qwen3.6:35b` als Antwortmodell tagsüber auf 39 GB und passt
auf einem 32-GB-Mac nicht mehr neben die anderen.

## Drei Läufe, ein Befehl je Lauf

Vorher: `ollama pull` für jedes Modell des Laufs. Jeder Lauf schreibt einen
Bericht (Markdown und JSON) nach `--ausgabe`.

**Lauf A, die Vorauswahl:**

```
python -m messlatte lauf --welt messlatte/welt \
  --modell ollama:qwen3.6:35b --modell-hintergrund ollama:qwen3.6:35b \
  --modell-frage ollama:qwen3.5:4b --ausgabe /tmp/messlatte/a
```

**Lauf B, schnell am Tag:**

```
python -m messlatte lauf --welt messlatte/welt \
  --modell ollama:gemma4:12b --modell-hintergrund ollama:qwen3.6:35b \
  --modell-frage ollama:qwen3.5:4b --ausgabe /tmp/messlatte/b
```

**Lauf C, das Hintergrundmodell im Vergleich:**

```
python -m messlatte lauf --welt messlatte/welt \
  --modell ollama:qwen3.6:35b --modell-hintergrund ollama:nemotron-3.5-lightning:30b \
  --modell-frage ollama:lfm2.5:8b --ausgabe /tmp/messlatte/c
```

Danach mit 10.000 Rauschquellen wiederholen (`--rauschen 10000 --seed 1`),
mindestens für den Gewinner.

**Lauf D, das Prüfmodell im Vergleich** (zweites Tor, `docs/35-belegte-antworten.md#zweites-tor-prüfmodell`). Antwort-
und Fragemodell wie beim Gewinner von A bis C, nur `--modell-pruefung` wechselt:

```
python -m messlatte lauf --welt messlatte/welt \
  --modell ollama:GEWINNER --modell-hintergrund ollama:qwen3.6:35b --modell-frage ollama:qwen3.5:4b \
  --modell-pruefung ollama:bespoke-minicheck:7b --ausgabe /tmp/messlatte/d1
python -m messlatte lauf --welt messlatte/welt \
  --modell ollama:GEWINNER --modell-hintergrund ollama:qwen3.6:35b --modell-frage ollama:qwen3.5:4b \
  --modell-pruefung ollama:tev1:4b --ausgabe /tmp/messlatte/d2
```

Dazu derselbe Lauf ohne `--modell-pruefung` als Vergleich. Woran man den Gewinner erkennt, in dieser Reihenfolge:
falsche Aussagen 0 (die Kategorie `inhalt` ist dafür gebaut); dann **„vom Prüfmodell verworfen“ (Abschnitt „Zwei Tore
der Satzprüfung“) bei Antworten, die ohne Prüfmodell richtig waren**: Jeder solche Satz ist ein zu Unrecht verworfener,
der die Antwort in den Zitatmodus schieben kann; dann der Abschnitt `pruefung_modell` der Antwortzeit (Ziel: die ganze
Antwort bleibt unter 8 s im Median). Grobe Kontrolle ohne echtes Modell: `--modell skript:unaufmerksam
--modell-pruefung skript:pruefung --nur inhalt --einordnung regel` (Berichte `2026-09-30-pruefmodell-skript-*`).

## So liest man das Ergebnis

Im Markdown-Bericht ganz oben stehen die Kennzahlen; entscheidend sind:

- `falsch` bei der Stufe Antwort: muss 0 sein. Ist es nicht 0, steht in der
  Fehlerliste, welche Frage und welcher Satz. Diese Fälle sind das erste, was zu
  beheben ist, vor jeder Modellwahl.
- `Antwortzeit im Ziel`: bestanden / nicht bestanden, mit Median und
  90-Prozent-Wert je Abschnitt. Ist `saetze_modell` der langsame Teil, ist der
  Schalter „Sätze an/aus“ unter Einstellungen → Lokale KI die Stellschraube, bevor
  ein anderes Modell geladen wird.
- Belege gefunden und Fragen vollständig, verglichen mit dem Stand ohne Modell
  (`docs/evaluations/messlatte/README.md`): Ein Modell in der Rolle `frage` sollte
  über 124 von 136 liegen; liegt es darunter, versteht es die Frage schlechter als
  die Regeln.

Gewinner ist der Lauf mit 0 falschen Aussagen und der besten Antwortzeit; bei
Gleichstand der mit mehr Belegen. Die Wahl kommt als Vorauswahl in
`model_recommendation.KATALOG` (mit Datum), die Berichte nach
`docs/evaluations/messlatte/`.

## Danach: eigene Fragen

```
python -m messlatte lokal --fragen messlatte/beispiel-eigene-fragen.json
```

Fünf eigene Fragen, deren Antwort man kennt, reichen als erste Probe. Meldungen
aus „Stimmt nicht?“ werden mit `python -m messlatte faelle --aus <Datei>` zu
weiteren Fällen ([`38-rueckkanal.md`](38-rueckkanal.md)).

## Was außerdem auf der Liste steht und später zählt

- **`gemma4` versteht Audio.** Damit können Gespräche eines Tages lokal
  transkribiert werden, ohne Export aus einer anderen App.
- **`glm-ocr`, `deepseek-ocr`** lesen gescannte PDFs und Bilder: der Weg zu
  Anhängen in der Aufnahme.
- **`reader-lm`** macht aus HTML-Mails sauberen Text; ein Kandidat für die Aufnahme, wenn die heutige HTML-Bereinigung an Newslettern scheitert.
- **`granite4.1-guardian`, `gpt-oss-safeguard`** sind Prüfmodelle; für die
  zweite Satzprüfung (Runde 2) sind die kleineren Entscheidungsmodelle die
  bessere Wahl, weil sie nur ja/nein liefern.

## Cloud über Ollama

Ollama bietet Modelle mit dem Tag `cloud` an (etwa `deepseek-v4.1-flash:cloud`).
Das lokale Ollama nimmt die Anfrage an und reicht sie an Ollamas Server weiter.
Im Modellverzeichnis steht so ein Modell wie jedes andere, und der Endpunkt ist
Loopback. Wer nur die Adresse prüft, hält es für lokal.

**Woran Kingfisher es erkennt** (`ollama_inventar.py`): Je installiertem Modell
gilt es als *lokal*, wenn `/api/tags` das Format `gguf`, einen Digest und kein
`remote_host`/`remote_model` meldet. Alles andere, auch ein Tag mit `cloud`, ist
*Cloud über Ollama*. `/api/show` wird nur für Zeilen gefragt, die in `/api/tags`
keine Einzelheiten haben. Die Antwort wird 30 Sekunden gemerkt (nach einem
Ausfall 5 Sekunden, damit sich ein Neustart von Ollama schnell zeigt); das Laden
eines Modells und das Öffnen der Modellkarte lesen sofort neu.
**Fail closed:** Antwortet Ollama nicht oder ist die Antwort unbrauchbar, ist
die Art *unbekannt*, und unbekannt gilt nicht als lokal.

**Was daraus folgt** (`model_roles.py`, `model_roles_routes.py`):

| Rolle | Modell mit Cloud über Ollama |
|---|---|
| `hintergrund`, `einbettung` | nie; die Rolle hat dann keinen Anbieter (`None`) und ruht. Die Wahl wird abgelehnt, ein Handeintrag in der Datei wirkt nicht. Die Einbettung fällt auf die Vorgabe zurück. |
| `frage`, `antwort` | nur mit gültiger Einwilligung je Rolle, Anbieter `ollama-cloud`. Der Satz zur Einwilligung nennt: Die Daten gehen an Ollama (USA), nicht an den Modellhersteller. Ohne Einwilligung gilt das belegt lokale Standardmodell, sonst `None`; nie stillschweigend. |

Der Anbieter eines solchen Modells trägt `is_local = False`, damit jede Prüfung
weiter unten („lokal?“) es als Cloud sieht. Gewählte Modelle werden auch
gegen das Inventar geprüft, wenn sie als „lokal“ gespeichert sind (Handeintrag,
später getauschtes Modell). Ohne Rollenwahl gilt der Standardanbieter; ist er ein
Ollama-Modell, muss er für Hintergrund und Einbettung belegt lokal sein, und als
Cloud über Ollama bekommt auch die Antwort ihn nicht ohne Einwilligung.

**Was der Nutzer sieht:** Die Modellkarte und „Lokale KI“ führen solche Modelle
getrennt („Läuft in Ollamas Cloud, nicht auf diesem Rechner“) und bieten sie
nicht als lokale Vorauswahl an. Unter „Für Fortgeschrittene“ lassen sie sich für
Frage und Antwort mit einer Einwilligung wählen. Die Verarbeitung meldet den
Zustand `cloud_ueber_ollama` statt `wrong_model`; die Mailaufnahme nennt
`analysis_blocked`.

**Grenze:** Verdichter und Zusammenfasser halten ihren Anbieter seit dem
Neuaufbau des Agenten. Startet Kingfisher vor Ollama, haben sie bis zum nächsten
Neuaufbau keinen (die Läufe des Zeitplans holen ihn frisch und sind nicht betroffen).

## Speicherbedarf des Orchesters

Jedes Modell einzeln unter 85 Prozent des Arbeitsspeichers reicht nicht: Die
Modelle laufen zusammen, und jedes liegt auf der Festplatte.

| | Modelle | Summe |
|---|---|---|
| Tag | `antwort` + `frage` + `pruefung` + `einbettung` | `tag_gb`, gegen Arbeitsspeicher mal 0,85 |
| Nacht | `hintergrund` + `einbettung` | `nacht_gb`, gegen dieselbe Grenze |
| Festplatte | alle vier Rollen | `festplatte_gb`; für die Prüfung zählt nur, was noch zu laden ist, plus 2 GB Reserve |

Dasselbe Modell in zwei Rollen wird einmal gezählt (es wird einmal geladen).
`model_recommendation.orchester_bedarf(auswahl, geraet, vorhanden)` liefert die Summen
und `passt_tag`, `passt_nacht`, `passt_festplatte`. Diese sind `True`, `False` oder
`None`: **`None` heißt „nicht zu sagen“** (Gerät, freier Platz oder Modellgröße
unbekannt). Nichts davon wird geraten; ein Modell außerhalb des Katalogs steht in
`unbekannte_modelle` und macht aus einem „passt“ ein „unbekannt“.

**Ausweichwahl.** `empfehle_alle` schlägt kein Orchester vor, das tagsüber nicht passt. Zuerst gibt die Prüfung
Speicher her, wenn das allein reicht (ein kleineres Prüfmodell verwirft im Zweifel, ein kleineres Antwortmodell schreibt
mehr falsche Sätze); reicht es auch mit dem kleinsten Prüfmodell nicht, gilt die Regel für Antwort und Frage, und die
Prüfung wird danach nur so klein wie nötig (32 GB: `tev1:4b` statt `bespoke-minicheck:7b`; 24 GB: `tev1:0.8b`, das
Antwortmodell bleibt). Sonst:
Es tauscht das größte Modell von Antwort oder Frage gegen die nächstkleinere Wahl
(zuerst eine Alternative der Stufe, sonst ein Modell der kleineren Stufe), bis es passt.
Nachts gilt dasselbe für das Hintergrundmodell. Die Einbettung wird nie getauscht, ein
Wechsel baut den Bedeutungsindex neu. Auf einem 32-GB-Mac wird so aus `qwen3.6:35b`
für die Antwort `gemma4:12b` und für den Hintergrund `nemotron-3.5-lightning:30b`
(das große Modell käme nachts mit der Suche auf 29 von 27,2 GB); die Zeile der Aufgabe
trägt den Satz dazu, und die große Wahl bleibt ausdrücklich möglich. Die Tabelle
„Die Kandidaten“ oben nennt die Vorauswahl je Rolle und Stufe; was davon auf einem
Gerät wirklich vorgeschlagen wird, entscheidet diese Rechnung. Auf 8 GB gibt es
nichts Kleineres; dort sagt die Karte das, statt zu rechnen, bis es passt.

**Festplatte.** Der freie Platz kommt vom Helfer auf dem Rechner
(`scripts/report_device.py`, nur die Zahl `disk_free_bytes`, gemessen dort, wo
Ollama seine Modelle ablegt: `OLLAMA_MODELS`, sonst `~/.ollama/models`, sonst Home).
Fehlt die Meldung, misst der Sidecar selbst, aber nur außerhalb eines Containers;
im Container sagt die Messung nichts über den Rechner. Sonst ist der Platz `None`.
Vor dem Laden (`POST /api/v1/models/pull`) lehnt der Server mit einem Satz ab, wenn
ein noch nicht installiertes Modell samt Reserve nicht passt, und nennt ein kleineres.
Ein schon installiertes Modell wird nur übernommen und braucht keinen Platz.

**Ausstattung ohne Bericht** (Fremdprobe, Befund 10). Meldet kein Helfer das Gerät, misst der Sidecar den
Arbeitsspeicher selbst (`device_profile.eigene_ausstattung`: `SC_PHYS_PAGES`, im Container zusätzlich die
cgroup-Grenze). Läuft er direkt auf dem Rechner, ist das die Ausstattung; im Container (Docker Desktop: die virtuelle
Maschine) ist es eine **Untergrenze**, der Rechner hat mindestens so viel. Die Empfehlung nennt die Herkunft in
`geraet.quelle` (`bericht`, `eigene`, `untergrenze`, `unbekannt`); ein Bericht des Helfers geht immer vor. Niemand wird
nach seinem Arbeitsspeicher gefragt.

**Anderes Modell nehmen** (Befund 11). Besteht ein geladenes Modell die Prüfung nicht, trägt der Fehler `art:
"pruefung"`, und die Empfehlung nennt je Aufgabe `ausweich`: `model_recommendation.ausweichwahl` (zuerst die
Alternativen der Stufe, dann die Vorauswahl kleinerer Stufen, zuletzt die übrigen Modelle der Aufgabe, kleinste zuerst;
nur, was in den Speicher passt). `POST /api/v1/models/pull` erlaubt diese Modelle zusätzlich zu Vorauswahl und
Alternativen, nichts anderes.

**Was der Nutzer im Assistenten sieht** (`Einrichtung/RechnerKarte.tsx`): drei Fähigkeiten (Fragen beantworten:
`frage`, `antwort`, `einbettung`; im Hintergrund einordnen: `hintergrund`; Antworten prüfen: `pruefung`) mit je einem
Stand („Bereit“, „Wird geladen … 40 %“, „Prüfung nicht bestanden“, „Noch nicht eingerichtet“), einen Satz zur
Ausstattung, Größe und Dauer des Ladens und einen Knopf „Laden und einrichten“. Eine nicht bestandene Prüfung hält die
übrigen Aufgaben nicht auf; darunter steht „Anderes Modell nehmen“. Modellnamen, die Messlatte und der Speicher je
Tageszeit stehen nur im Aufklapper „Für Techniker“ und unter Einstellungen → Für Techniker.

**Was der Techniker sieht** (Modellkarte unter „Für Techniker“): eine Zeile „Zusammen: 22 GB
Arbeitsspeicher am Tag, 25 GB nachts, 35,8 GB Festplatte (frei: 210 GB).“ und, wenn
etwas nicht passt, ein ruhiger Satz mit dem Vorschlag, was stattdessen
(`orchester.hinweise` der Empfehlungsroute).
