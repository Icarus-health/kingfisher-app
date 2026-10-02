# Fremdprobe: Erststart aus Sicht eines Nicht-Technikers

Stand: 30. September 2026, Commit `c1ba712`.

## Vorgehen

Ein Prüfer ohne Kenntnis von Repository und Dokumentation (gelesen wurde nur
`README.md`) ist als neuer Nutzer durch Erststart und erste Stunde gegangen:
Willkommen, Name, Mail, Kalender, Modelle, Freigaben, Autostart, Startseite,
erste Frage, Briefing, alle Bereiche der Einstellungen. Bedient wurde nur die
Oberfläche im echten Chromium (Playwright), bei 1280, 768 und 390 px Breite.
Es wurde kein Code geändert.

Aufbau der Probe, damit die Befunde richtig gelesen werden:

- Sidecar mit `create_app()` unter uvicorn auf `127.0.0.1:8890`, frisches
  Datenverzeichnis, Oberfläche aus `npm run build` (mit `design-source` wie im
  Dockerfile). Kein Docker, kein Mac-Helfer, Betriebssystem Linux.
- Ollama-Attrappe als echter HTTP-Dienst auf `127.0.0.1:11434` (Modellliste,
  Laden mit Fortschritt, Bereitschaftsprüfung, feste Antwort im Gespräch).
  Inhalte der Antworten sind deshalb kein Befund.
- Kein Netz nach außen: IMAP bei WEB.DE und der Ortsdienst des Wetters waren
  nicht erreichbar. Das Postfach wurde mit einer synthetischen Adresse
  (`lena.probe@web.de`) und einem erfundenen Passwort verbunden. Einen
  IMAP-Attrappenserver bieten die Probe-Skripte nicht.
- Bildschirmfotos liegen außerhalb des Repositorys im Scratchpad der Sitzung
  (`…/scratchpad/fremdprobe/bilder/`); die Dateinamen stehen in der Tabelle.

Schwere: **blockiert** (ein normaler Nutzer kommt nicht weiter oder glaubt
fälschlich, es funktioniere), **verwirrt** (versteht nicht, was los ist oder was
er tun soll), **stört** (kommt weiter, aber es reibt).

## Befunde

| Nr. | Schwere | Seite / Element | Wortlaut bzw. Beobachtung | Erwartet hätte ich | Bild |
|---|---|---|---|---|---|
| 1 | blockiert | Gespräche, Aufgaben, Nachrichten, Kalender, Einstellungen bei 390 und 768 px; Heute bei 768 px | Seite bleibt 1280 px breit, seitliches Scrollen, rechts abgeschnitten (Suchfeld, Kacheln, Einstellungsnavigation). Nur Heute (390) und Gedächtnis (768) passen sich an. | Einspaltige Ansicht wie bei Heute auf 390 px | `60-390-*.png`, `60-768-*.png`, `62-390-settings-direkt.png` |
| 2 | blockiert | Einrichtung → Mail → „Mit Google anmelden“ (ebenso Kalender → Google, Einstellungen → Mail/Kalender) | Knopf gesperrt. „Noch nicht freigeschaltet: Eine Google-Desktop-App-Konfiguration wird einmalig benötigt.“ Ausgeklappt: „Im eigenen Google-Cloud-Projekt einen OAuth-Client vom Typ Desktop-App anlegen … als Testnutzer eintragen“, dazu ein Feld „Desktop-Client-JSON“. „Die bisherige Kontoanbindung unten“ gibt es an dieser Stelle nicht. | Mit Google anmelden, ohne Cloud-Projekt; sonst Hinweis auf den Weg mit Adresse und Passwort | `07-google.png`, `08-google-vorbereiten.png`, `16-kalender-google.png` |
| 3 | blockiert | Einrichtung → Mail → „Postfach verbinden“ | Nach etwa 8 s: „Dein Postfach ist verbunden.“ Der Mailserver war nicht erreichbar, das Passwort erfunden; geprüft wurde also nichts. | Anmeldung wird geprüft; bei Fehler Grund in einem Satz (Passwort falsch, IMAP aus, Server nicht erreichbar) | `11-webde-verbinden.png` |
| 4 | blockiert | Einrichtung → Mail → „Mails einlesen“ | Knopf zeigt „Wird gestartet …“, nach dem Neuladen wieder „Mails einlesen“. Kein Ergebnis, kein Fehler. In den Einstellungen steht danach „Aufnahme noch nicht gestartet“. | Sichtbarer Start oder ein Grund, warum nicht | `12-mails-einlesen.png`, `13-mail-nach-einer-minute.png`, `46-einstellungen-mail.png` |
| 5 | blockiert | Einrichtung → Fertig | „Mails 0 … Gerade läuft nichts mehr im Hintergrund. Dein Briefing ist bereit.“ Das Postfach hat nie geantwortet. Der Hinweis darauf steckt eingeklappt auf der Startseite unter „Quellen teilweise nicht verfügbar (2)“. | „Dein Postfach antwortet nicht“ auf der Fertig-Seite, mit Knopf zur Behebung | `34-fertig.png`, `37-quellen-nicht-verfuegbar.png` |
| 6 | blockiert | Einrichtung → Freigaben → Meetings; Einstellungen → Dokumente | Auch für den Vorgabeordner: „Bitte wähle den Ordner im Fenster, das sich auf deinem Mac geöffnet hat. Der Mac-Helfer meldet sich gerade nicht … öffne sie neu“. Mit Docker und Browser (Startweg aus der README) gibt es weder Fenster noch App. | Vorgabeordner ohne Fenster übernehmen; ohne Mac-Helfer ein Weg, der im Browser geht | `26-meetings-einrichten.png`, `27-meetings-vorgabeordner.png`, `28-meetings-anderer-ordner.png` |
| 7 | blockiert | Einstellungen → Kalender → „Kalender hinzufügen“ | Für ein WEB.DE-Konto gibt es nur „HTTPS-iCalendar-Abonnement“ oder „CalDAV“ mit dem Feld „HTTPS-Abonnement-Adresse“. Die Einrichtung sagt nur: Google oder Mac. | Wie bei der Mail: Anbieter erkennen (WEB.DE ist bekannt), Adresse selbst ergänzen | `14-kalender.png`, `52-kalender-hinzufuegen.png` |
| 8 | blockiert | Einstellungen → Sicherung → „Sicherung öffnen“ | „Der lokale Sicherungshelfer ist nicht erreichbar. Öffne „Kingfisher-starten.command“ auf deinem Mac.“ Die Passwortfelder werden trotzdem angeboten. | Eine Sicherung, die ohne Zusatzprogramm läuft, oder kein Formular, das ins Leere führt | `53-sicherung-offen.png` |
| 9 | verwirrt | Einstellungen → Einrichtung und → Lokale KI | Die Einrichtung meldete „Alles eingerichtet und geprüft.“ Die Einstellungen sagen gleichzeitig: „Anderer Anbieter eingerichtet: qwen3.5:4b. Eine gespeicherte Modellauswahl bestätigt keine Verbindung.“, unter „Modell verwalten“: „Keine Modellliste erreichbar. Ollama starten …“, und unter „Gerät und lokale Modelle“: „Ollama meldet noch kein installiertes Modell.“ | Eine einzige Aussage: eingerichtet und funktionsfähig | `24-laden-zweiter-versuch-ende.png`, `45-einstellungen.png`, `49-lokale-ki.png`, `50-modell-verwalten.png` |
| 10 | verwirrt | Einrichtung → Dieser Rechner | Modellnamen stehen im Vordergrund (`qwen3.5:2b`, `tev1:0.8b`, `bge-m3`), dazu „Messlatte“, „8 GB nachts“. „Eine vorsichtige Vorauswahl, die auf jedem Rechner läuft“ braucht laut derselben Karte 13,5 GB Arbeitsspeicher. „Dieser Rechner hat seine Ausstattung noch nicht gemeldet“ ohne Hinweis, wie er das tut. | Aufgaben und ein Knopf; Modellnamen nur für Fortgeschrittene; die Ausstattung ermittelt das Programm selbst | `17-dieser-rechner.png` |
| 11 | verwirrt | Einrichtung → Dieser Rechner, fehlgeschlagenes Laden | „Das Modell ist geladen, hat die Prüfung aber nicht bestanden … Ein anderes Modell aus den Alternativen wählen oder die Messlatte auf diesem Rechner laufen lassen.“ Daneben steht weiter „Fehlt“; die übrigen drei Modelle werden nicht geladen. (Ausgelöst durch die Attrappe, die die Bereitschaftsfrage zunächst nicht beantwortete; der Wortlaut ist der Befund.) | Ein Knopf „Anderes Modell nehmen“; kein Fachwort; Status passend zum Text | `21-laden-laeuft.png`, `22-laden-fertig.png` |
| 12 | verwirrt | Einstellungen → Mail | Fachwörter in Folge: „Automatische Quellenaufnahme“, „Bestandsaufnahme“, „Mailbereiche prüfen“, „Posteingang (INBOX)“, „Aufnahmestand aktualisieren“; Zeitplan als Zahlenfeld „Abstand in Minuten“ (240). | Ein Schalter „Mails regelmäßig abrufen“ mit vernünftiger Vorgabe | `46-einstellungen-mail.png` |
| 13 | verwirrt | Einstellungen → Mail → „Mailbereiche prüfen“ | Über 28 s „Mailbereiche werden geprüft …“, dann „Die Änderung oder die Prüfung der Mailbereiche konnte nicht abgeschlossen werden. Bitte erneut versuchen.“ Kein Grund; das Konto heißt weiter „Verbunden“. | Grund in einem Satz, nach wenigen Sekunden | `47-mailbereiche-pruefen.png`, `48-mailbereiche-nach-90s.png` |
| 14 | verwirrt | Nachrichten | Mehrere Sekunden Ladeplatzhalter, dann „Der lokale Posteingang ist gerade nicht erreichbar.“ Nicht erreichbar war der Server von WEB.DE, nicht etwas Lokales. | „WEB.DE antwortet nicht“ mit Knopf zu den Verbindungen | `60-1280-nachrichten.png`, `61-nachrichten-40s.png` |
| 15 | verwirrt | Gespräch → „Gesprächsquelle ansehen“ | „Gespeicherte Quelle · keine bestätigte Aussage“, „Gespeichert · automatische Einordnung pausiert“, „Sortierergebnis verwerfen“, „Quelle ausschließen“, „Angabe berichtigen“. Unklar, warum etwas pausiert ist und was die Knöpfe bewirken. | Wenig oder kein Fachvokabular unter der eigenen Frage | `42-gespraechsquelle.png` |
| 16 | verwirrt | Einstellungen → Rückmeldungen | „Aus ihr wird ein Fall für die Messlatte … Gemessen wird mit python -m messlatte lokal --fragen rueckmeldungen-faelle.json.“ | Kein Kommandozeilenbefehl in der Oberfläche | `51-einstellungen-06-rckmeldungen.png` |
| 17 | verwirrt | Einstellungen → Automatik (Vorgabe) | Nach Einrichtung von Mail und Modellen: „Quellen automatisch sortieren: Pausiert“, „Automatische Quellenaufnahme: ausgeschaltet“, Zeitplan aus. Nichts davon wurde in der Einrichtung gefragt. | Nach verbundener Mail und fertigen Modellen läuft das Einlesen, oder die Einrichtung fragt einmal danach | `45-einstellungen.png`, `51-einstellungen-04-automatik.png` |
| 18 | verwirrt | Mehrere Stellen, Browser unter Linux | „Auf diesem Mac gespeichert“, „öffne sie auf diesem Mac neu“, „Öffne Kingfisher über die Mac-App“, „Docker-Speicher ist keine Angabe zum RAM des Rechners“. | Texte passend zum System, auf dem Kingfisher läuft | `15-kalender-mac.png`, `45-einstellungen.png`, `49-lokale-ki.png` |
| 19 | verwirrt | Einrichtung → Freigaben → Fahrzeiten | Häkchen gesetzt: „Fahrzeiten werden berechnet.“ Obwohl kein Startort eingetragen ist und „Apple Karten läuft nur auf dem Mac“. Alternativ „Eigenen Kartendienst einrichten“ mit `openrouteservice` und Schlüsselfeld. Die Marke neben der Überschrift bleibt „Aus“, bis die Seite neu geladen wird. | Einschalten erst möglich, wenn es auch rechnen kann; Marke sofort „An“ | `31-fahrzeiten.png`, `32-fahrzeiten-an.png` |
| 20 | verwirrt | Briefing | Englische Beschriftungen „MORNING BRIEFING“ (auch am Abend) und „Dashboard“ als Zurück-Knopf. Der Audiospieler zeigt ein Pause-Symbol, als liefe er, darunter „Lokales Audio ist derzeit nicht verfügbar.“ | Deutsch; Spieler ausgeblendet oder als nicht verfügbar erkennbar | `38-briefing-offen.png` |
| 21 | stört | Einrichtung → Name → „Später weitermachen“ | Name „Lena“ eingetippt, dann „Später weitermachen“: der Name ist verworfen, Gruß „Guten Tag.“ ohne Namen, ohne Rückfrage. | Getipptes wird mitgenommen | `03-name-eingetippt.png`, `04-mail-schritt.png` |
| 22 | stört | Heute | Bei nicht antwortendem Postfach 8,6 s nur Platzhalterkacheln, bevor der Gruß erscheint. | Gruß sofort, Mail nachladen | `35-zum-briefing.png` |
| 23 | stört | Einrichtung → Fertig → „Zum Briefing“ | Führt auf „Heute“, nicht ins Briefing; ein zweiter Klick auf „Briefing öffnen“ ist nötig. | Briefing öffnet sich direkt | `36-briefing-nach-12s.png` |
| 24 | stört | Briefing, Kopf | Datum „Mi, 30. September 2026 · Europe/Berlin“ und Überschrift werden von der Baumgrafik links überdeckt („…ptember 2026“). | Text lesbar über der Grafik | `38-briefing-offen.png` |
| 25 | stört | Briefing, leere Kacheln; Einrichtung → Mail | „Du findest es unter Einstellungen → Wetter und Nachrichten.“ und „Pausieren kannst du jederzeit unter Einstellungen → Mail.“ als Text, nicht als Verweis. | Ein Klick dorthin | `38-briefing-offen.png`, `11-webde-verbinden.png` |
| 26 | stört | Einrichtung → Beim Anmelden | Eigener Schritt, dessen einziger Inhalt ist: „Auf diesem System ist das noch nicht verfügbar.“ | Schritt ausblenden, wo es nicht geht | `33-beim-anmelden.png` |
| 27 | stört | Einrichtung, Schrittleiste | „Schritt 1 von 6“ bei sieben Punkten; bei 1280 px bricht „Fertig“ in eine zweite Zeile; „Fertig“ heißt zugleich der Knopf, der ein aufgeklapptes Feld schließt. | Stimmige Zählung, eine Zeile, eindeutige Knopfnamen | `01-erster-aufruf.png`, `26-meetings-einrichten.png` |
| 28 | stört | Gedächtnis | Bei 390 px ragt die Reiterzeile 27 px über den Rand. Leerer Zustand „Hier ist noch Platz. Sobald belegte Einträge vorliegen, erscheinen sie hier.“ ohne nächsten Schritt. In den Einstellungen: „Wortteile für die letzten N Jahre (0 = alle)“ als Zahlenfeld, „Alle 1 Quellen“. | Passende Breite; Hinweis, woher Einträge kommen; Auswahl statt Zahl | `60-390-gedaechtnis.png`, `60-1280-gedaechtnis.png`, `51-einstellungen-03-gedchtnis.png` |
| 29 | stört | Heute, erster Tag | „Seit gestern Abend: 1 Rückmeldung „Stimmt nicht“ notiert.“ am Tag der Einrichtung. | „Heute“ | `60-1280-today.png` |
| 30 | stört | Heute → „Quellen teilweise nicht verfügbar“ → „Verbindungen prüfen“ | Öffnet die Einstellungsübersicht, nicht den Bereich Mail. | Direkt zum betroffenen Postfach | `64-verbindungen-pruefen.png` |
| 31 | stört | Einstellungen → Sicherung | Passwort zweimal, mindestens 16 Zeichen. Beim Passwort üblich, aber doppelte Eingabe. | Ein Feld mit „anzeigen“ | `53-sicherung-offen.png` |
| 32 | stört | Einrichtung → Freigaben → Wetter, Browserkonsole | Ortssuche ohne Netz: „Der Ortsdienst antwortet gerade nicht. Bitte später erneut versuchen.“ (ehrlich); die Konsole meldet dazu `502 GET /api/v1/wetter/orte?suche=Mainz`. | Keine Konsolenfehler bei erwartbarem Ausfall | `30-wetter-suchen.png` |

## Stand je Befund

Nachgestellt in `scripts/probe_fremdprobe_ui.py` (Chromium, IMAP-Attrappe, die die Anmeldung verweigert,
schweigt oder nach der Anmeldung nicht mehr antwortet; Ollama-Attrappe als HTTP-Dienst). Die Befunde 6, 7, 8, 10, 11,
19, 25, 26 und 27 stellt `scripts/probe_einrichtung_ui.py` nach (Chromium, IMAP- und CalDAV-Attrappe als TLS-Dienste,
Ollama-Attrappe mit durchfallendem Prüfmodell, eigenes Benutzerverzeichnis, kein Helfer), die Befunde 1, 12, 14, 15,
16, 18, 20, 22, 24, 28, 31 und 32 `scripts/probe_seiten_ui.py` (alle Seiten bei 390, 768 und 1280 px, dazu je Befund
ein Abschnitt; IMAP-Attrappe, die nach dem Verbinden schweigt; Ortsdienst, der nicht antwortet). Befund 2 stellt
`scripts/probe_google_ui.py` nach (IMAP-Attrappe statt Gmail, iCal-Attrappe statt Google Kalender, Namensdienst-Attrappe
für eine Workspace-Domain).

| Nr. | Stand | Was sich geändert hat | Commit |
|---|---|---|---|
| 3 | behoben | „Postfach verbinden“ meldet sich vor dem Speichern einmal an (Wanduhr 10 s); sonst ein Satz mit Grund (Passwort falsch bzw. IMAP aus, App-Passwort, nicht erreichbar), und es wird kein Konto angelegt. | `8649538`, `e2b0f0c` |
| 4 | behoben | „Mails einlesen“ zeigt, worauf es wartet, und nach höchstens 15 s den Grund; sonst den Fortschritt („300 von 1.200 Mails gelesen“). Ursache: keine Wanduhr um die Abfrage der Mailbereiche, eine hängende Namensauflösung hielt den Knopf minutenlang. | `8649538`, `e2b0f0c` |
| 5 | behoben | Die Fertig-Seite prüft die Postfächer (`GET /api/v1/mail/erreichbar`) und sagt „Dein Postfach antwortet nicht“ mit Grund und Knopf „Postfach prüfen“ (zum Mail-Schritt, dort „neu verbinden“); „Dein Briefing ist bereit“ nur, wenn es stimmt. | `8649538`, `e2b0f0c` |
| 9 | behoben | Eine Statusquelle `lokale_ki.py` (bereit, fehlt, Ollama antwortet nicht, Cloud, keins); Übersicht, „Lokale KI“ und „Gerät und lokale Modelle“ zeigen nur ihren Satz. Die Modellliste kommt von der Adresse, unter der Kingfisher Ollama selbst findet, nicht mehr fest von `host.docker.internal`. | `f7363b9` |
| 17 | behoben | Die Fertig-Seite bietet einmal, vorausgewählt, an: Mails regelmäßig einlesen und Quellen lokal sortieren (nur Vorschläge). Nach „Zum Briefing“ laufen beide; Einstellungen → Für Techniker → Stand aller Bereiche sagt es. | `e2b0f0c`, `f7363b9` |
| 21 | behoben | „Später weitermachen“ (und jeder Sprung in der Schrittleiste) speichert den getippten Namen. | `8079a4b` |
| 23 | behoben | „Zum Briefing“ öffnet das Briefing direkt (`/today?briefing=1`). | `8079a4b` |
| 27 | behoben | „Schritt 1 von 7“ über sieben Punkten; der Knopf zum Zuklappen heißt „Zuklappen“. Ab 701 px steht die Schrittleiste in einer Zeile, „Fertig“ bricht bei 1280 px nicht mehr um (mit sechs und mit sieben Punkten). | `8079a4b`, `d592c5d` |
| 26 | behoben | Der Stand der Einrichtung nennt `autostart_verfuegbar`; ohne Helfer (Browser, Docker) entfällt „Beim Anmelden“, und Zählung, Nachbarn und erster offener Schritt folgen der sichtbaren Liste („Schritt 1 von 6“). Auf dem Mac bleibt die Frage. | `d592c5d` |
| 25 | behoben | „Einstellungen → …“ ist ein Verweis, der dorthin springt (`verweis.ts`, `Verweis.tsx`): Mail, Einlesen, Kalender, Freigaben, Anmelden, Fertig und die leeren Kacheln Wetter und Nachrichten im Briefing. Ein Test verbietet den Weg als Text in diesen Dateien. | `1d4b2ae` |
| 19 | behoben | Einschalten erst, wenn es rechnen kann (Startort und Apple Karten oder ein Kartendienst); sonst bietet die Karte das Feld für den Startort an bzw. sagt in einem Satz, dass ein Kartendienst fehlt, und verweist dorthin. Der Server lehnt es ebenso ab (409). Die Marke im Assistenten steht sofort auf „An“. | `12feff6` |
| 7 | behoben | Kalender wie Mail: Adresse genügt, Anbieter erkannt (WEB.DE, GMX, iCloud, Posteo, mailbox.org, Fastmail), Kalender selbst gefunden, Anmeldung vor dem Speichern mit Wanduhr 10 s und Grund in einem Satz; das Passwort eines Postfachs mit derselben Adresse gilt; unbekannter Anbieter: „Für diesen Anbieter brauche ich die Adresse“ mit Feld; Google und Microsoft: ehrlicher Satz. Die Adressen im Katalog sind nicht abgerufen (siehe docs/47). | `2a89dc7` |
| 6 | behoben | Ohne Mac-Helfer: Ordner im Browser wählen (bekannte Orte, eigener Pfad mit Prüfung, ein Satz), der Sidecar liest selbst, sofort und dann etwa einmal pro Minute. Mit Helfer verspricht der Vorgabeordner kein Fenster mehr. Im Container ohne eingebundenen Ordner sagt die Karte das in einem Satz. | `dd57961` |
| 8 | behoben | Ohne Sicherungshelfer: Kingfisher schreibt das verschlüsselte Archiv selbst (`sicherung_download.py`), stellt es zur Probe wieder her und gibt es dem Browser als Datei; auf dem Rechner bleibt keine Kopie. Kein Formular mehr, das ins Leere führt. Die Sätze der Sicherung gehen durch `system.ts` (Befund 18): kein „Mac“ außerhalb des Mac; schweigt der Helfer auf dem Mac, sagt ein Satz, wie er wiederkommt, und der Download bleibt. | `97bc837`, `4806c43` |
| 31 | behoben | Das Sicherungspasswort steht einmal da, mit „anzeigen“/„verbergen“; der Hinweis zählt die fehlenden Zeichen. Gilt für den Weg mit Helfer und für den Download. | `97bc837`, `13a2980` |
| 10 | behoben | „Dieser Rechner“ zeigt, was Kingfisher hier kann (Fragen beantworten, im Hintergrund einordnen, Antworten prüfen), Größe und Dauer des Ladens und einen Knopf; Modellnamen nur im Aufklapper „Für Techniker“. Ohne Bericht misst der Sidecar den Arbeitsspeicher selbst (im Container als Untergrenze). | `2eb360f` |
| 11 | behoben | Eine nicht bestandene Prüfung hält die übrigen Modelle nicht auf; der Stand heißt dann „Prüfung nicht bestanden“, und „Anderes Modell nehmen“ lädt die nächste passende Wahl. Kein „Messlatte“ im Satz. | `2eb360f` |
| 29 | behoben | Am Tag, an dem das Logbuch angelegt wurde, heißt es „Heute: …“ bzw. „Heute noch nichts Neues.“ | `6600aa8` |
| 30 | behoben | „Verbindungen prüfen“ führt nach `/settings#zugaenge` (bei Wetter `#darf`); die Einstellungen öffnen den Reiter aus der Adresse (docs/47). | `8079a4b` |
| 13 | teilweise | Die Prüfung der Mailbereiche nennt jetzt den Grund (gleiche Sätze wie beim Verbinden) nach höchstens 15 s; der Kontostatus „Verbunden“ daneben ist unverändert. | `8649538` |
| 1, 28 | behoben | Keine Mindestbreite mehr; `Seitenbreite.css` gibt allen Seiten die Stufen 1100/900/700 px, die Gedächtnisauswahl bricht um; leerer Zustand im Gedächtnis mit Satz und Verweis „Quellen verbinden“; Suchindex als Auswahl, „1 Quelle“ im Singular. | `640ae55` |
| 12 | behoben | „Mails regelmäßig abrufen“ als Schalter (Vorgabe alle vier Stunden, alle Postfächer) und Auswahl „Wie oft“; „Ältere Mails einlesen“, „Ordner ansehen“, „Posteingang“ statt der Fachwörter (Liste in docs/47). | `b33d16c` |
| 14, 22 | behoben | `postfach_lage.py`: Wanduhr, Grund in einem Satz, schweigendes Postfach wird gemerkt und sofort gemeldet; Nachrichten sagen „Probe-Post antwortet gerade nicht“ mit „Postfach prüfen“; Heute zeigt den Gruß sofort und holt die Post danach. | `393a516` |
| 15 | behoben | Unter der eigenen Frage ein Satz, der Wortlaut, „Wortlaut berichtigen“ und „Nicht mehr verwenden“; Technisches im Aufklapper „Für Techniker“. | `2cef4f9` |
| 16 | behoben | Kein Befehl in der Oberfläche; „Was daraus wird: Jede Meldung wird eine Prüffrage …“; der Befehl steht in docs/38. | `c7fba70` |
| 18 | behoben | `laufumgebung.py` sagt, wo Kingfisher läuft (Mac-App, Docker im Browser, Linux, Windows); die Oberfläche wählt ihre Sätze mit `system.ts` („Auf diesem Rechner gespeichert“; was nur ein Mac-Helfer kann, sagt das). Seit dem Zusammenführen mit der Einrichtung auch dort, in der Ordnerwahl, der Sicherung und bei „Akten als Ordner“; `tests/system.test.mjs` prüft alle Dateien der Oberfläche, Ausnahmen nur mit Grund. | `4806c43`, `468976b`, `e428cb0` |
| 20, 24 | behoben | „Briefing“ und „Zurück zu Heute“; kein Audiospieler ohne lokales Audio; Datum und Überschrift auf einer hellen Fläche über dem Bild. | `164629c` |
| 32 | behoben | Stummer Ortsdienst: 200 mit `grund` und Satz statt 502; die Konsole bleibt leer. | `9ab5129` |
| 2 | behoben | Google ohne eigenes Cloud-Projekt: Gmail über IMAP mit App-Passwort (zwei Sätze mit Verweis auf die Google-Seite „App-Passwörter“; die typische Ablehnung heißt „App-Passwort nötig“), Google Workspace mit eigener Domain am Mailserver erkannt, Kalender über die „Geheime Adresse im iCal-Format“ (nur lesen, vorher ein Abruf mit Zeitgrenze, nichts sonst geht hinaus, die Adresse im Schlüsselbund). „Mit Google anmelden“ steht vorne nur, wenn ein Techniker es eingerichtet hat; kein gesperrter Knopf mehr (docs/47). Browserprobe `scripts/probe_google_ui.py`. | `88b0a08` |

Hinweis zu 32: Die Ortssuche antwortet bei stummem Dienst jetzt mit 200 und einem Satz. Die erwartbaren Fehlantworten
beim Verbinden eines Postfachs (422 bei abgelehnter Anmeldung, 503 bei schweigendem Postfach) erscheinen weiter in der
Browserkonsole; `probe_fremdprobe_ui.py` führt sie getrennt. `probe_seiten_ui.py` braucht keine erwarteten Fehlantworten.

Browserkonsole: Außer Nr. 32 blieb sie auf allen besuchten Seiten leer. (Ein
erster Lauf ohne `design-source` im Bau zeigte 404 für Schriften und Bilder;
das lag am Probenaufbau, nicht an der App, und ist kein Befund.)

## Anzahl je Schwere

| Schwere | Anzahl |
|---|---|
| blockiert | 8 |
| verwirrt | 12 |
| stört | 12 |

## Was am besten gefiel

1. **Mail mit Adresse und Passwort.** Nach der Adresse steht sofort
   „Erkannt: WEB.DE“, ein Passwortfeld und der Satz, dass IMAP eingeschaltet
   sein muss, mit „So bekommst du es“. Kein Host, kein Port. Genau so sollte
   auch der Kalender gehen.
2. **Modelle mit einem Knopf.** „Alles einrichten“ fragt einmal nach, nennt
   Größe (7,9 GB) und Dauer (3 bis 11 Minuten), zeigt Fortschritt in Prozent
   und endet mit „Alles eingerichtet und geprüft.“ Nichts wird ohne
   Bestätigung geladen.
3. **„Stimmt nicht?“ und die Freigaben.** Rückmeldung zu einer Antwort in zwei
   Klicks, quittiert mit „Gemerkt.“. Auf der Freigaben-Seite ist alles
   ausgeschaltet, jede Karte sagt in einem Satz, welche Daten wohin gehen, und
   das Ausschalten (Fahrzeiten) wurde sofort bestätigt.
