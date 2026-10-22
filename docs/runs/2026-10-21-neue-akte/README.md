# Paket B4: Vorschlag „Neue Akte?“ (neues Projekt erkennen, mit einem Klick anlegen)

Stand 22.10.2026, Branch `feat/neue-akte-vorschlag-20261021` auf `main` 1.0.26. Geprüft wurde
ausschließlich mit synthetischen Daten (Attrappe mit vier erfundenen Mails, Messlatte-Welt); keine
persönlichen Daten, kein Modellaufruf. Beschreibung: [`30-akten.md`, Abschnitt „Neue Akte?“](../../30-akten.md#neue-akte-paket-b4-migration-24).

## Was gebaut wurde

| Bereich | Dateien |
|---|---|
| Kern (Schwellen, Grund, Annehmen, Ablehnen, Zurücknehmen, Ablage) | `sidecar/icarus_memory/akten_vorschlaege.py` |
| Routen, Briefing-Zulieferung, Zeile der Akte, Logbuch | `akten_vorschlaege_routes.py`, `akten_routes.py` (`akte_vorschlag` in der Akte), `server.py` (`akten_vorschlaege` im Dashboard, Registrierung), `briefing.py` (Punkt `akte_vorschlag`, Gewicht 50), `morning.py` (Karte auf Heute), `logbuch.py` (Art `akte_vorschlag`) |
| Ablage | Migration **24** der Episoden (`episodes.py`: `_migrate_v24`, `_verify_v24`, `vorschlaege=True` in `_verify_v10/_verify_v20`), Tabelle `akten_vorschlag_entscheidungen` (Kennung, Entscheidung, Zeit, Sache, Projekt-ID, Quellen-IDs), `workspace.remove_project` |
| Oberfläche | `app/kingfisher/src/AkteAbschnitte.tsx` (`NeueAkte`, Übergabe des Satzes in die neue Akte), `AkteVorschlagKnoepfe.tsx`, `TodayOverview.tsx`, `akteVorschlag.ts`, `api.ts`, `AkteAbschnitte.css` |
| Tests | `sidecar/tests/test_akten_vorschlaege.py` (25), `app/kingfisher/tests/akte-vorschlag.test.mjs` (6); Versionsbehauptungen 23 → 24 in zwölf bestehenden Testdateien, `test_migrations.py`, `working_memory_legacy.py` |
| Doku | `30-akten.md`, `17-stabschef.md` (Etappe 1), `DEVELOPER-START.md` (Codekarte, Schemastand), `21-sqlite-migrationen.md`, `44-logbuch.md` |
| Browserprobe | `scripts/probe_neue_akte_ui.py` |

Grundsätze, an denen gemessen wurde: Ein Projekt ist Ablage, kein Fakt; es entsteht nur durch den Klick
(der Vorschlag speichert nichts, Annehmen legt keine Aussage und keinen Wissensvorschlag an). Ohne
Modell, deterministisch, mit Grund in einem Satz und Textstellen. Reversibel: Annehmen lässt sich
zurücknehmen, „Nein danke“ wird gemerkt und nicht wiederholt. Keine neue `ProposalKind`, keine Liste.

## Tests

| Prüfung | Vorher | Nachher |
|---|---|---|
| `test_akten_vorschlaege.py` (neu) | Sammlung bricht ab (`ModuleNotFoundError: akten_vorschlaege`), danach 14 von 15 grün bis zur ersten Korrektur (409 nach Annehmen), dann 22 von 25 (Idempotenz nach Unterbrechung, Route `/morning-briefing`, sechs Spalten) | **25 bestanden** |
| Gezielte Bestandstests (`test_bezuege`, `test_project_suggestions`, `test_akten*`, `test_akten_arten`, `test_logbuch*`, `test_briefing`, `test_migrations*`, Versionsbehauptungen, `test_kingfisher`, `test_tagesbriefing`, `test_kreis`) | 256 bestanden (vor der Änderung, kleinere Auswahl) | **419 bestanden** |
| Volle Backend-Suite (`pytest tests -n 4`) | – | erster Lauf **7.753 bestanden, 3 fehlgeschlagen, 3 übersprungen** (17 min): zwei Befunde an diesem Paket (`test_datumstext`: ISO mit Z nur über `datumstext.py` lesen; `test_pruefe_anfuehrungszeichen`: der Name des neuen UI-Tests trug selbst das verbotene Muster), beide behoben (`9dd1829`); zweiter Lauf **7.755 bestanden, 1 fehlgeschlagen, 3 übersprungen** (21 min). Der eine Rest ist `test_cloud_memory.py::test_bulk_accepts_101_sources_after_pilot_and_uses_larger_budget`: `finish` wartet 5 s auf den Faden von 101 Quellen, unter vier parallelen Arbeitern zu knapp; allein dreimal grün (16 s, 2,4 s, 2,7 s), Dateien seit #75 unberührt, nicht Teil dieses Pakets |
| UI (`node --test`) | – (nicht getrennt gemessen) | **769 bestanden**, davon 6 neu |
| `tsc -b` | grün | **grün** |
| `npm run build` | grün | **grün** |

Messlatte Akten (`python -m messlatte akten --welt messlatte/welt`, Regel-Einordnung, ohne Modell):
vorher **5 von 5, Quellen im Verlauf 15 von 15** (Bezüge für 240 Quellen in 0,56 s); nachher **5 von 5,
15 von 15** (1,9 s, gemessen während die volle Suite auf vier Kernen lief). Die Welt enthält keine
Projekt-Erwähnungen (Regel-Einordnung liefert keine Entitäten), deshalb entsteht dort kein Vorschlag.

## Sabotageproben

Jede Zusicherung wurde absichtlich im Code gebrochen (Treiber im Scratch, Datei danach mit `git checkout`
zurückgesetzt) und `test_akten_vorschlaege.py` (bei S11 dazu `test_migrations.py`) lief.

| Probe | Gebrochene Zusicherung | Ergebnis |
|---|---|---|
| S1 | Schwelle auf eine Quelle (`MIN_QUELLEN = 1`) | gefangen: `test_unter_jeder_schwelle_kein_vorschlag` |
| S2 | Vorhandenes Projekt wird trotzdem vorgeschlagen (Vergleich entfernt) | gefangen: `test_kein_vorschlag_in_umschrift_eines_vorhandenen_projekts`. Der Fall gleicher Schreibweise bleibt grün, weil `bezuege.Register.projekt` die Erwähnung schon dem Projekt zuordnet (keine `n:`-Akte mehr); der Vergleich hier ist nur für die Umschrift nötig |
| S3 | Umschrift beim Vergleich ignoriert | gefangen: derselbe Test |
| S4 | Annehmen schreibt einen Fakt (ein Wissensvorschlag der Art Aussage entsteht) | gefangen: `test_annehmen_legt_projekt_an_und_ordnet_nur_quellen_ohne_projekt_zu` (`proposals.counts()` ändert sich). Erste Fassung der Probe war unwirksam gebaut (ungültiger Vorschlag, 500) und wurde wiederholt |
| S5 | Ablehnen vergessen (abgelehnte Namen kommen wieder) | gefangen: `test_ablehnen_wird_gemerkt_und_nie_wiederholt_bis_zum_zuruecknehmen` |
| S6 | Zwei Vorschläge im Briefing | gefangen: `test_briefing_zeigt_hoechstens_einen_vorschlag…`, `test_briefing_ohne_vorschlag_und_rein_aus_den_daten` |
| S7 | Zurücknehmen lässt Zuordnung stehen | gefangen: `test_zuruecknehmen_stellt_den_stand_vorher_her`, `test_zuruecknehmen_laesst_ein_projekt_mit_anderen_quellen_stehen` |
| S8 | „Nein danke“ wird nicht gemerkt | gefangen: `test_ablehnen_wird_gemerkt…` |
| S9 | Zweites Annehmen ist kein 409 | erste Fassung (nur die Prüfung der Route entfernt) **wirkungslos**, weil der Kern dieselbe Prüfung trägt; mit beiden entfernt gefangen: `test_annehmen_zweimal_ist_409_und_aendert_nichts` |
| S10 | Annehmen hängt auch Quellen mit anderem Projekt um | gefangen: `test_annehmen_legt_projekt_an_und_ordnet_nur_quellen_ohne_projekt_zu` |
| S11 | Migration 24 ohne Schemavertrag (`vorschlaege=True` fehlt) | gefangen: 7 Tests rot, 23 Fehler beim Aufbau des Speichers (unerwartete Tabelle), dazu `test_migrations.py` |
| S12 | Logbuch bekommt den Klick nicht | gefangen: `test_logbuch_haelt_annehmen_und_ablehnen_fest` |
| S13 | Grund ohne Beteiligte | gefangen: `test_grund_nennt_zahl_datum_und_beteiligte…` |

14 Proben (13 geplant, S4 und S9 je zweimal), alle gefangen; zwei Proben waren in der ersten Fassung
unwirksam und wurden wiederholt, nicht gezählt.

## Browserprobe

`PYTHONPATH=sidecar python scripts/probe_neue_akte_ui.py --ausgabe <DIR>` (Chromium
`/opt/pw-browsers/chromium-1194/chrome-linux/chrome`, gebaute Oberfläche in `app/dist`). Attrappe: vier
Mails von Anna Keller und Ben Braun über drei Wochen mit „Projekt Atlas“, Erwähnungen aus einem
Regel-Skriptmodell. Ergebnis `ok`, **Konsole leer**, acht Bilder:

| Bild | Was zu sehen ist |
|---|---|
| `neue-akte-akte-vorschlag.png` | Akte `projekt:n:atlas`, 1280 px: „Neue Akte? Daraus eine Akte machen? In 4 Mails seit 2. Oktober mit Anna Keller und Ben Braun.“, vier Textstellen mit Quelle, „Akte anlegen“ und „Nein danke“; nichts gespeichert |
| `neue-akte-akte-nein-danke.png` | nach „Nein danke“: „Gemerkt: „Projekt Atlas“ wird nicht mehr vorgeschlagen.“ mit „Rückgängig“, darunter „Doch vorschlagen“; Ablage trägt `abgelehnt` |
| `neue-akte-akte-angelegt.png` | nach „Akte anlegen“: neue Akte `projekt:p-akte-…` mit „Akte „Projekt Atlas“ angelegt, 4 Quellen zugeordnet.“ und „Rückgängig“, 4 Quellen, Anna Keller und Ben Braun unter Zusammenhänge, Zeitstrahl, „Aus einem Vorschlag angelegt, 4 Quellen zugeordnet. Akte wieder auflösen“ |
| `neue-akte-akte-zurueckgenommen.png` | nach „Rückgängig“: zurück in `projekt:n:atlas`, „Zurückgenommen: 4 Quellen gelöst, Projekt „Projekt Atlas“ entfernt.“; Projekt weg, Quellen ohne Projekt, der Vorschlag steht wieder |
| `neue-akte-heute-vorschlag.png` | Heute: ein Punkt „Neue Akte?“ mit dem Satz und zwei Knöpfen, kein zweiter |
| `neue-akte-heute-angelegt.png` | nach „Akte anlegen“ auf Heute: der Punkt ist weg, die Antwort bleibt mit „Akte öffnen“ |
| `neue-akte-akte-390.png`, `neue-akte-heute-390.png` | 390 px, Seite und Zeile ohne Überlauf (`scrollWidth == innerWidth`, Zeile 0 px) |

## Offene Punkte und Grenzen

* Die Erwähnungen (`projekt:n:<Name>`) kommen vom Modell der Einordnung (`memory_categories`). Ohne
  lokales Modell gibt es keine erwähnten Projekte und damit keinen Vorschlag; die Messlatte-Welt misst
  den Vorschlag deshalb nicht. Die Browserprobe arbeitet mit einem Regel-Skriptmodell.
* Der Name des Projekts ist die Schreibweise der jüngsten Quelle („Projekt Atlas“), nicht normalisiert.
  Ein Nutzer, der „Atlas“ bevorzugt, benennt das Projekt um; die Zuordnung der Erwähnungen bleibt
  (`projekt_kennung` streicht „Projekt“).
* Zurücknehmen entfernt das Projekt nur, wenn keine anderen Quellen, Aufgaben, Notizen oder Termine
  daran hängen; sonst bleibt es und der Satz sagt warum. Ein nach dem Annehmen geschlossenes Projekt
  bleibt als solches stehen (Annehmen meldet dann 409 statt es wieder zu öffnen).
* `vorschlag_zu` kennt nach einer Unterbrechung (Projekt angelegt, Entscheidung nicht gemerkt) die Akte
  des Projekts als Vorschlag; damit könnte eine handgebaute Anfrage ein solches Projekt „ablehnen“. Ohne
  Wirkung auf Vorschläge (es gibt dort keinen), aber unschön.
* Die Zeitangabe „seit 2. Oktober“ nutzt die Zeitzone des Prozesses (`astimezone()`), nicht die
  eingestellte (Kingfisher und du). Am Tagesrand kann der Tag abweichen.
* Das Dashboard rechnet die Vorschläge bei jedem Abruf (Sachen `projekt:n:*`, je Quellen und
  Beteiligte). Bei sehr vielen erwähnten Projekten (Grenze 500 Sachen) kostet das spürbar; ein
  Zwischenspeicher am Änderungsstand der Bezüge wäre der nächste Schritt.
* Die Umschrift-Prüfung vergleicht nur gegen vorhandene Projekte, nicht zwei Erwähnungen untereinander
  („Mueller“ und „Müller“ sind zwei Vorschläge, bis einer angenommen ist; danach ist der andere stumm).
