# Paket B6: Aufgaben folgen der Post

Stand 21.10.2026, Branch `feat/aufgaben-folgen-der-post-20261021` auf `feat/gesendet-ordner-20261020` (PR #86,
gesendete Mails). Ausschließlich synthetische Daten (Lena Probe, Anna Berg, Jonas Keller); kein Postfach, kein
Modellaufruf. VERSION unverändert.

Wunsch: „Ich soll das und das machen, dann geht die E-Mail dazu raus, und die Aufgabe wird automatisch auf erledigt
gelegt.“ Grundsätze: reversibel, deshalb ohne Rückfrage; nur bei sicherer Zuordnung automatisch, sonst Vorschlag;
ohne Modell, deterministisch. Beschreibung in [`docs/30-akten.md`](../../30-akten.md#aufgaben-folgen-der-post-oktober-2026).

## Was gebaut wurde

| Bereich | Datei | Kern |
|---|---|---|
| Durchlauf | `sidecar/icarus_memory/aufgaben_post.py` (`Lauf.schritt`, `verarbeiten`, `_treffer`, `tragende_woerter`, `woerter_in`, `heute`, `schritt_fuer`) | Je neue Mail einmal (Stand und Merkliste in `tasks.sqlite3`); eigene Mail im Verlauf oder an die Person mit tragendem Wort erledigt, Antwort von „wartet auf“ holt zurück; sonst Vorschlag; Rundmail, über 90 Tage überfällig, Gleichstand nie automatisch; Mail vor der Bitte zählt nicht; Bestand von vor dem Umbau wird nicht neu gedeutet |
| Aufgabenablage | `sidecar/icarus_memory/tasks.py` (Migration 4 `aufgaben_folgen_der_post`: `aufgaben_post_mails`, `aufgaben_post_getrennt`, `aufgaben_post_stand`; `erledigt_grund`, `geaendert_grund`; `post_erledigen`, `post_zurueckholen`, `post_rueckgaengig`, `post_trennen`, `post_aenderungen`) | Grund samt vorigem Zustand an der Aufgabe; Rückgängig stellt her und trennt Aufgabe und Mail; Geschichte `post_completed`, `post_returned`, `post_undone`; die Ablage selbst weist ab, was nicht passt (fail closed) |
| Quellen | `sidecar/icarus_memory/episodes.py` (`letzte_zeile`, `mails_ab`, `anhang_titel`), `akten.py` (`verlaeufe`) | Neue Mails ab Zeilennummer, Anhangnamen, Mailverläufe über genaue Kopfzeilen |
| Vorschläge | `sidecar/icarus_memory/proposals.py` (`ProposalKind.TASK_DONE`, `TASK_WAITING_RESOLVED`) | „Erledigt?“ und „Wieder bei dir?“ mit Mail als Beleg und `target_ref` Aufgabe; Annehmen = dieselbe Änderung, Verwerfen = Trennung |
| Logbuch | `sidecar/icarus_memory/logbuch.py` (`aufgabe_post`, `Zusammenfassung.aufgaben_post`, `_post_saetze`) | „1 Aufgabe nach deiner Post erledigt, 1 Aufgabe wieder bei dir“; nur Kennungen, kein Text |
| Akte und Briefing | `akten._braucht_dich` (Art `aufgabe_post`, 14 Tage), `tagesbriefing._aufgaben_post_zeile`, `tag_routes.briefing` | „Braucht dich“ zeigt die Änderung mit Rückgängig; die Tageslage nennt „Erledigt durch deine Mail an …“ höchstens einmal |
| Routen und Takt | `sidecar/icarus_memory/server.py` (`POST /api/v1/tasks/{id}/rueckgaengig`, `GET /api/v1/aufgaben-post/vorschlaege`, `POST …/{id}/annehmen`, `…/verwerfen`; `schritt_fuer` nach `run_mail_intake`) | 404/409 wie die anderen Routen; der Durchlauf läuft nach jedem Takt der Aufnahme, auch „nur neue Post“ in der Pause |
| Oberfläche | `app/kingfisher/src/aufgabenPost.ts`, `TaskRow.tsx`, `App.tsx`, `TaskDetail.tsx`, `AufgabenPostVorschlaege.tsx`, `AkteAbschnitte.tsx`, `TagesLage.tsx`, `api.ts`, `WorkspaceTasks.css` | Zeile „Erledigt, weil du Anna Berg am 21. Oktober „Druckdaten“ geschickt hast. Rückgängig“; Karte „Aus deiner Post“ mit „Ja, erledigt“/„Nein“; Akte und Tageslage |
| Doku | `docs/30-akten.md`, `docs/03-delegation.md`, `docs/21-sqlite-migrationen.md`, `docs/DEVELOPER-START.md` | |

## Tests

Erst rot, dann grün. `sidecar/tests/test_aufgaben_post.py` (22 Tests) scheiterte vor dem Bau beim Import des
Moduls (1 Fehler beim Sammeln, alle 22 rot), danach 22 bestanden. Drei bestehende Tests nennen die neue
Schemaversion 4 der Aufgabenablage (`test_migrations.py`, `test_task_save_requests.py`).

| Lauf | Ergebnis |
|---|---|
| Neue Tests vor dem Bau | Importfehler, 22 rot |
| `test_aufgaben_post.py` nach dem Bau | 22 bestanden |
| Nachbarn (`test_task*.py`, `test_offene_punkte.py`, `test_akten*.py`, `test_briefing*.py`, `test_proposal*.py`, `test_logbuch*.py`, `test_tagesbriefing*.py`, `test_gesendete_mails.py`, `test_pause_neue_post.py`, `test_mail_intake*.py`, `test_mailaufnahme_ende_zu_ende.py`, `test_complete_recovery.py`, `test_backup.py`, `-n auto`) | 715 bestanden, 1 übersprungen, 1 fehlgeschlagen (`test_task_save_requests.py::test_v2_upgrade…` erwartete Version 3; auf 4 gestellt, danach 4 bestanden) |
| Volle Suite `pytest sidecar/tests -q -n auto` (15:38 min) | 7.782 bestanden, 3 übersprungen, 0 fehlgeschlagen, 26 Untertests bestanden, 5 Warnungen |
| Oberfläche `npm test` | 772 bestanden (5 neu in `aufgaben-post.test.mjs`) |
| `npx tsc --noEmit` | ohne Befund |
| `npm run build` | gebaut |

Neu geprüft wird unter anderem: tragende Wörter ohne Füll-, Handlungs- und Stoppwörter und ohne Namen, mit Umschrift
und Beugung; eigene Antwort im Verlauf mit Wort erledigt mit Grund, Geschichte `post_completed` und Logbucheintrag ohne
Text; eigene Mail an die Person ohne Verlauf; Anhangname zählt; Mail an jemand anderen oder Aufgabe ohne Quelle ändert
nichts; Mail vor der Bitte zählt nicht; ohne Wort Vorschlag, Annehmen erledigt mit Grund „geantwortet hast“, zweites
Annehmen 409; Rundmail Vorschlag; über 90 Tage überfällig Vorschlag; Gleichstand zweier Aufgaben Vorschlag, Verlauf
schlägt Person; „wartet auf Anna“ und Antwort im Verlauf zurück zu dir (offen, nicht erledigt), ohne Verlauf und Wort
Vorschlag, Verwerfen trennt; fremde Mail erledigt nie, was bei dir liegt; Rückgängig stellt her (auch Warten samt
Datum), trennt dauerhaft, 404/409; Mail nur einmal, auch nach Neustart der Ablage, Stand rückt vor; Bestand von vor dem
Umbau wird nicht neu gedeutet; Migration 4; Briefingzeile höchstens einmal, morgen nicht mehr; Logbuchzeile; Akte
„Braucht dich“ mit `aufgabe_post`, die Bitte gilt in der Akte als erledigt; Routen über die API samt Tageslage; die
Mailaufnahme stößt den Durchlauf in beiden Takten an.

## Sabotageproben

Jede Zusicherung absichtlich gebrochen (Sidecar auf einer Kopie des `sidecar`-Ordners, Oberfläche auf einer Kopie
von `src` und `tests`), passender Test rot, danach zurückgesetzt. Zahlen aus den Läufen (`test_aufgaben_post.py`:
22 Tests; `aufgaben-post.test.mjs`: 5 Tests).

| Nr. | Sabotage | Test rot |
|---|---|---|
| 1 | Wort-Bedingung weggelassen (ohne tragendes Wort automatisch) | 2 failed, 20 passed |
| 2 | Rundmail automatisch | 1 failed, 21 passed |
| 3 | „wartet auf“ erledigen statt zurückgeben (Durchlauf) | 3 failed, 19 passed |
| 3b | dazu die Sperre in der Ablage weg (`post_erledigen` ohne Prüfung) | 2 failed, 20 passed |
| 4 | Rückgängig ohne Trennung (Aufgabe, Mail) | 1 failed, 21 passed |
| 5a | Mail nicht gemerkt (Merkliste weg) | 1 failed, 21 passed |
| 5b | Stand nicht vorgerückt | zunächst 22 passed (die Merkliste allein hielt die Zusicherung); Test um die Prüfung des Stands ergänzt, danach 1 failed, 21 passed |
| 6 | Gleichstand automatisch | 1 failed, 21 passed |
| 7 | über 90 Tage überfällige Aufgabe automatisch | 1 failed, 21 passed |
| 8 | Logbuch-Art `aufgabe_post` fehlt | 2 failed, 20 passed |
| 9 | Briefingzeile je Aufgabe statt einmal | 2 failed, 20 passed |
| 10 | Mail von vor der Bitte zählt | 1 failed, 21 passed |
| 11 | fremde Mail greift ohne Warten (Sperre im Durchlauf und in der Ablage weg) | 1 failed, 21 passed |
| U1 | Zeile ohne „Rückgängig“ | 1 fail, 4 pass |
| U2 | Satz bleibt nach „Rückgängig“ (wieder offen) stehen | 1 fail, 4 pass |
| U3 | Akte ohne „Rückgängig“ | 1 fail, 4 pass |
| U4 | Vorschlag ohne „Nein“ | 1 fail, 4 pass |

## Browserprobe

`scripts/probe_aufgaben_post_ui.py` (Chromium `/opt/pw-browsers/chromium-1194`, echter Sidecar, eigene Adresse in den
Einstellungen, Mails als Quellen wie nach der Aufnahme, Aufgabe aus Annas Bitte). Ergebnis `ok: true`, Konsole leer.

| Bild | Was zu sehen ist |
|---|---|
| `aufgaben-post-1-erledigt.png`, `-390.png` | Aufgaben → Erledigt: „Erledigt, weil du Anna Berg am 21. Oktober „Druckdaten“ geschickt hast. Rückgängig“; 390 px ohne seitliches Scrollen, der Satz umbricht |
| `aufgaben-post-2-rueckgaengig.png` | Nach „Rückgängig“: die Aufgabe wieder unter „Meine Aufgaben“, ohne Zeile |
| `aufgaben-post-3-vorschlag.png`, `-390.png` | Karte „Aus deiner Post · 1“: „Erledigt? „Druckdaten an Anna schicken““, der Satz mit Mail, „Ja, erledigt“, „Nein“, „Mail öffnen“ |
| `aufgaben-post-4-angenommen.png` | Nach „Ja, erledigt“: „Als erledigt abgelegt. Rückgängig geht in der Aufgabenliste.“ |
| `aufgaben-post-5-akte.png`, `-390.png` | Akte Anna Berg, „Braucht dich 1“: die Aufgabe mit Grund, „Rückgängig“, „Mail öffnen“; keine offene Bitte mehr |
| `aufgaben-post-6-heute.png` | Heute → Tageslage: „Post: Erledigt durch deine Mail an Anna Berg: „Druckdaten an Anna schicken“.“ mit „Aufgabe öffnen“; Verlauf „2 Aufgaben nach deiner Post erledigt“ |

Die Bilder liegen außerhalb des Repositories (Scratchpad der Sitzung). Zwei Korrekturen aus der Probe: die
Tageslage ist auf Heute eingeklappt (die Probe öffnet sie), und die Zeile mit dem Grund brach bei 390 px nicht um
(`styles.css` kürzt `.task-copy small`; `task-post` umbricht jetzt).

## Abweichungen vom Bauplan und Grenzen

* **Person der Aufgabe.** Die Aufgabe hat kein Personenfeld; „die Person der Aufgabe“ ist der Absender ihrer
  Quellmail (bei einer eigenen Quellmail ihr erster fremder Empfänger). Aufgaben ohne Quelle erledigt nur ein Mensch
  (oder sie werden über „wartet auf“ zurückgeholt).
* **Mail vor der Bitte.** Ergänzt (nicht im Bauplan): Eine eigene Mail, die älter ist als die Quelle der Aufgabe
  (ohne Quelle: als die Aufgabe), kann sie nicht erfüllen und zählt nicht.
* **Rückgängig trennt vollständig.** Was der Nutzer per Rückgängig oder „Nein“ getrennt hat, kommt weder automatisch
  noch als Vorschlag wieder (der Bauplan nennt nur „nie automatisch“).
* **Erster Durchlauf.** Der Bestand von vor dem Umbau wird nicht gegen die Aufgaben gedeutet; der erste Durchlauf setzt
  nur den Stand. Alte Mails, die später nachgeladen werden, zählen über den Datumsvergleich.
* **Logbuch zählt Ereignisse.** „2 Aufgaben nach deiner Post erledigt“ zählt auch, was danach zurückgenommen wurde
  (Rückgängig steht als eigener Eintrag `rueckgaengig`, ohne Zeile).
* **Morgenbriefing (`briefing.py`)** unverändert: Die erledigte Aufgabe mahnt dort nicht mehr (sie ist nicht mehr
  offen); die Zeile „Erledigt durch deine Mail an …“ steht in der Tageslage (`tagesbriefing.py`).
* **Name von „wartet auf“.** „Anna“ passt zu „Anna Berg“ (Vor- oder Nachname, Adresse); bei zwei Annas entscheidet
  der Verlauf oder das Wort, sonst gibt es nur Vorschläge.
* **Kein Modell.** Ein Modell darf später nur Kandidaten liefern; nicht Teil dieses Pakets.
* Nicht am Mac geprüft; nicht gegen einen echten Anbieter.
