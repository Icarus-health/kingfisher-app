# Gespräche und Meetings im Gedächtnis (Etappe F3)

Stand: 29. September 2026. Umsetzung der Entscheidung „Gespräche und Meetings“
aus [`26-plan-stabschef.md`](26-plan-stabschef.md). Code: `transkript_eingang.py`
(Lesen), `transkript_zuordnung.py` (Termin, Sprecher, Ablage),
`transkript_routes.py` (Verdrahtung), `folder_sync.py` (Ordnerroute, jetzt für
zwei Ordner), `scripts/mac_folder_worker.py` (Rolle `transkripte`),
`nachbereitung.py` (Nachfrage), Oberfläche `TranscriptSettings.tsx` und
`CalendarFollowup.tsx`. Tests: `test_transkript_*.py`, `test_gespraech_nachfrage.py`,
`test_mac_transkript_worker.py`. Anleitung für den Nutzer:
[`09-einrichtung.md`](09-einrichtung.md), Abschnitt „Meetings“.

## Was sich ändert

Telefonate werden nicht aufgezeichnet, Meetings schon: MacWhisper auf dem Mac, Teams,
Meet oder Zoom bei anderen. Jede dieser Anwendungen kann eine Mitschrift als Datei
ablegen. Kingfisher beobachtet dafür **einen** Ordner, liest die Dateien als
Rohquelle, ordnet sie dem Termin zu und stellt sie in Suche, Einordnung, Bezüge und
Akten wie jede andere Quelle. Wo keine Mitschrift vorliegt (Telefonat, Termin ohne
Aufnahme), fragt das Briefing einmal knapp nach; die Antwort wird eine Quelle.

## Zwei Wege in denselben Bestand

| Weg | Wo | Wie |
|---|---|---|
| Mac-Ordnerarbeiter | Mac-App | `mac_folder_worker.py --role transkripte`, Route `/api/v1/transcript-sync` (gleiche Route wie der Dokumentenordner, `folder_sync.Ordnerart`) |
| Ordneradapter | Container, Zeitplan, `POST /ingest` | Adapter `transkripte` in `ingest.py`; der Ordner muss ein freigegebener Ordner sein (`ICARUS_FILE_ROOTS`) |

Beide rufen `transkript_eingang.aufnehmen` und danach `Zuordner.vormerken`. Es gibt
keinen dritten Weg. Später kommen direkte Anbindungen (Meet über Google Drive, Teams
über Microsoft Graph) als weitere Ordnerquellen dazu; alles danach bleibt gleich.

### Freigabe: nur der gewählte Ordner

* Der Ordner wird **nie getippt.** Die Oberfläche bittet um eine Auswahl
  (`POST /api/v1/transkripte/ordner`), der Mac-Helfer öffnet den Auswahldialog
  (`osascript … choose folder`) oder legt auf Wunsch `Dokumente/Kingfisher/Transkripte`
  an, und meldet den gewählten Ordner mit der Kennung der Anfrage zurück. Der Server
  kann den Helfer nur bitten, einen Dialog zu zeigen; welchen Ordner der Helfer
  meldet, bestimmt allein die Wahl am Mac.
* **Erst die Wahl gibt frei.** Ein Ordner, den der Helfer ohne gültige Anfrage meldet
  (etwa sein gemerkter), ist registriert, aber **nicht aktiv**. Eine falsche oder
  abgelaufene Anfragekennung gibt nichts frei (zehn Minuten Gültigkeit).
* Der Helfer liest wie bisher (`scan`): keine Symlinks, keine versteckten Dateien,
  stabile Dateien, Ordnerkennung mit Gerät und Inode, Grenzen 5 MiB und 2.000 Dateien.
  Zusätzlich gibt er die Änderungszeit der Datei mit. Gelesen werden nur `.txt`,
  `.vtt`, `.srt`, `.docx`, `.md`; PDF, CSV und alles andere bleibt liegen.
* **Ein anderer Ordner** entzieht die Mitschriften des alten (bestehende Regel der
  Ordnerroute). **Pausieren** stoppt das Lesen, ohne etwas zu entziehen.
* **Trennen** (`DELETE /api/v1/transkripte/ordner`) entzieht alle Mitschriften des
  Ordners sofort (`invalidate_with_corrections`, Ausschluss mit Marke
  `entzogen:ordner`), leert die Einstellung und markiert sie als getrennt. Der Helfer
  vergisst daraufhin seine gemerkte Wahl (`<Konfiguration>.transkripte.json`) und
  bietet den alten Ordner nicht wieder an. Die Dateien bleiben unberührt. Wird
  derselbe Ordner später erneut gewählt, gelten unveränderte Mitschriften wieder
  (`aufnehmen` öffnet Quellen mit dieser Marke; ein Ausschluss durch den Nutzer nie).

## Lesen (`transkript_eingang.py`)

Aus einer Datei wird **abgelesen, nie gedeutet**:

* **Text.** SRT/VTT über den vorhandenen Parser (`text_aus_mitschrift`, Sprecher aus
  `<v Name>` bleiben), DOCX über `document_text`, TXT/MD unverändert. Zeitmarken
  fallen weg, die Teams-Form („Name 0:05“ mit dem Text darunter), `[00:01] Name: Text`
  und `Name [00:01]: Text` werden zu „Name: Text“.
* **Sprecher.** Eine Zeile „Name: …“ zählt, wenn dieselbe Marke mindestens zweimal
  vorkommt (danach auch einmalige Sprecher mit großgeschriebenem Namen). Kopfwörter
  (Datum, Thema, Ergebnis, Teilnehmer …) sind nie Sprecher, „Sprecher 1“ und
  „Speaker 2“ sind anonym und werden keiner Person zugeordnet.
* **Zeit.** Nur aus dem Dateinamen oder dem Kopf (Frontmatter, „Datum: …“):
  `2026-09-28 14.30`, `20260928_143012` (Teams), `(2026-09-28 at 14:02 GMT+2)` (Meet),
  `28.09.2026 14:30`, sonst nur der Tag. Ohne Zone gilt die Zeitzone des Nutzers.
  Der **Dateizeitpunkt** bleibt ein schwaches Zeichen für die Zuordnung und wird nie
  Zeitpunkt der Quelle: ein kopierter Ordner würde sonst jede Quelle zur neuen
  Fassung machen.
* **Episode.** Art `document`, Marke `transkript`, Titel „Mitschrift: <Titel>“, Text
  mit Kopf (Titel, Datei, Zeit, Sprecher), `occurred_at` aus Name/Kopf (sonst leer),
  Beteiligte = die Sprecher als Namen, `source_key` je Datei. Ein geänderter Text
  ist eine neue Fassung (`track_source`), dieselbe Datei erneut kein zweites
  Exemplar.
* **Identität = Text.** Nach der Bestätigung der Zuordnung wachsen die Metadaten der Quelle
  (Sprecher als Beteiligte, `EpisodeStore.add_contacts`; Lösen nimmt sie zurück). `aufnehmen` vergleicht
  darum den Text mit der aktuellen Fassung, nicht die Metadaten, sonst sähe ein
  erneutes Einlesen wie eine Dublette aus.

## Zuordnung zum Termin (`transkript_zuordnung.py`)

Kandidaten sind die Termine des Gedächtnisses (Episoden der Art `event`, Etappe C1,
Beginn im Fenster um die Mitschrift; nicht ganztägige, geltende). Punkte:

| Zeichen | Punkte |
|---|---|
| Uhrzeit der Datei liegt im Termin (bis 15 Minuten vor Beginn) | 3 |
| gleicher Tag laut Datei, oder Datei bis 4 Stunden nach Ende geschrieben | 1 |
| ein Titelwort stimmt überein (Hälfte und mehr der Titelwörter: 3) | 2 (3) |
| Sprecher unter den Teilnehmern (höchstens zwei zählen) | je 1 |

Widerspricht die Datei mit Uhrzeit oder Tag dem Termin (anderer Tag), entfällt der
Termin. Der Dateizeitpunkt allein schließt niemanden aus.

* **zugeordnet:** bester Termin mit ≥ 3 Punkten und Alleinstellung oder ≥ 2 Punkte
  Abstand. Mit Gründen; als Bezug der Quelle jederzeit lösbar oder änderbar.
* **vorschlag:** bester ≥ 2 Punkte, aber nicht eindeutig. Bis zu drei Termine, ein
  Klick entscheidet (Einstellungen und Kalender).
* **allein:** sonst. Von Hand zuordnen über Kalender → Nachbereiten →
  „Mitschrift zuordnen“.

`von = 'nutzer'` (Klick oder Lösen) überschreibt der Abgleich nie; ein gelöster
Termin wird für diese Mitschrift nicht erneut vorgeschlagen. Termine, die erst
nach der Mitschrift im Gedächtnis erscheinen, holt `nachziehen()` beim Öffnen der
Übersicht nach.

Ist ein Projekt für den Termin gewählt, erbt die Mitschrift es nach der Bestätigung (`link_project`); die
Projektakte enthält sie dann.

### Sprecher als Personen

Nur bei einer **vom Nutzer bestätigten** Zuordnung („Stimmt so“ oder eigene Wahl), gegen die
Teilnehmerliste dieses Termins: voller Name gleich (ohne Titel, „Keller, Anna“ = „Anna
Keller“), oder der Vorname allein, wenn genau ein Teilnehmer so heißt; fehlt der Anzeigename,
gilt der Teil der Adresse vor dem @ („anna.berg“). Bei Treffer trägt die Quelle die Adresse als
Anker (wie Mail), sonst bleibt der Sprecher ein Name. Zwei Teilnehmer „Anna“ machen aus „Anna“
keine von beiden. Eine automatische Zuordnung ist nur ein Vorschlag und schreibt nichts in die
Quelle (Regel des Gedächtnisses). Was die Bestätigung hinzufügt (Kontakte, Texte, Projekt), merkt
die Ablage in `uebernommen`; „Zuordnung lösen“ und eine Bestätigung für einen anderen Termin
nehmen genau das wieder zurück (`EpisodeStore.remove_contacts`, `link_project(…, None)`), nie,
was schon vorher in der Quelle stand. Eine falsche Person lässt sich zusätzlich in ihrer Akte
ablehnen (D1).

### Ablage

Eine eigene Datei, `gespraeche.sqlite3` (Tabelle `zuordnung`, eigene Versionierung
über `migrations.py`): Episode, Status, Termin, `von`, die Zeichen aus der Datei,
Kandidaten, Gründe, abgelehnte Termine, Übernommenes (`uebernommen`). Abgeleitet: keine Quelltexte. Eine entzogene
Quelle zählt nirgends mehr, gleich was in der Datei steht.

## Nachfrage (`nachbereitung.py`)

Das Briefing fragt nach einem vergangenen Termin (letzte 48 Stunden) **nur, wenn**
er Externe hatte (Teilnehmer ohne Adresse oder mit fremder Domäne; eine eigene
Firmendomäne macht Kollegen zu Internen, ein privater Anbieter nicht), ihn niemand
beantwortet oder mit „Nicht nötig“ abgewiesen hat, und **keine Mitschrift**
zugeordnet ist. Höchstens **drei** Karten zugleich, neueste zuerst. Ein gewähltes
Projekt allein löst keine Frage mehr aus (bisher schon; die Entscheidung F3 ist
enger). Jede Karte trägt `mit` (Namen) und `frage` („Wie war das Gespräch mit Anna
Keller?“).

Die Antwort (Kalender → Nachbereiten, ein Textfeld) wird wie bisher eine Quelle
(`POST /api/v1/calendar/nachbereitung`): Art `message`, Herkunft Nutzerangabe, an den
Termin und seine Teilnehmer gebunden, mit Projekt des Termins. Rohmaterial: sie geht
durch Einordnung und Aufgabenerkennung, ein Fakt entsteht erst durch Annahme. „Nicht
nötig“ und Antwort sind endgültig für diesen Termin (Serientermine je Vorkommen);
wer ein „Nicht nötig“ zurücknimmt, wird wieder gefragt. Liegt später eine Mitschrift
vor, entfällt die Frage; löst der Nutzer die Zuordnung, kommt sie wieder.

## Was noch fehlt

* **Diktat** für die Antwort (Tonaufnahme → Text) ist nicht gebaut.
* **Briefing und Morgenkarte** tragen ihre Formulierung in `briefing.py` und
  `morning.py` („… ist vorbei. Was ist herausgekommen?“, „Was kam bei … heraus?“).
  `nachzubereiten` liefert `frage` und `mit`; die Sätze umzustellen ist Sache der
  Arbeit am Briefing.
* **Lange Mitschriften** (30.000 Zeichen und mehr) wurden bis zum 30. September nie eingeordnet, also nie Beleg. Jetzt
  teilt `abschnitte.py` sie an Sprecherwechseln in Abschnitte von 3.000 bis 6.000 Zeichen und ordnet sie in
  Häppchen ein ([`35-belegte-antworten.md`](35-belegte-antworten.md#lange-quellen-in-abschnitten)). Das Transkript
  bleibt eine Quelle; der Beleg zeigt auf den Sprecherbeitrag an der richtigen Stelle im Volltext. Über 200.000 Zeichen
  (nach `MAX_TEXT` der Mitschrift höchstens 512 KiB) bleibt sie zurückgestellt, und das Logbuch vermerkt es.
* **Word-Transkripte aus Meet** erscheinen je nach Export mit oder ohne Sprechernamen;
  die Erkennung ist für die Formen oben getestet, nicht gegen echte Dateien.
* **Mehrere Dateien zu einem Termin** (Teams-VTT und Word-Export desselben Meetings)
  werden beide zugeordnet und sind zwei Quellen.
* **Sprecher nachträglich zuordnen** (Klick auf einen Namen) fehlt; heute bleibt ein
  nicht eindeutiger Sprecher ein Name.
* **Der Mac-Teil** (Auswahldialog, Start durch `start_mac_app.py`) ist auf dieser
  Umgebung nicht gelaufen (kein macOS). Getestet ist alles darum herum, der Dialog
  selbst (`osascript`) ist durch eine Funktion ersetzt.

## Prüfung

Backend: `test_transkript_eingang.py` (Formate, Sprecher, Zeit aus Namen und Kopf),
`test_transkript_zuordnung.py` (Punkte, Zuordnung, Vorschlag, Sprecher, Nutzerwahl,
Entzug), `test_transkript_routes.py` (Freigabe, Trennen, Auswahl, Ordnerwechsel,
Token), `test_transkript_ingest.py` (Ordneradapter), `test_mac_transkript_worker.py`
(Helfer gegen die echten Routen), `test_gespraech_nachfrage.py` (Karten),
`test_transkript_gedaechtnis.py` (Suche, Einordnung, Bezüge, Entzug).

Browser (Chromium, synthetische Daten, echter Mac-Helfer gegen einen Entwicklungsserver
mit Schein-Home; der Auswahldialog ersetzt durch „Ordner verwenden“): Einstellungen →
Dokumente → Meetings: Ordner wählen, Status („2 Mitschriften aufgenommen · 1 einem
Termin zugeordnet · 1 ohne Termin“), Vorschlag per Klick zuordnen, Trennen mit
Rückfrage und Meldung. Kalender → Nachbereiten: Karte „Wie war das Gespräch mit …?“
mit „Nicht nötig“, „Zu diesem Termin liegt eine Mitschrift vor“ mit „Gehört nicht
hierher“, Angebot „Mitschrift zuordnen“. Konsole ohne Fehler und Warnungen.

## Sabotageproben

Je Zusicherung absichtlich gebrochen, die genannten Testdateien liefen, danach
zurückgespielt. In jedem Fall wurde der genannte Test rot.

| Gebrochene Zusicherung | Rot wurde |
|---|---|
| Aufnahme ohne Freigabeprüfung | `…ohne_ausdrueckliche_wahl_wird_nichts_gelesen` |
| jede Kennung gilt als Wahl im Dialog | `…die_wahl_im_dialog_ist_die_freigabe_genau_dieses_ordners` |
| Trennen entzieht nicht | `…trennen_entzieht_alle_mitschriften…` |
| alter Ordner wird nach dem Trennen wieder angeboten | derselbe Test |
| Ordnerwechsel entzieht den alten nicht | `…ordner_wechseln_entzieht_den_alten` |
| PDF und CSV werden mitgelesen | `…nur_mitschriftformate_werden_aufgenommen_und_zugeordnet` |
| kein Abstand zum zweiten Termin | `…mehrdeutig_ist_ein_vorschlag…` |
| Schwelle für „zugeordnet“ auf 1 | `…mehrdeutig_ist_ein_vorschlag…` |
| anderer Tag schließt den Termin nicht aus | `…datei_mit_anderem_tag_schliesst_den_termin_aus…` |
| Dateizeitpunkt allein genügt für einen Vorschlag | `…dateizeitpunkt_allein_ordnet_nie_zu` |
| mehrdeutiger Vorname wird der ersten Person zugeschrieben | `…sprecher_nur_bei_eindeutigem_treffer` |
| Sprecher werden auch bei Vorschlag zu Personen | `…bei_einem_vorschlag_werden_keine_sprecher_zu_personen` |
| Abgleich überschreibt Nutzerwahl | `…klick_auf_einen_vorschlag_ordnet_zu_und_bleibt` |
| gelöster Termin wird erneut vorgeschlagen | `…entscheiden_ist_rein_und_speichert_nichts` |
| entzogene Mitschrift zählt weiter | `…entzogene_mitschrift_zaehlt_nirgends_mehr` |
| erneutes Einlesen vergleicht nicht den Text | `…erneutes_einlesen_nach_der_zuordnung_legt_nichts_doppelt_an` |
| Interne werden auch gefragt | `…interne_termine_fragen_nicht_nach` |
| mehr als drei Karten | `…nie_mehr_als_drei_karten…` |
| Abgewiesene oder beantwortete Termine fragen erneut | `…erledigte_und_abgewiesene_termine_fragen_nie_wieder` |
| Nachfrage trotz zugeordneter Mitschrift | `…mit_mitschrift_wird_nicht_gefragt` |
| Antwort als Ableitung statt Aussage des Nutzers | `…antwort_wird_quelle_und_kein_fakt` |
| Mitschrift nicht als Rohquelle der Art `document` | `…suche_findet_die_mitschrift` |

Die erste Fassung der Probe „anderer Tag“ blieb grün: Der Test lag außerhalb des
Suchfensters und hätte den Widerspruch nie geprüft. Er wurde durch einen Test auf
der Bewertung selbst ersetzt, danach wurde die Probe rot.
