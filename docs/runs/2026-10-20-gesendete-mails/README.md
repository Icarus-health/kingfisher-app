# Paket B1: Gesendete Mails einlesen (eigene Zusagen)

Stand 20.10.2026, Branch `feat/gesendet-ordner-20261020` auf `main` (1.0.26). Ausschließlich
synthetische Daten (IMAP-Attrappe mit Lena Probe, Anna Berg, Jonas Keller); kein echtes
Postfach, kein Modellaufruf nach außen. VERSION unverändert.

## Was gebaut wurde

| Bereich | Datei | Kern |
|---|---|---|
| Ordner | `sidecar/icarus_memory/connectors/mail.py` (`folders`, `GESENDET_NAMEN`, `ist_gesendet_ordner`, `Message.entwurf`, `_hat_flag`) | Ohne `\All` werden INBOX **und** Gesendet (SPECIAL-USE `\Sent`, sonst erster üblicher Name) als Startordner markiert; Trash/Junk bleiben draußen; `\Draft` wird gelesen |
| Aufnahme | `sidecar/icarus_memory/mail_intake.py` (`eigene_mail`, `Intake.ergaenzen`, `_step`) | Eigene Mails ohne Regeln und Modell (nur Spam-Kopf des Servers gilt); Entwürfe gezählt (`filtered:entwurf`), nicht aufgenommen; Ordner nachtragen ohne Pause aufzuheben |
| Routen | `sidecar/icarus_memory/mail_intake_routes.py` (`umfang_beschreibung`, `POST …/ordner-ergaenzen`, Stand mit `umfang`, `gesendet_dabei`, `gesendet_erkennbar`) | Drei Sätze zum Umfang; Nachtragen antwortet in einem Satz; 404/409/503 wie die anderen Intake-Routen |
| Stand | `sidecar/icarus_memory/mail_stand.py` (`konto_stand`) | „Der Posteingang ist gelesen (5 Mails). Gesendete Mails werden nachgelesen: bisher keine gefunden.“ |
| Oberfläche | `app/kingfisher/src/mailIntakeGesendet.ts`, `MailIntake.tsx`, `api.ts` | Satz vom Sidecar; Knopf „Gesendete Mails auch einlesen“ nur im Posteingang-Fall; Antwort als Status, 503 mit Grund als Alert |
| Attrappe | `sidecar/tests/imap_attrappe.py` (`gesendet`, `gesendet_name`, `gesendet_attribut`, `flags`) | Gesendet-Ordner, Ordnerwahl bei SELECT, FLAGS je Mail |
| Doku | `docs/14-posteingang.md` („Welche Ordner“), `docs/46-hintergrund.md` („Gesendet nachlesen“), `docs/DEVELOPER-START.md` (Codekarte) | |

## Tests

Erst rot, dann grün (gezielte Dateien `test_mail_inventory.py`, `test_mail_intake_routes.py`,
`test_mail_intake.py`, `test_mail_intake_filter.py`, `test_gesendete_mails.py`,
`test_mailaufnahme_ende_zu_ende.py`, `test_microsoft_graph.py`, `test_fremdprobe2_alltag.py`):

| Lauf | Ergebnis |
|---|---|
| Vorher (Bestand, 7 Dateien) | 123 bestanden |
| Neue Tests vor der Änderung | 28 rot, 98 grün |
| Nach der Änderung (8 Dateien) | 152 bestanden (30 neu, 1 umgestellt) |
| Volle Suite `pytest sidecar/tests -q -x -n auto` | 1 fehlgeschlagen, 2.229 bestanden, 1 übersprungen, bei `-x` abgebrochen (`test_cloud_access.py::…key_revocation…`: Thread-Lebenszeichen unter Parallellast; allein 18 bestanden) |
| Volle Suite `pytest sidecar/tests -q -n auto` (ohne `-x`, 32:44 min) | 2 fehlgeschlagen, 7.758 bestanden, 3 übersprungen, 26 Untertests bestanden |
| Oberfläche `npm test` | 767 bestanden (4 neu in `gesendet-ordner.test.mjs`) |
| `npx tsc --noEmit` | ohne Befund |
| `npm run build` | gebaut |

Die zwei Fehlschläge der vollen Suite: `test_pruefe_anfuehrungszeichen.py` fand `„…\"` im Meldungstext meines
eigenen UI-Tests (behoben, danach 34 bestanden); `test_cloud_memory.py::test_bulk_accepts_101_sources_after_pilot…`
scheitert an der Join-Zeitgrenze von 5 s (`finish`) und fällt in dieser Umgebung ebenso gegen den unveränderten
`origin/main` (Kopie im Scratchpad, dreimal geprüft); das Paket berührt `cloud_memory` nicht.

Neu geprüft wird unter anderem: `\Sent` wird Startordner, Namen ohne Attribut (zehn Schreibweisen),
Attribut vor Namenstreffer, kein zweiter Ordner bei `\All`, Trash/Junk trotz `\Sent` draußen;
Beschreibung je Fall; Nachtragen nur einmal, Pause bleibt, 404/409/503; INBOX und Gesendet im Takt;
eigene Mail aus Gesendet mit `richtung von_mir`; Entwurf nicht aufgenommen, auch nicht nach
„Erneut prüfen“; eigene Absender umgehen Regeln und Modell, fremde nicht; Ende zu Ende über die API:
Zusage „Ich schicke dir die Unterlagen bis Freitag.“ aus Gesendet wird `own_commitment`
(Modellattrappe) und steht unter „Was habe ich zugesagt?“ (ohne Modell); altes Konto trägt Gesendet
nach, Stand-Satz dabei; Mail an sich selbst in beiden Ordnern (Grenze). `test_microsoft_graph.py`
unverändert grün.

## Sabotageproben

Jede Zusicherung absichtlich gebrochen (auf einer Kopie des `sidecar`-Ordners, UI im Baum), passender
Test rot, danach zurückgesetzt. Zahlen aus den Läufen.

| Nr. | Sabotage | Test rot |
|---|---|---|
| 1 | `\Sent`-Attribut nicht erkannt (`ist_gesendet_ordner` und `folders`) | `test_mail_inventory.py`: 1 failed, 50 passed |
| 1b | Attribut-Vorrang in `folders()` aus (nur Namenstreffer zählt) | `test_mail_inventory.py`: 1 failed, 51 passed |
| 2 | Gesendet-Name nicht erkannt | `test_mail_inventory.py` + `test_mail_intake_routes.py`: 12 failed, 55 passed |
| 3 | Gesendet trotz Gesamtbestand (`\All`) zusätzlich markiert | `test_mail_inventory.py`: 1 failed, 50 passed |
| 4 | Eigene Mails doch durch den Filter | `test_mail_intake_filter.py`: 1 failed, 15 passed |
| 5 | Entwürfe durchlassen | `test_mail_intake.py`: 3 failed, 33 passed |
| 6 | Nachtragen hebt die Pause auf | `test_mail_intake_routes.py`: 1 failed, 15 passed |
| 6b | Nachtragen meldet Vorhandenes als neu | Routen + Ende zu Ende: 4 failed, 17 passed |
| 7 | Beschreibung falsch („Nur der Posteingang“ bei Gesendet) | Routen + Ende zu Ende: 4 failed, 17 passed |
| 8 | Stand fällt auf „wird durchgesehen“ zurück | `test_gesendete_mails.py`: 2 failed, 3 passed |
| 9 | `\Draft`-Flag nicht gelesen | `test_mail_inventory.py`: 1 failed, 50 passed |
| 10 | Spam-Kopf bei eigener Mail ignoriert | `test_mail_intake_filter.py`: 1 failed, 15 passed |
| 11 | UI: Knopf trotz „Gesendet dabei“ | `gesendet-ordner.test.mjs`: 1 fail, 3 pass |
| 12 | UI: Knopf trotz „nachgesehen, keiner da“ | `gesendet-ordner.test.mjs`: 1 fail, 3 pass |
| 13 | UI: Satz des Sidecars ignoriert | `gesendet-ordner.test.mjs`: 1 fail, 3 pass |

Probe 1 griff beim ersten Versuch nicht, weil der Testordner „Sent Mail“ auch über den Namen erkannt
wurde; der Test nutzt jetzt „Verzonden“ nur mit Attribut, dazu ein Test für den Vorrang des Attributs.

## Browserprobe

`scripts/probe_gesendet_ui.py` (Chromium `/opt/pw-browsers/chromium-1194`, echter Sidecar, IMAP-Attrappe
mit fünf Mails im Posteingang und einer eigenen in „Gesendet“, Konto wie vor dem Umbau mit nur INBOX
gestartet und fertig gelesen). Ergebnis `ok: true`, Konsole leer; die einzige Zeile des Browsers war
dessen eigene Netzmeldung zum absichtlich ausgelösten 503 (genau eine, als erwartet vermerkt).

| Bild | Was zu sehen ist |
|---|---|
| `gesendet-1-knopf.png`, `-390.png` | Satz „Nur der Posteingang; …“, darunter der Knopf; 390 px ohne seitliches Scrollen (390/390) |
| `gesendet-2-fehler.png` | Postfach schweigt: Alert „Probe-Post antwortet gerade nicht. Prüfe die Internetverbindung …“, Knopf bleibt |
| `gesendet-3-nachgetragen.png`, `-390.png` | Status „Gesendete Mails werden jetzt mit eingelesen.“, Satz „Posteingang und Gesendet; …“, kein Knopf mehr, Stand „Der Posteingang ist gelesen (5 Mails). Gesendete Mails werden nachgelesen: bisher keine gefunden.“; 390/390 |
| `gesendet-4-gelesen.png` | Nach dem nächsten Takt: „Postfach Probe-Post ist gelesen: 6 Mails“, die eigene Mail „Unterlagen“ im Gedächtnis |

Die Bilder liegen außerhalb des Repositories (Scratchpad der Sitzung).

## Abweichungen vom Bauplan und Grenzen

* **Spam-Kopf bei eigenen Mails.** Der Bauplan sagt „weder Regeln noch Modell“. Umgesetzt ist das für
  alle Regeln und das Modell; einzig `X-Spam-Flag` des eigenen Servers gilt weiter, weil ein gefälschter
  eigener Absender das klassische Spam-Muster im Posteingang ist und der Kopf vom Anbieter stammt (fail
  closed; Test `test_eigene_absender_umgehen_regeln_und_modell_fremde_nicht`).
* **Nachtragen hebt keine Pause auf.** `store.start()` setzt `paused=0` für das ganze Konto; die Route nutzt
  deshalb `Intake.ergaenzen`, das neue Ordner mit dem Pausenstand des Kontos anlegt.
* **„Gesendet-Ordner erkennbar“** kennt der Stand nur nach einer Ordnersuche dieses Laufs
  (`gesendet_erkennbar`, nicht gespeichert); ohne sie zeigt die Oberfläche den Knopf, und die Antwort
  sagt ehrlich, ob es einen gibt. Jede Statusabfrage eine IMAP-LIST zu schicken wäre falsch.
* **Entwürfe** zählen unter „ausgefiltert“ (`filtered:entwurf`), damit kein Ordner auf „4 von 5“ stehen
  bleibt; eine eigene Zählerzeile gibt es in der Oberfläche nicht.
* **Mail an sich selbst** liegt in Posteingang und Gesendet und wird zweimal zur Quelle (wie Microsoft);
  bewusst so gelassen, siehe `docs/14-posteingang.md`.
* **503 als Alert mit Grund** gilt jetzt für alle Aktionen der Karte „Ältere Mails einlesen“ (vorher
  „Das hat nicht geklappt“), nicht nur für das Nachtragen.
* `docs/30-akten.md` nennt den Posteingang nicht als Grenze; dort war nichts zu ändern.
* Nicht am Mac geprüft; nicht gegen einen echten Anbieter (Ordnernamen von web.de, GMX, Posteo, iCloud nur
  nach Liste, nicht beobachtet).
