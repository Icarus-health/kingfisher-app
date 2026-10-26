# Paket P: Projekte von selbst (26.10.2026)

Entscheidung des Nutzers ([`66-automatik.md`](../../66-automatik.md)): Ein Projekt, das sich in den Mails **klar**
bildet, legt Kingfisher selbst an und ordnet die Mails zu, mit Rückgängig. Unklare bleiben Frage. Personen werden dem
Projekt zugeordnet. Der Nutzer soll so wenig wie möglich selbst tun. Fachdoku:
[`30-akten.md`, „Projekte von selbst“](../../30-akten.md#projekte-von-selbst-paket-p-migration-25).

## Befund vorher (am Code geprüft)

* „Neue Akte?“ (`akten_vorschlaege.py`): Schwellen wie beschrieben (eine von drei genügt), keine vorhandenen Namen,
  keine Kurz- oder Zahlennamen; Anlegen nur per Klick; „Nein danke“ gemerkt. Die Route gab den besten Vorschlag, das
  Briefing zeigte ihn mit Gewicht 50.
* **Unstimmigkeit:** Doku (`30-akten.md`, Fassung 1.0.27) sagte „höchstens ein Vorschlag am Tag“, der Code zeigt
  „einer nach dem anderen“ (nach einer Entscheidung sofort der nächste). Aufgelöst: Die Doku beschreibt jetzt den Code,
  ein Test prüft „nach „Nein danke“ steht sofort der nächste da“.
* Zuordnung Mail → Projekt: echtes `project_id` nur per Klick oder Annahme; die Absenderregel war nur Vorschlag.
* Personen ↔ Projekte: nichts gespeichert, abgeleitet (Akte „Zusammenhänge“, Personenprofil „Wie verbunden?“).

## Was gebaut ist

| Teil | Wo |
|---|---|
| Klar oder unklar mit Begründung: ≥3 Quellen **und** ≥2 Personen, jüngste ≤30 Tage, kein ähnlicher vorhandener oder erwähnter Name, nicht abgelehnt oder zurückgenommen | `projekt_automatik.einschaetzen`, `aehnlich` |
| Klare Projekte selbst anlegen (wie der Klick), höchstens 3 am Tag; vor dem Briefing und nach jedem Takt der Mailaufnahme, nur mit vollständigen Bezügen | `projekte_anlegen`, `schritt_fuer`; Haken in `akten_vorschlaege_routes.fuer_briefing` und `server.run_mail_intake` |
| Absenderregel ohne Klick: alle früheren Mails des Absenders (≥2) in einem offenen Projekt; nie Rundmail (>5 Empfänger), eigene Mail, mehrere Projekte, frühere Mail ohne Projekt, gesperrte Mail; jede Mail einmal | `absender_ziel`, `absender_schritt` |
| Rückgängig löst nur Kingfishers eigene Zuordnungen und merkt es (abgelehnt plus Sperre); eine Zuordnung durch den Nutzer ersetzt die automatische | `projekt_automatik.zuruecknehmen`, `EpisodeStore.link_project(automatisch=)`, `akten_vorschlaege.zuruecknehmen(quellen=, danach=)` |
| Rückgängig je Mail | `POST /api/v1/projekte/automatik/zuordnung/{id}/zuruecknehmen` |
| Heute: „Neues Projekt: Umbau Praxis, aus 4 Mails mit Anna Keller und Ben Braun · Ansehen · Rückgängig“, mehrere zusammengefasst | `GET /api/v1/projekte/automatik`, `NeueProjekte.tsx`, `projektAutomatik.ts` |
| Akte: „Von Kingfisher angelegt. In 4 Mails seit … · Rückgängig“; „Beteiligte: …“ bzw. „Projekte: …“ unter dem Namen (abgeleitet) | `fuer_akte` + `projekt_automatik.ergaenzen`, `AkteAbschnitte.tsx`, `akteVorschlag.ts` |
| Quelle: „Zugeordnet nach Absender · Ändern · Rückgängig“ | `project_suggestions.for_episode` (`automatisch`), `SourceProject.tsx` |
| Migration 25 der Episoden: Anlagen, Zuordnungen, Sperren, Stand (nur Verweise und Zahlen) | `projekt_automatik.migrate`, `episodes._MIGRATIONS` |

Keine neue Seite, keine Liste: eine Zeile auf Heute, ein Satz in der Akte, eine Zeile an der Quelle. Kein Modell,
nichts Außenwirksames, keine Aussage über Personen.

## Zahlen

| Prüfung | Ergebnis |
|---|---|
| Neue Tests `test_projekt_automatik.py` | 25 bestanden |
| Gezielt (`test_projekt_automatik`, `test_akten_vorschlaege`, `test_project_suggestions`, `test_migrations`, `test_bezuege`, `test_category_diagnostics`, `test_compact_search_index`) | 159 bestanden |
| Volle Backend-Suite | 8058 bestanden, 3 übersprungen, 1 fehlgeschlagen: `test_cloud_access::test_anthropic_import_route_preview_start…` (Hintergrundfaden unter Last noch am Leben; allein 3 von 3 bestanden, ohne Bezug zu diesem Paket) |
| Oberfläche: `tsc --noEmit`, `node --test tests/*.test.mjs`, `vite build` | ohne Fehler; 933 bestanden (neu `neue-projekte.test.mjs`, 7) |
| Browserprobe `scripts/probe_projekte_automatik_ui.py`, hell und dunkel, 1280 und 390 px | `ok`, Konsole leer, kein Überlauf |
| `scripts/probe_neue_akte_ui.py` (Bestand) | `ok` |
| `scripts/probe_seiten_ui.py` hell und dunkel | hell und dunkel `ok`, je 75 Breiten geprüft, 0 nicht in Ordnung |

## Sabotageproben

Jede Zusicherung absichtlich gebrochen (Ausdruck ersetzt), `test_projekt_automatik.py` laufen lassen, zurückgesetzt.
Alle gefangen.

| Probe | Gebrochen | Gefangen von |
|---|---|---|
| S1 | Zurückgenommenes Projekt nicht gemerkt, nicht gesperrt (kommt wieder) | `test_rueckgaengig_entfernt_das_projekt_und_merkt_es` |
| S2 | Zuordnung durch den Nutzer bleibt als automatische stehen (Rückgängig träfe sie) | `test_rueckgaengig_loest_nur_eigene_zuordnungen…`, `test_neue_mail_folgt_dem_absender…`, `test_was_der_nutzer_aendert_gilt…` |
| S3 | Absender mit Mails in zwei Projekten wird zugeordnet | `test_absender_mit_mails_in_zwei_projekten…` |
| S4 | Ähnlicher vorhandener Name zählt nicht | `test_vorhandener_aehnlicher_name_wird_nicht_angelegt`, `test_klar_braucht_alles_zugleich…` |
| S5 | Eine Person reicht für „klar“ | `test_unklares_bleibt_frage…`, `test_klar_braucht_alles_zugleich…`, `test_selbst_angelegt_und_zurueckgenommen…` |
| S6 | Keine Tagesgrenze | `test_hoechstens_drei_am_tag` |
| S7 | Rundmail zählt nicht | `test_nie_bei_rundmail_eigener_mail…` |
| S8 | Selbst angelegt und zurückgenommen sperrt die Automatik nicht | `test_selbst_angelegt_und_zurueckgenommen_wird_nie_automatisch` |
| S9 | Frühere Mail ohne Projekt wird übergangen | `test_absender_mit_mails_in_zwei_projekten_oder_ohne_projekt…` |
| S10 | Gesperrte Mail wird wieder zugeordnet | `test_neue_mail_folgt_dem_absender_sichtbar_und_mit_rueckgaengig` |
| S11 | Stille Projekte (über 30 Tage) gelten als klar | `test_klar_braucht_alles_zugleich…`, `test_unklares_bleibt_frage…` |
| U1 | Heute fasst mehrere Projekte nicht zusammen | `neue-projekte.test.mjs` („mehrere neue Projekte …“) |
| U2 | Bloße Erwähnung gilt als Projekt einer Person | `neue-projekte.test.mjs` („Personen ↔ Projekte …“) |

## Browser

Messlatte-Welt (Stichtag 29.09.2026, Uhr eingefroren) plus synthetische Mails: vier zu „Umbau Praxis“ von Anna Keller
und Ben Braun (klar), drei zu „Projekt Gartenhaus“ nur von Carla Fuchs (unklar), danach eine neue Mail von Anna ohne
Projektnamen. Ergebnis: „Umbau Praxis“ angelegt, Gartenhaus bleibt Frage, Annas neue Mail folgt dem Absender;
„Rückgängig“ an der Quelle löst nur sie, „Rückgängig“ auf Heute entfernt das Projekt mit „Kingfisher legt es nicht
wieder an.“, ein weiterer Takt legt nichts wieder an.

| Bild | Inhalt |
|---|---|
| [Heute 1280](projekte-heute-1280.jpg), [dunkel](projekte-heute-1280-dunkel.jpg), [390](projekte-heute-390.jpg) | Frage zu Gartenhaus, darunter die Zeile „Neues Projekt: …“ |
| [Akte 1280](projekte-akte-1280.jpg), [dunkel](projekte-akte-1280-dunkel.jpg) | „Beteiligte: Anna Keller und Ben Braun“, „Von Kingfisher angelegt. … Rückgängig“ |
| [Quelle](projekte-quelle-absender.jpg), [dunkel](projekte-quelle-absender-dunkel.jpg) | „Zugeordnet nach Absender · Ändern · Rückgängig“ |
| [Person](projekte-person-1280.jpg) | „Projekte: Umbau Praxis“ unter Annas Namen |
| [Nach Rückgängig](projekte-heute-zurueckgenommen.jpg) | Zeile weg, Hinweis mit dem Satz |

## Grenzen

* Neue Projekte gibt es nur aus Erwähnungen der Einordnung (Modell der Themen); ohne sie nur die Absenderregel.
* Die Absenderregel ist bewusst streng: Wer über mehreres schreibt (eine frühere Mail ohne Projekt), wird nie
  automatisch zugeordnet. In der Probe war das zuerst sichtbar (Anna schrieb auch zu Gartenhaus) und ist gewollt.
* „Ähnlich“ ist eine Zeichenregel (enthalten ab 4 Zeichen, ein Zeichen Abstand ab 5); sie hält im Zweifel zurück.
* Der Heute-Hinweis steht drei Tage nach der Anlage; es gibt kein „gesehen“.
* Der Rückweg eines Rückgängig (Projekt wieder anlegen) ist „Akte anlegen“ in der Akte der Erwähnung (dann als eigene
  Entscheidung), kein zweites Rückgängig im Hinweis.
* Während des Laufs war die gemeinsame Platte zeitweise voll; ein erster voller Lauf scheiterte daran. Der gezählte Lauf
  lief mit `--basetemp` und `TMPDIR` im Arbeitsspeicher (`/dev/shm`) und `tmp_path_retention_policy=none`.
* Ein automatisch angelegtes Projekt lässt `area` leer; der Bereich wird aus den Quellen abgeleitet (Paket K).
