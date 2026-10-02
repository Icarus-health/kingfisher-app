# Fremdprobe 2: Ersteinrichtung und erste Stunde

Prüfprotokoll, 1. Oktober 2026. Stand: Commit `7fa2d60`
(Branch `dobby/youthful-bardeen-pf69mq`).

## 1. Auftrag und Rolle

Der Prüfer spielt einen Menschen ohne technisches Wissen, der Kingfisher zum
ersten Mal einrichtet und das Produkt nie gesehen hat. Gelesen wurde nur
`README.md`. Nicht gelesen wurden `docs/`, Quellcode, Tests, Commit-Nachrichten
und frühere Fremdproben. Was die Oberfläche nicht erklärt, ist ein Befund.

Gemessen wird:

1. die Zeit vom ersten Aufruf bis „Kingfisher ist eingerichtet und ich sehe
   mein Briefing“, mit realistischer Bedienzeit;
2. die erste Stunde: fragen, Quelle öffnen, Antwort als falsch melden,
   Vorschlag annehmen, Akten, Einstellungen (vorne und „Für Techniker“), Kreis,
   Geburtstag;
3. jeder Moment, an dem der Prüfer etwas wissen musste, nicht wusste, was
   passiert, oder sich geärgert hat.

Schweregrade: **blockiert** (kommt nicht weiter oder glaubt fälschlich, es
funktioniere), **verwirrt**, **stört**.

## 2. Aufbau (technisch, nicht Teil der Probe)

| Teil | Umsetzung |
|---|---|
| Oberfläche | `app/kingfisher`: `npm ci && npm run build`, ausgeliefert vom Sidecar |
| Sidecar | `create_app()` unter uvicorn auf `127.0.0.1:8890`, frisches `ICARUS_DATA_DIR`, `KINGFISHER_TIMEZONE=Europe/Berlin` |
| Lokales Modell | eigene HTTP-Attrappe auf `127.0.0.1:11434` (Modellliste, `/api/show`, `/api/pull`, `/api/embed`, `/v1/chat/completions`), nach dem Vorbild der Attrappe in `scripts/probe_fremdprobe_ui.py` |
| Postfach | `sidecar/tests/imap_attrappe.py` (Modus `annehmen`, leeres Postfach) auf `127.0.0.1:9993`, Zertifikat über `SSL_CERT_FILE` |
| Browser | Chromium `/opt/pw-browsers/chromium-1194` mit Playwright, Breiten 1280, 768 und 390 px |
| Daten | nur synthetisch: Postfach `lena.probe@example.org`, eine selbst geschriebene Besprechungsnotiz (`Besprechung-Atlas.md`, Anna Berg, Tom Weiler) |

Docker und `make start` wurden nicht benutzt; der Startweg aus dem README ist
deshalb nur gelesen und bewertet, nicht gemessen.

Hinweise zur Attrappe, damit kein Befund falsch zugeordnet wird:

* Der erste Ladeversuch im Schritt „Dieser Rechner“ scheiterte, weil die
  Attrappe geladene Modelle noch nicht in ihrer Liste führte. Nach einer
  Anpassung der Attrappe lief der zweite Versuch durch. Gewertet wird nur, wie
  die Oberfläche den Fehlschlag darstellt.
* Die Attrappe beantwortet Einordnungsaufträge nicht sinnvoll. Dass im
  Hintergrund nichts einsortiert wurde und die Notiz keine Akte für Anna Berg
  erzeugte, ist **kein** Befund. Der Gedächtnisvorschlag im Gespräch wurde mit
  einem von der Attrappe gelieferten Werkzeugaufruf erzeugt.
* Inhalte von Modellantworten werden nicht bewertet.
* Das IMAP-Postfach der Attrappe ist leer.

Bildschirmfotos liegen im Scratchpad der Sitzung, nicht im Repository; die
Dateinamen stehen in der Befundtabelle.

## 3. Startweg laut README

Das README verlangt: „Voraussetzungen: Git, Docker mit Compose, `make` und
`openssl`. Docker muss laufen.“ und danach `git clone …`, `cd Kingfisher`,
`make start` im Terminal. Ein Mensch ohne technisches Wissen kommt hier ohne
Hilfe nicht weiter (Befund 1). Der Rest der Probe beginnt deshalb beim ersten
Aufruf von `http://127.0.0.1:8890/today`, wie das README ihn nennt.

## 4. Zeit bis zum ersten Briefing

Die Zeiten sind realistische Bedienzeiten (Lesen jeder Karte, Tippen,
Warten), nicht die Laufzeit des Skripts. Wo der Prüfer etwas außerhalb der
Oberfläche wissen musste, steht „nachgeschlagen“.

| Nr. | Schritt | Was geschah | Zeit |
|---|---|---|---|
| 1 | Willkommen, „Wie heißt du?“ | Lesen, „Lena“ tippen, Weiter | 0:30 |
| 2 | Mail: Adresse | `lena.probe@example.org` getippt; Anbieterliste erscheint, `example.org` ist nicht dabei | 0:50 |
| 3 | Mail: Ausweg über Einstellungen | Link „Einstellungen → Zugänge“, Assistent verlassen, „+“ bei Postfächer gesucht, Adresse erneut getippt | 1:00 |
| 4 | Mail: Servereinstellungen | IMAP-Server und -Port verlangt; „Die Angaben stehen auf der Hilfeseite deines Mailanbieters.“ **nachgeschlagen** (Techniker-Werte der Attrappe eingetragen); Passwort, „Lokal speichern“ | 4:30 |
| 5 | Zurück in den Assistenten | „Einrichtung fortsetzen“, landet richtig bei Kalender | 0:15 |
| 6 | Kalender | Beide Wege gelesen; „Adresse deines Kalenders“ bzw. „Geheime Adresse im iCal-Format“ unbekannt, übersprungen | 1:15 |
| 7 | Dieser Rechner | Karte gelesen, „Laden und einrichten“; erster Versuch scheitert (Attrappe), zweiter „Alles eingerichtet und geprüft.“ | 0:40 Bedienung + Laden |
| 7a | Laden der Modelle | Oberfläche: „etwa 14 GB, je nach Internetleitung 4 bis 20 Minuten“. In der Probe 25 s. Gerechnet mit der Mitte der Angabe | 10:00 |
| 8 | Freigaben | Drei Karten gelesen, Wetter aufgeklappt, übersprungen | 1:10 |
| 9 | Fertig | Karte gelesen, „Zum Briefing“ | 0:50 |
| 10 | Briefing | Briefing sichtbar (leer: keine Mails, kein Kalender) | 0:30 |

**Summe Bedienung ohne Modellladen: 11:40 min.**
**Mit Modellladen laut Oberfläche: 15:40 bis 31:40 min, mittlerer Fall 21:40 min.**
Bei einer Leitung mit 50 Mbit/s dauern 14 GB rechnerisch eher 37 Minuten.
Der Start im Terminal (README) ist darin nicht enthalten.

### Urteil zum 15-Minuten-Kriterium

**Nicht erfüllt.** Gründe:

1. Schon der Start setzt Terminal, Docker, `make` und `openssl` voraus
   (Befund 1). Das ist „nachgeschlagen“, bevor die Oberfläche überhaupt
   erscheint.
2. Ein Postfach mit eigener Domain lässt sich nur mit IMAP-Server und -Port
   einrichten, die der Nutzer nachschlagen muss (Befund 2). Der Kalender
   verlangt eine Adresse, die ebenfalls niemand im Kopf hat (Befund 5).
3. Das einmalige Laden der Modelle allein dauert laut Oberfläche 4 bis 20
   Minuten; schon im günstigen Fall liegt die Gesamtzeit über 15 Minuten.
4. Das Briefing am Ende ist leer, weil weder Mail noch Kalender sichtbar etwas
   geliefert haben; ob die Mail überhaupt funktioniert, kann der Nutzer nicht
   erkennen (Befund 17).

Ohne eigene Domain (ein Anbieter aus der Liste) und mit schnellem Netz wäre
die reine Bedienung in etwa 7 Minuten zu schaffen. Das Laden der Modelle und
der Start im Terminal bleiben die Hürden.

## 5. Erste Stunde

| Was | Ergebnis |
|---|---|
| Datei aufnehmen | Einstellungen → Zugänge → „Dateien verwalten“ → Datei auswählen → „Datei als Quelle aufnehmen“. Klare Rückmeldung „Datei als Quelle aufgenommen.“ |
| Frage stellen | „Was hat Anna zuletzt geschrieben?“ im Feld auf Heute; öffnet ein Gespräch mit Antwort (Inhalt nicht bewertet) |
| Quelle öffnen | Nur „Gesprächsquelle ansehen“ unter der eigenen Frage; unter der Antwort kein Beleg (Befund 13) |
| Als falsch melden | „Stimmt nicht?“ → „Falsch“ → „Richtig wäre …“ → „Melden“ → „Gemerkt.“ In „Für Techniker → Rückmeldungen“ wiedergefunden |
| Vorschlag annehmen | „Merke dir bitte: …“ im Gespräch → Karte „Gedächtnisvorschlag“ mit Zitat, „Bestätigen“ → „Als Wissen bestätigt.“ mit „Als falsch widerrufen“ |
| Akten | Gedächtnis → Menschen → Anna Berg → Akte mit „Bestätigter Wissensstand“ |
| Kreis | In der Akte nicht zu finden (Befund 19) |
| Geburtstag / Wiederkehrendes | Bestätigter Geburtstag erscheint weder im Kalender noch auf Heute noch in der Akte unter „anstehenden Terminen“ (Befund 20) |
| Einstellungen vorne | Zugänge, Was Kingfisher darf, Kingfisher und du, Sicherung: verständlich; Name aus dem Assistenten übernommen |
| Für Techniker | Modelle, Zeitplan, Rückmeldungen, Stand aller Bereiche geöffnet |
| Falsches Passwort (zweites Postfach) | Anmeldung wird geprüft und abgelehnt; die Meldung steht aber weit oben (Befund 4) |
| 768 und 390 px | Kein waagerechtes Scrollen auf Heute, Einstellungen, Gespräch, Akte, Assistent, Aufgaben; Befund 25 |

## 6. Befunde

| Nr. | Schwere | Seite / Element | Wortlaut | Erwartet | Bild |
|---|---|---|---|---|---|
| 1 | blockiert | README, „Lokal starten“ | „Voraussetzungen: Git, Docker mit Compose, `make` und `openssl`. Docker muss laufen.“ … `make start` | Ein Programm zum Doppelklicken oder ein Installationsweg ohne Terminal; die Mac-App setzt laut README „eine bereits eingerichtete lokale Docker-Instanz“ voraus | – |
| 2 | blockiert | Assistent, Schritt Mail | „Ist dein Anbieter nicht dabei, richtest du das Postfach mit den Angaben deines Anbieters unter Einstellungen → Zugänge ein.“ dort: „IMAP-Server“, „IMAP-Port“, „Die Angaben stehen auf der Hilfeseite deines Mailanbieters.“ | Kingfisher findet den Server für eine eigene Domain selbst (oder probiert die üblichen Namen durch) und bleibt dabei im Assistenten | 03-mail-adresse-1280, 06-postfach-ausgefuellt-1280 |
| 3 | stört | Einstellungen → Zugänge, „Postfach hinzufügen“ | Feld „E-Mail-Adresse“ leer | Die eben im Assistenten getippte Adresse steht schon drin | 05-postfach-neu-1280 |
| 4 | blockiert | Einstellungen → Zugänge, „Lokal speichern“ mit falschem Passwort | „Vertippt2 hat die Anmeldung abgelehnt: Adresse oder Passwort stimmen nicht. Wiederholen“, klein und rot ganz oben auf der Seite, etwa 1300 px über dem Knopf | Die Meldung direkt am Knopf bzw. am Passwortfeld; am Knopf passiert sichtbar nichts. Außerdem: „Vertippt2“ ist der Name, den der Nutzer dem Postfach gab, nicht der Anbieter, der ablehnt | 26-falsches-passwort-1280, 26b-falsches-passwort-1280 |
| 5 | verwirrt | Assistent, Schritt Kalender | „Für diesen Anbieter brauche ich die Adresse deines Kalenders.“ Feld „https://…“ | Ein Hinweis, wo diese Adresse steht, oder Kingfisher leitet sie aus dem Postfach ab; sonst Hinweis, dass man den Schritt ohne Nachteil überspringen kann | 08-kalender-1280 |
| 6 | verwirrt | Assistent, Dieser Rechner | Vorher „Einmal laden: etwa 14 GB, je nach Internetleitung 4 bis 20 Minuten.“, nach dem Fehlschlag „etwa 1,2 GB, je nach Internetleitung 1 bis 2 Minuten.“ | Eine Angabe, die stimmt; wenn sich die Menge ändert, ein Satz warum | 08c-dieser-rechner-1280, 09b-laden-1280 |
| 7 | verwirrt | Assistent, Dieser Rechner nach Fehlschlag | „Fast alles ist eingerichtet. Wo etwas fehlt, steht hier darunter, was du tun kannst.“ während alle drei Karten „Prüfung nicht bestanden“ zeigen; „Deine Fragen beantworten: Das geladene Modell hat die Prüfung nicht bestanden …“ steht doppelt; „Prüfung nicht bestanden“ steht schon 4 Sekunden nach dem Klick auf allen Karten | „Nichts ist eingerichtet“ und ein Knopf „Noch einmal versuchen“; jede Meldung einmal | 09b-laden-1280 |
| 8 | stört | Assistent, Fertig | „Kingfisher liest deine Mails und Termine.“ | Ohne verbundenen Kalender: nur „deine Mails“ | 13-fertig-1280 |
| 9 | stört | Briefing, Kopf | „Do, 01. Oktober 2026 · UTC“ | Keine Zeitzone, oder die eingestellte („Zeitzone: Europe/Berlin“ unter Kingfisher und du) | 14-briefing-1280 |
| 10 | stört | Briefing, Kacheln | Orange Zähler „0“ bei „Heutige Top-Prioritäten“ und „Relevantes aus der Welt“ | Bei null kein Signalfarbenzähler | 14-briefing-1280 |
| 11 | stört | Heute | Uhrzeit zweimal (Seitenleiste und oben rechts); Hinweis „⌘ K“ auch unter Linux und auf dem Telefon | Eine Uhr; Tastenhinweis passend zum Gerät oder gar keiner | 15b-quellen-nicht-verfuegbar-1280, 35-heute-390 |
| 12 | stört | Heute → Frage → Gespräch, „Stimmt nicht?“ | Nach „Melden“ nur „Gemerkt.“ | Ein Satz, was mit der Meldung geschieht (steht nur unter Für Techniker → Rückmeldungen) | 21-gemeldet-1280 |
| 13 | verwirrt | Gespräch, Antwort | Unter der eigenen Frage „Gesprächsquelle ansehen“, das die eigene Frage zeigt („So hat Kingfisher deine Frage gespeichert …“); unter der Antwort kein Beleg; links „Keine aktuell verwendbaren Gedächtnispunkte.“ | Unter der Antwort sichtbar, ob und worauf sie sich stützt („ohne Beleg“ deutlich kennzeichnen) | 19-frage-anna-1280, 20-gespraechsquelle-1280 |
| 14 | stört | Gespräch, Systemmeldung | „Ich habe einen Gedächtnisvorschlag vorbereitet. Bitte bestätige ihn nur, wenn er stimmt.“ mit „Stimmt nicht?“ darunter | „Stimmt nicht?“ nur unter Antworten, nicht unter Hinweisen des Programms | 31-vorschlag-im-gespraech-1280 |
| 15 | verwirrt | Heute, Tageszeile | „Im Hintergrund hat es 3-mal gehakt (Einordnung, Zusagen und Verdichtung)“ | Alltagssprache und was der Nutzer tun soll oder dass er nichts tun muss (Ursache war die Attrappe; bewertet ist nur der Wortlaut) | 27-heute-nach-sortieren-1280 |
| 16 | verwirrt | Gedächtnis → Verarbeitung & Verlauf | „Aktiv mit qwen3.5:9b.“ direkt gefolgt von „Wenn du sie aktivierst, werden …“; Kacheln „Prüflauf durchgeführt“, „Teilweise geprüft“, „Prüfung fehlgeschlagen 2“; „Gefundene Angaben stehen im Gespräch zur Verfügung, ohne Einzelbestätigung.“ | Ein Satz zum Stand in Alltagssprache; kein „wenn du aktivierst“, wenn es schon aktiv ist | 23-gedaechtnis-verarbeitung-1280 |
| 17 | verwirrt | Mailstatus an mehreren Stellen | Heute dauerhaft „Deine Mails werden gelesen: bisher 0 gefunden“; Für Techniker „Privat: noch nicht abgerufen“ und „Noch kein erfolgreicher automatischer Abruf bestätigt.“, obwohl im Assistenten „Mails von Privat jetzt und danach regelmäßig einlesen“ angehakt war und Nachrichten → „Aktualisieren“ gedrückt wurde | Eine Aussage: „Postfach Privat abgerufen um 14:43, keine Mails“ oder der Grund, warum nicht. (Das Postfach der Attrappe ist leer; ob der Abruf lief, kann der Nutzer nicht erkennen) | 15b-quellen-nicht-verfuegbar-1280, 37-nachrichten-aktualisiert-1280 |
| 18 | stört | Nachrichten, „Aktualisieren“ | Nach dem Klick keine Rückmeldung, Liste unverändert „Keine Nachrichten in dieser Ansicht.“ | „Gerade abgerufen, nichts Neues“ oder ein Grund | 37-nachrichten-aktualisiert-1280 |
| 19 | verwirrt | Einstellungen → Kingfisher und du, „Kreis“ / Akte Anna Berg | „Für jede Person schlägt Kingfisher einen Kreis vor … Du bestätigst ihn mit einem Klick in ihrer Akte.“ In der Akte kein Kreis, kein Vorschlag, keine Wahl | In der Akte ein Kreis-Vorschlag oder eine Wahl, auch wenn noch wenig bekannt ist | 24-einst-kingfisher-du-1280, 33-akte-anna-1280 |
| 20 | verwirrt | Kalender, Heute, Akte | Bestätigt: „Anna Berg hat am 12. Oktober Geburtstag.“ Kalender Oktober leer; Akte „Noch keine Bitten, Zusagen, Angaben, Aufgaben oder anstehenden Termine.“ | Der bestätigte Geburtstag erscheint im Kalender bzw. als wiederkehrender Termin und rechtzeitig auf Heute | 33-akte-anna-1280, 34-calendar-1280 |
| 21 | stört | Akte Anna Berg | „1 belegter Kontakt“, „Letzter Kontakt heute.“ | Anna hat nicht geschrieben; der Nutzer hat nur über sie gesprochen | 33-akte-anna-1280 |
| 22 | stört | Briefing, „Relevante Nachrichten“ | Zähler „1“, darin „Neue Hinweise – 4 Quellen aufgenommen“ | Eigene Gesprächszeilen und eine selbst aufgenommene Datei sind keine relevanten Nachrichten | 34-today-1280 |
| 23 | stört | Einstellungen → Zugänge, Karte „Microsoft 365“ | Text und Knopf kleben ohne Innenabstand am Kartenrand | Gleicher Innenabstand wie die anderen Karten | 04-zugaenge-1280 |
| 24 | stört | Einstellungen → Zugänge | Postfach und Kalender hinzufügen nur über einen runden „+“-Knopf ohne Beschriftung | Beschrifteter Knopf „Postfach hinzufügen“ | 04-zugaenge-1280 |
| 25 | stört | 390 px | Navigation nur als Symbole ohne Beschriftung; im Assistenten verschwinden die Schrittnamen bis auf den aktuellen | Beschriftung oder wenigstens der Name des aktiven Bereichs | 35-heute-390, 35-assistent-390 |
| 26 | stört | Einstellungen → Kingfisher und du | „wie er dir antworten soll“ | Sonst überall „es“ | 24-einst-kingfisher-du-1280 |
| 27 | stört | Für Techniker | „Chip unbekannt · 15,7 GB Arbeitsspeicher (selbst gemessen)“ und darunter „Die Ausstattung des Rechners ist noch unbekannt.“ / „Der Rechner hat seine Ausstattung noch nicht gemeldet.“; „1 gespeicherte Dokumente“; „Der Sicherungshelfer ist gerade nicht erreichbar.“ neben „Sicherung: Erstellt“ unter „Was zuletzt lief“ | Widerspruchsfreie Angaben, richtige Einzahl | 25-techniker-offen-1280, 36-techniker-rueckmeldungen-1280 |
| 28 | stört | Für Techniker → Zeitplan → Was zuletzt lief | „Dabei kann ein Sprachmodell gerufen werden, das Kosten verursacht.“ | Bei rein lokalen Modellen keine Kostenwarnung; sonst sagen, welches Modell Kosten verursacht | 36-techniker-rueckmeldungen-1280 |
| 29 | stört | Für Techniker → Zeitplan → Was zuletzt lief | „Wissensvorschläge: Fehler · Nichts zu tun.“ | Entweder Fehler mit Grund oder „nichts zu tun“ | 36-techniker-rueckmeldungen-1280 |
| 30 | stört | Einstellungen → Zugänge, Meetings | Feld „Anderer Ordner“ mit Platzhalter „~/Documents/Mitschriften“ zum Tippen | Ordnerauswahl per Dialog | 04-zugaenge-1280 |

### Anzahl je Schwere

| Schwere | Anzahl |
|---|---|
| blockiert | 3 (Nr. 1, 2, 4) |
| verwirrt | 9 (Nr. 5, 6, 7, 13, 15, 16, 17, 19, 20) |
| stört | 18 |
| **gesamt** | **30** |

### Browserkonsole

Auf allen Wegen der Probe keine JavaScript-Fehler und keine Warnungen. Einzige
Konsolenmeldung: `Failed to load resource: … 422 (Unprocessable Entity)` für
`POST /api/v1/integrations/mail` beim falschen Passwort. Das ist die erwartete
Ablehnung, erscheint aber als Fehler in der Konsole. (Ein vom Prüfer von Hand
getippter, nicht existierender Pfad `/tasks` lieferte 401 mit rohem JSON
„ungültiges Token“; das ist kein Bedienweg und nicht als Befund gezählt.)

## 7. Was am besten gefiel

1. **Die Sprache der Kontrolle.** „Es liest nur mit und verschickt nichts ohne
   dein Ja.“, die Freigaben mit je einem Satz, was den Rechner verlässt, und
   „Fünf Schalter, alle aus, bis du sie einschaltest.“ Das schafft Vertrauen,
   ohne Fachwissen zu verlangen.
2. **Der Vorschlag im Gespräch.** Ein Satz wie „Merke dir …“ ergibt eine Karte
   mit dem wörtlichen Zitat, „Bestätigen“ mit einem Klick, danach „Als Wissen
   bestätigt.“ und „Als falsch widerrufen“. Genau so einfach und kontrolliert
   soll es sein; das Ergebnis steht sofort in der Akte.
3. **Der Assistent verzeiht Umwege.** „Später weitermachen“, „Einrichtung
   fortsetzen“ am Kopf der Zugänge, der Assistent setzt am richtigen Schritt
   wieder ein, der Name wandert in die Einstellungen, und die Prüfung des
   Postfachpassworts beim Speichern (statt stillschweigend zu speichern) ist
   richtig. Dazu „Stimmt nicht?“ mit fertigen Gründen und einem freiwilligen
   Feld „Richtig wäre …“.

## 8. Stand je Befund (Alltag)

Die Befunde der ersten Stunde (Branch `fremdprobe2-alltag`). Browserprobe für alle Zeilen:
`scripts/probe_fremdprobe2_alltag_ui.py`; Tests `sidecar/tests/test_fremdprobe2_alltag.py` und
`app/kingfisher/tests/{heute,beleg,verarbeitung,technik}.test.mjs`. Jede Zusicherung wurde absichtlich gebrochen
(28 Sabotageproben an den Tests, alle gefangen; dazu „Gestützt auf“ umbenannt: Der lokale Nachbau des Container-Vertrags schlägt in den Phasen „browser“ und „memory-controls“ fehl).

| Nr. | Stand | Commit |
|---|---|---|
| 10 | Kacheln im Briefing und „Braucht dich“ zeigen ihren Zähler nur, wenn es etwas zu zählen gibt (`heute.ts`). | `749966a` |
| 11 | Heute hat nur die Uhr der Seitenleiste; am Suchfeld „⌘ K“ auf dem Mac, „Strg K“ sonst, auf Touchgeräten nichts (`system.ts tastenHinweis`). | `749966a` |
| 12 | Nach „Melden“: „Gemerkt. Die Meldung bleibt auf diesem Rechner und ändert nichts an deinem Gedächtnis. Aus ihr wird eine Prüffrage …“ mit Verweis auf die Rückmeldungen. | `d1ab547` |
| 13 | Unter jeder Antwort „Gestützt auf“ mit dem lesbaren Quellenhinweis und einem Klick zur Quelle, sonst „Ohne Beleg: …“; unter der eigenen Nachricht „So ist deine Nachricht gespeichert“; die linke Spalte widerspricht nicht. Container-Vertrag zieht mit. | `d1ab547` |
| 14 | „Stimmt nicht?“ nur unter Antworten, nicht unter dem Gedächtnisvorschlag oder anderen Hinweisen des Programms. | `d1ab547` |
| 15 | „Im Hintergrund ist 3-mal etwas nicht fertig geworden (Quellen einordnen, Zusagen erkennen und Wissensvorschläge). Du musst nichts tun: Kingfisher versucht es von selbst noch einmal.“; bei Postfach oder Sicherung steht, wo man nachsieht. | `749966a` |
| 16 | Verarbeitung & Verlauf: ein Satz zum Stand, einer zur Wirkung passend dazu, einer zur Prüfung; Kacheln und Modellname hinter „Für Techniker“. | `f71d367` |
| 17 | Je Postfach eine Aussage aus einer Quelle (`mail_stand.py`): liest (x von y), verbunden und leer, gelesen, angehalten, noch nicht abgerufen oder Fehler mit Grund; dieselbe auf Heute, in „Kingfisher lernt gerade“, unter „Was zuletzt lief“ und „Stand aller Bereiche“. | `2ddd138` |
| 18 | Nach „Aktualisieren“: „Gerade abgerufen um 14:43, nichts Neues.“ (oder wie viel neu kam, oder der Grund), Uhrzeit in der Zeitzone des Nutzers. | `2ddd138`, `64d9793` |
| 19 | Karte „Kreis“ in jeder Personenakte, auch ohne Adresse und ohne Vorschlag („Noch kein Vorschlag; du kannst den Kreis selbst festlegen.“ mit drei Knöpfen); „Kingfisher und du“ sagt dasselbe. | `f7e5ab6` |
| 20 | Ein angenommener Geburtstag steht jedes Jahr im Kalender (nur in Kingfisher), in der Akte unter „Steht an“ und, nur für den bestätigten inneren Kreis, am Vortag und am Tag im Briefing. Ohne Annahme nichts. | `f7e5ab6` |
| 21 | „Letzter Kontakt“ und „belegte Kontakte“ zählen nur Quellen, an denen die Person selbst beteiligt war; ein Gespräch über sie zählt nicht. | `f7e5ab6` |
| 22 | „Relevante Nachrichten“ zählt keine eigenen Gesprächszeilen und keine hochgeladenen Dateien. | `749966a` |
| 26 | „wie es dir antworten soll“. | `f7e5ab6` |
| 27 | Eine Aussage zur Ausstattung („15,7 GB Arbeitsspeicher, selbst gemessen“) an beiden Stellen, „1 gespeichertes Dokument“, Sicherung ohne „Helfer nicht erreichbar“ neben „Erstellt“. | `21acfb4` |
| 28 | Kostenwarnung nur, wenn beim Abruf ein Modell außerhalb des Rechners gerufen werden kann, und dann mit Namen. | `21acfb4` |
| 29 | Ein Lauf mit Fehler nennt den Grund; nie „Fehler · Nichts zu tun.“ | `21acfb4` |

## 9. Stand je Befund (Start und Einrichtung)

Bearbeitet auf Branch `claude/fremdprobe2-einrichtung` (Basis `5260948`): Start und Einrichtung, damit das
15-Minuten-Kriterium erreichbar wird. Die übrigen Befunde (10 bis 22, 26 bis 29) stehen in Abschnitt 8.

| Nr. | Stand | Commit |
|---|---|---|
| 1 | `Kingfisher starten.command` (Doppelklick im Finder) ruft `scripts/kingfisher_starten.py`: findet Docker Desktop und startet es, sonst ein Satz mit Link zur Downloadseite; erzeugt Token und Passphrase ohne `openssl`; baut und startet wie `make start`; fehlt Ollama, ein Satz mit Link; öffnet den Browser. Die README ist englisch und führt zuerst über den Doppelklick; Terminal und Docker stehen unter „For developers“. | `04c4489` |
| 2 | Kingfisher findet den Mailserver einer eigenen Domain selbst (`server_finden.py`: SRV, Autoconfig der Domain, MX gegen den Katalog) und zeigt im Assistenten „Erkannt: …“ und nur das Passwortfeld; ohne Fund Servername und Port (993) im Assistenten selbst. Hinaus geht nur die Domain. | `148a907` |
| 3 | Die zuletzt getippte Adresse steht in „Postfach hinzufügen“ unter Zugänge, auch in den Servereinstellungen für Techniker. | `148a907` |
| 4 | Die Ablehnung steht direkt am Knopf, mit Fokus und Bildlauf, im Assistenten und unter Zugänge, und nennt den Anbieter oder „Der Mailserver <Name>“, nie den selbst vergebenen Namen. | `148a907` |
| 5 | Kalender: Adresse und Passwort des Postfachs werden übernommen; für eine eigene Domain sucht Kingfisher per `_caldavs._tcp` oder `/.well-known/caldav` auf dem Mailserver (erst ohne Passwort); Google und Outlook mit Weg und Link; erst danach das Feld „Adresse“ mit einem Satz; Überspringen bleibt. | `148a907` |
| 6 | „Laden starten“ startet einen Lauf im Sidecar, der an keiner Seite hängt; der Assistent geht sofort weiter. Fortschritt auf Fertig und Heute, eine Frage bekommt „Kingfisher lädt noch sein Sprachmodell (60 %)“. Die Größe kommt aus einer Quelle (`orchester.festplatte_noch_gb`); liegt ein Teil schon da, sagt der Satz „Noch zu laden: etwa 1,2 von 14 GB; der Rest liegt schon auf diesem Rechner“. | `9835d17` |
| 7 | Nach dem Lauf genau ein Satz: „Alles eingerichtet und geprüft.“, „Teilweise eingerichtet: 4 von 5 Aufgaben …“ oder „Nichts ist eingerichtet …“ mit „Noch einmal versuchen“; jedes Problem je Fähigkeit einmal. | `9835d17` |
| 8 | Die Fertig-Seite sagt „Kingfisher liest deine Mails“, „… deine Termine“ oder beides, je nachdem, was verbunden ist. | `9835d17` |
| 9 | Das Briefing gilt in der eingestellten Zeitzone („Do, 01. Oktober 2026 · Europe/Berlin“), nicht in der des Browsers. | `148a907` (Sidecar, `api.ts`), `9835d17` (Kopf) |
| 23 | Die Karte „Microsoft 365“ hat denselben Innenabstand wie die anderen Karten. | `148a907` |
| 24 | „Postfach hinzufügen“ und „Kalender hinzufügen“ sind beschriftete Knöpfe. | `148a907` |
| 25 | Bei 390 px trägt der aktive Bereich in der Leiste seinen Namen; im Assistenten steht der Name des aktuellen Schritts (schon vorher so, jetzt in der Browserprobe geprüft). | `9835d17` |
| 30 | „Anderen Ordner auswählen …“ klickt sich durch die Unterordner (nur Namen, nichts wird dadurch freigegeben); der getippte Pfad steht eingeklappt für Techniker. | `148a907` |

### Zeit bis zum ersten Briefing, neu gerechnet

Mit denselben Bedienzeiten wie in Abschnitt 4: Schritte 3 bis 5 (Ausweg über die Einstellungen, Servereinstellungen
nachschlagen, zurück in den Assistenten, zusammen 5:45) entfallen; im Assistenten werden nur noch Adresse und Passwort
getippt (gerechnet 1:30 statt 0:50 plus 4:30). Der Kalender ist ohne Eingabe verbunden (0:30 statt 1:15 und
übersprungen). Das Laden der Modelle (7a, 10:00) zählt nicht mehr, weil man sofort weitergeht. Ergebnis: etwa 6 Minuten
Bedienung vom ersten Aufruf bis zum Briefing, mit Mail und Kalender. **Nicht gemessen** ist der erste Start mit
Doppelklick: Docker Desktop herunterladen und installieren und das erste Bauen des Containers (einige Minuten Warten,
kaum Bedienung). Ob das in 15 Minuten passt, zeigt erst eine Probe auf einem Mac.

### Prüfungen

* Tests: `test_server_finden.py`, `test_kalender_eigene_domain.py`, `test_mail_anmeldung.py` (Befund 4),
  `test_anbieter_erkennen.py`, `test_ordner_lokal.py` (Befund 30), `test_modelle_laden.py` (Befunde 6, 7),
  `test_briefing_zeitzone.py` (Befund 9), `test_kingfisher_starten.py` (Befund 1); in der Oberfläche
  `postfach-weg.test.mjs`, `kalender-weg.test.mjs`, `rechner.test.mjs`, `lernt.test.mjs`, `fertig.test.mjs`.
  Attrappen: `dns_attrappe.py` mit SRV, `autoconfig_attrappe.py` (HTTPS auf 127.0.0.1), `caldav_attrappe.py` mit
  Umleitung für den Mailserver; jeder Test hinter der Netzsperre, `server_finden.TRANSPORT` ist in Tests nie das Netz.
* Sabotageproben (jeweils danach zurückgenommen): DOCTYPE-Sperre aus (1 Test rot), Weiterleitungen verfolgt (1), SRV
  nach Vorrang verkehrt (1), Autoconfig vor SRV (2), Größengrenze 64 MB statt 64 KB (1); Postfachname wieder in der
  Ablehnung (2); Passwort ohne Vorabfrage an den Mailserver (3); Laden bricht nach dem ersten Fehlschlag ab (1),
  „läuft“ immer falsch (2); Briefing ohne eingestellte Zeitzone (1); Ordnerauswahl ohne Wurzelprüfung (3); Schlüssel
  bei jedem Start neu (1), ohne Docker trotzdem weiter (1); „Nichts ist eingerichtet“ nie gesagt (1), Fertig-Seite nennt
  immer Mails und Termine (1), Anmeldename ohne Namensteil (1). Der Wortlistentest fand beim Bauen „Server“ in einem
  vorderen Satz; der Satz ist umformuliert.
* Browserprobe `scripts/probe_fremdprobe2_einrichtung_ui.py`: der Weg mit `lena.probe@example.org` von Name bis
  Briefing, 47 Prüfungen; im Assistenten getippt werden nur Name, Adresse und Passwort.

### Offen

* **Nur auf dem Mac prüfbar:** der Doppelklick selbst (Gatekeeper fragt bei einer aus dem Netz geladenen Datei; ob das
  ZIP von GitHub das Ausführungsrecht erhält), das Starten von Docker Desktop durch den Starter, das Angebot der
  Entwicklerwerkzeuge von Apple, das Öffnen des Browsers, die Dauer des ersten Bauens.
* **Nur mit echtem Netz prüfbar:** SRV- und Autoconfig-Einträge echter Domains, die MX-Endungen der Hoster (IONOS,
  STRATO, ALL-INKL, netcup) und ihre Postfachserver, die Outlook-Seite „Kalender veröffentlichen“ und ihre Adresse,
  `/.well-known/caldav` bei echten Hostern. Eine falsche Zeile scheitert sichtbar an der Anmeldung, nie still.
* Windows hat noch keinen Starter zum Doppelklicken (M7).
* Das Eingabefeld auf Heute nennt während des Ladens noch „Für freie Gespräche ein Modell verbinden“; die Antwort selbst
  sagt ehrlich, dass geladen wird.
