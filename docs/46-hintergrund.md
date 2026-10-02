# Hintergrund ohne Nacht

Stand: 30. September 2026. Gehört zu M2 aus [`41-zielbild.md`](41-zielbild.md)
(Abschnitt „Hintergrundarbeit ohne Nacht“).

Viele Menschen schalten den Rechner nachts aus. „Nachts“ war nie die Bedingung
der Hintergrundarbeit, nur der bequemste Fall. Dieses Dokument hält zuerst fest,
was es heute an Hintergrundarbeit gibt, und dann die neue Regel.

## Bestandsaufnahme (vor dem Umbau)

Alle Arbeit mit Modell läuft über **einen** Faden, den Zeitplan
(`scheduler.py`, Faden `icarus-zeitplan`), verdrahtet in `server._wire_scheduler`.
Er läuft nur, wenn der Zeitplan eingeschaltet ist (`ScheduleSettings.enabled`,
Vorgabe aus; das Starten der Mailaufnahme schaltet ihn ein), und ruft ein Modell
nur mit der eigenen Freigabe `with_model` und einem lokalen Anbieter der Rolle
`hintergrund`.

| Arbeit | Wo gestartet | Takt | Sperren | Beim Start mit Rückstand | Während der Nutzer tippt |
|---|---|---|---|---|---|
| Mailaufnahme des Bestands (Konten mit Aufnahme) | `Scheduler._loop` → `run_mail_intake` → `mail_intake.Intake.background_step` | alle 30 s ein Paket (25 Mails), Verlauf alt → neu (`ORDER BY uid`), neue Post (Spur `live`) zuerst | `_run_lock` (nicht blockierend), `conversation_lock` je Mail | läuft weiter, wo der Zeiger in `mail_intake_items` stand | läuft weiter |
| Empfänger älterer Mails nachtragen | im Takt der Mailaufnahme, `teilnehmer_nachtrag.Lauf.schritt` | 10 Mails je Takt, pausiert bei Rückstau der Einordnung | wie oben | beginnt von vorn zu zählen, Arbeit ist wiederholbar | läuft weiter |
| Einordnung neuer Quellen (Upload, frisch aufgenommene Mail) | `Scheduler.request_working_memory` → `_run_prompt_once` | sofort, 5 je Paket, 1 s Pause | `_run_lock`, `conversation_lock` je Quelle | Warteliste nur im Speicher, geht verloren; der Rückstand fängt es auf | läuft weiter, **Modell parallel zur Antwort** |
| Einordnung des Rückstands (`working_memory_worker.run`, Themen `memory_categories`) | `_loop` → `_run_background_working_memory` | je Takt (30 s) ein Paket von 5 Quellen, 2 Themen | `_run_lock` | Zeiger `working_memory_scan` bleibt; Reihenfolge nach Kennung, also **zufällig** über die Zeit | läuft weiter, Modell parallel |
| Lagen (Ebene 3) | `_loop` → `_run_background_lage` | je Takt ein Paket (2 Sachen), wichtigste zuerst | `_run_lock` | wichtigste zuerst | läuft weiter, Modell parallel |
| Voller Durchgang: Ordner neu lesen, Mail ohne Aufnahme, öffentliche Quellen, Termine abgleichen, Beobachtungen, Zusagen, Verdichtung, Zusammenfassung, Sicherung | `_loop` → `run_once` | alle 240 min (einstellbar, mindestens 15) | `_run_lock` (blockierend), `conversation_lock` je Schritt | **sofort beim Start**: der letzte Lauf wird nicht gemerkt | läuft weiter, Modell parallel |
| Akten: Bezüge nachführen | jede Akten-Ansicht, jede Antwort (`akten_routes.nachfuehren`, höchstens 1,5 s), Rest im Faden `akten-bezuege` | bei Bedarf, alle 3 s höchstens einmal je Antwort | `_FADEN_SPERRE` (nur Starten) | beim ersten Aufruf | läuft, ohne Modell |
| Weltmeldung fürs Briefing | `welt_meldungen.anstossen`, Faden `welt-abruf` | höchstens alle 30 min, beim Briefing | eigene Sperre | beim ersten Briefing | läuft, Netz statt Modell |
| Modell laden | `model_pull`, eigener Faden | nur auf Klick | – | – | – |
| Mac-Helfer (Kalender, Karten, Audio, Sicherung, Ordner, Mitschriften) | `scripts/start_mac_app.py`, eigene Prozesse auf dem Mac | 2–5 s Abfrage | Dateisperre je Helfer | starten mit der App | laufen weiter |
| Lint über alle Akten, Akten als Markdown (Export) | noch nicht gebaut (M2, Runde 2) | – | – | – | – |

Befunde:

1. **Kein Begriff von Nutzen.** Der Rückstand der Einordnung läuft nach
   Kennung, also für den Menschen in zufälliger Reihenfolge; die Mails des
   Verlaufs von alt nach neu. Eine Mail von gestern wartet unter Umständen, bis
   die von 2019 eingeordnet ist.
2. **Kein Rücksicht auf den Menschen.** Nichts pausiert, wenn jemand tippt oder
   eine Antwort entsteht. Das Hintergrundmodell und das Antwortmodell laufen
   gleichzeitig; auf einem Rechner mit knappem Speicher heißt das Auslagern und
   eine zähe Antwort.
3. **Voller Durchgang bei jedem Start.** Wer den Rechner morgens einschaltet,
   bekommt den teuersten Durchgang genau dann, wenn er anfängt zu arbeiten.
4. **Gedrosselt nur durch den Takt.** 5 Quellen je 30 s, unabhängig davon, ob
   der Rechner gerade frei ist; ein Rückstand von 18.000 Quellen braucht so mehr
   als einen Tag reine Laufzeit, auch wenn niemand am Rechner sitzt.
5. **Fortschritt ohne Ende.** „Kingfisher lernt gerade“ zeigt Zeilen je Arbeit,
   aber nicht, wann es fertig ist; die gemessene Rate (`working_memory_worker.Pace`)
   lebt nur im Speicher und misst die Pausen mit, auch die Nacht, in der der
   Rechner aus war.
6. **Kein Autostart.** Der Hintergrund läuft nur, wenn jemand die App öffnet.

## Die neue Regel

Eine Steuerung, `sidecar/icarus_memory/hintergrund.py`, ordnet die vorhandenen
Läufe, statt sie zu kopieren. Der Zeitplan (`scheduler.py`) fragt sie in jedem
Takt; der Einbau in `server.create_app` ist ein einziger Aufruf
(`hintergrund.einbauen`).

**Läuft immer, wenn die App läuft.** Nicht nachts, sondern in kleinen Häppchen,
sobald der Rechner wach ist und niemand arbeitet. Die Freigaben bleiben, wie
sie sind: Ohne eingeschalteten Zeitplan (Mailaufnahme gestartet) und ohne
Modellprüfung mit lokalem Modell ruft der Hintergrund kein Modell.

**Reihenfolge nach Nutzen** (`hintergrund.ordnen`), für die Einordnung aller
offenen Quellen:

1. *morgen*: Termine von heute bis drei Tage voraus; Quellen der Personen dieser
   Termine (über die Bezüge der Akten, höchstens 30 je Person); Post von heute
   und gestern; jüngere Quellen (60 Tage) mit einer offenen Frist
   (`fristen.fristen_in`, Regeln, kein Modell). Diese Stufe geht auch neuen
   Uploads vor.
2. *neu*: alles der letzten 14 Tage, dann neue Uploads in ihrer Reihenfolge.
3. *Rückstand*: der Rest.

Innerhalb jeder Stufe **von neu nach alt**. Die Entscheidung: Für das Briefing
zählt Aktualität, und wer nach „Kontakt vor drei Jahren“ fragt, findet die
Quelle schon über den Suchindex (FTS5, [`29-suchindex.md`](29-suchindex.md)),
auch wenn sie noch nicht eingeordnet ist; es fehlen ihr dann nur die
abgeleiteten Hinweise. Alt nach neu hieße: Wer 18.000 Mails mitbringt, hat
tagelang ein Briefing aus 2019. Aus demselben Grund holt die Mailaufnahme den
Verlauf eines Postfachs jetzt mit der höchsten UID zuerst; neue Post (Spur
`live`) bleibt in Eingangsreihenfolge und hat weiter Vorrang.

Die Schlange braucht keinen eigenen Speicher. Was offen ist, steht in
`working_memory_sources`; die Reihenfolge wird daraus höchstens jede Minute neu
gebildet. Eine ausgegebene, aber nicht erledigte Quelle ruht eine Stunde (der
ordentliche Durchlauf des Speichers findet sie trotzdem). Geänderte Fassungen
schon eingeordneter Quellen findet ebenfalls der ordentliche Durchlauf.

**Rücksicht.** Der Hintergrund tritt zurück, (a) solange die letzte Eingabe
weniger als 20 s her ist, (b) solange eine Antwort formuliert wird
(`POST /chat`, `POST /api/v1/conversations/{id}/messages` und `…/retry`), und
danach wieder 20 s, (c) solange der Mensch pausiert hat. Als Eingabe zählt eine
verändernde Anfrage aus der Oberfläche und die gedrosselte Meldung
`POST /api/v1/hintergrund/aktiv`, die die Oberfläche bei Taste, Klick,
Scrollen sendet (höchstens alle 5 s, `aktivitaet.ts`). **Abfragen im Takt
(GET) zählen nicht**, sonst hielte die Anzeige „Kingfisher lernt gerade“ das
Lernen an; Anfragen der Mac-Helfer (Kopf `X-Icarus-Token`) auch nicht.

**Ein Modellaufruf zugleich.** Jeder Aufruf eines lokalen Modells geht über die
Ampel (`ModellAmpel`, im Anbieter `OpenAICompatible`). Die Antwort wartet
höchstens auf den einen Aufruf des Hintergrunds, der schon läuft; der
Hintergrund beginnt keinen neuen, solange eine Antwort läuft oder wartet oder
seine Steuerung ihn sperrt. So pausiert er auch mitten in einem Paket. Parallel
nur, wenn beide Modelle laut Katalog (`model_recommendation`) zugleich in den
Speicher des gemeldeten Geräts passen und verschieden sind; unbekannt heißt
nacheinander. Entfernte Anbieter warten nicht an der Ampel.

**Drosselung.** Nach jedem Häppchen ruht der Takt so lange, wie es gedauert hat
(höchstens die Hälfte der Zeit Arbeit; mindestens 2 s, höchstens 30 s). Der
Faden des Zeitplans und der Faden der Akten laufen mit niedriger Priorität
(`setpriority` je Faden unter Linux, also im Container; auf anderen Systemen
nicht, weil `os.nice` den ganzen Prozess und damit die Antworten träfe). Das
Modell selbst läuft in Ollama; es bremst die Ampel, nicht die Priorität.

**Lange Quellen in Häppchen.** Eine Quelle über rund 6.000 Zeichen geht in Abschnitten durch das Modell
([`35-belegte-antworten.md`](35-belegte-antworten.md#lange-quellen-in-abschnitten)). Die Steuerung gibt die Quelle
einmal aus (danach ruht sie eine Stunde, siehe oben); der Arbeitsgang macht sie in Häppchen fertig: Ein Paket ruft
das Modell höchstens `max(8, Quellen je Paket)`-mal auf (`working_memory_worker.ABSCHNITTE_JE_PAKET`), also nie alle
Abschnitte einer 100.000-Zeichen-Quelle auf einmal. Die fertigen Abschnitte merkt sich ein Zwischenstand im Speicher
(nur Stellen und Arten, nie Text); die angefangene Quelle kommt im nächsten Paket vor allem anderen dran, und in den
Bestand wird erst mit dem letzten Abschnitt geschrieben. So gelten Rücksicht und Drosselung unverändert je Paket: Wer
tippt, hält den Hintergrund zwischen zwei Abschnitten an, und nach jedem Paket ruht der Takt. Ein Neustart verliert
den Zwischenstand, nicht den Bestand; die Quelle beginnt dann von vorn. Fehler, Wechsel des Modells oder eine geänderte
Quelle werfen den Zwischenstand der Quelle weg. Die Fortschrittszeile zählt Quellen, nicht Abschnitte: Eine Quelle in
Arbeit steht bis zu ihrem letzten Abschnitt unter „offen“.

**Kein Schlaf wird verhindert.** Kein `caffeinate`, keine Energiesperre.

**Neustart.** Der Zustand, der einen Neustart überdauern muss, steht in
`hintergrund.json` im Datenordner: die Pause des Menschen, der letzte volle
Durchgang, Messpunkte der Rate. Nach dem Start läuft der volle Durchgang nicht
mehr sofort, sondern wenn er fällig ist; ist noch keiner gemerkt, nach fünf
Minuten Anlauf. Die Einordnung geht dort weiter, wo der Bestand steht.

**Sichtbarer Fortschritt.** `GET /api/v1/hintergrund` liefert Zustand (`aus`,
`ohne_modell`, `laeuft`, `wartet`, `pausiert`, `fertig`), Grund, Fortschritt
(erledigt, gesamt, offen), die Schlange je Stufe, die Rate je Stunde und die
Schätzung. Die Rate zählt nur Laufzeit: Messpunkte jede Minute, Lücken über
drei Minuten (Rechner aus, App zu) zählen nicht; unter fünf Minuten Messung
heißt es „noch unklar“. Die Schätzung nimmt an, dass der Rechner an bleibt;
deshalb steht bei mehr als zwei Stunden der Satz „Es geht schneller, wenn der
Rechner heute anbleibt.“, ohne Aufforderung. `POST /api/v1/hintergrund/pause`
und `…/weiter` schalten die Pause. Die Oberfläche erweitert die vorhandene
Karte „Kingfisher lernt gerade“ um die Gesamtzeile; das Sortieren der Mails ist
darin enthalten und erscheint dann nicht doppelt.

**Autostart** ist eine Frage im Assistenten, siehe
[`09-einrichtung.md`](09-einrichtung.md#autostart).

## Prüfungen

- `sidecar/tests/test_hintergrund.py`: Reihenfolge, erledigte Quellen, Ausgabe
  mit Zurückstellen, Pause bei Eingabe und Antwort, Drosselung, Zeitplan
  arbeitet nicht bei Eingabe, Neustart, Anlauf, Ampel (Antwort wartet,
  Hintergrund wartet, parallel nur mit Speicher), lokaler Anbieter an der Ampel,
  Rate ohne Nacht, Schätzung und Satz, Fadenpriorität, Routen, Middleware.
- `sidecar/tests/test_autostart.py`: plist-Inhalt, ohne Antwort keine Datei,
  Aus entfernt nur die eigene Datei, der ganze Weg vom Klick bis zur Datei.
- `sidecar/tests/test_mail_intake.py::test_verlauf_von_neu_nach_alt`.
- `app/kingfisher/tests/hintergrund.test.mjs`: Gesamtzeile, kein Doppel,
  Pause, gedrosselte Meldung, Autostart-Texte.
- Browserprobe `scripts/probe_hintergrund_ui.py --ausgabe DIR`.

Sabotageproben (jeweils die Zusicherung gebrochen, die genannten Tests fielen):
Reihenfolge nach Kennung statt nach Nutzen (4 Tests), Verlauf der Mailaufnahme
wieder alt nach neu (1), Sperre im Zeitplan ignoriert (1), Sperre in der Ampel
und Eingabe in der Middleware ignoriert (2), Anbieter ohne Ampel (1), plist ohne
Antwort geschrieben (2).

## Offen

- **Mac:** Der Helfer `scripts/mac_autostart.py` ist gegen einen temporären
  Ordner geprüft, nicht auf einem Mac. Beim echten Anmelden muss Docker oder
  Colima starten können (`start_mac_app.ensure_engine`); das Protokoll steht
  neben der Konfigurationsdatei (`autostart.log`).
- **Windows und Linux:** kein Autostart-Helfer; die Oberfläche sagt „noch nicht
  verfügbar“. Ein Helfer müsste nur `POST /api/v1/autostart/helfer` sprechen
  (Plattform ergänzen) und einen Eintrag im Autostart anlegen oder entfernen.
- **Speicherregel:** Parallel nur mit Katalogwerten; gemessener Speicherbedarf
  (Ollama `ps`) wäre genauer.
- Lint und Export (M2, Runde 2) gibt es noch nicht; sie gehören als weitere
  Schritte hinter die Einordnung in denselben Zeitplan und fragen dieselbe Sperre.
- Die Bezüge der Akten (ohne Modell) rechnet weiter der eigene Faden
  `akten-bezuege`, nur mit niedriger Priorität, nicht pausiert.
- Einbettungen (`local_embeddings`) gehen nicht über die Ampel; sie sind klein.
- Ein von außen übergebener Agent (nur in Prüfungen) hat beim Einbau noch keinen
  Zeitplan; dort bleibt es beim alten Verhalten.
