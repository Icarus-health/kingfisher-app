# Einrichtung und Erststart

Stand 2026-09-29. Verbindlich für `sidecar/icarus_memory/config.py` und den
Einrichtungsbereich unter „Einstellungen“ in `app/kingfisher/src/` (`App.tsx`).

Bis hierher kam alles aus Umgebungsvariablen: Anbieter, Schlüssel, Mailserver,
freigegebene Ordner. Für eine Entwicklungsumgebung ist das richtig. Für eine App,
die jemand herunterlädt, ist es das Ende — **niemand legt eine `.env` an, bevor
er ein Programm zum ersten Mal öffnet.**

## Es gibt kein Konto

Icarus kennt keinen Server, bei dem man sich anmelden könnte. Das ist keine
fehlende Funktion, sondern die Prämisse des Projekts: Der Bestand liegt auf dem
Rechner der Person.

Was beim Einrichten passiert, ist deshalb kein Login, sondern eine einzige
Frage — **welchem Anbieter wird das Gespräch anvertraut?** Und die Antwort darf
„keinem" sein. Ohne Modell bleibt das Gedächtnis vollständig nutzbar: Aussagen
aufnehmen, ersetzen, widerrufen, exportieren und Notizen einlesen funktioniert
offline.

## Zwei Ablagen, klar getrennt

| Wohin | Was | Warum |
| --- | --- | --- |
| `einstellungen.json` (0600) | Anbieter, Modell, Serveradressen, freigegebene Ordner | Muss lesbar und sicherbar sein |
| Schlüsselbund | API-Schlüssel, Mail- und CalDAV-Passwort | Landet nie auf der Platte |

Die Trennung ist keine Förmlichkeit. Die Einstellungsdatei landet in Backups, in
Sicherungen des Datenverzeichnisses, womöglich in einem Cloud-Ordner. Ein
Schlüssel darin wäre genau der Klartext, den [`secrets.py`](../sidecar/icarus_memory/secrets.py)
vermeiden soll.

**Ohne Schlüsselspeicher** — Linux ohne `secret-tool`, manche Serverumgebungen —
gilt ein eingetragener Schlüssel nur für die laufende Sitzung. Er wird
ausdrücklich **nicht** ersatzweise in die Einstellungsdatei geschrieben, und die
Oberfläche sagt das beim Öffnen. Lieber unbequem als Klartext auf der Platte.

## Vorrang

Umgebungsvariablen schlagen die Datei. Wer `ICARUS_PROVIDER=ollama` vor den
Start setzt, bekommt Ollama, egal was eingestellt ist — der Weg, einen Testlauf
zu fahren, ohne die Einstellungen des Nutzers anzufassen. Dieselbe Regel wie in
`secrets.load_into_env()`.

## Ohne Neustart

`PUT /setup` baut Konnektoren, Werkzeuge und Agent neu (`_build_agent`). Wer
einen Schlüssel einträgt, kann unmittelbar danach sprechen; wer einen Ordner
freigibt, kann unmittelbar danach einlesen.

Das ist kein Komfortdetail. Ein Programm, das nach jeder Einstellung einen
Neustart verlangt, wird beim ersten Versuch weggelegt — und der erste Versuch
ist der einzige, den die meisten Menschen unternehmen.

Der Gesprächsverlauf geht dabei absichtlich verloren: Ein Verlauf, der vor einem
Anbieterwechsel entstand, gehört einem anderen Modell.

## Der Assistent beim Erststart

Ziel (Etappe 1 in [`24-weg-zum-jarvis.md`](24-weg-zum-jarvis.md)): in wenigen Minuten
bis zum ersten Briefing, ohne dass jemand einen Server, einen Port oder einen
Modellnamen kennen muss. Beim ersten Öffnen und solange Wesentliches fehlt (weder Mail
noch Kalender noch ein Modell) geht die Startseite von selbst in den Assistenten
(`/willkommen`). Wer „Später weitermachen“ wählt, wird in dieser Sitzung nicht noch
einmal gefragt; die leere Startseite nennt dann genau einen nächsten Schritt.

Sieben Schritte, **jeder überspringbar**, in Alltagssprache:

1. **Wie heißt du?** Ein freiwilliges Feld. Der Name steht nur im Gruß des Briefings
   („Guten Morgen, Lea.“). Eine Umgebungsvariable `KINGFISHER_USER_NAME` schlägt ihn.
2. **Deine Mail verbinden.** „Mit Google anmelden“ (der vorhandene Weg) oder Adresse und
   Passwort. Der Anbieter wird an der Adresse erkannt (`providers_mail.py`, Feld
   `domains`); Server und Ports füllt das Programm. Ist der Anbieter unbekannt, fragt
   eine Liste „Welcher Anbieter?“, nie nach einem Server. Danach ein Klick auf „Mails
   einlesen“: erst er startet die Aufnahme (Umfang prüfen und starten in einem Zug). Die
   Frage nennt das Postfach mit seiner Adresse („Soll Kingfisher dein Postfach … jetzt
   einlesen?“) und verweist fürs Anhalten auf „Pausieren“ auf Heute, nicht unter „Für
   Techniker“ (Fremdprobe 3, Befund 5; `Einrichtung/postfach.ts`).
3. **Deinen Kalender verbinden.** Google-Kalender oder Kalender auf diesem Mac (die
   vorhandenen Bausteine); alles Weitere unter Einstellungen → Zugänge. Ist ein Kalender
   verbunden, bleibt der Satz stehen, was verbunden ist, und statt der Wege steht
   „Weiteren Kalender verbinden“ (Fremdprobe 3, Befund 7).
4. **Kingfisher auf diesem Rechner einrichten.** Die Karte „Für diesen Rechner
   empfohlen“ mit Fortschritt (siehe unten).
5. **Was darf Kingfisher noch?** Meetings-Ordner, Wetter, Fahrzeiten: je ein Satz, was
   passiert, und Aus als Vorgabe. „Einrichten“ öffnet die vorhandene Einstellung. Sobald
   man hier etwas ändert, heißt der Knopf „Weiter“, und der Schritt gilt als erledigt.
   Ohne gewählten Ort ist das Wetter aus (der Schalter öffnet dann nur die Ortssuche);
   wer es einschalten wollte und keinen Ort fand, liest das in einem Satz: „Das Wetter
   ist noch aus, weil noch kein Ort gewählt ist.“ (Fremdprobe 3, Befund 4;
   `Einrichtung/freigaben.ts`).
6. **Kingfisher beim Anmelden starten?** Ein Schalter, **nicht vorausgewählt**, mit einem
   Satz, warum: Hintergrundarbeit und Briefing ohne Zutun. Siehe „Autostart“ unten.
7. **Fertig – dein erstes Briefing entsteht jetzt.** Wie viele Mails gelesen und Termine
   aufgenommen sind, der Fortschritt der Aufnahme und was im Hintergrund weiterläuft.
   Die Termine werden erst nach dem Abgleich gezählt (bis dahin „…“), die Mails nur, wenn
   das Einlesen läuft (Fremdprobe 3, Befund 6; `fertig.schonDaZahlen`).

Die Schritte betten die vorhandenen Bausteine ein (`GoogleSignIn`, `MacCalendarSettings`,
`ModelRecommendation`, `TranscriptSettings`, `Wetter`, `WegezeitSettings`); es gibt keine
zweite Anbindung. Die Dateien liegen in `app/kingfisher/src/Einrichtung/`, die
Ablauflogik in `schritte.ts` (mit Tests).

**Der Fortschritt liegt im Sidecar**, nicht im Browser: Einstellung `einrichtung`
(Name, je Schritt „erledigt“ oder „übersprungen“, „abgeschlossen“), Route
`GET/PUT /api/v1/einrichtung` in `einrichtung_routes.py`. Nach einem Neustart, in einem
anderen Fenster oder nach dem Neuladen geht es dort weiter, wo man aufhörte
(`?schritt=…` wählt einen Schritt). Was schon da ist, zählt als erledigt, auch wenn es
nicht im Assistenten geschah. Der Assistent lässt sich jederzeit über Einstellungen →
Einrichtung wieder öffnen.

Zwei Entscheidungen daran sind Absicht:

**Jeder Schritt ist überspringbar, und am Ende funktioniert Icarus.** Ein
Assistent mit Pflichtfeldern erzeugt Abbrüche an genau der Stelle, an der jemand
das Programm noch nicht kennt und deshalb nichts eintragen *kann*.

**Ein fehlgeschlagener Schritt bleibt stehen.** Weiterzuspringen würde
suggerieren, es habe geklappt — und der Nutzer sucht den Fehler später an der
falschen Stelle. Jede Aktion antwortet mit Ergebnis oder Grund.

## Leere Startseite und „Kingfisher lernt gerade“

Solange noch nichts da ist, zeigt „Heute“ statt leerer Karten einen einzigen nächsten
Schritt („Mail verbinden, dann kann ich dir morgen früh sagen, was wichtig ist.“). Liest
Kingfisher gerade die ersten Mails, steht dort der Fortschritt.

Die ruhige Karte „Kingfisher lernt gerade“ (Startseite, Einstellungen → Zugänge, letzter
Schritt) zeigt nur, was jetzt läuft, und verschwindet, wenn nichts läuft: Mails lesen (x von
y), Absender und Empfänger älterer Mails ergänzen, Mails nach Themen sortieren, Personen,
Projekte und Orte zusammenstellen. Quellen: `GET /api/v1/mail/intake` und
`GET /api/v1/einrichtung/lernt` (offene Berechnung der Akten); die Zeilen bildet `lernt.ts`.

Seit M2 steht oben eine Gesamtzeile aus `GET /api/v1/hintergrund`: „2.400 von 18.000
Quellen, fertig etwa morgen Mittag“. Die Schätzung kommt aus der gemessenen Rate (nur Zeit,
in der Kingfisher lief); ohne genug Messung heißt es „noch unklar“. Dauert es länger als zwei
Stunden, steht darunter ein Satz ohne Aufforderung: „Es geht schneller, wenn der Rechner
heute anbleibt.“ Ein Textknopf pausiert oder setzt fort. Das Sortieren der Mails ist Teil der
Gesamtzeile und erscheint dann nicht noch einmal. Die Regel dahinter steht in
[`46-hintergrund.md`](46-hintergrund.md).

## Autostart

„Kingfisher beim Anmelden starten?“ ist eine Frage im Assistenten und später unter
Einstellungen → Was Kingfisher darf, keine stille Vorgabe. Der Sidecar im Container kann auf dem
Rechner nichts einrichten; er merkt sich nur Ja oder Nein (`autostart.json`, Route
`GET/PUT /api/v1/autostart`, `autostart.py`). Auf dem Mac setzt der Helfer
`scripts/mac_autostart.py` (startet mit `start_mac_app.py`) die Antwort um: Ja legt
`~/Library/LaunchAgents/local.kingfisher.start.plist` an (startet beim Anmelden
`start_mac_app.py --no-browser`, ohne `KeepAlive`), Nein entfernt genau diese Datei, ohne
Antwort geschieht nichts. Über die API kommt nie ein Pfad oder Befehl. Meldet sich kein
Helfer (Windows, Linux, Container ohne Mac), sagt die Oberfläche „Auf diesem System ist das
noch nicht verfügbar.“ und der Schalter ist gesperrt.

## Verbindungen werden geprüft, nicht behauptet

`POST /setup/test/{modell|mail|kalender}` probiert die Verbindung wirklich aus
und gibt den **echten** Fehler zurück. Ein Einrichtungsassistent, der
„gespeichert" sagt und beim ersten Gebrauch scheitert, ist schlimmer als keiner.

## Kein Vorgabeordner

`file_roots` ist leer und bleibt leer, bis jemand etwas einträgt. Weder der Code
noch der Assistent schlagen einen vor. Ein voreingestelltes Home-Verzeichnis
wäre die Bequemlichkeit, die den Schutz aufhebt — dieselbe Begründung wie in
[`05-sicherheit.md`](05-sicherheit.md).

## Modelle nach Aufgabe: „Für diesen Rechner empfohlen“

Einstellungen → Für Techniker → Modelle je Aufgabe schlägt je Aufgabe ein Modell vor, das zum Rechner
passt, und richtet es mit einem Klick ein. Niemand muss Modellnamen kennen.

| Aufgabe (Rolle) | In der Oberfläche | Was sie tut |
|---|---|---|
| `frage` | Fragen verstehen | Frage in Stichworte übersetzen (klein, schnell) |
| `antwort` | Antworten formulieren | Gespräch und Antworten |
| `hintergrund` | Im Hintergrund ordnen | Einordnen, Themen, Verdichtung; nur lokal |
| `einbettung` | Bedeutungen finden | Suche nach Sinn (bge-m3); nur lokal |

- **Empfehlung** (`model_recommendation.py`): Plattform, Chip und Arbeitsspeicher
  (Bericht von `scripts/report_device.py`, macOS, Windows oder Linux) ergeben
  eine Stufe (8/16/24/32/64/128 GB). Die Tabelle `KATALOG` ist datiert und die
  einzige Stelle mit Modellnamen. Es ist eine **Vorauswahl**: Ob ein Modell
  taugt, zeigt die Messlatte (`python -m messlatte lauf --modell ollama:NAME`,
  für die Einordnung getrennt mit `--modell-hintergrund`, für das Verstehen der Frage mit `--modell-frage`). Ohne Gerätebericht gilt
  die kleinste Stufe.
- **Einrichten**: „Einrichten“ zeigt in einem Satz Größe und Dauer; erst nach
  „Laden und einrichten“ lädt Kingfisher über `POST /api/pull` des lokalen
  Ollama (Fortschritt abfragbar), prüft das Modell mit der vorhandenen
  Qualifikationsprüfung und übernimmt es erst dann. Geladen wird nur, was der
  Katalog für diesen Rechner nennt. Fehler kommen mit Grund und nächstem Schritt
  (kein Ollama, kein Speicherplatz, Netz).
- **Ohne Ollama** (Fremdprobe 3, S3): „Dieser Rechner“ sagt, dass Kingfisher mit dem
  kostenlosen Programm Ollama denkt und es gerade nicht antwortet, verlinkt den Download
  und nennt, was ohne geht (Mails, Termine, Briefing) und was nicht (Fragen beantworten,
  im Hintergrund einordnen); „Laden starten“ steht dann nicht da (`rechner.OHNE_OLLAMA`).
  Eine Frage ohne jedes Modell bekommt `agent.OHNE_MODELL_SATZ` in Alltagssprache statt
  eines Hinweises auf eine Konfigurationsdatei. README und Starter sagen dasselbe:
  Ollama installieren, ohne gibt es Mails, Termine und Briefing.
- **Rollen** (`model_roles.py`, Einstellung `model_roles`): Je Rolle Modell
  („wie Standard“ ist die Vorgabe) und, für `frage` und `antwort`, Cloud mit
  ausdrücklicher Einwilligung samt Zeitstempel. Die Einwilligung gilt nur für
  diese Rolle; ohne gültigen Zeitstempel wird die Cloudwahl ignoriert. Die
  Rollen `hintergrund` und `einbettung` lesen alle Quellen und bleiben lokal.
  Ohne Rollenkonfiguration verhält sich alles wie zuvor.
- Routen: `model_roles_routes.py` (`/api/v1/models/recommendation`, `/roles`, `/pull`).

## Meetings: Transkripte in diesen Ordner exportieren

Wer Meetings aufzeichnet, muss Kingfisher nichts erklären: Die Mitschrift kommt als
Datei in **einen** Ordner, Kingfisher liest sie und ordnet sie dem passenden Termin
zu. Einmal einrichten: Einstellungen → Zugänge → Ordner und Dateien → Meetings → „Ordner
„Dokumente/Kingfisher/Transkripte“ verwenden“ (Kingfisher legt ihn an) oder „Anderen
Ordner wählen …“ (ein normaler Auswahldialog, nichts wird getippt). Gelesen wird nur
dieser Ordner, und nur `.txt`, `.vtt`, `.srt`, `.docx` und `.md`. „Ordner trennen“
nimmt alle Mitschriften wieder aus dem Gedächtnis; die Dateien bleiben liegen.

**MacWhisper.** Aufnahme fertig transkribiert? In MacWhisper die Transkription über
„Exportieren“ als Text (`.txt`), Untertitel (`.srt`, `.vtt`) oder Word (`.docx`)
speichern und den Meeting-Ordner als Ziel wählen. Mit eingeschalteter
Sprechererkennung stehen die Namen mit im Export.
Heißt die Datei zum Beispiel „2026-09-28 14.30 Jour fixe Winter“, erkennt Kingfisher
Tag, Uhrzeit und Titel daran; ohne Datum im Namen geht es auch, dann mit etwas
weniger Sicherheit.

**Teams.** Vor oder während der Besprechung „Aufzeichnung und Transkription starten“.
Danach in den Chat der Besprechung gehen, beim Transkript „Herunterladen“ wählen
(Word `.docx` oder `.vtt`) und die Datei in den Meeting-Ordner legen.

**Google Meet.** Wenn dein Konto Transkripte anbietet, legt Meet sie nach der
Besprechung als Google-Dokument in deinem Drive ab (Ordner „Meet Recordings“). Dort
öffnen, „Datei → Herunterladen“ als Word (`.docx`) oder Nur-Text (`.txt`) und in den
Meeting-Ordner legen.

**Zoom und andere.** Was als Text, Word oder Untertitel herauskommt, geht: bei Zoom
das Transkript der Cloud-Aufzeichnung (`.vtt`).

**Telefonate** werden nicht aufgezeichnet. Nach einem Telefonat oder einem Termin
ohne Mitschrift fragt Kingfisher einmal kurz („Wie war das Gespräch mit …?“) und
höchstens für drei Termine zugleich, nur wenn Externe dabei waren. Zwei Sätze als
Antwort genügen, „Nicht nötig“ beendet die Frage.

Was Kingfisher daraus macht: Gehört die Mitschrift eindeutig zu einem Termin, ist
sie ihm zugeordnet; bei Zweifel bietet Kingfisher bis zu drei Termine mit einem
Klick an; sonst steht sie für sich und lässt sich im Kalender unter „Nachbereiten“
einem Termin zuordnen. Jede Zuordnung ist zu ändern. Sprecher werden nur dann
Personen, wenn der Name zu genau einem Teilnehmer des Termins passt. Aus einer
Mitschrift wird nie ungefragt eine Tatsache; Bitten und Zusagen daraus erscheinen
als Vorschlag. Design und Grenzen: [`34-gespraeche.md`](34-gespraeche.md).

**Ohne die Mac-App (Container).** Der Ordner ist dann ein eingebundener, freigegebener
Ordner (`ICARUS_FILE_ROOTS`); eingelesen wird er mit dem Adapter `transkripte`, per
Zeitplan (Quelle mit Adapter `transkripte`) oder einmalig über `POST /ingest`.

## Was offen ist

**Kein Dateiauswahldialog** außer beim Mitschriften-Ordner (dort öffnet der Mac-Helfer
den Auswahldialog). Alle anderen Ordner werden getippt. Das Mac-Fenster (`macos/`)
könnte den Dialog für sie ebenso öffnen; das ist der nächste Schritt, weil einen Pfad
abzutippen genau die Art Reibung ist, die dieses Dokument beseitigen soll.

**Der Assistent fragt nicht nach der Person.** Er richtet Technik ein, aber
Icarus weiß danach immer noch nichts über den Nutzer. Sobald die Verdichtung
steht, gehört ein Schritt dazu, der aus dem eingelesenen Material die ersten
Aussagen **vorschlägt** — vorlegen, nicht schreiben.

**Kein Zurück im Assistenten.** Wer sich vertippt, geht danach auf
„Einrichtung". Vertretbar, aber nicht schön.

## Verwandte Dokumente

- [`05-sicherheit.md`](05-sicherheit.md) — warum es keinen Vorgabeordner gibt
- [`08-gedaechtnisschichten.md`](08-gedaechtnisschichten.md) — was beim Einlesen passiert
- [`07-mcp-tuer.md`](07-mcp-tuer.md) — dasselbe Gedächtnis für andere Assistenten
