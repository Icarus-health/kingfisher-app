# Hintergrund ohne Nacht

Stand: 8. Oktober 2026. Gehört zu M2 aus [`41-zielbild.md`](41-zielbild.md)
(Abschnitt „Hintergrundarbeit ohne Nacht“).

Viele Menschen schalten den Rechner nachts aus. „Nachts“ war nie die Bedingung
der Hintergrundarbeit, nur der bequemste Fall. Dieses Dokument hält zuerst fest,
was es heute an Hintergrundarbeit gibt, und dann die neue Regel.

## Akku und geschlossene App

Die Mac-App ab 1.0.6 meldet nach erfolgreichem Start und dann alle 30 Sekunden
nur ihre Energiequelle an den eigenen lokalen Dienst. Auf Akku halten die
älteren Mails und jede Modellarbeit an (Einordnung, Lagen, Zusagen, Verdichtung,
KI-Filter, Texterkennung); neue Post, der Kalenderabgleich und die geplante
Sicherung laufen ohne Modell weiter, genau wie in der Pause des Menschen
(siehe unten „Pause und Akku“; bis Oktober 2026 hielt Akku alles an).
Am Netzteil läuft alles mit den bisherigen Ruhepausen weiter. Eine ausdrücklich
gewählte Pause bleibt auch dann erhalten. Lesen, Aufgaben und direkte Anfragen
bleiben erreichbar; bewusst ausgelöste Modellanfragen können weiterhin Energie
verbrauchen. Bereits laufende Modellanfragen werden nicht mitten in ihrer
Antwort abgebrochen.

Die Messung muss höchstens 90 Sekunden alt sein. Fehlt sie, gilt das wie Akku;
eine alte Netzteilmeldung gilt nach einem Neustart nicht weiter. Die Pflicht zur
Hostmessung bleibt nach dem ersten Bericht gespeichert. Ein eigenständiger
Server ohne Mac-Geräteprofil und ohne bisherige Hostmeldung bleibt unverändert.
Der Wartegrund erscheint in der Fortschrittsanzeige, ohne erfundenen
Fertigstellungstermin. Eine Energiesperre ersetzt weder eine manuelle Pause noch
eine Modellfreigabe.

Fenster schließen beendet die App nicht zwingend; auch „Kingfisher beenden“
beendet den Docker-Dienst und andere lokale Helfer nicht. Ohne neue Meldungen
wartet der geschützte Zeitplan nach Ablauf der 90 Sekunden. Docker selbst,
andere Container und separat laufende Quellenhelfer sind damit nicht angehalten.
Die Regel ist daher kein Versprechen eines vollständig stromlosen Dienstes.

Die neue Meldung braucht das neue native App-Bündel. Die Mindest-App-Version
der Fassung 1.0.6 verhindert, dass der normale Updater nur den Backend-Teil in
eine ältere App übernimmt. Die bisher installierte 1.0.5 erhält den Schutz erst
durch eine spätere vollständige Aktualisierung. Der Batterieverbrauch muss danach
noch in einem echten Arbeitsdurchgang verglichen werden.

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

Auch die Bestandsaufnahme selbst (welche Nummern es im Postfach gibt) geht bei
IMAP von oben nach unten, in Fenstern von 200 Nummern
(`MailConnector.inventory_page(…, absteigend=True)`). Vorher lief sie
aufsteigend: Bei 5.000 Mails waren zuerst nur die ältesten Nummern bekannt, und
„höchste UID zuerst“ wählte unter diesen. Offen ist immer
(`scan_uid`, `upper_uid`]; `upper_uid` sinkt mit jedem Fenster und wird erst
zusammen mit den gefundenen Nummern gespeichert. Ein Abbruch wiederholt also
das Fenster, statt es zu überspringen; eine vor dem Update aufsteigend
begonnene Aufnahme (unten bis `scan_uid` erfasst) geht ohne Lücke und ohne
Doppelung weiter. Microsoft (Laufnummern der Delta-Abfrage) bleibt
aufsteigend, weil seine Nummern keine dichte Reihe sind. Die Gegendruck-Grenze
(höchstens 200 erfasste, noch nicht eingeordnete Altmails) gilt unverändert.

Die Schlange braucht keinen eigenen Speicher. Was offen ist, steht in
`working_memory_sources`; die Reihenfolge wird daraus höchstens jede Minute neu
gebildet. Eine ausgegebene, aber nicht erledigte Quelle ruht eine Stunde (der
ordentliche Durchlauf des Speichers findet sie trotzdem). Geänderte Fassungen
schon eingeordneter Quellen findet ebenfalls der ordentliche Durchlauf.

**Rücksicht.** Der Hintergrund tritt zurück, (a) solange die letzte Eingabe
weniger als 20 s her ist, (b) solange eine Antwort formuliert wird
(`POST /chat`, `POST /api/v1/conversations/{id}/messages` und `…/retry`), und
danach wieder 20 s, (c) solange der Mensch pausiert hat (dann nur mit den
älteren Mails und der Modellarbeit, siehe „Pause und Akku“). Als Eingabe zählt eine
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

### Pause und Akku

„Pausieren“ auf Heute (Karte „Kingfisher lernt gerade“, Titel dann
„Verarbeitung pausiert“, Knopf „Weiter“) hielt bis Oktober 2026 alles an: neue
Post, Kalenderabgleich, geplante Sicherung, die Übernahme des Mac-Kalenders.
Ein Stabschef, der in der Pause die Post von heute liegen lässt, verliert etwas.
Jetzt gilt für die Pause und ebenso für den Akkubetrieb (und eine fehlende
Energiemeldung, die wie Akku zählt; `hintergrund.NEUE_POST_WEITER`):

| Hält an | Läuft weiter, ohne Modell |
|---|---|
| ältere Mails (die Spur „Verlauf“ der Aufnahme samt ihrer Bestandsaufnahme), Empfänger älterer Mails nachtragen | neue Post (Spur „neu“), im Takt der Aufnahme |
| jede Modellarbeit: Einordnung, Uploads, Lagen, Zusagen, Verdichtung, Zusammenfassung, KI-Filter, Texterkennung | Kalenderabgleich (Kalenderquellen und Übernahme des Mac-Kalenders) |
| der übrige volle Durchgang: Ordner, öffentliche Quellen, Beobachtungen | geplante Sicherung (höchstens alle vier Stunden) |

Unverändert halten **alles** an: knapper Speicherplatz (`_capacity_gate`),
Speicherdruck des Macs, eine frische Meldung der App ohne Speicherlast
(`speicher_unbekannt`) und die Rücksicht auf den Menschen (Eingabe, Antwort);
`Steuerung.sperre_ohne_modell()` sagt das. Speicher geht dabei der
Energiequelle vor (`host_power.reason`): Akku mit Speicherdruck oder mit
unbekannter Speicherlast hält alles an, ebenso am Netzteil. Nur ganz ohne
frische Meldung (App geschlossen oder eben gestartet) gilt
`energie_unbekannt`, das wie Akku nur ältere Mails und Modellarbeit anhält;
sonst stünde bei geschlossener App auch die neue Post.

Wird mitten in einem Paket pausiert, wartet der nächste Modellaufruf nicht an
der Ampel bis „Weiter“, sondern gibt den Faden frei (`BackgroundInterrupted`,
wie bei Akku); Sperren und Wiederherstellungsgrenze werden frei, der nächste
Takt ist schon der leichte. Anbieter, die nicht über die Ampel laufen, fragen
zwischen den Quellen `permitted()`, und das enthält jetzt
`hintergrund.modellarbeit_frei` (im Faden des Zeitplans: nicht pausiert, keine
Energie- oder Speichersperre; ein ausdrücklicher Lauf bleibt erlaubt). Auch
der volle Durchgang prüft vor jedem Schritt (`Scheduler._zwischen_schritten`,
`hintergrund.unterbrechen_wenn_gesperrt`) und gibt den Faden frei, statt die
übrigen Schritte leer laufen zu lassen; unter „Was zuletzt lief“ steht dann
kein „… nach geänderter Freigabe gestoppt“. Der Zeitplan ruft dann je Takt
`Scheduler._leichter_takt`: neue Post über `Intake.step(nur_neu=True)`,
Kalender und Sicherung über `_leichter_lauf` im Abstand des Zeitplans. Der
volle Durchgang bleibt dabei fällig (`_last_at` rückt nicht vor) und läuft nach
„Weiter“.

Nach einem teuren Paket ruht der Hintergrund (Drosselung, die vierfache Dauer
des Pakets, auch wenn es abgebrochen wurde). Diese Ruhe gilt nur der
Modellarbeit und dem vollen Durchgang: Der leichte Takt (neue Post, Kalender,
Sicherung) läuft auch in ihr, sonst hieße ein 30-Minuten-Paket zwei Stunden
ohne neue Post. „Weiter“ (`Scheduler.ruhe_aufheben`), „Erneut versuchen“ und
eine neue Anmeldung (`aufnahme_wecken`) heben die Ruhe auf; ein Takt oder eine
Meldung der App weckt nur. Ein in der Pause begonnenes Einlesen merkt sich nur die Grenze für
neue Post (`Intake._grundlinie`); die älteren Mails kommen nach der Pause ohne
Lücke. Neue Post wird nur vorgemerkt, eingeordnet wird sie nach der Pause.

Ohne Modell heißt auch: keine Texterkennung. Eine neue Mail mit gescanntem
Anhang wartet deshalb, wenn ein OCR-Modell da ist, statt ohne Text gespeichert
zu werden (`zurueckstellen`, zählt nicht als gescheitert). Das gilt auch für
eine PDF, die nur teilweise Text hat, etwa Seite 1 getippt und Seite 2
gescannt (`anhaenge.wartet_auf_texterkennung`: Seiten ohne Text); Seiten
jenseits der Lesegrenze sind kein Grund zu warten. Die Mail wird in der Pause
nicht immer wieder heruntergeladen: Sie trägt `grund='zurueckgestellt'` und
ruht bis zum ersten vollen Durchgang nach Pause oder Akku, der sie sofort
freigibt; in einer langen Pause kommt sie höchstens alle sechs Stunden wieder
dran (`mail_intake.ZURUECKGESTELLT_S`). Ist der KI-Filter für Post an, prüft
die lokale KI jede neue Mail vor dem Speichern; dann wartet in der Pause auch
die neue Post, und der Satz sagt es.

Microsoft (Graph) trennt neue von alter Post erst, wenn die erste
Delta-Auflistung eines Ordners fertig ist; bis dahin gilt alles als älter.
Diese Auflistung geht deshalb in der Pause weiter, aber nur mit Kennung und
Eingangszeit je Mail (`MicrosoftPost._fortschreiben`): kein Inhalt, kein
Eintrag für ältere Mails, kein Modell. Ohne sie käme bei einem in der Pause
verbundenen Konto nie neue Post an. Die Inhalte der älteren Mails holt die
Aufnahme erst nach der Pause.

Ein Update setzt die älteren Mails nicht fort: Die Pause steht in
`hintergrund.json` und gilt nach jedem Neustart; nach einem Neustart fehlt
zudem die Energiemeldung, was wie Akku zählt.

Was der Mensch liest (eine Aussage je Postfach, `mail_stand.nur_neue_post_satz`,
und `GRUND_TEXT`):

* Grund in der Karte (`Steuerung.grund_text`, auch unter Gedächtnis →
  Verarbeitung): „Pausiert. Neue Post und Termine kommen weiter an; ältere
  Mails und das Lernen warten, bis du „Weiter“ wählst.“ (auch ohne Modell, wenn
  nur Mails eingelesen werden); im Akkubetrieb „… warten, bis der Mac am
  Netzteil ist.“ Der Satz verspricht nur, was wirklich läuft: Hält zugleich
  Speicherplatz, Speicherdruck oder eine fehlende Speichermeldung alles an,
  heißt es „Pausiert, bis du „Weiter“ wählst.“ mit diesem Grund; ist der
  KI-Filter an, „Termine kommen weiter an; neue Post, ältere Mails und das
  Lernen warten …, denn die lokale KI prüft neue Post vor dem Speichern.“
* Je Postfach: „Postfach Privat: Neue Post wird weiter geholt; ältere Mails
  sind pausiert (bereits 120 von 4.300 Mails gelesen). Auf Heute geht es mit
  „Weiter“ weiter.“ Im Akkubetrieb „… ältere Mails warten, bis der Mac am
  Netzteil ist (…).“ Mit KI-Filter „Neue Post und ältere Mails sind pausiert,
  weil die lokale KI neue Post vor dem Speichern prüft (…).“ Bei Speicherdruck
  wird nichts versprochen (bisheriger Satz).
* Im Assistenten: „Die älteren Mails hältst du jederzeit auf Heute mit
  „Pausieren“ an; neue Post kommt weiter.“

Ganz anhalten, auch neue Post, lässt sich das Einlesen weiter je Postfach
(Für Techniker → Zeitplan und Hintergrund, „Einlesen pausieren“) oder mit dem
Schalter „Mails regelmäßig abrufen“.

### Neue Postfachkennung

Vergibt der Server die Nummern eines Ordners neu (UIDVALIDITY; bei Microsoft
geht die Ablage der Nummern verloren), beginnt die Bestandsaufnahme von vorn.
Früher legte sie dabei jede schon gespeicherte Mail ein zweites Mal an, und
eine ausgeschlossene Mail kam zurück. Jetzt gleicht die Aufnahme vor dem
Anlegen ab (`mail_ingestion._dieselbe_mail_im_konto`): gleiche Message-ID im
selben Konto (über den kontogebundenen Kopfindex `episode_mail_headers`),
gleiche Prüfsumme des Textes, dazu gleicher Absender, Betreff und Zeitpunkt.
Trifft das auf eine Quelle zu, die die Aufnahme unter einer **früheren**
Generation **desselben Ordners** geholt hat (`Intake._frueher_geholt`), zeigt
der neue Eintrag auf diese Quelle (Status „schon bekannt“), statt eine zweite
anzulegen; eine ausgeschlossene bleibt ausgeschlossen.

Jede alte Quelle geht dabei an höchstens eine neue UID: Zeigt schon eine andere
UID der aktuellen Generation desselben Ordners auf sie, prüft die Aufnahme die
nächste passende alte Quelle, sonst legt sie eine eigene an. Lagen zwei gleiche
Mails unter der alten Kennung, findet so jede neue UID ihre eigene; liegt eine
Mail nach dem Wechsel zweimal da, verknüpft die erste, die zweite wird eine
eigene Quelle. Dieselbe Mail in einem anderen Ordner (der seine eigene Kennung
hat) ist keine frühere Fassung; ordnerübergreifend verknüpft nur eine Kennung
des Anbieters.

Ein Ziel für Aktionen beim Anbieter (`local_mail_routes._remote_uid`) nennt nur
die UID aus der aktuellen Generation des Ordners. Hat die neue
Bestandsaufnahme die Mail noch nicht wiedergefunden, gibt es keine Aktion statt
einer veralteten UID, die auf eine andere Mail zeigen könnte.

Bewusst nicht verknüpft wird: gleiche Message-ID mit anderem Text, Absender,
Betreff oder Zeitpunkt (die Message-ID ist ein fremdes Kopffeld); eine Mail ohne
Message-ID; dieselbe Mail in einem anderen Konto; und zwei Nachrichten
derselben Generation (zwei UIDs, gleicher Inhalt). Diese bleiben zwei Quellen
mit je eigenem Beleg, wie `test_mail_ingestion.py::test_mail_identity_and_versions_keep_independent_evidence`
es festhält. Der regelmäßige Abruf ohne Aufnahme (`sync_account`) führt keine
Generationen und verknüpft deshalb nicht.

## Prüfungen

- `sidecar/tests/test_hintergrund.py`: Reihenfolge, erledigte Quellen, Ausgabe
  mit Zurückstellen, Pause bei Eingabe und Antwort, Drosselung, Zeitplan
  arbeitet nicht bei Eingabe, Neustart, Anlauf, Ampel (Antwort wartet,
  Hintergrund wartet, parallel nur mit Speicher), lokaler Anbieter an der Ampel,
  Rate ohne Nacht, Schätzung und Satz, Fadenpriorität, Routen, Middleware.
- `sidecar/tests/test_autostart.py`: plist-Inhalt, ohne Antwort keine Datei,
  Aus entfernt nur die eigene Datei, der ganze Weg vom Klick bis zur Datei.
- `sidecar/tests/test_mail_intake.py::test_verlauf_von_neu_nach_alt`.
- `sidecar/tests/test_pause_neue_post.py`: nur neue Post in der Aufnahme,
  Grundlinie, Zurückstellen ohne Texterkennung, Zeitplan in Pause, Akku und
  fehlender Energiemeldung, Gegenbeispiele Speicherdruck, Speicherplatz und
  Eingabe, „Weiter“, Neustart nach dem Update, der ganze Weg mit der
  IMAP-Attrappe samt Sätzen, teilweise gescannte PDF, keine Wiederholung
  zurückgestellter Mails in der Pause; dazu
  `test_microsoft_graph.py::test_in_der_pause_listet_outlook_nur_kennungen_und_holt_neue_post`;
  bewusst angepasst
  `test_host_power.py::test_scheduler_does_not_start_intake_or_models_until_fresh_ac_and_normal_memory`
  und `test_mac_calendar_background_gate.py`. Oberfläche:
  `app/kingfisher/tests/pause-neue-post.test.mjs`; Browserprobe
  `scripts/probe_hereinholen_ui.py`.
- `sidecar/tests/test_mail_intake.py` (neue Postfachkennung, Gegenbeispiele,
  eine alte Quelle je neuer UID, anderer Ordner),
  `sidecar/tests/test_neue_postfachkennung.py` (API gegen die IMAP-Attrappe) und
  `sidecar/tests/test_local_mail_routes.py::test_remote_uid_gilt_nur_fuer_die_aktuelle_ordnergeneration`.
- `sidecar/tests/test_bestand_neueste_zuerst.py`: großes Postfach neueste
  zuerst, Fenster von oben nach unten, Abbruch und Neustart ohne Lücke und
  Doppelung, aufsteigend begonnene Aufnahme nach dem Update.
- `app/kingfisher/tests/hintergrund.test.mjs`: Gesamtzeile, kein Doppel,
  Pause, gedrosselte Meldung, Autostart-Texte.
- Browserprobe `scripts/probe_hintergrund_ui.py --ausgabe DIR`.

Sabotageproben (jeweils die Zusicherung gebrochen, die genannten Tests fielen):
Reihenfolge nach Kennung statt nach Nutzen (4 Tests), Verlauf der Mailaufnahme
wieder alt nach neu (1), Bestandsaufnahme wieder aufsteigend (3), Fenster unter
die alte untere Grenze (2), Zeiger rückt bei gescheiterter Suche weiter (2),
absteigender Zeiger nicht gespeichert (2), Abgleich bei neuer Postfachkennung
abgeschaltet (3), Prüfsumme, Absender, Betreff oder Zeitpunkt nicht verglichen
(je 1), jede gleiche Mail im Konto, dieselbe Generation oder ein anderer Ordner
als „früher“ (je 1), eine alte Quelle an zwei neue UIDs (2), Aktionsziel aus
einer alten Generation (1); zur
Pause: kein leichter Takt (6), Akku hält auch neue Post an (7), Eingabe zählt
in der Pause nicht (2), ältere Mails trotz Pause geholt (1), Bestandsaufnahme
trotz Pause (2), leichter Lauf rückt den vollen Durchgang vor (4), Kalender und
Sicherung in jedem Takt (3), Texterkennung ohne Modellfreigabe (1), teilweise
gescannte PDF ohne Warten gespeichert (1), Zurückgestelltes wieder alle zehn
Minuten (1), voller Durchgang gibt Zurückgestelltes nicht frei (1),
Bestandsaufnahme älterer Microsoft-Mails in der Pause (1), KI-Filter in
der Pause nicht übersprungen (1), Satz verspricht neue Post bei Speicherdruck
(1), Mac-Kalender nach alter Sperre (3), Grund der Pause nur mit Modell (1),
Grundlinie fehlt (2), in der Oberfläche alter Satz im Assistenten und „Einlesen
pausiert“ (je 1); Sperre im Zeitplan ignoriert (1), Sperre in der Ampel
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
