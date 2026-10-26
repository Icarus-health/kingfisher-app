# Paket A „Aufgaben von selbst“ (26.10.2026)

Entscheidung des Nutzers ([`66-automatik.md`](../../66-automatik.md)): Eindeutige Bitten an dich und eigene Zusagen
werden automatisch Aufgaben, mit „Von Kingfisher angelegt · Rückgängig“, Projekt und Person zugeordnet. Unsichere
bleiben Vorschläge, mit „Alle übernehmen“. Fachdoku: [`30-akten.md`](../../30-akten.md#aufgaben-von-selbst-26102026),
Schalter: [`47-einstellungen.md`](../../47-einstellungen.md#aufgaben-aus-mails-selbst-anlegen-26102026).

## Was gebaut ist

* **Eindeutig, als eigene Regel** (`aufgaben_von_selbst.pruefen`, jede Bedingung mit ihrem Satz und Kürzel): Mail;
  Auftrag von der Aufgabenerkennung in der ganzen Mail geprüft (`task-review-v1`, Titel von der Textstelle getragen);
  nicht schon zurückgenommen; nicht aus der Bestandsaufnahme eines Postfachs; neu nach `neu_eingegangen` (heute bis
  vorgestern); keine weitere Mail im Verlauf; Empfängerrollen bekannt; höchstens drei Empfänger, kein Newsletter;
  Bitte: kein Sammel- oder Absenderpostfach, du stehst unter „An“; Zusage: eigene Mail an jemanden; keine Dublette
  (Quelle mit Titel oder Textstelle, offener gleicher Titel). Höchstens zehn je Durchlauf, jeder Vorschlag einmal.
* **Automatisch anlegen** nach jeder Mailaufnahme und nach jeder Aufgabenerkennung (je eine Zeile in `server.py`):
  Titel, Frist (nur eine eindeutige Angabe in der Textstelle), Quelle, Projekt (Quelle, Absenderregel, gemerkter
  lokaler Hinweis; nur vorhandene offene Projekte), Person (Adresse und Name; neues Feld `Task.person`), Herkunft
  `Task.angelegt` (`automatisch`, Satz, Grundsatz, Mail). Migration 5 in `tasks.sqlite3`: `aufgaben_auto_geprueft`,
  `aufgaben_auto_zurueck`, `aufgaben_auto_einstellung`. Logbuch `aufgabe_post`, `sorte: angelegt` (ein Satz „N
  Aufgaben aus der Post angelegt“; der dabei angenommene Vorschlag zählt nicht als „von dir angenommen“).
* **Rückgängig** entfernt die Aufgabe (Geschichte behält `auto_removed`), verwirft den Vorschlag und merkt sich Quelle,
  Titel und Textstelle; ein späterer Vorschlag aus derselben Mail wird ebenfalls verworfen. „Rückgängig“ im Hinweis
  stellt die Aufgabe unverändert wieder her. In Liste und Detail: „Von Kingfisher angelegt · aus der Mail von Anna
  Berg vom 26. Oktober · Rückgängig“; die Person steht in der leisen Zeile und führt im Detail zur Akte.
* **Heute**: eine ruhige Zeile „2 Aufgaben aus der Post angelegt. Ansehen · Rückgängig“ (nimmt alle noch offenen von
  heute zurück, der Hinweis holt sie wieder). Die Übernahme eines Vorschlags auf Heute und im Mail-Briefing nimmt den
  Projekthinweis mit (`zuordnung_aus_vorschlag`, im Mail-Briefing serverseitig) statt `project_id: null`.
* **Vorschläge**: Person und Frist vorbefüllt (`person_vorschlag`, `frist_vorschlag`), Projekt wie bisher; „Alle N
  übernehmen“ für die sichtbaren in einem Klick, „Rückgängig“ für die ganze Gruppe (die Vorschläge stehen wieder offen).
* **Schalter** „Aufgaben aus Mails selbst anlegen“ unter „Was Kingfisher darf“, Vorgabe an, ein Satz Erklärung.

## Zahlen

* Neue Tests: `sidecar/tests/test_aufgaben_von_selbst.py` 24 (Regel, Durchlauf, Rückgängig, Projekt, Heute, Logbuch,
  Migration, Routen), `app/kingfisher/tests/aufgaben-von-selbst.test.mjs` 5. Angepasst: Migrationsversion 5 in
  `test_migrations.py`, `test_aufgaben_post.py`, `test_task_save_requests.py`; acht Schalter in `einstellungen-gliederung.test.mjs`.
* Volle Backend-Suite (`-n 4`): 8055 bestanden, 3 übersprungen, 3 rot unter Last
  (`test_cloud_memory::test_bulk_accepts_101…`, `test_cloud_access::test_anthropic_import_route…`,
  `test_postfach_lage::test_nachrichten_nennen…`); alle drei allein erneut: grün. `test_task_save_requests.py`
  erwartet jetzt Fassung 5. Oberfläche: `npx tsc --noEmit` ohne Befund, `node --test tests/*.test.mjs` 931 grün (vor dem Hinweis auf die Platte, danach nur gezielt),
  `npx vite build` ohne Fehler.
* `scripts/probe_seiten_ui.py` hell und dunkel: 75 Breiten geprüft, 0 Befunde.

## Sabotageproben

| Gebrochen | Rot |
|---|---|
| Altbestand-Regel aus (`aus_bestand`, `ist_neu`) | `…[alt-nicht_neu]`, `test_altbestand_aus_der_bestandsaufnahme…` |
| Zurückgenommen-Regel aus | `test_rueckgaengig_entfernt_merkt_und_dieselbe_bitte_kommt_nicht_wieder` |
| Schalter wirkungslos | `test_schalter_aus_legt_nichts_an_und_merkt_nichts`, `test_routen_schalter_…` |
| Rundmail-Regel aus (Empfänger, Newsletter) | `…[rundmail-rundmail]`, `…[newsletter-rundmail]` |
| Obergrenze aus | `test_hoechstens_zehn_je_durchlauf…` (und die Zählung der Vorschläge) |
| Heute ohne Projekthinweis (`zuordnung_aus_vorschlag` entfernt) | `aufgaben-von-selbst.test.mjs` „Verdrahtung“ |
| Zeile auch bei „Alle übernehmen“ | `aufgaben-von-selbst.test.mjs` „Die Zeile nennt Herkunft …“ |

Jeweils zurückgesetzt, danach wieder grün.

## Browser

`scripts/probe_aufgaben_von_selbst_ui.py` (echter Sidecar, Chromium, Europe/Berlin, synthetische Welt: Lena Probe,
Anna Berg, Jonas Keller; Zeit relativ zu „jetzt“ statt Messlatte-Stichtag, damit „neu“ ohne Uhrumstellung gilt). Der
Durchlauf legt genau die Bitte an Lena allein und die eigene Zusage an; Kopie, Rundmail an fünf und Altbestand (40
Tage) bleiben Vorschläge. Konsole leer, 390 px ohne seitliches Scrollen.

| Bild | Was |
|---|---|
| [1 Heute](aufgaben-von-selbst-1-heute.jpg), [390](aufgaben-von-selbst-1-heute-390.jpg) | Eine Zeile „2 Aufgaben aus der Post angelegt. Ansehen · Rückgängig“ |
| [2 Aufgaben](aufgaben-von-selbst-2-aufgaben.jpg), [390](aufgaben-von-selbst-2-aufgaben-390.jpg) | „Von Kingfisher angelegt · aus der Mail von Anna Berg …“, Person, Projekt, Frist |
| [3 Zurückgenommen](aufgaben-von-selbst-3-zurueckgenommen.jpg) | Hinweis „Zurückgenommen. Kingfisher legt diese Aufgabe nicht wieder an. · Rückgängig“ |
| [4 Detail](aufgaben-von-selbst-4-detail.jpg) | Person als Verweis zur Akte, Zeile mit Rückgängig |
| [5 Zur Prüfung](aufgaben-von-selbst-5-pruefen.jpg), [390](aufgaben-von-selbst-5-pruefen-390.jpg) | „Alle 3 übernehmen“, Projekt, Person und Frist vorbefüllt |
| [6 Alle übernommen](aufgaben-von-selbst-6-alle-uebernommen.jpg) | Hinweis „3 Aufgaben übernommen. · Rückgängig“ |
| [7 Schalter](aufgaben-von-selbst-7-schalter.jpg), [390](aufgaben-von-selbst-7-schalter-390.jpg) | „Aufgaben aus Mails selbst anlegen“, an |
| [8 Heute dunkel](aufgaben-von-selbst-8-heute-dunkel.jpg), [9 Aufgaben dunkel](aufgaben-von-selbst-9-aufgaben-dunkel.jpg), [390](aufgaben-von-selbst-9-aufgaben-dunkel-390.jpg) | dunkel |

## Grenzen

* „Eindeutig“ hängt an der Prüfung der Aufgabenerkennung (lokales Modell oder Cloud-Einordnung). Ohne sie entsteht
  nichts von selbst; das ist gewollt.
* Die Person ist die Adresse der Mail (wer bittet, erster fremder Empfänger unter „An“ bei einer Zusage), kein Abgleich
  mit zusammengeführten Personen; die Akte findet sie über die Adresse.
* „Alle übernehmen“ nimmt die sichtbare Seite (bis 25), nicht alle Seiten; ein vorgeschlagenes **neues** Projekt legt
  es nicht an (nur vorhandene).
* Eine selbst angelegte Aufgabe, die schon erledigt ist, nimmt „Rückgängig“ auf Heute nicht mehr mit.
* Kein Bereich (Privat/Arbeit) an der Aufgabe: Das leitet Paket K ab.
