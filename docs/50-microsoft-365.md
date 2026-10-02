# Microsoft 365: Outlook, Kalender und Teams-Mitschriften über einen Zugang (M5, erster Teil)

Stand: 1. Oktober 2026. Umsetzung des ersten Teils von M5 aus [`41-zielbild.md`](41-zielbild.md) („Microsoft 365
zuerst“). Fertig heißt dort: *Ein Meeting erscheint ohne Handgriff als Quelle mit Vorschlägen.* Code:
`microsoft_anmeldung.py` (Anmeldung), `microsoft_graph.py` (Post, Kalender, Mitschriften),
`microsoft_routes.py` (Verdrahtung, Takt); Erkennen über die eine Anbieter-Erkennung `anbieter_erkennen.py` mit
`dns_abfrage.py` (DNS ohne Zusatzpaket), dieselbe wie für Google Workspace; Oberfläche
`MicrosoftAnmeldung.tsx`, `microsoftAnmeldung.ts`, `MicrosoftZugang.tsx`, `MicrosoftVorbereiten.tsx`, Mail-Schritt
`Einrichtung/MailSchritt.tsx`. Tests: `test_microsoft_anmeldung.py`, `test_microsoft_graph.py`,
`test_microsoft_routes.py` gegen die Attrappe `sidecar/tests/graph_attrappe.py`, `test_anbieter_erkennen.py` gegen die
DNS-Attrappe `sidecar/tests/dns_attrappe.py`; UI-Test
`microsoft-anmeldung.test.mjs`; Browserprobe `scripts/probe_microsoft_ui.py`.

## Warum

Hochschul-Tenants lassen oft kein IMAP-Passwort zu (Basic Auth ist bei Exchange Online abgeschaltet, App-Passwörter
sind gesperrt). Die Anmeldung bei Microsoft (Entra ID) mit delegierten Rechten bringt Post, Kalender und
Teams-Mitschriften über einen Zugang, ohne dass ein Passwort Kingfisher berührt.

## Der Weg für den Menschen

1. Im Mail-Schritt der Einrichtung die eigene Adresse eintippen. Gehört die Domain zu Microsoft 365, steht da
   „Erkannt: Microsoft 365 deiner Hochschule oder Firma“ und statt des Passwortfelds „Mit Microsoft anmelden“.
   Dasselbe steht unter Einstellungen → Zugänge, Karte „Microsoft 365“.
2. Klick: Kingfisher zeigt einen kurzen Code (Knopf „Code kopieren“) und „Seite von Microsoft öffnen“
   (`https://microsoft.com/devicelogin`). Der Mensch meldet sich dort an, wie er es von der Hochschule kennt
   (auch mit zweitem Faktor), und gibt den Code ein. Die Karte zählt, wie lange der Code noch gilt.
3. Kingfisher fragt im Hintergrund nach und sagt „Verbunden: Post und Kalender von …“. Daraus werden ein Postfach
   und ein Kalender in den Einstellungen (nur lesen). Die Post liest Kingfisher erst nach „Mails einlesen“, wie
   bei jedem Postfach.
4. Unter Zugänge: „Teams-Mitschriften dazunehmen“ ist ein zweiter Code. Danach holt Kingfisher alle zehn Minuten
   die Mitschriften vergangener Online-Besprechungen; je Besprechung steht ein Satz, was daraus wurde.

Was niemand tun muss: einen Server, Port, Mandanten oder eine Kalenderadresse kennen. Was ein Techniker einmal tun
muss: die Kennung der App eintragen (siehe unten), solange das Projekt keine eigene veröffentlichte App hat.

### Ehrliche Sätze

| Lage | Woran erkannt | Satz (gekürzt) |
|---|---|---|
| IT muss zustimmen | `AADSTS65001`, `AADSTS90094`, `AADSTS90095`, `consent_required` | „Deine Hochschule oder Firma muss Kingfisher erst freigeben …“ |
| … nur für Mitschriften | dieselben Codes bei der Anmeldung mit Mitschriften | „Teams-Mitschriften gibt Microsoft erst frei, wenn die IT … Post und Kalender bleiben verbunden.“ |
| Code abgelaufen | `expired_token`, `AADSTS70019`, Zeit abgelaufen | „Der Code ist abgelaufen, er gilt nur eine Viertelstunde …“ |
| abgebrochen | `authorization_declined`, `AADSTS65004`, Knopf „Abbrechen“ | „… abgelehnt oder abgebrochen …“ |
| kein Netz | Verbindungsfehler | „Microsoft antwortet gerade nicht …“; beim Nachfragen bleibt der Code gültig |
| App unbekannt | `AADSTS700016`, `AADSTS700038`, `invalid_client` | „Microsoft kennt die hinterlegte Kennung der App nicht …“ |
| Code-Weg aus | `AADSTS7000218`, `unauthorized_client` | „… öffentliche Clientflows zulassen …“ |
| nicht zugewiesen | `AADSTS50105` | „Deine IT hat Kingfisher nur für bestimmte Personen freigegeben …“ |
| Richtlinie | `AADSTS53003`, `AADSTS53000` | „Deine IT lässt diese Anmeldung von diesem Gerät nicht zu …“ |
| abgemeldet | `AADSTS700082`, `50173`, `50076`, `50078`, 401 | „… Melde dich unter Zugänge noch einmal an.“ |
| keine App-Kennung | Einstellung und `KINGFISHER_MS_CLIENT_ID` leer | „… fehlt noch die Kennung der App. Ein Techniker …“, dazu der Weg mit Passwort |

Die Codes stammen aus der Liste der Entra-Fehlercodes und aus RFC 8628 (`authorization_pending`, `slow_down`,
`expired_token`, `access_denied` bzw. bei Entra `authorization_declined`). **Nicht geprüft mit einem echten
Tenant:** ob Entra bei fehlender Administratorzustimmung im Gerätecode-Weg tatsächlich `invalid_grant` mit
`AADSTS65001` an den Nachfragenden liefert oder nur im Browser „Genehmigung erforderlich“ zeigt und das
Nachfragen bis zum Ablauf auf `authorization_pending` stehen lässt. Für den zweiten Fall steht während des Wartens
der Hinweis „Zeigt Microsoft ‚Genehmigung erforderlich‘ …, muss die IT … erst freigeben.“

## Rechte (Scopes)

Delegiert, nur lesend; die Liste ist fest (`GRUND_SCOPES`, `MITSCHRIFT_SCOPE`), und `nur_lesend` weist jedes andere
Recht ab, bevor eine Anfrage hinausgeht (Test und Sabotageprobe).

| Recht | Wofür | Zustimmung der IT nötig |
|---|---|---|
| `User.Read` | wer angemeldet ist (`/me`: Adresse) | nein |
| `Mail.Read` | Post lesen (`/me/mailFolders/{inbox,sentitems}/messages/delta`, `/me/messages/{id}`) | nein |
| `Calendars.Read` | Kalender lesen (`/me/calendarView`) | nein |
| `OnlineMeetings.Read` | die Besprechung zu einem Termin finden (`/me/onlineMeetings?$filter=JoinWebUrl eq '…'`) | nein |
| `offline_access` | dauerhafte Anmeldung (Refresh-Token) | nein |
| `OnlineMeetingTranscript.Read.All` | Teams-Mitschriften (`/me/onlineMeetings/{id}/transcripts`, `…/{tid}/content?$format=text/vtt`) | **ja, immer** |

Die erste Anmeldung fragt nur die oberen fünf. Stünde das Mitschriften-Recht darin, scheiterte an einer Hochschule
ohne diese Freigabe die ganze Anmeldung, auch für Post und Kalender. Ob eine Hochschule Nutzern überhaupt erlaubt,
Apps selbst zuzustimmen, entscheidet ihre IT; viele Hochschulen verbieten es, dann braucht schon die erste Anmeldung
die Freigabe (Satz „IT muss zustimmen“).

`Files.Read` (OneDrive) wird **nicht** erbeten: Kingfisher liest OneDrive noch nicht über Graph (siehe OneDrive),
und eine Berechtigung ohne Nutzung wird nicht verlangt. Sie kommt wie die Mitschriften als eigener Schritt dazu,
wenn es gebaut ist.

## Datenschutz: was wohin geht

* **Beim Tippen der Adresse:** nichts an Microsoft. Kingfisher fragt den Namensdienst des Rechners nach dem
  DNS-Eintrag der Domain (nur die Domain, nie die Adresse): MX auf `….mail.protection.outlook.com`,
  `autodiscover.<domain>` als CNAME auf `autodiscover.outlook.com`, oder der Bestätigungseintrag `MS=ms…` eines
  Microsoft-365-Mandanten. Das ist dieselbe Art Anfrage, die jedes Mailprogramm stellt. Keine Antwort heißt „nicht
  erkannt“; dann bleibt der Weg mit Passwort und der Anbieterliste. Seit der Zusammenführung mit „Google ohne
  Cloud-Projekt“ ist das **eine** Erkennung für Google Workspace, Microsoft 365 und den Katalog
  (`anbieter_erkennen.erkennen`, ein Endpunkt `GET /api/v1/integrations/mail-providers/erkennen`, Antwort
  `{provider, erkannt_an, dienst, art}`); der frühere `GET /api/v1/microsoft/erkennen` ist entfallen. Der Mailserver
  entscheidet zuerst: Liegt die Post bei Google, ist es Google, auch wenn ein autodiscover-Eintrag auf Microsoft
  zeigt. Einzelheiten und Sabotageproben: [`47-einstellungen.md`](47-einstellungen.md#eine-erkennung-für-google-microsoft-und-den-katalog-oktober-2026).
* **Beim Klick „Mit Microsoft anmelden“:** die Domain an `login.microsoftonline.com/<domain>/v2.0/.well-known/
  openid-configuration` (Mandant), die Kennung der App und die Rechte an den Endpunkt für Gerätecodes; danach das
  Nachfragen mit dem Gerätecode. Das Passwort gibt der Mensch nur bei Microsoft ein.
* **Danach:** nur `graph.microsoft.com`, nur GET (`GraphClient` kennt keine andere Methode), das Token nur an die
  eingestellte Graph-Adresse, auch bei Folgeseiten aus `@odata.nextLink` (Test und Sabotageprobe).
* **Gespeichert:** der Refresh-Token im Schlüsselspeicher des Rechners (`ICARUS_MICROSOFT_TOKEN_<Hash der Adresse>`,
  Keychain bzw. verschlüsselte Datei); das Zugriffstoken nur im Arbeitsspeicher bis zwei Minuten vor Ablauf. In
  `einstellungen.json` stehen nur Adresse und Art der Zugänge. Nummern der Post und der Stand der Mitschriften liegen
  in `microsoft.sqlite3` im Datenordner (keine Texte, keine Token). Keine Antwort, kein Protokoll, kein
  Statusbericht enthält ein Token oder den Gerätecode (Tests prüfen Antworten, Protokoll und Einstellungsdatei).
* **Trennen:** Trennt der Mensch den letzten Zugang eines Kontos (Postfach und Kalender), verschwinden Refresh-Token
  und Nummern. Die Freigabe bei Microsoft zieht er zusätzlich unter `myaccount.microsoft.com` → Apps zurück; das
  steht auf der Karte.

## Post: dieselbe Aufnahme wie IMAP

`MicrosoftPost` hat die Schnittstelle des IMAP-Postfachs (`folders`, `inventory_page`, `message_in_folder`,
`inbox`, `message`, `pruefe_anmeldung`). Damit laufen `mail_intake.Intake`, die Stände („300 von 1.200
gelesen“), die Drosselung des Hintergrunds, die Reihenfolge nach Nutzen (`hintergrund.py`), die Filterregeln, der
Empfängernachtrag und „Antwortet das Postfach?“ unverändert. Gelesen werden Posteingang und Gesendet (ohne
Junk-E-Mail und Gelöschte Elemente); Text statt HTML (`Prefer: outlook.body-content-type="text"`), unveränderliche
Kennungen (`IdType="ImmutableId"`), Seiten zu 100 Nachrichten, bis zu drei Seiten je Durchgang.

**Nummern.** Die Aufnahme rechnet mit UIDs (Ganzzahl, je Ordner). `Postablage` vergibt je Nachricht eine Nummer aus
der Eingangszeit (Sekunden seit 1970, bei Gleichstand eins daneben), damit „Rückstand von neu nach alt“ stimmt, und
eine Laufnummer in der Reihenfolge der Delta-Abfrage, die als Fortschritt dient: der Bestand 1, 2, 3 …, neue Post
nach der ersten vollständigen Abfrage ab 2.000.000.001 (Spur „neu“). Geht die Ablage verloren, entsteht eine neue
Generation, und die Aufnahme beginnt die Bestandsaufnahme neu (wie bei geändertem UIDVALIDITY; Dubletten erkennt die
Episodenschicht). Verfällt der Stand der Delta-Abfrage bei Microsoft (410), beginnt sie neu; Bekanntes bleibt.

**Drosselung durch Microsoft.** 429/503/504 mit `Retry-After`: Bis dahin geht keine Anfrage hinaus (Test); die
Aufnahme vermerkt den Ordner und versucht es im nächsten Takt.

## Kalender

`MicrosoftKalender` liest den Standardkalender über `/me/calendarView` (Wiederholungen aufgelöst, Zeiten in UTC,
Seiten bis 20). Teilnehmer mit Name und Adresse, der Organisator dazu; abgesagte Termine fallen weg. Danach gilt alles
aus [`28-termine-im-gedaechtnis.md`](28-termine-im-gedaechtnis.md). Weitere Kalender des Kontos (`/me/calendars`)
sind ein Folgeschritt.

## Teams-Mitschriften

`Mitschriften.durchgang` sucht in den Terminen der letzten 14 Tage die vergangenen Online-Besprechungen
(`isOnlineMeeting`, `onlineMeeting.joinUrl`), höchstens zehn je Durchgang, neueste zuerst, findet die Besprechung über
die Teilnahme-Adresse, listet die Mitschriften und holt ihren Inhalt als VTT. Daraus wird über
`transkript_aus_vtt` dieselbe `Transkript`-Form wie aus einer Datei im Transkript-Ordner
([`34-gespraeche.md`](34-gespraeche.md)): Sprecher aus `<v Name>`, Titel des Termins, Beginn aus der Mitschrift.
Anders als bei Dateien behält jede Wortmeldung ihre Uhrzeit („Anna Keller: [09:03] …“), damit jeder Beleg Sprecher
und Zeit trägt. Abgelegt wird über `transkript_eingang.aufnehmen` (Quellenschlüssel
`microsoft:teams:<konto>:<mitschrift>`), dann Zuordnung zum Termin (`Zuordner.vormerken`), Abschnitte und
Einordnung (`scheduler.request_working_memory`), Logbuch „quellen/transkript“. Vorschläge entstehen wie bei jeder
Quelle; Fakten nur über Annahme.

Der Takt läuft alle zehn Minuten (erste Runde 30 s nach dem Start), sobald ein Konto die Mitschriften hat, und tritt
zurück, solange der Hintergrund gesperrt ist (pausiert, jemand arbeitet, eine Antwort entsteht). „Jetzt nachsehen“
unter Zugänge stößt ihn sofort an.

| Stand | Satz | weiter? |
|---|---|---|
| `aufgenommen` | „Mitschrift aufgenommen.“ | nein |
| `noch_keine` | „Noch keine Mitschrift; Kingfisher sieht in einer Stunde wieder nach.“ | stündlich bis zwei Tage nach Ende |
| `keine` | „Für diese Besprechung gibt es bei Microsoft keine Mitschrift.“ | nein |
| `nicht_erlaubt` (403) | „Teams-Mitschriften gibt Microsoft erst frei, wenn die IT … zugestimmt hat.“ | einmal am Tag |
| `nicht_herausgegeben` (nicht gefunden) | „Microsoft gibt die Mitschrift dieser Besprechung nicht heraus. Das geht meist nur bei Besprechungen, die du selbst angesetzt hast.“ | nein |
| `fehler` | „… ließ sich gerade nicht holen …“ | nach 15 Minuten oder `Retry-After` |

## OneDrive

Nicht gebaut, bewusst. Auf dem Mac liegt OneDrive als synchronisierter Ordner; den liest der Ordner-Adapter schon
heute, wenn der Mensch ihn wählt (ein anderer Agent baut das Lesen von PDF und Bild). Über Graph wäre es ein eigener
Schritt: `Files.Read` als zusätzliches Recht wie die Mitschriften, Auswahl der Ordner über `/me/drive/root/children`
mit Klick (nie getippt), Lesen nur der gewählten Ordner über `/me/drive/items/{id}/delta`, Ablage über denselben Weg
wie die Dokumentenordner. Sinnvoll vor allem außerhalb des Mac (Windows ohne OneDrive-Programm, Docker).

## Für Techniker: die App registrieren

Solange das Projekt keine eigene, bei Microsoft veröffentlichte App hat, braucht jede Installation die Kennung einer
App-Registrierung (öffentlicher Client, kein Geheimnis):

1. Microsoft Entra Admin Center → Anwendungen → App-Registrierungen → Neue Registrierung. Name „Kingfisher“.
   Kontotypen: „Konten in einem beliebigen Organisationsverzeichnis“ (für Hochschul- und Firmenkonten; mit
   persönlichen Microsoft-Konten, wenn auch outlook.com gewünscht ist). Keine Umleitungs-URI.
2. Authentifizierung → Erweiterte Einstellungen → „Öffentliche Clientflows zulassen“: **Ja** (sonst `AADSTS7000218`).
3. API-Berechtigungen → Microsoft Graph → Delegiert: `User.Read`, `Mail.Read`, `Calendars.Read`,
   `OnlineMeetings.Read`, `offline_access`; für Mitschriften zusätzlich `OnlineMeetingTranscript.Read.All`.
   Keine Anwendungsberechtigungen, kein geheimer Clientschlüssel, kein Zertifikat.
4. Die Anwendungs-ID (Client-ID) unter Einstellungen → Für Techniker → „Microsoft-Anmeldung vorbereiten“ eintragen
   oder als `KINGFISHER_MS_CLIENT_ID` setzen (die Einstellung gewinnt).
5. In der Hochschule: Die IT erteilt unter Unternehmensanwendungen → Kingfisher → Berechtigungen die
   Administratorzustimmung, mindestens für `OnlineMeetingTranscript.Read.All`. Ist die Zustimmung durch Nutzer im
   Tenant ausgeschaltet, für alle Rechte. Für Mitschriften muss außerdem die Transkription in Teams erlaubt sein.

Weitere Umgebungsvariablen: `KINGFISHER_MS_TENANT` (fester Mandant statt der Erkennung), `KINGFISHER_MS_LOGIN_URL`
und `KINGFISHER_MS_GRAPH_URL` (nur für Attrappen und Tests; Vorgabe `https://login.microsoftonline.com` und
`https://graph.microsoft.com/v1.0`).

## Grenzen bei Hochschul-Tenants (nur mit echtem Tenant zu prüfen)

* Ob Nutzer der Hochschule Apps selbst zustimmen dürfen; viele Hochschulen verbieten es (Satz „IT muss zustimmen“).
* Ob Conditional Access den Gerätecode-Weg sperrt (viele Tenants blockieren „Device code flow“ seit 2024/2025 per
  Richtlinie; dann `AADSTS53003`). Wäre das an der Hochschule so, bliebe nur ein Weg mit Browser-Rücksprung
  (Autorisierungscode mit PKCE auf `127.0.0.1`, wie bei Google) als Folgeschritt.
* Für welche Besprechungen Microsoft die Mitschrift delegiert herausgibt (nach Doku: Besprechungen, die der Nutzer
  angesetzt hat; ob auch als Teilnehmer, ist zu prüfen), und ob `JoinWebUrl`-Filter für Kanalbesprechungen greift.
* Ob `createdDateTime` der Mitschrift der Beginn der Aufzeichnung ist (davon hängen die Uhrzeiten je Wortmeldung ab).
* Wie sich die Delta-Abfrage bei sehr großen Postfächern (50.000+) verhält (Seitengröße, Drosselung).
* Ob die Fehlercodes beim Nachfragen so ankommen wie in der Tabelle oben (insbesondere 65001/90094).

## Prüfungen

* `test_microsoft_anmeldung.py`: nur lesende Rechte (auch in der gesendeten Anfrage), Gerätecode mit
  `authorization_pending`, `slow_down` (Intervall +5 s, keine Nachfrage zu früh), Erfolg; Fehler als ein Satz;
  Ablauf ohne Nachfrage; kein Netz; App-Kennung fehlt oder falsch; unbekannte Domain; Erneuern mit Tausch und
  Merken; abgemeldet; DNS-Antworten mit Kompression; DNS ohne Netz bleibt leer; Vorgaben auf HTTPS.
* `test_anbieter_erkennen.py`: Erkennen über DNS (MX, autodiscover, TXT; nie die Adresse, nur an den Namensdienst
  des Rechners, unter der Netzsperre), Microsoft nie als Google und umgekehrt, private Konten, Merken, Schweigen.
* `test_microsoft_graph.py`: Outlook-Post durch `Intake` mit Ständen, Reihenfolge neu nach alt und Spur „neu“;
  Einzelnachricht mit Empfängern; alte Generation; nur GET, Token nur an Graph; Drosselung; Kalender mit Seiten;
  Mitschrift mit Sprecher und Uhrzeit, nur einmal geholt; ohne Freigabe ein Satz.
* `test_microsoft_routes.py`: im echten Sidecar vom Erkennen (DNS-Attrappe, Graph-Attrappe nicht gefragt) bis zum Trennen (Postfach, Kalender, Umfang,
  Aufnahme, Mitschriften, Zuordnung), kein Token in Antworten, Protokoll und Einstellungsdatei; Scheitern legt
  nichts an; ohne App-Kennung; abgemeldet beim Prüfen.
* Kein Netz in Tests: Die Fixture `kein_netz` (`tests/microsoft_hilfen.py`) lässt nur Verbindungen zu 127.0.0.1 zu,
  entfernt Proxy-Variablen und lässt jeden Test scheitern, der es trotzdem versucht hat.
* Sabotageproben (je eine Zusicherung gebrochen, der passende Test schlug fehl): `Mail.Send` in den Rechten; Sperre
  schreibender Rechte entfernt; URL-Prüfung im `GraphClient` entfernt; Gerätecode in der Ansicht; Refresh-Token im
  Protokoll; Basisadresse fest auf Microsoft (Netzversuch); `slow_down` ohne längeres Intervall; Trennen lässt den
  Zugang liegen; 403 bei Mitschriften als Fehler; neue Post in die Verlaufsspur.
* Browserprobe `scripts/probe_microsoft_ui.py` (23 Prüfungen, Konsole leer; erkennt über die DNS-Attrappe).
