# Einstellungen in zwei Ebenen (M3)

Stand: 30. September 2026. Umsetzung von M3 („Für Nicht-Techniker“) aus
[`41-zielbild.md`](41-zielbild.md): zwei Ebenen in den Einstellungen, Feed-Vorgaben zum Anklicken und eine Seite, die
auch schmal funktioniert. Oberfläche: `app/kingfisher/src/Einstellungen/`. Die einzelnen Karten sind dieselben
Komponenten wie zuvor; neu ist nur die Gliederung darüber.

## Die Regel: vorne Alltag, hinten Technik

> **Vorne steht, was ein Mensch tun will. Hinten steht, was ein Techniker einstellen könnte.**

Vorne gibt es vier Karten in Alltagssprache. Alles andere liegt hinter „Für Techniker“, eingeklappt und mit einem Satz,
dass dort nichts geändert werden muss. Ein Wort kommt nach vorne, wenn es die sechs Prüffragen aus `CLAUDE.md`
besteht: Der Nutzer muss nichts wissen, was er nicht wissen kann, nichts doppelt eingeben, nichts tippen, was er
zeigen könnte; er sieht, was passiert ist; er kann es zurücknehmen; die Vorgabe ist die richtige. Ein Fachwort, das
das nicht besteht („IMAP“, „Embedding“, „Rolle“, „Feed“), gehört hinter „Für Techniker“ oder wird übersetzt.

## Bestandsaufnahme vor M3

Zwölf Reiter, alle gleichrangig, in der Reihenfolge, in der die Dinge entstanden. „Jeder“ heißt: ein Nicht-Techniker
kommt im Alltag damit in Berührung. „Techniker“ heißt: Die Vorgabe genügt; wer hier etwas ändert, weiß, was er tut.

| Reiter | Karte (Überschrift) | Was sie tut | Wer | Fachwörter, die sie vorne zeigte |
|---|---|---|---|---|
| Einrichtung | Einrichtung in einem Durchgang | Assistent wieder öffnen, was noch offen ist | jeder | – |
| Einrichtung | Beim Anmelden starten | Schalter für den Autostart | jeder | – |
| Einrichtung | Kingfisher lernt gerade | Fortschritt der Einordnung im Hintergrund | jeder | „Einordnung“ |
| Einrichtung | acht Statuskarten (`SetupOverview`) | Stand je Bereich, Sprung dorthin | beide | „Lokale KI“, „Automatik“, „Quellenaufnahme“ |
| Mail | Gmail (`GoogleSignIn`) | Mit Google anmelden; einmalige Vorbereitung | jeder, Vorbereitung Techniker | „OAuth-Client“, „Desktop-Client-JSON“, „Cloud-Projekt“ (eingeklappt) |
| Mail | Mail (Liste, Formular) | Postfächer verbinden und trennen | jeder | „IMAP-Server“, „SMTP“, „Port“ (eingeklappt, nur bei unbekanntem Anbieter) |
| Mail | Automatische Quellenaufnahme | Zeitplan, Kontenwahl, Bestandsaufnahme | Techniker | „Zeitplan“, „Quellen“, „INBOX“ |
| Kalender | Google-Kalender | Mit Google anmelden | jeder | wie oben |
| Kalender | Kalender (Liste, Formular) | Kalender verbinden und trennen | jeder | „CalDAV“, „HTTPS-iCalendar-Abonnement“ |
| Kalender | Kalender auf diesem Mac | Mac-Kalender wählen | jeder | „Adapter“ (eingeklappt) |
| Kalender | Fahrzeiten | Wegezeit berechnen, Startort, Verkehrsmittel, Kartendienst | Schalter jeder, Kartendienst Techniker | „Kartendienst“, „Schlüssel“, „OpenRouteService“ |
| Wetter und Nachrichten | Wetter im Briefing | Wetter holen, Ort wählen | jeder | „Open-Meteo“ |
| Wetter und Nachrichten | Nachrichten im Briefing | Eine Meldung am Tag, Quellen wählen | jeder | „Feed“, „RSS oder Atom“, „https“ |
| Lokale KI | Für diesen Rechner empfohlen | Modell je Aufgabe, Speicherbedarf des Orchesters, ein Klick | Techniker | „Modell“, „Orchester“, „Arbeitsspeicher“, „Cloud je Aufgabe“ |
| Lokale KI | Antwortzeit | Protokoll, Schalter für Sätze und Prüfmodell | Techniker | „Median“, „90 %-Wert“, „Prüfmodell“ |
| Lokale KI | Lokale KI | Ollama-Modell wählen und prüfen | Techniker | „Ollama“, „Modell“ |
| Lokale KI | Gerät und lokale Modelle | Ausstattung, installierte Modelle | Techniker | „GiB“, „RAM“ |
| Dokumente | Meetings | Eingangsordner für Mitschriften | jeder | „MacWhisper“ |
| Dokumente | Dokumente automatisch aufnehmen | Ordner überwachen | jeder | „SRT“, „VTT“, „DOCX“ (eingeklappt) |
| Dokumente | Dateien | Einzelne Dateien aufnehmen | jeder | „Transkripte (SRT/VTT)“, „Textebene“ (eingeklappt) |
| Gedächtnis | Was Kingfisher aufgefallen ist | Befunde des Lint über alle Akten | Techniker | „Lint“, „Befund“ |
| Gedächtnis | Suche in alten Quellen | Wortteile für die letzten N Jahre (seit der Fremdprobe eine Auswahl) | Techniker | „Wortteile“, „Suchindex“ |
| Automatik | Quellen automatisch sortieren | Einordnung im Hintergrund an und aus | Techniker | „sortieren“, „lokale KI“ |
| Automatik | Mailfilter | Erlaubte und gesperrte Absender | Techniker | „@Domain“ |
| Arbeitsvorlieben | Arbeitsvorlieben | Antwortlänge, Anrede, Emojis je Bereich | jeder | „Bereich“, „Herkunft“, „Belegantworten“ |
| Rückmeldungen | Was du gemeldet hast | Liste der „Stimmt nicht?“-Meldungen, Export | Techniker | „Messlatte“ |
| Sicherung | Vollständige Sicherung | Verschlüsselt sichern | jeder | – |
| Erweitert | Lokale Modellauswahl | Automatische Auswahl, Prüfung | Techniker | „Routing“, „Werkzeugfähigkeit“ |
| Erweitert | Aktuelle Quellen | Öffentliche Seiten von Hand abrufen | Techniker | „HTTPS-Adresse“, „Themen“ |
| Erweitert | Für Techniker → Akten als Ordner | Akten als Markdown für Obsidian | Techniker | „Markdown“, „Obsidian“ |

Dazu kam rechts eine Spalte „Deine Daten bleiben bei dir“ (336 px breit, auf jeder Reiterseite).

Befund: Von 29 Karten braucht im Alltag etwa die Hälfte niemand. Die Reiter sagen nicht, was man tun will („Erweitert“,
„Automatik“, „Gedächtnis“), und die drei Einwilligungen, die etwas nach außen schicken (Wetter, Nachrichten,
Fahrzeiten), standen auf zwei Reitern, der Autostart auf einem dritten und die Cloud für Antworten hinter „Lokale KI“
in einem Aufklappbereich für Fortgeschrittene.

Dazu die Breite: `styles.css` setzte `html, body, #root { min-width: 1280px }`; unter 1280 px war die Seite breiter als
das Fenster, die Seitenleiste (220 px, fest) deckte die linken Reiter zu.

## Die neue Gliederung

Fünf Reiter, in dieser Reihenfolge. Die Reiter stehen im Adressteil (`/settings#darf`), damit Verweise von anderen Seiten
ankommen; die alten Kennungen (`#world`, `#model`, `#memory`, …) führen an den neuen Ort (`gliederung.ts`, `ALT`).

| Reiter | Was dort ist | Bausteine (unverändert, nur anders einsortiert) |
|---|---|---|
| **Zugänge** | Postfächer, Kalender, Ordner und Dateien: verbinden, trennen, Stand. Oben der Einrichtungsassistent und „Kingfisher lernt gerade“. | `GoogleSignIn`, Quellenliste und -formulare (`Quellenformulare.tsx`), `MacCalendarSettings`, `TranscriptSettings`, `FolderSyncSettings`, `DocumentImport`, `EinrichtungKopf` |
| **Was Kingfisher darf** | Zehn Schalter (Stand Paket D, 26.10.2026; drei davon von Haus aus an, siehe unten „Wege nach draußen“). Ursprünglich sieben, alle aus: morgens das Wetter holen, eine Meldung aus der Welt zeigen, Wegezeit berechnen, beim Anmelden starten, Mitteilungen auf dem Mac (seit Oktober 2026, siehe unten), Cloud für Fragen und Antworten nutzen, neue Mails in der Cloud einordnen (nur Anthropic, eigene Einwilligung, [46-hintergrund.md](46-hintergrund.md#cloud-einordnung-neuer-mails)). Bei jedem ein Satz, was den Rechner verlässt. | `Wetter`, `Nachrichten` (`WeltSettings.tsx`), `WegezeitSettings`, `AutostartWahl`, `Mitteilungen`, `CloudSchalter`, `CloudEinordnungSchalter` |
| **Kingfisher und du** | Name, Startort, Zeitzone (nur zum Lesen), Kreis (kommt später), ausgeklappt „Wie Kingfisher dir antwortet“. | `Ich.tsx`, `WorkingProfileSettings` |
| **Sicherung** | Verschlüsselt sichern. | `RecoverySettings` |
| **Für Techniker** | „Hier muss nichts geändert werden.“ Fünfzehn eingeklappte Abschnitte, die erst beim Aufklappen laden. | siehe unten |

Hinter „Für Techniker“: Modelle je Aufgabe und Speicherbedarf (mit lokaler Modellwahl und Gerät), Modellauswahl (Routing),
Antwortzeiten mit den Schaltern für Sätze und Prüfmodell, Suchindex, Akten als Ordner, Rückmeldungen, Befunde, Zeitplan
und Hintergrund (Sortieren, Abruf je Postfach), Filterregeln für Post, weitere öffentliche Quellen, eigener Kartendienst
für die Wegezeit, Google-Anmeldung vorbereiten, Microsoft-Anmeldung vorbereiten, Stand aller Bereiche, Speicherorte.

### Was sich für den Nutzer ändert

* **Keine Doppelung.** Der Startort steht nur unter „Kingfisher und du“; die Wegezeit zeigt ihn und verweist dorthin, das
  Wetter schlägt den Ort daraus vor. Der Autostart stand vorher in der Einrichtung und im Assistenten, jetzt bei den
  Schaltern (der Assistent fragt ihn weiter einmal).
* **Der Schalter führt.** „Morgens das Wetter holen“ ohne Ort öffnet nur die Ortssuche; erst der Klick auf einen Treffer
  schaltet ein. Die Quellen zum Anklicken erscheinen erst, wenn der Schalter an ist (ohne Einwilligung kein Abruf).
* **Cloud mit einem Klick zurück.** Einschalten braucht einen Anbieter mit hinterlegtem Zugang und die Zustimmung in einem
  Satz; fehlt der Zugang, sagt die Karte das und verweist an „Für Techniker“. Ausschalten ist ein Klick. Der Schalter
  gilt für „Fragen verstehen“ und „Antworten formulieren“; alles andere bleibt auf diesem Rechner (`cloud_moeglich`).
* **Mails abrufen in Alltagswörtern** (Fremdprobe, Befund 12). Unter „Zeitplan und Hintergrund“ steht ein Schalter „Mails
  regelmäßig abrufen“ (beim Einschalten gelten alle verbundenen Postfächer, Vorgabe alle 30 Minuten, seit Fremdprobe 3, Befund 13) und eine Auswahl
  „Wie oft“ (alle 30 Minuten, jede Stunde, alle vier Stunden, täglich) statt eines Zahlenfelds; jede Änderung gilt sofort. Dahinter
  derselbe Zeitplan (`PUT /api/v1/schedule`). Fachwortliste, alt → neu (`mailAbruf.ts`, `ALTE_WOERTER`, Test
  `mail-abruf.test.mjs`):

  | Vorher | Jetzt |
  |---|---|
  | Automatische Quellenaufnahme | Mails regelmäßig abrufen |
  | Zeitplan einschalten, Abstand in Minuten | Schalter; Auswahl „Wie oft“ |
  | Bestandsaufnahme, Mailbestand aufnehmen | Ältere Mails einlesen |
  | Mailbereiche prüfen | Ordner ansehen |
  | Bestand aufnehmen und aktuell halten | Diese Ordner einlesen |
  | Posteingang (INBOX), INBOX | Posteingang |
  | Aufnahmestand aktualisieren, Status aktualisieren | Stand neu laden |
  | Bestand erfassen, Quellen aufnehmen | Mails zählen, Mails einlesen |

* **Fachwörter übersetzt.** Kalender: „Mit einer Adresse (Kalender-Abo, nur lesen)“ statt „HTTPS-iCalendar-Abonnement“,
  „Mit Benutzername und Passwort“ statt „CalDAV“. Die Servereinstellungen eines Postfachs stehen nur noch eingeklappt
  unter „Nur wenn dein Anbieter nicht dabei ist“ (`ServerFelder.tsx`). Die Google-Vorbereitung (OAuth-Client) wanderte
  hinter „Für Techniker“; seit Befund 2 steht „Mit Google anmelden“ vorne nur noch, wenn sie erledigt ist (siehe
  „Google ohne eigenes Cloud-Projekt“ unten).

### Mac oder Rechner

Kein Text der Einstellungen nennt den Mac fest (Fremdprobe, Befund 18). Der Sidecar sagt, wo Kingfisher läuft
(`laufumgebung.py`: Mac-App, Docker im Browser, Linux, Windows); die Oberfläche setzt in Texte mit `{Rechner}` „Mac“ oder
„Rechner“ ein (`fuerSystem` in `system.ts`). Was nur ein Mac-Helfer kann (Mac-Kalender, Ordner im Fenster wählen,
Sicherung in den Sicherungsordner), sagt auf dem Mac, was zu tun ist, wenn der Helfer schweigt, und anderswo ehrlich,
dass es das dort nicht gibt (`nurAufDemMac`). Die Karte „Kalender auf diesem Mac“ erscheint nur auf dem Mac. Wo es einen
Weg ohne Helfer gibt (Ordner im Browser, Sicherung als Download, siehe unten), gilt dieser; der Satz zum Helfer steht
dann nur auf dem Mac. `tests/system.test.mjs` prüft alle Dateien unter `src/`, auch `Einrichtung/`.

## Zugänge ohne Fachwissen (Fremdprobe, Oktober 2026)

* **Kalender wie Mail** (Befund 7). „Kalender hinzufügen“ fragt zuerst nach der Mailadresse (`KalenderMitAdresse.tsx`,
  dieselbe Karte im Assistenten). Der Anbieter wird erkannt, die Adresse des Kalenders steht im Katalog
  (`providers_mail.caldav_url`), Kingfisher sucht die Kalender selbst und meldet sich vor dem Speichern an
  (`kalender_anmeldung.py`, `POST /api/v1/integrations/calendar/anmelden`, Wanduhr 10 s, Grund in einem Satz). Ist schon
  ein Postfach mit derselben Adresse verbunden, gilt dessen Passwort. Kennt der Katalog den Anbieter nicht, sagt die
  Karte „Für diesen Anbieter brauche ich die Adresse deines Kalenders“ und bietet ein Feld; bei Google und Microsoft
  steht, dass es mit Passwort nicht geht. Das Abo mit eigener Adresse und das Formular mit Benutzername stehen
  eingeklappt unter „Für Techniker: ein Kalender-Abo oder eine eigene Adresse“; auch dort wird vorher angemeldet.
  **Die Kalenderadressen im Katalog sind nicht abgerufen** (iCloud, GMX, WEB.DE, mailbox.org, Posteo, Fastmail; der
  Container erreicht das Netz nicht). Die Suche fällt auf `/.well-known/caldav` desselben Hosts zurück; scheitert sie,
  fragt die Karte nach der Adresse.
* **Ordner im Browser** (Befund 6). Ohne Helfer am Mac zeigen Meetings und Dokumente bekannte Orte zum Anklicken
  (Vorgabeordner `~/Documents/Kingfisher/…`, nur außerhalb eines Containers; von einem Techniker eingebundene Ordner aus
  `KINGFISHER_ORDNER`) und ein Feld für einen anderen Ordner, den Kingfisher prüft (`ordner_lokal.py`,
  `GET/POST …/orte|lokal`). Freigegeben wird nur der angeklickte Ordner; der Sidecar liest ihn selbst, sofort und dann
  etwa einmal pro Minute. Mit Helfer gilt dessen Auswahldialog; der Vorgabeordner braucht dort kein Fenster.
* **Sicherung ohne Helfer** (Befund 8). Ohne Sicherungshelfer schreibt Kingfisher das verschlüsselte Archiv selbst,
  stellt es zur Probe wieder her und gibt es dem Browser als Datei (`sicherung_download.py`,
  `POST /api/v1/recovery/herunterladen`); ein Passwortfeld mit „anzeigen“/„verbergen“, der Hinweis zählt die fehlenden
  Zeichen (Befund 31). Die Sätze gehen durch `system.ts`: Außerhalb des Mac nennt die Sicherung keinen Mac; schweigt der
  Helfer auf dem Mac, sagt ein Satz, wie er wiederkommt, und der Download bleibt.
* **Google ohne eigenes Cloud-Projekt** (Befund 2, 1. Oktober 2026). „Mit Google anmelden“ braucht ein
  Google-Cloud-Projekt mit OAuth-Client; das legt kein Nicht-Techniker an. Vorne steht deshalb der Weg, der ohne geht:
  * **Post:** Gmail über IMAP mit App-Passwort. Die Karte sagt in zwei Sätzen, dass Google nur ein App-Passwort annimmt,
    dass es dafür die Bestätigung in zwei Schritten braucht und wo man es erzeugt; der Verweis heißt „Zur Google-Seite
    „App-Passwörter““ und führt nach `https://myaccount.google.com/apppasswords` (`providers_mail.py`, `help_label`).
    Lehnt Google ab (am Server `imap.gmail.com` oder an Googles Wortlaut `Invalid credentials (Failure)` erkannt), steht
    „App-Passwort nötig: …“ da, und es wird kein Konto angelegt (`mail_anmeldung.GOOGLE_SATZ`).
  * **Google Workspace mit eigener Domain:** erkennt die eine Anbieter-Erkennung (siehe unten, „Eine Erkennung für
    Google, Microsoft und den Katalog“) am Mailserver der Domain, statt „Welcher Anbieter?“ zu fragen.
  * **Kalender:** über die „Geheime Adresse im iCal-Format“ aus den Einstellungen des Google-Kalenders, nur lesend
    (`GoogleKalenderAdresse.tsx`, `googleWeg.ts`, `kalender_abo.py`, `POST /api/v1/integrations/calendar/abo`). Die
    Karte sagt in zwei Sätzen, wo die Adresse steht und dass nichts hinausgeht außer dem Abruf dieser Adresse.
    Kingfisher erkennt die Adresse (geheim, öffentlich, eine Einbettungs- oder Einstellungsseite, `webcal://`), ruft sie
    vor dem Speichern einmal ab (Wanduhr 10 s, keine Weiterleitung, höchstens 25 MB, gültiges iCalendar) und nennt sonst
    den Grund in einem Satz. Die Adresse ist ein Schlüssel zum Kalender: Sie liegt im Schlüsselbund wie ein Passwort; in
    den Einstellungen steht nur `https://calendar.google.com/`. Wer bei „Kalender hinzufügen“ eine Gmail- oder
    Workspace-Adresse eingibt, landet bei demselben Feld.
  * **„Mit Google anmelden“** steht vorne nur, wenn ein Techniker es unter „Für Techniker → Google-Anmeldung
    vorbereiten“ eingerichtet hat (und Zugänge geschützt gespeichert werden). Ohne Einrichtung gibt es keinen gesperrten
    Knopf und kein „Noch nicht freigeschaltet“ mehr (`googleAnmeldungVorne`; Mail-Schritt, Kalender-Schritt, Zugänge).
  * Prüfung: `test_kalender_abo.py` (iCal-Attrappe `tests/ical_attrappe.py`, echter HTTPS-Dienst), `test_anbieter_erkennen.py`
    (Namensdienst-Attrappe `tests/dns_attrappe.py`, Netzsperre `kein_netz`), `test_mail_anmeldung.py` (IMAP-Attrappe im Modus
    `google_ablehnen`), `google-weg.test.mjs`, `kalender-weg.test.mjs`; Browserprobe `scripts/probe_google_ui.py`.
  * Offen: Die Google-Adressen sind nicht gegen Google abgerufen (kein Netz im Container); der Pfad der geheimen Adresse
    folgt der heute dokumentierten Form. Ein Kalender-Abo mit eigener Adresse unter „Für Techniker“ wird weiter ohne
    Probeabruf gespeichert.
* **Wegezeit** (Befund 19). Der Schalter lässt sich erst einschalten, wenn Kingfisher rechnen kann (Startort und Apple
  Karten oder ein eigener Kartendienst); die Karte bietet das Feld für den Startort an oder verweist auf den
  Kartendienst hinter „Für Techniker“. Der Server lehnt ein Einschalten ohne beides mit 409 und demselben Satz ab.

* **Zugänge, die nicht laden** (V3, 25.10.2026). Antwortet `GET /api/v1/integrations` nicht, steht oben „Die lokalen
  Integrationen sind gerade nicht erreichbar.“ mit „Wiederholen“, und unter Postfächer und Kalender je „Nicht geladen.“
  statt grauer Ladebalken, die ewig stehen blieben (`gliederung.zugangListe`, Test `einstellungen-gliederung.test.mjs`,
  Browserprobe `scripts/probe_einstellungen_ui.py`). Ein späterer Fehler (etwa beim Trennen) lässt die geladene Liste stehen.

## Microsoft 365 unter Zugänge (M5, Oktober 2026)

* **Mit Microsoft anmelden** (Karte „Microsoft 365“, `MicrosoftZugang.tsx`): Code mit Kopierknopf, Link zu Microsoft,
  Stand mit Restzeit; danach ein Postfach und ein Kalender („Microsoft · nur lesen“). Je Konto
  „Teams-Mitschriften dazunehmen“ (zweiter Code, Zustimmung der IT nötig) und je Besprechung ein Satz, was aus der
  Mitschrift wurde, mit „Jetzt nachsehen“. Trennen des letzten Zugangs eines Kontos nimmt die Anmeldung mit.
* **Im Mail-Schritt** erkennt Kingfisher Microsoft 365 an der Adresse (dieselbe eine Erkennung wie für Google, siehe
  unten; DNS, ohne Microsoft zu fragen) und zeigt statt des Passwortfelds die Anmeldung; „Lieber mit Adresse und
  Passwort“ bleibt. Fehlt die Kennung der App, sagt die Karte das und zeigt den Weg mit Passwort.
* **Für Techniker → Microsoft-Anmeldung vorbereiten** (`MicrosoftVorbereiten.tsx`): die Kennung der App
  (Client-ID), Vorgabe aus `KINGFISHER_MS_CLIENT_ID`. Anleitung zur Registrierung in
  [`50-microsoft-365.md`](50-microsoft-365.md#für-techniker-die-app-registrieren).

## Eine Erkennung für Google, Microsoft und den Katalog (Oktober 2026)

Bis zur Zusammenführung von M5 mit „Google ohne Cloud-Projekt“ gab es zwei Erkennungen mit je eigener DNS-Abfrage und
eigenem Endpunkt: `anbieter_erkennen.py` (MX, Microsoft nur als „Outlook“) und `microsoft_anmeldung.erkennen` (MX,
autodiscover, TXT) hinter `GET /api/v1/microsoft/erkennen`. Der Mail-Schritt fragte beide nacheinander. Jetzt gibt es
eine:

* **Eine DNS-Abfrage** (`dns_abfrage.py`): MX, CNAME, TXT über den Namensdienst des Rechners (`/etc/resolv.conf`,
  höchstens zwei), ohne Zusatzpaket; Zeitgrenze 2 s je Frage, Antworten zehn Minuten gemerkt, Schweigen nicht.
  `KINGFISHER_DNS=host:port` ersetzt den Namensdienst (nur für Attrappen in Tests und Browserproben).
* **Eine Erkennungsfunktion** (`anbieter_erkennen.erkennen`): liefert den Katalogeintrag für den Passwortweg, den
  Dienst (`google`, `microsoft` oder leer), die Art (`organisation` für Workspace oder Microsoft 365 einer Hochschule
  oder Firma, `privat` für gmail.com, outlook.com …) und das Zeichen (`domain`, `mx`, `autodiscover`, `txt`). Reihenfolge:
  Endung ohne Anfrage; Mailserver (Exchange Online `….mail.protection.outlook.com` oder Google `….google.com`,
  `….googlemail.com`), denn er sagt, wo die Post wirklich liegt; dann `autodiscover.<domain>` auf Microsoft; dann der
  Bestätigungseintrag `MS=ms…`.
* **Ein Endpunkt:** `GET /api/v1/integrations/mail-providers/erkennen?adresse=…` →
  `{provider, erkannt_an, dienst, art}`. `GET /api/v1/microsoft/erkennen` ist entfallen.
* **Eine Frage im Mail-Schritt** (`useAnbieter.ts`, `Einrichtung/MailSchritt.tsx`): Microsoft 365 → „Mit Microsoft
  anmelden“ (`microsoftZuerst`; der Passwortweg über Outlook auf Wunsch oder wenn die Kennung der App fehlt);
  Google → Gmail mit App-Passwort-Karte, im Kalenderweg die geheime iCal-Adresse; sonst der Katalog oder „Welcher
  Anbieter?“. Private Microsoft-Konten (outlook.com) gehen den Passwortweg.
* **Datenschutz:** Gefragt wird nur nach der Domain, nur beim Namensdienst des Rechners; Google und Microsoft
  erfahren beim Tippen nichts. Tests: `test_anbieter_erkennen.py` mit DNS-Attrappe (MX, CNAME, TXT) und Netzsperre
  `kein_netz` (jeder Versuch außer 127.0.0.1 lässt den Test scheitern; ohne Attrappe geht jedes Paket nur an den
  Namensdienst aus `resolv.conf` und enthält nur die Domain), `test_microsoft_routes.py` (Erkennen fragt die
  Graph-Attrappe nicht), Browserproben `probe_microsoft_ui.py` und `probe_google_ui.py`.
* **Sabotageproben:** Microsoft-Mailserver als Google gemeldet → `test_anbieter_erkennen.py` (drei Tests) und
  `test_microsoft_routes.py` rot; DNS fest an einen fremden Dienst (`9.9.9.9`) → sechs Tests rot und die Netzsperre
  meldet den Versuch; zusätzlich die ganze Adresse gefragt → fünf Tests rot; `microsoftZuerst` ohne Blick auf den
  Dienst (Workspace als Microsoft) → `microsoft-anmeldung.test.mjs` rot.

## Eigene Domain ohne Servereingabe (Fremdprobe 2, Oktober 2026)

Die zweite Fremdprobe (docs/51) richtete `lena.probe@example.org` ein; die Domain stand in keinem Katalog, und der Weg
führte aus dem Assistenten in die Einstellungen zu „IMAP-Server“ und „IMAP-Port“. Jetzt:

* **Server selbst finden** (`server_finden.py`, in der einen Erkennung nach Google und Microsoft): DNS-SRV
  `_imaps._tcp.<domain>` und `_submission._tcp.<domain>` (RFC 6186; Ziel `.` heißt „gibt es nicht“), dann die
  Autoconfig-Datei der Domain im Thunderbird-Format (`https://autoconfig.<domain>/mail/config-v1.1.xml`, danach
  `https://<domain>/.well-known/autoconfig/mail/config-v1.1.xml`; nur HTTPS mit gültigem Zertifikat, keine
  Weiterleitung, höchstens 64 KB, kein DOCTYPE, nur IMAP mit TLS, Versand nur mit STARTTLS), dann der Mailserver (MX)
  gegen den Katalog (`MailProvider.mx`: IONOS, STRATO, mailbox.org, Fastmail, iCloud, Zoho; `HOSTER_AM_MX`: ALL-INKL,
  netcup, deren MX zugleich der Postfachserver ist). Zeitgrenze 3 s je Abruf, 9 s insgesamt; ein Fund gilt zehn
  Minuten. Die Antwort trägt `provider.id = "gefunden"` und `erkannt_an` `srv`, `autoconfig` oder `mx`.
* **Was hinausgeht:** nur die Domain, als DNS-Anfrage an den Namensdienst des Rechners und als HTTPS-Abruf beim Server
  der Domain selbst; nie die Adresse, nie an Dritte, keine zentrale Datenbank. Der Satz steht beim Nachsehen auf der
  Karte (`postfachWeg.nachsehenSatz`).
* **Eine Karte für Assistent und Zugänge** (`PostfachMitAdresse.tsx`): „Erkannt: …“ und nur das Passwort; ohne Fund
  „Welcher Anbieter?“ und als letzte Möglichkeit „Nicht dabei: Mailserver selbst eintragen“ mit Servername und Port
  (Vorgabe 993) und einem Satz, wo man den Namen findet. Unter Zugänge stehen die Servereinstellungen von Hand nur noch
  eingeklappt „Für Techniker“. Die zuletzt getippte Adresse steht schon da (`adresseEntwurf.ts`, nur in der
  Browsersitzung).
* **Fehler am Knopf** (`useImBlick.ts`): die Ablehnung steht direkt unter dem Knopf, bekommt den Fokus, die Seite rollt
  hin; sie nennt den Anbieter oder „Der Mailserver <Name>“, nie den selbst vergebenen Postfachnamen
  (`mail_anmeldung.anbieter_name`).
* **Kalender einer eigenen Domain** (`kalender_anmeldung.eigener_kalender`): `_caldavs._tcp` (Pfad aus TXT), sonst
  `/.well-known/caldav` auf dem Mailserver des Postfachs; dort wird zuerst ohne Passwort gefragt, ob ein Kalenderdienst
  antwortet, erst dann mit dem Passwort des Postfachs. Für Outlook steht der Weg über „Kalender veröffentlichen“ mit
  Link zur Kalenderseite von Outlook da. Erst danach das Feld „Adresse deines Kalenders“ mit einem Satz.
* **Beschriftete Knöpfe** „Postfach hinzufügen“, „Kalender hinzufügen“; die Karte „Microsoft 365“ mit Innenabstand.
* **Ordner per Auswahl** (`OrdnerImBrowser.tsx`, `GET …/unterordner`): „Anderen Ordner auswählen …“ klickt sich vom
  Benutzerordner (im Container von den eingebundenen Ordnern) durch die Unterordner; gezeigt werden nur Ordnernamen,
  nichts wird dadurch freigegeben. Der getippte Pfad steht eingeklappt für Techniker.
* **Tests:** `test_server_finden.py`, `test_kalender_eigene_domain.py` (DNS-, Autoconfig-, CalDAV-Attrappe, Netzsperre),
  `test_mail_anmeldung.py`, `test_ordner_lokal.py`, `postfach-weg.test.mjs`, `kalender-weg.test.mjs`; Browserprobe
  `scripts/probe_fremdprobe2_einrichtung_ui.py`. Sabotageproben stehen in docs/51 unter „Stand je Befund“.

## Neu anmelden, wenn die Anmeldung nicht mehr gilt (Oktober 2026)

Ändert jemand sein Passwort beim Anbieter, oder läuft die Microsoft-Anmeldung ab, ließ die Mailaufnahme das Postfach
bisher als „antwortet gerade nicht. Du musst nichts tun“ stehen, für immer. Jetzt:

* **Erkennen.** Scheitert die Bestandsaufnahme oder das Abholen an der Anmeldung, merkt die Aufnahme den Grund
  `anmeldung` (`mail_intake.bestandsfehler`). Erkannt mit der vorhandenen Einordnung: `mail_anmeldung.einordnen` für
  eine vom IMAP-Server abgelehnte Anmeldung (`connectors.mail.AnmeldungAbgelehnt`, nur LOGIN bzw. XOAUTH2, nicht ein
  BAD auf eine spätere Suche) und `MicrosoftFehler('abgemeldet')`. Was RFC 5530 als vorübergehend kennzeichnet
  (`[UNAVAILABLE]`, `[INUSE]`, `[LIMIT]`, `[SERVERBUG]`, „too many“, „temporar…“, ein erschöpftes Gmail-Kontingent,
  `mail_anmeldung._VORUEBERGEHEND`), Netz und Zeitgrenze bleiben „antwortet gerade nicht“. Ein ausdrücklicher Code
  einer echten Ablehnung (`[AUTHENTICATIONFAILED]`, `[AUTHORIZATIONFAILED]`, `[EXPIRED]`) geht dem Freitext vor:
  „[AUTHENTICATIONFAILED] Too many failed login attempts, try again later“ ist eine Ablehnung. Eine Mail, deren Abholen an der Anmeldung scheitert, zählt
  nicht als gescheitert; sie bleibt offen und kommt nach der neuen Anmeldung dran. Nie Text vom Server.
* **Nicht weiter anklopfen.** Nach einer abgelehnten Anmeldung ruht das ganze Postfach bis zu einer Stunde, statt das
  alte Passwort weiter zu schicken; manche Anbieter sperren ein Konto nach wiederholten Fehlversuchen. Die Ruhe gilt
  für jede Verbindung mit denselben Zugangsdaten (`connectors.mail.ANMELDERUHE`, vor jedem Verbindungsaufbau): die
  Aufnahme in allen Ordnern zusammen (`Intake.anmeldung_ruht`, nicht je Ordner), offene Mails, den Nachtrag der
  Beteiligten (`Intake.aktiv`) und den Posteingang auf Heute und unter „Nachrichten“. Dort steht dann derselbe Satz
  wie im Stand, statt einer neuen Anmeldung (`postfach_lage.anmeldung_ruht`), und Heute verspricht nicht „sobald es
  wieder antwortet“. Danach genau ein neuer Versuch, falls das Passwort beim Anbieter inzwischen doch wieder gilt.
  Erkannt werden die Zugangsdaten an Server, Benutzer und einem Fingerabdruck des Passworts: Ein neues Passwort gilt
  sofort, „Verbinden“ und „Neu anmelden“ fragen immer den Server. Eine vorübergehende Ablehnung wartet wachsend, erst
  eine Minute, dann jeweils doppelt so lange, höchstens 30 Minuten (`VORLAEUFIG_ERST_S`, `VORLAEUFIG_HOECHSTENS_S`).
  Nur im Speicher; nach einem Neustart höchstens ein Versuch. Ein Schritt, der noch mit dem alten Passwort lief,
  schreibt nach „Neu anmelden“ keinen Grund mehr zurück (sein Leser gilt nicht mehr, `permitted`).
* **Sagen.** Eine Aussage an allen Stellen (`mail_stand.GRUND['anmeldung']`, Heute unter „Postfachstand“, Assistent,
  „Für Techniker“): „Postfach Privat lässt Kingfisher nicht mehr hinein: Die Anmeldung ist abgelaufen oder das
  Passwort hat sich geändert. Melde dich unter Einstellungen → Zugänge neu an.“ Dazu `verweis: 'zugaenge'`; die
  Oberfläche macht aus dem Wortlaut „Einstellungen → Zugänge“ einen Klick (`verweis.satzMitVerweis`,
  `SatzMitVerweis`). Auf Heute klappt „Postfachstand“ dann von selbst auf (`heute.postfachMussHandeln`).
* **Tun.** Unter Zugänge steht am Postfach derselbe Satz und der Weg, der zum Zugang passt
  (`Einstellungen/neuAnmeldenWeg.ts`):
  * Passwortpostfach: „Neu anmelden“, nur das neue Passwort (`POST /api/v1/integrations/mail/{id}/anmelden`, hinter dem
    Zugangsschutz der übrigen Routen). Kingfisher meldet sich vorher an; abgelehnt heißt ein Satz am Feld, nichts
    gespeichert, der Fokus bleibt im Feld. Kein zweites Postfach, also kein zweites Einlesen. Escape schließt das Feld
    und gibt den Fokus an „Neu anmelden“ zurück; die Statuszeile (`role="status"`) steht immer im Dokument, damit
    Bildschirmleser das „Angemeldet.“ auch hören.
  * Ein CalDAV-Kalender, der bei der Einrichtung das Postfachpasswort übernommen hat (gleicher Benutzer, gleiches
    gespeichertes Passwort), bekommt das neue mit, aber erst, nachdem Kingfisher ihn damit geöffnet hat. Gelingt das
    nicht, bleibt sein Passwort, das Postfach ist trotzdem angemeldet, und ein Satz nennt alle betroffenen Kalender je
    Grund mit dem nächsten Schritt (`server._kalender_satz`): Lehnt einer ab oder findet Kingfisher dort keinen Kalender
    mehr, „Entferne ihn unter Einstellungen → Zugänge und verbinde ihn mit „Kalender hinzufügen“ neu.“ Antwortet er nur
    gerade nicht, versucht Kingfisher es beim nächsten Kalenderabgleich von selbst (`server._kalender_nachpruefen`,
    nur im Speicher). Ein Kalender mit eigenem Passwort bleibt, wie er ist.
  * Google-Postfach: „Mit Google anmelden“ mit demselben Konto ersetzt die Freigabe des vorhandenen Postfachs, statt ein
    zweites anzulegen (`google_routes`, Rückgabe `neu_angemeldet`). Ein Passwortpostfach derselben Adresse wird dabei
    nicht umgebaut (409 mit Satz).
  * Microsoft: das Konto gilt als nicht verbunden und zeigt seine „Neu anmelden“-Karte (`microsoft_routes`).

  In allen drei Fällen löscht die neue Anmeldung den Grund sofort und weckt die Aufnahme
  (`mail_intake.nach_neuer_anmeldung`); die Ruhezeit gilt dann nicht mehr. Stand kein Postfach an der Anmeldung
  (erste Verbindung, vorsorglich neues Passwort), bleibt der Zeitplan in seinem Takt. Danach „Angemeldet. Kingfisher liest …
  gleich weiter.“ Eine abgelehnte Eingabe (422) wiederholt nie Passwort, Geheimnis oder Token
  (`server._ohne_geheimnisse_in_ablehnungen`): Die Eingabe fällt weg, wenn der Ort ein Geheimnis nennt, und immer,
  wenn sie ein Objekt oder eine Liste ist; fehlt ein anderes Pflichtfeld, wäre sie sonst das ganze Objekt samt
  Passwort. Ort und Meldung bleiben.
* **Tests:** `sidecar/tests/test_anmeldung_abgelaufen.py` (Einordnung, Code vor Freitext, vorübergehende Codes,
  Gegenbeispiele, Satz, Ruhezeit für jede Verbindung und das ganze Postfach, wachsende Wartezeit, IMAP-Attrappe vom
  geänderten Passwort bis zur neuen Anmeldung samt Heute, „Nachrichten“ und Nachtrag, Wettlauf mit „Neu anmelden“,
  Graph-Attrappe, Zugangsschutz, 422 ohne Geheimnis auch bei fehlendem Feld), `test_kalender_anmeldung.py`
  (mitgenommener Kalender, alle im Satz, später selbst geprüft, eigenes Passwort bleibt), `test_google_oauth.py`
  (Freigabe ersetzt, Grund gelöscht), `app/kingfisher/tests/anmeldung-abgelaufen.test.mjs`; Browserprobe
  `scripts/probe_hereinholen_ui.py` mit Fokus, Escape und ohne Rahmen um die Statuszeile (sie bekommt den Fokus nur
  für Bildschirmleser, ein Satz ist kein Bedienelement). Sabotageproben: Erkennung abgeschaltet (7 Tests), Ursache am `MailError` übersehen (4), Connector
  kennzeichnet nicht (2), vorübergehende Codes als Passwortfehler (5), jeder IMAP-Fehler als Anmeldung (1), Passwort
  jeden Takt (2), Neu anmelden ohne Prüfung (1), Passwort vor der Prüfung gespeichert (3), Route ohne Zugangsschutz
  (1), Grund nicht gelöscht (3), nicht geweckt (2), auch ohne Grund geweckt (1), Microsoft löscht den Grund nicht (1), Kalender nicht mitgenommen
  (1), Kalender ungeprüft ersetzt (1), Google legt zweites Postfach an (1), Ablehnung nennt das Passwort (1),
  Abholfehler als gescheitert (1), Microsoft bleibt verbunden (1), Satz ohne Verweis (3); im Nach-Review (in einer
  Kopie): Ruhe nur je Ordner (3), nach Ablehnung weiter zum nächsten Ordner (2), Connector ohne Ruhe (2), Heute und
  „Nachrichten“ ohne Vorprüfung (1), Heute verspricht „sobald es wieder antwortet“ (1), Nachtrag ohne Ruhe (1),
  ausdrückliche Prüfung beachtet die Ruhe (1), Fingerabdruck ohne Passwort (1), Neu anmelden vergisst die Ruhe nicht
  (1), vorübergehend ohne Wartezeit (1), Freitext vor dem Code (3), Gmail-Kontingent als App-Passwort (1), Merkmal
  „temporar“ entfernt (1), nur der letzte Kalender im Satz (1), kein späterer Versuch (1), Kalender mit eigenem
  Passwort ersetzt (1), laufender Schritt schreibt nach Neu anmelden (je 1 für Bestandsaufnahme und Abholen), Google
  ohne `nach_neuer_anmeldung` (1), 422 nennt Objekte mit Passwort (3); in der Oberfläche Einrichtung mit „stockt
  gerade“, Weg nicht erkannt, Heute ohne Verweis, Postfachstand klappt nicht auf, kein „Angemeldet“, Escape,
  Statuszeile nur bedingt, Fokus nach Ablehnung, Google ohne Weg, Rahmen um die Statuszeile (je 1).
* **Offen:** Der regelmäßige Abruf ohne Einlesen (`sync_account`) merkt weiter nur `unavailable`. Ein Google-Zugang
  meldet Fehler beim Erneuern des Tokens ohne Unterscheidung zwischen Netz und widerrufener Freigabe (`GoogleError`);
  er bleibt deshalb „antwortet gerade nicht“; als abgelaufen zählt nur eine XOAUTH2-Anmeldung, die der IMAP-Server
  ablehnt. Der Weg zurück ist aber keine Sackgasse mehr: „Mit Google anmelden“ ersetzt die Freigabe am vorhandenen
  Postfach.

## Konten und Bereiche (Paket K, 26.10.2026)

Entscheidung des Nutzers ([66-automatik.md](66-automatik.md)): **Bereich je Postfach und Kalender**. Kingfisher schlägt
„Privat“ oder „Arbeit“ vor, der Mensch bestätigt einmal; Mails, Termine, Aufgaben und Projekte erben den Bereich.

* **Eine Zeile je Konto** (`Einstellungen/KontoZeile.tsx`): Name, darunter die Adresse (nicht, wenn das Postfach nach
  ihr heißt) und der **Stand in einem Satz** („Zuletzt gelesen vor 4 Min.“, „Wird gelesen: 120 von 4.300 Mails.“ oder
  der Fehler mit Weg, rot; „Neu anmelden“ steht wie bisher darunter, ohne den Satz zu wiederholen). Beim Kalender stammt
  der Stand aus dem letzten Lesen (Kalenderseite, Heute, Abgleich); der Mac-Kalender meldet seinen eigenen Stand.
* **Umbenennen**: ein Klick auf den Namen, Enter speichert, Escape bricht ab. Ein Name gilt je Art nur einmal
  („Diesen Namen trägt schon ein anderes Postfach.“). Mac-Kalender heißen wie am Mac.
* **Eindeutige Namen**: Neue Postfächer heißen nach ihrer Adresse (`postfachName`), nicht nach dem Anbieter. Trugen zwei
  Postfächer denselben Namen (früher jedes Gmail-Konto „Gmail / Google Workspace“), heißen sie beim nächsten Start nach
  ihrer Adresse (`konten_routes.namen_eindeutig_machen`; nur der Anzeigename).
* **Doppelt**: Ein Postfach mit derselben Anmeldung beim selben Server wird beim Passwortweg nicht ein zweites Mal
  angelegt; stattdessen ein Satz („Dieses Postfach ist schon verbunden: … Kingfisher liest es bereits.“), noch vor der
  Anmeldung. Google und Microsoft erkannten das schon. Seit Paket S (27.10.2026) steht der Satz schon nach der Adresse,
  ruhig (kein roter Rahmen) und mit „Zum Postfach“, das zur Zeile führt; ein Passwort wird gar nicht erst verlangt
  (`postfachWeg.schonVerbunden`). Jedes Passwortfeld vorne hat „Anzeigen“ (`grundlage/PasswortFeld.tsx`).
* **Bereich**: Ohne Bestätigung steht unter der Zeile der **Vorschlag mit Grund** („Vorschlag: Privat. gmail.com ist ein
  privater Anbieter, und nichts darin klingt nach Arbeit.“) mit „Übernehmen“ und „Anderer Bereich“. Regeln
  (`bereiche.py`): eigene Domäne → Arbeit; ein privater Anbieter (Gmail, GMX …) allein entscheidet seit Paket S nichts
  mehr, denn viele führen Kundenkonten bei Gmail. Erst was darin steht, gibt den Ausschlag (`inhalt_des_postfachs`,
  `mail_einschaetzen`): Geschäftspartner (ein Mensch bei einer Firma mit Projekt, eigener Antwort, förmlicher Anrede
  oder Firma in der Signatur; Rechnungen, Verträge und Newsletter an Privatkunden zählen nicht) in klarer Mehrheit →
  Arbeit, nichts Berufliches → Privat, gemischt oder noch nichts gelesen → kein Vorschlag; Kalender aus eindeutigen Wörtern im Namen („Arbeit“, „Team“, „Familie“), sonst aus dem
  Postfach mit derselben Adresse, sonst aus der Adresse; sonst **kein Vorschlag**, die Zeile fragt „Welcher Bereich?“.
  Ab zwei offenen Vorschlägen steht im Kopf der Gruppe „Alle Vorschläge übernehmen“. Neben dem Namen steht sichtbar
  „Umbenennen“ (Paket S; vorher war der Name selbst der unsichtbare Knopf). Ein über die Mailadresse gefundener Kalender
  heißt nach seinem Namen („Privat“, bei einem bekannten Anbieter „GMX: Privat“), nicht nach dem Server. Bestätigt steht der Bereich als
  leise Pille rechts; ein Klick ändert ihn, „Ohne“ löst ihn, „Eigener Bereich …“ legt einen mit Namen an (etwa
  „Verein“). Alles ohne Rückfrage, danach der Hinweis mit „Rückgängig“ (`PUT /api/v1/konten/bereich` mit dem Vorwert,
  `PUT /api/v1/konten/name` mit dem alten Namen).
* **Gespeichert** wird nur Bestätigtes, in der Konfiguration (`Settings.konten`: `eigene`, `bereich_je_konto`,
  `kalender_ausgeblendet`), ohne Datenbankspalte. Ein Vorschlag wirkt nie.
* **Vererbung, abgeleitet** (`bereiche.py`, öffentlich für andere Pakete): Mail → Postfach (Präfix der Quellreferenz),
  Termin → Kalender (beim Mac der einzelne Kalender), Aufgabe → ihre Quelle, sonst ihr Projekt; Projekt → `area`, wenn es
  einen Bereich nennt, sonst der überwiegende Bereich seiner Quellen (mehr als die Hälfte; sonst keiner).
  Bestätigte Geburtstage (nur innerer Kreis) gelten als privat. Feld `bereich` in `/api/v1/calendar`, `/api/v1/tasks`,
  `/api/v1/projects`, `/api/v1/local-mail`.
* **Filter**: Kalender und Aufgaben haben ein Segment „Alle · Arbeit · Privat · …“, sobald mindestens zwei Bereiche einem
  Konto zugeordnet sind; die Wahl merkt sich jede Seite (Browser). Auf der Kalenderseite bleiben **ausgeblendete
  Kalender ausgeblendet** (gespeichert, `PUT /api/v1/kalender/ausgeblendet`).
* **Eine Zahl** (Persona-Prüfung, Paket Z1, 27.10.2026): Der Aufgabenfilter filtert im Sidecar, vor Zählen und
  Blättern (`GET /api/v1/tasks?bereich=…`, `…/projects/{id}/task-overview?bereich=…`, `zaehlung.ids_im_bereich`). Zahl
  am Segment, Projektüberblick und Liste sind dieselbe Auswahl; über einer leeren Liste steht keine „1“ mehr. Unter
  „Zugänge“ zählt „N Kalender verbunden“ die Zeilen darunter, auch die Mac-Kalender (`zahlen.kalenderZeilen`). Liegen
  die Termine eines Zeitraums (im gewählten Bereich) nur in ausgeblendeten Kalendern, sagt der Kalender das statt „keine
  Termine“ und blendet sie mit einem Klick ein („Einblenden“, `zahlen.ausgeblendetLage`).
* Prüfung: `sidecar/tests/test_konten_bereiche.py`, `app/kingfisher/tests/konten-bereiche.test.mjs`, Browserprobe
  `scripts/probe_konten_ui.py` ([Protokoll](runs/2026-10-26-automatik-konten/README.md)).

## Quellen zum Anklicken (Feed-Vorgaben)

`sidecar/icarus_memory/welt_vorgaben.py` ist die Liste: tagesschau, Deutschlandfunk, heise online, ZEIT ONLINE, je mit
Kennung, Name, Adresse und einer Beschreibung. Die Route `GET /api/v1/welt/briefing` liefert alle Vorgaben mit `gewaehlt`
und `feed_id`; ein Klick ruft `POST /api/v1/welt/feeds` (die Adresse wird wie jede andere geprüft und einmal zur Probe
gelesen), der zweite `DELETE /api/v1/welt/feeds/{id}`. Ist die Quelle im Briefing abbestellt, steht sie „abbestellt“ da,
und ein Klick schaltet sie wieder ein. Darunter Felder für eine **eigene Quelle**; ohne „https://“ getippte Adressen
ergänzt die Oberfläche (`weltVorgaben.ts`).

* **Stand der Liste: 30. September 2026. Die Adressen sind nicht abgerufen.** Der Container, in dem sie entstand, erreicht
  das Netz nicht; sie stammen aus dem Wissen über die Anbieter. Die Oberfläche sagt das unter der Liste in einem Satz
  (`vorschlaege_stand`). Wer die Liste erneuert, ruft jede Adresse einmal ab und trägt `ABGERUFEN` ein.
* **Der dpa-Ticker fehlt absichtlich.** Die Agentur bietet ihn nicht als öffentlichen Feed an; eine Adresse wäre geraten.
* Der Test (`test_welt_vorgaben.py`) prüft nur Form und https (öffentlicher Name, kein Zahlenname, keine Zugangsdaten,
  eindeutig) und dass `ABGERUFEN` nicht behauptet wird, solange niemand abgerufen hat. Er ruft nichts ab.

## Seitenbreite

Es gibt keine Mindestbreite mehr, auf keiner Seite (Fremdprobe, Befunde 1 und 28). Früher setzte `styles.css` für alle
Seiten `min-width: 1280px`, und nur die Einstellungen, die Startseite und der Assistent hoben das auf
(`html:has(.settings-shell)`). Seit der Fremdprobe gilt das Prinzip der Einstellungen überall; die Regeln stehen in
`Seitenbreite.css`, die `main.tsx` als letzte lädt:

| Breite | Was geschieht |
|---|---|
| unter 1100 px | Spalten, die nebeneinander keinen Platz haben, stapeln sich: die Spalte „Deine Daten bleiben bei dir“, der Kontext neben einem Gespräch (er rutscht unter das Gespräch), die Bereichsauswahl im Gedächtnis (sie wird eine umbrechende Zeile über dem Inhalt), die Kacheln im Briefing (zwei Spalten, der Audiospieler ohne Wellenbild). |
| unter 900 px | Die Seitenleiste wird auf jeder Seite ein Streifen oben: alle Ziele in einer Reihe, das Zeichen über seinem Namen, ohne eigenen Rollbalken (Fremdprobe 3, Befund 14); unter 700 px trägt nur der aktive Bereich seinen Namen (Fremdprobe 2, Befund 25). Wird es noch enger, bricht die Reihe um. Die Regel steht nur in `Seitenbreite.css`. Das Briefing füllt das Fenster. |
| unter 700 px | Formulare, Aufgabenzeilen, Profilkarten und Briefing-Kacheln haben eine Spalte; Überschriften werden kleiner, Knöpfe stehen unter statt neben der Überschrift. |

Breite Inhalte brechen um, statt die Seite zu weiten (`overflow-wrap: break-word`, Knöpfe und Felder höchstens so breit
wie ihr Platz). Auswahlleisten (Reiter der Aufgaben, Filter der Nachrichten, Ansichten des Kalenders) brechen um, statt
seitlich zu rollen; der einzige seitlich wischbare Streifen ist die Seitenleiste.

Der Test `tests/seitenbreite.test.mjs` verbietet jede Mindestbreite ab 400 px in allen CSS-Dateien und prüft die drei
Stufen; die Browserprobe `scripts/probe_seiten_ui.py` misst alle Seiten bei 390, 768 und 1280 px (kein seitliches
Scrollen, kein Element über den Rand oder in einem abschneidenden Rahmen abgeschnitten, keine verdeckten oder
übereinanderliegenden Bedienelemente).

## Mitteilungen auf dem Mac (Oktober 2026)

Etappe 5 aus [`24-weg-zum-jarvis.md`](24-weg-zum-jarvis.md#5-von-sich-aus-melden): Kingfisher meldet sich von sich aus,
wenige Dinge, zu Zeiten, die passen. Der Schalter „Mitteilungen auf dem {Rechner}“ steht unter „Was Kingfisher darf“
zwischen „Beim Anmelden starten“ und der Cloud (`Einstellungen/Mitteilungen.tsx`, Logik `mitteilungenSchalter.ts`).

* **Vorgabe aus**, weil es eine Erlaubnis des Systems braucht, und die fragt die Kingfisher-App erst, wenn der Schalter
  an ist (einmal; Prüffrage 6: Wer nichts ändert, bekommt keine Systemfrage). Der Satz darunter: „Es verlässt nichts
  den Rechner. Morgens eine Mitteilung mit dem, was heute zählt, dazu höchstens zwei dringende: ein Termin gleich,
  eine verstrichene Zusage.“
* **Mit dem Schalter:** die Uhrzeit der Morgenmitteilung (Vorgabe 07:30, `HH:MM` vor 21:00 Uhr; danach gilt Ruhezeit,
  in der nur noch ein Termin gleich kommt) und der Satz, an dem die Etappe gemessen wird: „Diese Woche N Mitteilungen,
  davon M als überflüssig gemeldet.“ Jede Mitteilung auf dem Mac trägt dafür „War überflüssig“.
* **Fehlt die Erlaubnis**, sagt die Karte, wo man sie gibt: „Der Mac hat Mitteilungen für Kingfisher nicht erlaubt.
  Systemeinstellungen → Mitteilungen → Kingfisher.“ Solange die App noch nicht gefragt hat: „Die Kingfisher-App fragt
  beim nächsten Start einmal nach der Erlaubnis für Mitteilungen.“
* **Ohne Mac-App** (Docker im Browser, Linux) ist der Schalter gesperrt und sagt es ehrlich (`nurAufDemMac`); Ausschalten
  geht überall.

Dahinter: `GET/PUT /api/v1/mitteilungen/einstellung` (`an`, `morgens`, dazu `erlaubnis` und `woche`), die Einstellung
`mitteilungen` in `einstellungen.json` (`config.py`). Was fällig ist, entscheidet `sidecar/icarus_memory/mitteilungen.py`
(Morgen, Termin gleich, verstrichene eigene Zusage; je Abruf höchstens drei, je Art eine; Merkliste
`mitteilungen.sqlite3` ohne Inhalt, damit nichts doppelt kommt, auch nicht nach einem Neustart); die Mac-App fragt alle
fünf Minuten `GET /api/v1/mitteilungen/faellig` und meldet „zugestellt“ und „War überflüssig“ zurück (Logbuch-Arten
`mitteilung`, `mitteilung_ueberfluessig`, [`44-logbuch.md`](44-logbuch.md)). Die Wegezeit wird dafür nur gelesen
(`wegezeit.auskunft(nur_lesen=True)`): keine Anfrage an einen Kartendienst wegen einer Mitteilung. App-Seite:
[`macos/README.md`](../macos/README.md#mitteilungen).

Geprüft: `sidecar/tests/test_mitteilungen.py`, `app/kingfisher/tests/mitteilungen.test.mjs`, `macos/test_mac_app.py`
(Reporter, Kategorie, Aktionen, Bauskript, Verdrahtung), Browserprobe `scripts/probe_mitteilungen_ui.py`.
**Nicht geprüft:** die Mitteilung selbst auf einem Mac (kein Swift-Übersetzer hier); siehe das
[Protokoll](runs/2026-10-22-mitteilungen/README.md).

## Cloud für Fragen und Antworten: auch Gedächtnisfragen (Paket T, 26.10.2026)

Bis 1.0.28 half der Schalter „Cloud für Fragen und Antworten nutzen“ bei Fragen an das Gedächtnis nicht: Die belegte
Gedächtnisantwort lief nur lokal und sagte sonst „benötigt ein lokales Modell“. Entscheidung des Nutzers
([66-automatik.md](66-automatik.md)): Mit gültiger Einwilligung der Rolle `antwort` wählt der Cloudanbieter auch die
Quellen aus und formuliert die Sätze.

- **Was hinausgeht:** die Frage und die dafür gefundenen Quellen samt Absender, Betreff und Datum (präzisiert in Paket D:
  „Inhalte deiner Mails, Termine und Notizen, ganz oder in Auszügen“, mit Anbieter, Land und Region). Der Satz der
  Einwilligung sagt das jetzt wörtlich (erweitert, nicht gekürzt; Oberfläche `gliederung.ts`, Sidecar `ROLLEN["antwort"]`).
  Bestätigte Einträge der Wissensschicht gehen nie hinaus; sie stehen lokal gelesen unter der Antwort.
- **Wann nie:** Schalter aus, Einwilligung fehlt oder unlesbar, kein Schlüssel (dann gilt der lokale Standard), ein
  nicht lokaler Standardanbieter ohne Einwilligung, „nur lokal“. Die Einwilligung wird vor jedem einzelnen Versand neu
  gelesen; ein Widerruf mitten in einer Antwort hält den nächsten Aufruf an (`gedaechtnis_cloud.py`).
- **Was lokal bleibt:** Prüfung (zweites Tor), Einbettung und Hintergrund, wie bisher.
- **Sichtbar:** Unter einer solchen Antwort steht „Über Anthropic beantwortet.“; im Verlauf vermerkt
  `context.gedaechtnis_cloud` Anbieter, Modell und `gesendet: ["frage", "textstellen"]`.
- **Ohne Cloud:** Ist eine lokale Antwort langsamer als 8 s, steht darunter „Lokal dauert das. Mit der Cloud ginge es
  in wenigen Sekunden. Dann gingen deine Fragen und Inhalte deiner Mails an Anthropic (USA).“ (Empfänger seit Paket D) mit „Cloud einschalten“ (führt zu diesem Schalter, die Einwilligung bleibt hier) und „Nicht mehr
  zeigen“ (im Browser gemerkt).

## Wege nach draußen: Widerruf, Webabruf, Update-Prüfung (Paket D, 26.10.2026)

Aus der Persona-Prüfung (Datenschutzanwalt, Ärztin; [Protokoll](runs/2026-10-26-befunde-datenschutz/README.md)):

- **Widerruf sofort.** Ausschalten wartet nie auf eine laufende Antwort (`model_roles_routes.put_role`: nur ein Widerruf
  nimmt die Gesprächssperre nicht). Jeder einzelne Versand prüft die Einwilligung frisch: Gespräch vor jeder Runde, auch
  nach einem Werkzeug, Fragen verstehen, Gedächtnisantwort (`Agent._cloud_vor_versand`, `gedaechtnis_cloud.py`),
  Einordnung neuer Mails (`hintergrund_cloud.py`). Steht im Gespräch: „Die Cloud ist ausgeschaltet. Ab hier ist nichts mehr
  an den Anbieter gegangen.“ Der Schalter steht beim Klick auf „aus“.
- **Schalter erst nach Zustimmung an.** Solange die Zustimmung offen ist: „Noch aus: Die Cloud ist erst an, wenn du unten
  zustimmst.“ Die Zustimmung nennt den Anbieter mit Land und Region (`nach_draussen.ANBIETER`, `gliederung.zustimmungCloud`).
- **Webseiten im Gespräch abrufen** (`SCHALTER.web`, Vorgabe an): Jeder Abruf wartet auf eine Freigabe mit einem Klick, die
  Adresse, Empfänger der IP-Adresse und die mit der Adresse gesendeten Angaben nennt (`policy.Policy._IMMER_FREIGABE`,
  `tools.web_abruf_satz`); nach fremdem Inhalt bleibt die genaue Freigabe (Adresse abtippen). Aus: Das Modell bekommt das
  Werkzeug nicht (`PUT /api/v1/darf/web`).
- **Nach neuen Fassungen sehen** (`SCHALTER.updates`, Vorgabe an, vorher unter „Kingfisher und du“): ein Satz, was abgerufen
  wird, dass GitHub die IP-Adresse sieht, und was „aus“ kostet. Unter „Kingfisher und du“ bleiben Fassung und „Jetzt
  nachsehen“.
- **Was an die Cloud ging:** aufklappbar unter dem Cloud-Schalter, je Anfrage Zeit, Anbieter und wofür, ohne Inhalt
  (Logbuch-Art `cloud_anfrage`, `GET /api/v1/cloud/protokoll`). Gesprächsantworten aus der Cloud tragen wie
  Gedächtnisantworten „Über Anthropic beantwortet.“ (`context.cloud_antwort`).
- **IP-Adresse:** Wetter, Welt, Wegezeit, Webabruf und Update-Prüfung sagen, dass der Dienst sie sieht. Ohne Netz sagt
  eine Weltquelle „… ist gerade nicht erreichbar“ statt „nicht erlaubt“.

## Aufgaben aus Mails selbst anlegen (26.10.2026)

Der achte Schalter unter „Was Kingfisher darf“ (`Einstellungen/AufgabenSelbstSchalter.tsx`, Text in
`gliederung.ts`, `SCHALTER.aufgaben_selbst`) und der einzige, der **an** ist, bis man ihn ausschaltet: Es verlässt
nichts den Rechner, und jede so angelegte Aufgabe hat „Rückgängig“ (Prüffrage 5 und 6). Der Satz darunter: „Es
verlässt nichts den Rechner. Eindeutige Bitten an dich und deine Zusagen aus neuen Mails werden Aufgaben, jede mit
„Rückgängig“. Aus: Sie bleiben Vorschläge.“ Dahinter `GET/PUT /api/v1/aufgaben-von-selbst/einstellung` (`an`), gehalten
in `tasks.sqlite3` (`aufgaben_auto_einstellung`, keine Zeile heißt an). Was eindeutig ist, steht in
[`30-akten.md`](30-akten.md#aufgaben-von-selbst-26102026).

## Wie man prüft

* `app/kingfisher/tests/einstellungen-gliederung.test.mjs`: Reihenfolge der Reiter, genau sieben Schalter mit „was verlässt
  den Rechner“, alle Technik-Abschnitte verdrahtet, alte Verweise, **Wortliste**: kein Fachwort aus `FACHWOERTER` in den
  Texten der Gliederung und in den sichtbaren Texten der vorderen Dateien (`VORDERE_DATEIEN`), Breitenregeln im CSS.
* `welt-vorgaben.test.mjs`, `sidecar/tests/test_welt_vorgaben.py`: Vorgaben und ihr Zustand.
* Browserprobe `scripts/probe_einstellungen_ui.py` (Fake-Ollama, leerer Bestand, Chromium): Breite bei 390, 768, 1280 px
  für alle Bereiche ohne seitliches Scrollen und ohne verdeckte Reiter, Wortliste gegen den sichtbaren Text, die fünf
  Schalter, Quellen anklicken und abwählen, Startort und Name, Cloud mit Zustimmung, Laden erst beim Aufklappen.
* Sabotageproben: ein Fachwort („IMAP“, „Feed“) in einen vorderen Text gesetzt, die Anzeige „an“ der Vorgaben verfälscht,
  die Mindestbreite wieder gesetzt, eine Vorgabe auf http gestellt: jeweils fällt der passende Test.

## Wegweiser für ältere Doku

Ältere Seiten nennen die alten Reiter. Neu: „Einstellungen → Mail/Kalender/Dokumente/Einrichtung“ ist **Zugänge**;
„Wetter und Nachrichten“ ist **Was Kingfisher darf**; „Lokale KI“, „Gedächtnis“, „Automatik“, „Rückmeldungen“ und
„Erweitert“ sind Abschnitte hinter **Für Techniker**; „Arbeitsvorlieben“ ist ausgeklappt unter **Kingfisher und du**.

## Offen

* Die Zeitzone wird angezeigt, aber nicht gewählt (Vorgabe Europe/Berlin, `KINGFISHER_TIMEZONE`). Das Briefing gilt seit
  der zweiten Fremdprobe in dieser Zeitzone, nicht in der des Browsers.
* Der Kreis je Person steht seit M4 unter „Kingfisher und du“: bestätigt, offen, mit Weg zu den Vorschlägen (docs/49).
* Die 15-Minuten-Messung der zweiten Fremdprobe ist nicht erfüllt (docs/51); was daraus gebaut ist und was nur auf dem
  Mac oder mit echtem Netz zu prüfen bleibt, steht dort unter „Stand je Befund“.
