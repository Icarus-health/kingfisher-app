# Fremdprobe 3: Erste Einrichtung und erste Stunde

Stand: 1. Oktober 2026, Commit `495eeca` (Branch `dobby/youthful-bardeen-pf69mq`).

Ein Prüfer spielt eine Nutzerin ohne technisches Wissen („Lena Probe“, Postfach
`lena.probe@example.org`), die Kingfisher zum ersten Mal einrichtet und eine
Stunde benutzt. Gelesen wurde nur `README.md`. Den Quellcode hat der Prüfer nur
gelesen, um das Programm und die Attrappen zu starten, und für die technische
Ursache von Befund 1, nachdem der Befund in der Oberfläche schon feststand.
Alle Daten sind synthetisch.

## Ergebnis in Kürze

- **Einrichtung bis zum Briefing: etwa 5 Minuten 20 Sekunden** realistische
  Bedienzeit, ohne etwas nachzuschlagen. Das Laden der Modelle lief im
  Hintergrund und zählt nicht.
- **Urteil zum 15-Minuten-Kriterium: erfüllt bis auf den nur auf dem Mac
  prüfbaren Start.** Der Weg durch den Assistenten ist kurz, und nirgends muss
  man etwas wissen, das man nicht wissen kann. Ein Vorbehalt bleibt: Das
  Briefing, das man nach 5 Minuten sieht, wird auch danach nicht besser, weil
  Kingfisher keine einzige Mail ins Gedächtnis aufnimmt (Befund 1). Die
  Einrichtung *sieht* fertig aus, ist es inhaltlich aber nicht.
- **Erste Stunde: blockiert.** Alle 5 Mails scheitern beim Einlesen, ohne dass
  die Oberfläche es sagt. Darum gibt es keine Personen, keinen Kreis, keine
  Vorschläge und keine belegten Antworten.
- 1 × blockiert, 5 × verwirrt, 13 × stört (davon im Startweg 2 × verwirrt und
  2 × stört, nur auf dem Mac prüfbar).
- Die Browserkonsole blieb während der ganzen Probe ohne Fehler und Warnungen der
  App.

## Vorgehen

1. Den Startweg im README als Nicht-Techniker gelesen und bewertet.
2. Den Assistenten in Chromium bei 1280 px durchlaufen. Für jeden Schritt wurde
   eine realistische Bedienzeit (lesen, tippen, warten) angesetzt; gemessene
   Wartezeiten der App stehen getrennt daneben.
3. Die erste Stunde, in der Probe gerafft auf etwa 15 Minuten echte Laufzeit, weil
   Wiederholungen und Hintergrundarbeit von selbst nichts mehr änderten: Mails einlesen lassen, „Was wollte Anna?“ fragen, eine
   Antwort als falsch melden, Gedächtnis, Akten und Quellen ansehen, Aufgaben
   und Vorschläge suchen, Kalender, Einstellungen vorne und „Für Techniker“,
   zum Schluss das Briefing.
4. Die wichtigsten Seiten bei 768 px und 390 px nachgeprüft: Heute,
   Assistent, Nachrichten, Akte, Einstellungen, Gespräch, Kalender. Gemessen
   wurde auch, ob die Seite seitlich überläuft.
5. Die Browserkonsole lief die ganze Zeit mit: Fehler, Warnungen und
   HTTP-Antworten ab 400.

## Aufbau (technisch, nicht Teil der Probe)

- Worktree auf `495eeca` (vorgespult von `f9edd4a`), `npm ci && npm run build`
  in `app/kingfisher` ohne Fehler. Ausgabe nach `app/dist`.
- Sidecar: `create_app()` unter uvicorn auf `127.0.0.1:8890`, Python aus
  `/home/user/Kingfisher/.venv`, `PYTHONPATH=<worktree>/sidecar`, frisches
  `ICARUS_DATA_DIR` unter `/tmp`, `ICARUS_UI_DIR=<worktree>/app/dist`,
  `KINGFISHER_TIMEZONE=Europe/Berlin`, `ICARUS_SECRETS_PASSPHRASE` gesetzt,
  kein `ICARUS_SIDECAR_TOKEN` (wie bei den früheren Browserproben). Proxy-Variablen
  entfernt, damit nichts nach draußen geht.
- **Ollama:** Eine eigene Attrappe als echter HTTP-Dienst auf
  `127.0.0.1:11434` mit `/api/tags`, `/api/show` (gguf, Architektur,
  Parameterzahl, Fähigkeiten `completion` und `tools`), `/api/pull`
  (gestreamter Fortschritt, 40 s je Sprachmodell, 8 s für das Einbettungsmodell),
  `/api/embed` und `/v1/chat/completions`. Die Bereitschaftsprüfung
  (`readiness`-Werkzeug) besteht sie echt; `modell_pruefung` wurde **nicht**
  überschrieben. Antworten auf Fragen sind ein fester Satz, Antworten mit
  JSON-Schema ein leeres Objekt nach Schema. `sidecar/tests/ollama_fake.py` ist
  nur ein `httpx.MockTransport` und kein Dienst; darum die eigene Attrappe.
- **IMAP:** `ImapAttrappe` aus `sidecar/tests/imap_attrappe.py`, für die Probe
  um ein Postfach mit 5 synthetischen Mails erweitert (Unterklasse im
  Scratchpad, nicht im Repository): SELECT/EXAMINE mit `UIDVALIDITY 7` und
  `UIDNEXT 6`, `UID SEARCH`, `UID FETCH` mit `BODY.PEEK[]` und Teilabruf. Die
  Mails: Jonas Keller (Treffen am Montag), **Anna Berg „Bitte: Angebot
  Vereinsfest bis Freitag“ (Frist 9. Oktober)**, ein Newsletter mit
  `List-Unsubscribe`, eine Praxis-Erinnerung, Annas Nachtrag zum Aufbau.
  Passwort `Sommer-Garten-2026` für Postfach und Kalender.
- **DNS:** `Namensdienst` aus `sidecar/tests/dns_attrappe.py`, angebunden mit
  `KINGFISHER_DNS=127.0.0.1:<port>`.
- **Autoconfig:** `AutoconfigAttrappe` mit `example.org` → IMAP-Attrappe auf
  `127.0.0.1`, angebunden über `server_finden.TRANSPORT`. So gibt die eigene
  Domain ihren Mailserver wie bei einem Hoster selbst preis. Die Zertifikate
  der Attrappen stehen gebündelt in `SSL_CERT_FILE`.
- **CalDAV:** `CaldavAttrappe` (ein Termin „Probe-Termin beim Steuerbüro“,
  2. Oktober, 10:00 Uhr Berliner Zeit), angebunden über
  `app.state.caldav_transport` für den Mailserver-Host.
- **Browser:** Chromium `/opt/pw-browsers/chromium-1194`, headless, über CDP
  mit Playwright bedient. Der erste Lauf hatte die Zeitzone UTC des
  Containers; ab der Kalenderprüfung lief Chromium mit `TZ=Europe/Berlin`
  (siehe „Kein Befund“).
- Bildschirmfotos liegen im Scratchpad des Prüfers unter `fp3/bilder/`, nicht im
  Repository. Die Dateinamen in der Befundtabelle beziehen sich darauf.

**Kein Befund, weil die Umgebung es verursacht:** „Erkannt: 127.0.0.1“ und
„Kalender: 127.0.0.1: Privat“ (die Attrappe steht auf 127.0.0.1, bei einem echten
Hoster stünde dort sein Servername), „Der Ortsdienst antwortet gerade nicht“
beim Wetter (kein Netz), die Uhrzeit 08:00 statt 10:00 im Kalender, solange
der Browser in UTC lief (mit `TZ=Europe/Berlin` überall richtig 10:00),
Inhalte der Modellantworten und „Einordnung fehlgeschlagen“ bei der Quelle,
weil die Attrappe für die Einordnung nur leere JSON-Objekte liefert.

## Startweg laut README

Gelesen als jemand, der Kingfisher von einem Bekannten empfohlen bekommen hat.

| Schritt im README | Bewertung | Prüfbar hier? |
|---|---|---|
| „Code → Download ZIP“, ZIP öffnen | Machbar, wenn man GitHub schon einmal gesehen hat. Der grüne Knopf heißt „Code“, das errät man nicht, aber das README sagt es. | nein (Mac) |
| Doppelklick auf `Kingfisher starten.command`, beim ersten Mal Rechtsklick → **Öffnen** | Seit macOS 15 (Sequoia) öffnet Rechtsklick → Öffnen eine Datei von einem nicht verifizierten Entwickler nicht mehr. Man muss stattdessen über Systemeinstellungen → Datenschutz & Sicherheit → „Dennoch öffnen“ gehen. Gilt das, bleibt man an dieser Stelle stecken, und das README hilft nicht weiter. **S1, verwirrt.** | nein (Mac) |
| Docker Desktop installieren, einmal öffnen, Starter erneut doppelklicken | Für Nicht-Techniker die größte Hürde: großer Download, Administratorpasswort, Lizenzdialog, beim ersten Öffnen ein Anmeldeangebot von Docker. Dass das Fenster den Download selbst öffnet und Docker selbst startet, wenn es nur nicht läuft, ist gut. **S4, stört.** | nein (Mac) |
| Apple-Entwicklerwerkzeuge | Warum ein Programm für Mails „Entwicklerwerkzeuge“ braucht, versteht ein Laie nicht; der Download dauert. Das README sagt immerhin, dass macOS den Dialog selbst anbietet. Teil von S4. | nein (Mac) |
| Ollama „Kingfisher runs without it“ | Widerspricht dem Gefühl im Assistenten („Kingfisher denkt auf deinem Rechner nach“). Ob man Ollama installieren soll oder nicht, kann der Nutzer nicht entscheiden. **S3, verwirrt.** | nein |
| „The first start takes a few minutes“, dann öffnet sich der Browser mit dem Assistenten | Klar formuliert. | nein (Mac) |
| Sprache | Das README ist englisch, die App und die Zielgruppe sind deutsch. Wer kein Englisch liest, hat keinen Startweg. **S2, stört.** | ja |

Geschätzter Zeitbedarf auf einem Mac ohne Docker, getrennt gerechnet und **nicht
geprüft**: Docker Desktop laden und einrichten 5 bis 10 Minuten, dazu die
Entwicklerwerkzeuge, falls sie fehlen, 5 bis 15 Minuten, dann der erste Start
mit Bau „ein paar Minuten“. Mit diesen Voraussetzungen ist der Startweg allein
schon nahe an 15 Minuten oder darüber. Auf einem Mac, auf dem Docker schon
läuft, bleibt nur der erste Start.

## Zeit je Schritt: vom ersten Aufruf bis zum Briefing

Realistische Bedienzeit einer ungeübten Nutzerin. Wartezeiten der App sind
gemessen. Das Laden der Modelle lief im Hintergrund weiter und zählt nicht.

| Nr. | Schritt | Was zu tun war | Bedienzeit | gemessene Wartezeit |
|---|---|---|---|---|
| 1 | „Wie heißt du?“ | lesen, „Lena“ tippen, Enter | 0:20 | – |
| 2 | Mailadresse | lesen, Adresse tippen, „Erkannt: … Kingfisher hat deinen Mailserver in den Angaben deiner Domain gefunden.“ lesen | 0:40 | Erkennung beim Tippen, < 1 s |
| 3 | Passwort | tippen, „Postfach verbinden“ | 0:20 | 0,5 s |
| 4 | „Soll Kingfisher die Mails … jetzt einlesen?“ | lesen, „Mails einlesen“, „Weiter“ | 0:25 | – |
| 5 | Kalender | lesen, Adresse und Passwort sind schon da, „Kalender suchen und verbinden“, Ergebnis lesen, „Weiter“ | 0:35 | ca. 1 s |
| 6 | Dieser Rechner | lesen (14 GB, 4 bis 20 Minuten), „Laden starten“, „Weiter“ | 0:45 | Laden im Hintergrund |
| 7 | Freigaben | lesen; Wetter: „Einrichten“, Schalter, Ort tippen, „Suchen“, Meldung lesen; „Überspringen“ | 1:15 | Ortsdienst ca. 5 s (kein Netz) |
| 8 | Fertig | lesen, „Zum Briefing“ | 0:30 | – |
| 9 | Briefing | ansehen | 0:30 | Seite < 1 s |
| | **Summe** | | **5:20** | |

Ohne den Ausflug zum Wetter wären es etwa 4:30. Nachgeschlagen werden musste
nichts: Mailserver, Kalenderserver, Modellwahl und Speicherbedarf hat das
Programm selbst ermittelt. Das Sprachmodell war nach etwa 3 Minuten Attrappenzeit
fertig (drei Modelle nacheinander mit Prüfung). Mit echter Leitung nennt der
Assistent 4 bis 20 Minuten; man kann in dieser Zeit weiterarbeiten.

**Urteil: erfüllt bis auf den nur auf dem Mac prüfbaren Start.** Grund: Der Weg
durch die Oberfläche dauert gut 5 Minuten und braucht kein Fremdwissen. Ob der
Weg vom ZIP bis zum geöffneten Browser auf einem Mac ohne Docker in die übrigen
knapp 10 Minuten passt, ist hier nicht prüfbar und nach Lage des README
fraglich (S1, S4). Inhaltlich steht das Urteil unter dem Vorbehalt von Befund 1:
Das Briefing ist sichtbar, wird aber nie aus den Mails gespeist.

## Die erste Stunde

- **Mails einlesen:** Der Assistent zeigt „example.org: 0 von 5 Mails gelesen.“
  Heute zeigt „Kingfisher lernt gerade · Postfach example.org wird gelesen: 0 von
  5 Mails.“ Das blieb bis zum Ende der Probe so, rund 15 Minuten nach dem Verbinden. Die
  Wiederholungen warten danach immer länger (bis zu einer Stunde) und scheitern aus
  demselben Grund wieder (Befund 1). Die
  Seite **Nachrichten** zeigt die 5 Mails dagegen sofort und richtig
  („Posteingang (4)“, „Newsletter (1)“): Das Lesen des Posteingangs funktioniert,
  nur die Aufnahme ins Gedächtnis nicht (Befund 1).
- **„Was wollte Anna?“** über das Fragefeld auf Heute: Nach etwa 5 s kam eine
  Antwort mit dem Hinweis „Ohne Beleg: Diese Antwort stützt sich auf keine
  Quelle aus deinem Gedächtnis.“ Das ist ehrlich, denn es gibt keine Quelle
  (Befund 1). Eine Quelle konnte darum aus der Antwort heraus nicht geöffnet
  werden. Ersatzweise wurde die Quelle des Termins in der Akte „Mainz“ geöffnet
  (Inhalt aufklappbar, Zeit und Ort richtig).
- **Antwort als falsch melden:** „Stimmt nicht?“ → „Unvollständig“ → „Richtig
  wäre …“ → „Melden“. Die Rückmeldung „Gemerkt. Die Meldung bleibt auf diesem
  Rechner …“ kam sofort und steht unter Einstellungen → Für Techniker →
  Rückmeldungen. Gut gelöst bis auf die Sprache (Befund 11).
- **Vorschlag annehmen oder ablehnen:** nicht möglich. Unter Aufgaben steht
  „Keine offenen Aufgaben für dich.“, unter Gedächtnis „Prüfen (0)“. Ohne
  aufgenommene Mails entsteht nichts, und das automatische Sortieren war nach
  der Einrichtung ausgeschaltet (Befund 3).
- **Akten, Kreis einer Person:** nicht möglich. Unter Gedächtnis → Menschen steht
  „0 von 0 Einträgen“ und „Hier ist noch Platz … Quellen verbinden →“, obwohl
  Postfach und Kalender verbunden sind. Die einzige Akte ist der Ort „Mainz“ aus
  dem Termin. Unter Einstellungen → Kingfisher und du steht „Kreis … Noch für
  niemanden bestätigt. Kein Vorschlag offen.“
- **Einstellungen vorne:** Zugänge, Was Kingfisher darf, Kingfisher und du,
  Sicherung, alles verständlich und mit dem Satz, was den Rechner verlässt.
  **Für Techniker:** 15 aufklappbare Abschnitte. Der Einleitungssatz „Hier muss
  nichts geändert werden.“ beruhigt. Allerdings verweist der Assistent für
  etwas Alltägliches wie das Pausieren hierher (Befund 5).
- **Briefing am Ende:** unverändert seit der Einrichtung. Top-Priorität „3
  ungelesene Nachrichten liegen im Postfach.“ (Hoch), keine Frist von Anna,
  kein Hinweis auf das Treffen am Montag (Befund 15).

## Befunde

Schwere: **blockiert** (kommt ohne Hilfe nicht weiter), **verwirrt** (weiß nicht,
was passiert oder was zu tun ist), **stört** (ärgerlich, kostet Zeit oder
Vertrauen). Bilddateien im Scratchpad unter `fp3/bilder/`.

| Nr. | Schwere | Seite / Element | Wortlaut | Erwartung | Bild |
|---|---|---|---|---|---|
| 1 | **blockiert** | Hintergrund, Mail-Aufnahme | „Postfach example.org wird gelesen: 0 von 5 Mails.“ (bis zum Ende der Probe unverändert, alle Wiederholungen erfolglos) | Die Mails stehen nach Sekunden bis Minuten im Gedächtnis; daraus entstehen Personen, Fristen, Vorschläge und belegte Antworten. Tatsächlich stehen alle 5 Einträge der Aufnahme auf `failed` (3 Versuche je Mail). Technische Ursache (nach der Probe ermittelt, außerhalb der Nutzerrolle): Die Aufnahme liest in einer wiederverwendeten IMAP-Sitzung zuerst den Bestand (EXAMINE, dabei wird `UIDVALIDITY` aus den Antworten von `imaplib` entnommen) und ruft dann die Mail mit `frisch=False` ab, also ohne neues SELECT. `_mailbox_validity` findet `UIDVALIDITY` nicht mehr und wirft „Das Postfach liefert keine stabile Nachrichtenkennung.“ Ein normgerechter IMAP-Server sendet `UIDVALIDITY` nur beim SELECT/EXAMINE. Nachgestellt außerhalb der Oberfläche: `with connector.session(): inventory_page(…); message_mit_anhaengen('INBOX', '7.2')` → `MailError`; ohne Sitzung gelingt derselbe Abruf. Betroffen: `sidecar/icarus_memory/connectors/mail.py` (`_Sitzung.select`, `_mailbox_number`) und `mail_intake.py`, das die Ausnahme ohne Grund verschluckt. Die bisherigen Attrappen hatten ein leeres Postfach und konnten das nicht zeigen. | 17-heute-nach-laden.png, 22-gedaechtnis.png |
| 2 | verwirrt | Heute, Assistent, Einstellungen → Zugänge: „Kingfisher lernt gerade“ | „0 von 4 Quellen, wann es fertig ist, ist noch unklar“ · „Postfach example.org wird gelesen: 0 von 5 Mails.“ · „Wartet, solange du arbeitest.“ | Wenn das Einlesen scheitert, sagt die Oberfläche es in einem Satz und mit einem Knopf („Erneut versuchen“, „Was ist los?“). Fünf gescheiterte Mails dürfen nicht als „wird gelesen“ erscheinen. | 32-einstellungen.png, 40-390-today.png |
| 3 | verwirrt | Gedächtnis → Verarbeitung & Verlauf | „Automatisches Sortieren · Aus: Kingfisher sortiert gerade nichts von selbst.“ | Die Fertig-Seite verspricht „Es ordnet ein, wer wer ist und was zu welchem Projekt gehört.“ Dann muss das Sortieren nach der Einrichtung an sein, oder der Assistent fragt in einem Satz danach. Der Schalter liegt sonst versteckt unter Gedächtnis → Verarbeitung & Verlauf. | 23-verarbeitung.png |
| 4 | verwirrt | Assistent, Schritt 5 „Freigaben“ | Nach dem Einschalten von „Morgens das Wetter holen“ heißt der einzige Knopf nach vorn „Überspringen“; danach steht in der Leiste „Freigaben (übersprungen)“. In Einstellungen → Was Kingfisher darf ist das Wetter dann wieder aus, ohne Hinweis. | Ein Knopf „Weiter“, sobald man etwas angefasst hat. Kann der Schalter nicht an bleiben (kein Ort gefunden), sagt der Schritt das, statt ihn still zurückzusetzen. | 12-wetter-an.png, 14-fertig.png, 33-was-kingfisher-darf.png |
| 5 | stört | Assistent, Schritt 2 nach dem Verbinden | „Soll Kingfisher die Mails von example.org jetzt einlesen? … Pausieren kannst du jederzeit unter Einstellungen → Für Techniker → Zeitplan und Hintergrund.“ | „die Mails von example.org“ klingt nach Mails *von* der Firma example.org; besser „dein Postfach lena.probe@example.org“. Pausieren ist eine Alltagsfunktion und gehört nicht unter „Für Techniker“; auf Heute gibt es ohnehin „Pausieren“. | 04-nach-verbinden.png |
| 6 | stört | Assistent, Schritt 6 „Fertig“ | „Mails 0 · Termine 0“ | Der Termin war schon aufgenommen; Heute meldet gleichzeitig „Heute: 1 Termin aufgenommen“. Zähler sollen stimmen oder weggelassen werden. | 14-fertig.png |
| 7 | stört | Assistent, Schritt 3 „Kalender“ | Nach „Verbunden: dein Kalender „Privat“.“ bleibt der Knopf „Kalender suchen und verbinden“ aktiv. | Nach Erfolg verschwindet der Knopf oder wird zu „Weiteren Kalender verbinden“. | 07-kalender-verbunden.png |
| 8 | stört | Heute, „Kingfisher lernt gerade“ | „Wartet, solange du arbeitest.“ | Unklar, ob man aufhören soll zu arbeiten, damit Kingfisher lernt. Ein Satz wie „Kingfisher lernt weiter, sobald du eine Pause machst; du musst nichts tun.“ | 40-390-today.png |
| 9 | stört | Akte „Mainz“ → Quelle öffnen | „Herkunft: calendar:calendar-38d1718069744e76808c8e351eb567a6:probe-1@attrappe“ · „Einordnung fehlgeschlagen · erneuter Versuch bei aktiver Automatik“ | Technische Kennungen nicht vorne zeigen (oder nur unter „Für Techniker“). „bei aktiver Automatik“, während die Automatik an ist, liest sich wie ein Widerspruch. | 30-quelle.png |
| 10 | stört | Akte „Mainz“ | „Ort · Aus einer Quelle zusammengestellt; die Akte selbst ist ohne Modell berechnet, jede Zeile führt zur Quelle.“ | „ohne Modell berechnet“ ist Fachsprache. Besser: „Jede Zeile führt zur Quelle.“ | 29-akte-mainz.png |
| 11 | stört | Antwort → „Stimmt nicht?“ und Für Techniker → Rückmeldungen | „Aus ihr wird eine Prüffrage: Wer Kingfisher verbessert, stellt sie bei jeder neuen Fassung …“ · „Als Fälle für die Messlatte speichern“ | Wer ist „wer Kingfisher verbessert“? Was ist „die Messlatte“? Für die Nutzerin genügt: „Gemerkt. Kingfisher soll diesen Fehler nicht wieder machen.“ | 21-gemeldet.png, 34-rückmeldungen.png |
| 12 | stört | Gedächtnis → Verarbeitung & Verlauf, nach „Automatisches Sortieren einschalten“ | Gleichzeitig: „Das automatische Sortieren ist pausiert. Der Rest wird sortiert, sobald es wieder läuft.“ und „An: Kingfisher sortiert deine Quellen selbst“ | Der Stand passt sich nach dem Klick an, nicht erst nach einem Neuladen. | 24-sortieren-an.png |
| 13 | stört | Für Techniker → Zeitplan und Hintergrund | „An. Kingfisher ruft die Mails aus example.org alle vier Stunden ab.“ | Ist das die Vorgabe, erscheint eine neue Bitte von Anna erst Stunden später im Gedächtnis. Die Vorgabe sollte so gewählt sein, dass das Briefing am selben Vormittag stimmt, oder die Oberfläche sagt, dass neue Post zusätzlich sofort kommt. | 34-zeitplan.png |
| 14 | stört | Navigation bei 390 px | Die obere Leiste hat einen eigenen waagerechten Rollbalken; die Beschriftung des aktiven Punkts wird abgeschnitten („Kal…“). | Alle Ziele ohne Rollen erreichbar, oder nur Symbole ohne abgeschnittenen Text. (Im headless Chromium sind Rollbalken sichtbar; auf dem Mac mit ausgeblendeten Rollbalken wirkt es schwächer, die Abschneidung bleibt.) Seitlicher Überlauf der ganzen Seite: keiner bei 768 und 390 px. | 40-390-today.png, 40-390-calendar.png |
| 15 | stört | Briefing, „Heutige Top-Prioritäten“ | „3 ungelesene Nachrichten liegen im Postfach. Quelle: mail · Hoch“ | Ein Zähler ist keine Priorität und nimmt keine Entscheidung ab. Erwartet: „Anna braucht bis Freitag, 9. Oktober, das Angebot fürs Vereinsfest.“ (Folge von Befund 1, die Formulierung ist aber auch ohne Gedächtnis ein Befund.) | 41-briefing-ende.png |
| S1 | verwirrt | README, Startweg Mac | „right-click (or Control-click) the file, choose **Open**, then **Open** again.“ | Auf aktuellen macOS-Versionen führt dieser Weg nicht mehr zum Öffnen; der Weg über Systemeinstellungen → Datenschutz & Sicherheit → „Dennoch öffnen“ fehlt. **Nicht prüfbar hier.** | – |
| S2 | stört | README | Englisch | Der Startweg auf Deutsch, mindestens der Abschnitt „Start Kingfisher“. | – |
| S3 | verwirrt | README, Startweg | „**Ollama** (free) lets Kingfisher answer in its own words. Kingfisher runs without it“ | Klar sagen, ob man Ollama installieren soll. Der Assistent setzt in Schritt 4 („Laden starten“) voraus, dass es da ist. **Nicht prüfbar hier**, was ohne Ollama in Schritt 4 passiert. | – |
| S4 | stört | README, Voraussetzungen | Docker Desktop und Apple-Entwicklerwerkzeuge | Für Nicht-Techniker zwei fremde Programme mit Administratorpasswort und großem Download, bevor überhaupt etwas zu sehen ist. Zeitbedarf mutmaßlich 10 bis 25 Minuten. **Nicht prüfbar hier.** | – |

### Anzahl je Schwere

| Schwere | in der Oberfläche | im Startweg (nur Mac) | gesamt |
|---|---|---|---|
| blockiert | 1 | 0 | 1 |
| verwirrt | 3 | 2 | 5 |
| stört | 11 | 2 | 13 |

## Was am besten gefiel

1. **Der Mailserver der eigenen Domain wird gefunden, gefragt wird nur nach dem
   Passwort.** Schon während des Tippens der Adresse stand „Kingfisher hat
   deinen Mailserver in den Angaben deiner Domain gefunden.“ Beim Kalender waren
   Adresse und Passwort schon eingetragen („Kingfisher nimmt dasselbe Passwort
   wie für dein Postfach.“); ein Klick, eine Sekunde, verbunden.
2. **Die großen Downloads halten nicht auf.** „Das Laden läuft im Hintergrund
   weiter; du machst gleich mit der Einrichtung weiter.“ Das stimmte, der
   Fortschritt stand danach auf Heute, und die Modelle wurden ohne weiteres
   Zutun geladen und geprüft. Die Zahlen (Arbeitsspeicher, 14 GB, freier Platz)
   ersparen jede Entscheidung.
3. **Bei jeder Freigabe steht in einem Satz, was den Rechner verlässt**, und
   „Stimmt nicht?“ unter jeder Antwort ist mit drei Klicks erledigt und sagt,
   wo die Meldung bleibt. Die Antwort ohne Quelle sagt das offen („Ohne Beleg“),
   statt Sicherheit vorzutäuschen.

## Stand je Befund (1, 2, 3, 8, 9, 12, 13, 15)

Geprüft mit `sidecar/tests/test_mailaufnahme_ende_zu_ende.py` (echter Weg über die API gegen die IMAP-Attrappe mit fünf
synthetischen Mails) und der Browserprobe `scripts/probe_fremdprobe3_ui.py` in Chromium bei 1280 und 390 px.

| Nr. | Stand | Was jetzt gilt | Commit |
|---|---|---|---|
| 1 | behoben | Die Sitzung setzt UIDVALIDITY bei Wiederverwendung wieder ein. Die IMAP-Attrappe hat jetzt ein Postfach mit Mails und antwortet wie ein normgerechter Server (UIDVALIDITY nur bei SELECT/EXAMINE); der Ende-zu-Ende-Test schlägt ohne die Korrektur fehl. Dabei gefunden: Ein ausgefilterter Newsletter ließ das Postfach für immer bei „4 von 5“ stehen; Ausgefilterte zählen jetzt als gelesen. | `a771b17`, `6d6c589` |
| 2 | behoben | Gescheiterte Mails tragen Grund und technische Angabe (Migration 17, `mail_intake_grund.py`, nie Text vom Server). Heute, Assistent und Einstellungen → Zugänge sagen „5 Mails kamen nicht ins Gedächtnis.“ mit dem Grund in einem Satz und dem Knopf „Erneut versuchen“; die Angabe für Techniker steht aufgeklappt darunter. Nach dem Klick sind die Mails wieder offen, und die Aufnahme läuft sofort. | `6d6c589`, `c0a8450` |
| 3 | behoben | Entscheidung: Sortieren ist nach der Einrichtung an. Die Fertig-Seite bietet es vorausgewählt auch an, solange das Modell lädt, und merkt es vor; es beginnt, sobald das lokale Modell bereit ist. Ein Modell im Internet wird nie vorgemerkt. Ohne Häkchen verspricht die Seite die Einordnung nicht. Sortieren und Verdichtung schlagen weiter nur vor (`test_verdichtung.py`). | `b225355` |
| 8 | behoben | „Kingfisher lernt weiter, sobald du eine Pause machst; du musst nichts tun.“ (ebenso nach einer Antwort). | `5f1efac` |
| 9 | behoben | Herkunftskennungen stehen nur unter „Für Techniker“. Der Satz zum Einordnungsfehler hängt vom Stand ab: „versucht es von selbst noch einmal“ oder „sobald das automatische Sortieren läuft“. | `ad844e0` |
| 12 | behoben | Fortschritt und Stand lesen denselben Stand; nach dem Einschalten steht sofort „An:“ ohne „pausiert“ daneben. | `b225355` |
| 13 | behoben | Vorgabe alle 30 Minuten. Ein selbst gewählter Abstand bleibt (`interval_gewaehlt`); 240 ohne diesen Vermerk war die frühere Vorgabe und wird zur neuen. Die Sicherung im Zeitplan läuft höchstens alle vier Stunden, damit 14 Sicherungen weiter gut zwei Tage abdecken. | `5f1efac` |
| 15 | behoben | Die Zahl ungelesener Nachrichten ist keine Priorität mehr; sie steht nur im Nachsatz. | `193b691` |

## Stand je Befund (Oberfläche und README)

Behoben. Geprüft im echten Chromium mit
`scripts/probe_fremdprobe3_oberflaeche_ui.py` (64 Prüfungen, Konsole leer; Ollama antwortet dort absichtlich nicht,
der Ortsdienst des Wetters zuerst auch nicht); die berührten älteren Proben (`probe_einrichtung_ui.py`,
`probe_fremdprobe2_einrichtung_ui.py`, `probe_fremdprobe2_alltag_ui.py`, `probe_rueckkanal_ui.py`,
`probe_seiten_ui.py`, `probe_einstellungen_ui.py`) laufen weiter grün. Sabotageproben: Wer eine der Zusicherungen
bricht (kein „Weiter“ nach dem Anfassen, kein Satz zum Wetter, „die Mails von“, Pausieren unter „Für Techniker“,
Termine vor dem Abgleich gezählt, „Prüffrage“ vorne, rollende Navigation, eigene Navigationsregel je Seite, alter
Satz ohne Modell, README ohne „Dennoch öffnen“), bekommt rote Tests; die rollende Navigation und das fehlende
„Weiter“ fängt auch die Browserprobe.

| Nr. | Stand | Was jetzt gilt | Wo |
|---|---|---|---|
| 4 | behoben | Sobald man im Schritt „Freigaben“ etwas ändert (auch nur den Schalter des Wetters umlegt), heißt der Knopf „Weiter“; der Schritt gilt als erledigt, die Leiste zeigt ✓ statt „(übersprungen)“. **Ursache des stillen „Aus“:** Ohne gewählten Ort speichert der Schalter nichts, er öffnet nur die Ortssuche, sieht aber eingeschaltet aus; antwortet der Ortsdienst nicht, bleibt das Wetter aus, und der Assistent las den Stand erst beim Zuklappen neu. Das Wetter ohne Ort einzuschalten bleibt unmöglich (es weiß dann nicht, wo es nachsehen soll); jetzt sagt der Schritt das in einem Satz („Das Wetter ist noch aus, weil noch kein Ort gewählt ist.“), auch nach dem Zuklappen, und die Ortssuche sagt „An ist das Wetter erst, wenn du einen Ort gewählt hast.“ Mit gefundenem Ort ist es sofort an, auch unter Einstellungen → Was Kingfisher darf. | `Einrichtung/freigaben.ts`, `FreigabenSchritt.tsx`, `WeltSettings.tsx` (`beiAenderung`, `beiWunsch`), `TranscriptSettings.tsx` (`beiAenderung`); Tests `freigaben.test.mjs` |
| 5 | behoben | „Soll Kingfisher dein Postfach lena.probe@example.org jetzt einlesen? … Anhalten kannst du es jederzeit auf Heute mit „Pausieren“.“ Auch die Fertig-Seite verweist fürs Pausieren auf Heute statt unter „Für Techniker“. | `Einrichtung/postfach.ts`, `MailEinlesen.tsx`, `fertig.PAUSIEREN_AUF_HEUTE`; Test `postfach.test.mjs` |
| 6 | behoben | Ursache: Die Fertig-Seite zählte die Termine gleichzeitig mit dem Abgleich, also oft vor ihm, und zeigte dann 0; „Mails“ zählte Gelesenes, ohne es zu sagen, auch wenn noch gar nicht eingelesen wurde. Jetzt: „Termine aufgenommen“ erst nach dem Abgleich (bis dahin „…“), „Mails gelesen“ nur, wenn das Einlesen läuft. Die Probe liest die Seite gleich nach dem Ankommen alle 100 ms: nie „0“, am Ende so viele wie im Gedächtnis. | `fertig.schonDaZahlen`, `FertigSchritt.tsx`; Test `fertig.test.mjs` |
| 7 | behoben | Nach dem Verbinden bleibt „Verbunden: dein Kalender „Privat“.“ stehen; die Wege treten zurück, statt eines zweiten „Kalender suchen und verbinden“ steht „Weiteren Kalender verbinden“. Unter Zugänge verschwindet der Knopf nach dem Erfolg, bis eine andere Adresse getippt wird. | `KalenderSchritt.tsx`, `KalenderMitAdresse.tsx` |
| 10 | behoben | „Ort · Aus einer Quelle zusammengestellt. Jede Zeile führt zur Quelle.“ | `AkteAbschnitte.tsx` |
| 11 | behoben | Unter der Antwort: „Gemerkt. Kingfisher soll diesen Fehler nicht wieder machen. Die Meldung bleibt auf diesem Rechner und ändert nichts an deinem Gedächtnis. Du findest sie unter Einstellungen → Für Techniker → Rückmeldungen.“ Unter „Für Techniker“: „Jede Meldung wird eine Prüffrage. Jede neue Fassung von Kingfisher muss sie bestehen …“, der Knopf heißt „Als Prüffragen speichern“; „wer Kingfisher verbessert“ und „Messlatte“ stehen nicht mehr in der Oberfläche. | `rueckmeldung.ts`, `Rueckmeldung.tsx`; Test `beleg.test.mjs` |
| 14 | behoben | Unter 900 px stehen alle sieben Ziele in einer Reihe ohne eigenen Rollbalken, das Zeichen über seinem Namen in kleiner Schrift; unter 700 px trägt nur der aktive Bereich seinen Namen, ohne Abschneiden. Wird es noch enger, bricht die Reihe um. Die Regel steht nur noch in `Seitenbreite.css` (vorher je Seite eine eigene Kopie in fünf Dateien). Gemessen bei 390 und 768 px auf Heute, Gespräche, Aufgaben, Gedächtnis, Kalender, Nachrichten, Einstellungen: kein Rollen, alle Ziele im Bild und mindestens 40 px groß, keine abgeschnittene Beschriftung, kein seitlicher Überlauf der Seite. `probe_seiten_ui.py` nimmt die Seitenleiste nicht mehr von der Überstandsprüfung aus. | `Seitenbreite.css`; Test `seitenbreite.test.mjs` |
| S1 | behoben, nicht auf dem Mac geprüft | README (englisch und deutsch): ab macOS 15 der Weg über Systemeinstellungen → Datenschutz & Sicherheit → „Dennoch öffnen“, für ältere Versionen Rechtsklick → Öffnen. | `README.md`; Test `test_kingfisher_starten.py` |
| S2 | behoben | Ein deutscher Startweg „Kingfisher starten (auf Deutsch)“ im README, oben verlinkt; das übrige README bleibt englisch. | `README.md` |
| S3 | behoben | README und Starter sagen eindeutig: Ollama installieren; ohne Ollama gibt es Mails, Termine und Briefing, aber keine Antworten auf Fragen und keine Einordnung im Hintergrund. Geprüft, was die Oberfläche ohne Ollama tut: „Dieser Rechner“ zeigte nur „antwortet gerade nicht. Starte es“ (ohne Hinweis, wo es das gibt, für wen es nie installiert war) und kein „Laden starten“; eine Frage bekam „Für Gespräche einen Anbieter in .env eintragen.“ Jetzt nennt der Schritt das Programm, den Download-Link und was ohne geht, und die Antwort ohne Modell sagt in Alltagssprache, was fehlt und wo man es einrichtet. | `README.md`, `scripts/kingfisher_starten.py`, `rechner.OHNE_OLLAMA`, `RechnerKarte.tsx`, `agent.OHNE_MODELL_SATZ`; Tests `test_agent.py`, `test_mappe.py`, `test_kingfisher_starten.py` |

**Nachgetragen:** „Pausieren“ steht auf Heute jetzt auch, wenn Kingfisher ohne Modell nur Mails einliest (`lerntFuss` mit `liestMails`); die Pause hält auch das Einlesen an. S1 und der übrige Startweg sind nur
auf einem Mac prüfbar.
