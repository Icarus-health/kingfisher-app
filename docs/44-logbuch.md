# Logbuch: was seit dem letzten Blick geschah

Stand: 30. September 2026. Runde 2 des Plans ([`26-plan-stabschef.md`](26-plan-stabschef.md)),
Meilenstein M2 im [Zielbild](41-zielbild.md). Gemessen an „7:10, Briefing“: Morgens stehen drei
Zeilen da, ohne dass jemand nachsehen musste, was über Nacht lief.

> Seit gestern Abend: 41 Mails aufgenommen, 2 neue Akten (Anna Keller, Projekt Mainz).
> 1 Widerspruch gefunden, 1 neuer Vorschlag.

Code: `logbuch.py` (Chronik, Zusammenfassung, Wörter), `logbuch_routes.py` (Datei, Route, Zeilen fürs
Briefing). Aufrufe an den schreibenden Stellen siehe unten. Oberfläche: `Logbuch.tsx`, `TagesLage.tsx`.
Tests: `sidecar/tests/test_logbuch.py`, `sidecar/tests/test_logbuch_routes.py`,
`test_every_backup_store…` in `test_complete_recovery.py`. Browserprobe: `scripts/probe_logbuch_ui.py`.

## Was es tut

**Die Chronik.** Eine eigene kleine Datei, `logbuch.sqlite3` (Tabellen `ereignis` und `marke`,
eigene Versionierung). Ein Eintrag hat Zeitpunkt, Art und Nutzdaten. Er wird **nie geändert und nie
gelöscht**: Zwei Trigger verhindern UPDATE und DELETE auf Datenbankebene, wie beim Audit-Log.

**Kein Rohtext.** Mails, Notizen und Antworten stehen hier nie. Gespeichert werden Zähler, Titel von
Sachen, Kennungen und kurze Stichworte. Die Nutzdaten werden beim Schreiben auf 120 Zeichen gekürzt
und flach gehalten; Felder mit Namen wie `text`, `body`, `betreff`, `absender`, `antwort`, `detail`
fallen weg (`VERBOTENE_FELDER`). Bei einem Fehler der Hintergrundarbeit steht nur der Name des
Schritts („aufnahme“), nie der Fehlertext.

| Art | Nutzdaten | Wer schreibt |
|---|---|---|
| `quellen` | `sorte` (mail, dokument, gespraech, termin), `anzahl` | `mail_intake.py` (je Durchgang, nur neue Mails), `ingest.py` (je Ordnerlauf), `folder_sync.py` (je Datei vom Mac-Helfer), `calendar_memory.py` (neue Termine je Abgleich) |
| `akte_neu`, `akte_aktualisiert` | `sache`, `name` | `akten_routes.py` beim Nachführen der Bezüge (`Logbuch.akten_abgleichen`) |
| `vorschlag_erzeugt`, `vorschlag_angenommen`, `vorschlag_abgelehnt` | `sorte`, `id` | `proposals.py`, in `propose`, `accept`, `reject`: die eine Stelle, durch die alle Vorschläge gehen |
| `lint` | `befunde`: Anzahl je Art | der Lint-Lauf (siehe „Lint“) |
| `fehler` | `was` | `scheduler.py` nach jedem Lauf der Hintergrundarbeit |
| `modellwechsel` | `rolle`, `wofuer`, `lokal`, `modell` | `model_roles_routes.py` |
| `export` | `was` | `server.py`, Export des Selbstmodells |
| `rueckmeldung` | `sorte` | `rueckmeldung_routes.py` („Stimmt nicht?“) |
| `zu_lang` | `sorte`, `anzahl` | `working_memory_store.py` (`pending`): eine Quelle über der Obergrenze der Einordnung (200.000 Zeichen, `abschnitte.py`) bleibt zurückgestellt; einmal je Fassung der Quelle. Im Briefing: „1 Quelle zu lang zum Einordnen“ (Gruppe Betrieb) |

**Die Aufrufe scheitern nie.** Geschrieben wird mit `logbuch.vermerke(art, **daten)`, einer Funktion
auf Modulebene über das „aktive“ Logbuch (`logbuch.verbinde`). Jeder Fehler wird geschluckt und
geloggt: ein fehlendes oder geschlossenes Logbuch, eine kaputte Datei, unbrauchbare Nutzdaten, ein
werfendes Logbuch-Objekt. Eine Aufnahme, ein Vorschlag, ein Export gelingt oder scheitert nie wegen
des Logbuchs. `Logbuch.vermerke` gibt `False` zurück, wenn nichts geschrieben wurde.

**Zählen, nicht speichern.** Die Chronik hält je Durchgang einen Eintrag, nicht je Mail; bei
Vorschlägen einen je Vorschlag. `Logbuch.seit(zeitpunkt)` zählt zu einer `Zusammenfassung`, ohne
Listen zu laden.

## Die drei Zeilen

`drei_zeilen(zusammenfassung)` macht aus den Zählern höchstens drei Zeilen Alltagssprache. Die
Gruppen, in dieser Reihenfolge; leere Gruppen und leere Aussagen fehlen:

1. **Was hereinkam:** Quellen („41 Mails aufgenommen“, „3 Dokumente“, „1 Gespräch“) und Akten
   („2 neue Akten (Anna Keller, Projekt Mainz)“, bis zu drei Namen, dann „und 2 weitere“;
   „1 Akte ergänzt“). Eine Akte, die im Zeitraum entstand, zählt nicht zusätzlich als ergänzt.
2. **Was dein Auge braucht:** Befunde („1 Widerspruch gefunden“) und Vorschläge („3 neue Vorschläge“,
   „2 Vorschläge angenommen“, „1 Vorschlag abgelehnt“).
3. **Der Betrieb:** Modellwechsel („1 Modell gewechselt (Antworten formulieren)“), Exporte, Rückmeldungen und, als
   eigener Satz am Ende, was nicht fertig wurde, mit dem Satz, ob man etwas tun muss: „Im Hintergrund ist 3-mal etwas
   nicht fertig geworden (Quellen aufnehmen, Quellen einordnen). Du musst nichts tun: Kingfisher versucht es von selbst
   noch einmal.“ Bei Postfach und Sicherung steht stattdessen, wo man nachsieht (`fehler_satz`, Fremdprobe 2, Befund 15).

Die erste Zeile beginnt mit „Seit gestern Abend:“. Der Bezugspunkt wird gesagt, wie man ihn sagen würde:
„gestern Abend“, „heute früh“, „vorgestern“, „Samstag“, „dem 12. September“, „kurzem“. Ist nichts
geschehen, steht da ein Satz: „Nichts Neues seit gestern Abend.“ Fachwörter (Episode, Claim, Lint,
Proposal) kommen nicht vor; ein Test prüft das.

## Seit dem letzten Blick

Bezugspunkt ist der letzte Aufruf des Briefings, gespeichert in der Tabelle `marke`. Ein Neuladen
soll die Zeilen nicht leeren, und die Oberfläche fragt jede Minute nach. Darum gilt eine **Sitzung**:
Liegt der vorige Aufruf weniger als drei Stunden zurück, bleibt der Bezugspunkt, was er war; erst
nach einer Pause rückt er auf den letzten Aufruf vor der Pause. Ohne gespeicherten Aufruf gelten
24 Stunden. Weiter als 30 Tage schaut das Briefing nie zurück (die Chronik selbst bleibt). Der
Bezugspunkt ist halboffen (`[von, bis)`), damit kein Eintrag in zwei Zeiträume fällt.

**Wer als Blick zählt:** das Öffnen, also `GET /api/v1/tag/briefing` und `GET /api/v1/morning-briefing`.
Nicht als Blick zählen der Verlauf (`GET /api/v1/logbuch`) und das stille Erneuern der Oberfläche bei
offenem Tab (`GET /api/v1/tag/briefing?nachladen=true`, jede Minute und nach Klicks im Briefing). Ein Tab,
der über Nacht offen steht, hält den Bezugspunkt also nicht fest und verschiebt ihn auch nicht: Die Zeilen
zählen weiter seit dem letzten Öffnen, und ein Neuladen am Morgen rückt ihn vor.

## Im Briefing und der Verlauf

**Tagesbriefing** (`tagesbriefing.py`): `Tageslage.verlauf` trägt die Zeilen, `tag_routes.py` reicht sie
durch. Sie zählen nicht zu `MAX_ZEILEN` und stehen vor dem, was heute zählt. **Morgenbriefing**
(`morning.py`, `verlauf` im Ergebnis): dieselben Zeilen; das gesprochene Briefing (`AudioBriefing.tsx`)
beginnt mit ihnen. Ein Fehler im Logbuch lässt die Zeilen fehlen, nie das Briefing.

**Oberfläche.** Die Zeilen stehen ganz oben in `TagesLage`, gedämpft (Schriftfarbe `--today-muted`,
keine Fläche, keine Akzentfarbe, [`16-gestaltung.md`](16-gestaltung.md)). Darunter ein stiller Link
„Verlauf“, der die Chronik aufklappt (`Logbuch.tsx`); „Verlauf schließen“ klappt sie zu. Keine neue
Hauptseite, kein neuer Menüpunkt: Der Verlauf liegt hinter dem Link.

**Der Verlauf** (`GET /api/v1/logbuch?seit=…`): die Chronik nach Tagen, jüngster zuerst („Heute“,
„Gestern“, „Samstag, 26. September“), je Tag die Aussagen in denselben Wörtern wie oben, dazu
`zeilen` und `zusammenfassung` des Zeitraums. Tage ohne Aussage fehlen. `seit` ist ein ISO-Zeitpunkt;
ohne Angabe gelten sieben Tage, weiter als 366 Tage zurück wird gekürzt, Unlesbares ergibt 422.

## Akten: neu und ergänzt

`Logbuch.akten_abgleichen(sachen)` vergleicht die Sachen (Kennung, Name, letzte Aktivität) mit dem
zuletzt gesehenen Stand (Tabelle `marke`). Aufgerufen wird es nach jedem Nachführen der Bezüge, das
etwas berechnet hat (`akten_routes._ins_logbuch`), auch im Hintergrundfaden. Unbekannte Sachen sind
neu, Sachen mit späterer letzter Aktivität sind ergänzt, und jeder Stand wird nur einmal gemeldet.
Der **allererste** Abgleich hat keinen Stand: Was schon vor dem Logbuch da war (letzte Aktivität vor
dessen Anlegen), setzt nur den Stand und ist nicht „neu“. Sonst stünde nach dem Update „312 neue
Akten“. Bis zu 5.000 Sachen werden je Abgleich verglichen; was darüber liegt, bleibt im Stand.

## Lint

Ein anderer Baustein prüft die Akten (`lint.zusammenfassung()`). Das Logbuch hängt nicht von ihm ab:
Es bindet ihn über den optionalen `befunde_lieferant` ein, ein Aufruf ohne Argumente, der
`{Art: Anzahl}` liefert (auch `{'je_art': {...}}`; Summen wie `gesamt` zählen nicht doppelt).

* `logbuch_routes.befunde_lieferant_setzen(app, lieferant)` bindet ihn, `None` löst ihn. Er überlebt das
  Neuöffnen nach einer Wiederherstellung.
* Schreibt der Lint-Lauf selbst, was er fand (`logbuch.vermerke('lint', befunde={'widerspruch': 1})`), bestimmt
  das die Zeile: „1 Widerspruch **gefunden**“ (seit dem letzten Blick).
* Gibt es im Zeitraum keinen solchen Eintrag, zeigt der Lieferant den heutigen **Stand**: „1 Widerspruch
  **noch offen**“. Ein Stand kennt kein „seit“; darum sagt der Satz es anders.
* Fehlt der Lieferant oder wirft er, fehlt die Zeile. Bekannte Arten heißen `widerspruch`, `veraltet`,
  `ohne_akte`, `ohne_quellen`, `querverweis`; jede andere wird „Auffälligkeit“.

## Sicherung

`logbuch.sqlite3` steht in `SQLITE_DATA_FILES` (`backup.py`) wie `rueckmeldungen.sqlite3`, in der
Schema-Vorabprüfung vor Updates (`update_backup._targets`) und wird nach einer Wiederherstellung neu
geöffnet (`logbuch_routes.verbinden`). `test_every_backup_store…` legt Einträge an und prüft sie
nach der Wiederherstellung.

## Geprüft

* **Tests:** Chronik anhängend (UPDATE und DELETE scheitern), kein Rohtext, Zeitraumgrenzen, Zählen,
  die drei Zeilen des Beispiels, höchstens drei Zeilen, leere Kategorien und „Nichts Neues“, Einzahl und
  Mehrzahl, Namenslisten, keine Fachwörter, Bezugspunkt in Worten, Lieferant vorhanden, fehlend und
  kaputt, Bezugspunkt (24 Stunden, Sitzung, Pause, Neustart, 30 Tage), Akten (erster Abgleich, neu, ergänzt,
  einmal), Tagesgruppen, Aufrufe ohne aktives, geschlossenes, kaputtes und werfendes Logbuch,
  Vorschläge bei kaputtem Logbuch, Mail- und Ordneraufnahme (nur Neues), Routen und Briefing.
* **Sabotageproben** (Zusicherung gebrochen, Tests laufen lassen): fehlende Trigger; Rohtext-Filter aus;
  `vermerke` ohne Fangnetz (Methode und Funktion); Sitzungsregel weg; leere Gruppen als Zeilen; mehr als
  drei Zeilen; Stand der Akten nicht fortgeschrieben; erster Abgleich meldet alles; Sicherung ohne die
  Datei; „Nichts Neues“ fehlt; Verlauf zählt als Blick; Fehlertext im Logbuch; ungeschützter Aufruf in den
  Vorschlägen; doppelte Mails mitgezählt. Die ersten Durchläufe fingen drei nicht (nur die Funktion, nicht die
  Methode; keine doppelten Mails im Test); die Tests wurden ergänzt, danach fing jede Probe.
* **Browserprobe** (`scripts/probe_logbuch_ui.py`, echter Server, Chromium): die Zeilen stehen vor der
  Überschrift des Tages und gedämpfter als sie, Neuladen lässt sie stehen, „Verlauf“ klappt die Tage
  auf und zu, Anzeigen schreibt nichts, hell, dunkel und Telefonbreite ohne waagerechtes Scrollen, Konsole leer.

## Grenzen

* Die Chronik beginnt mit dem Tag der Einführung. Sie kennt nichts aus der Zeit davor.
* „Akte ergänzt“ heißt: Die letzte Aktivität einer Sache ist neuer als beim letzten Abgleich. Sie sagt nicht, was
  sich geändert hat; das steht in der Akte.
* Die Aufnahme über den alten, nicht wiederaufnehmbaren Weg für Postfächer (`run_sources` ohne
  `mail_intake`) vermerkt nichts; den Weg nutzt nur noch, wer die wiederaufnehmbare Aufnahme nicht gestartet hat.
