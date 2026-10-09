# Einstieg für Entwickler und Claude Code

Einstiegsstand: 9. Oktober 2026. Die gemeinsame CoS-Vorschau liegt in
[Draft #46](https://github.com/Icarus-health/kingfisher-app/pull/46), Branch
`integration/cos-preview-reviewed-20261009`; sie ist noch nicht in `main`
übernommen oder auf dem persönlichen Mac installiert. Vor weiterer Arbeit
den [aktuellen Abnahmestand](64-cos-abnahme-status-2026-10-09.md) und die
[Alltagsabnahme](60-alltagsabnahme.md) lesen. Die dort verlinkten Lieferprotokolle
trennen aktuelle Prüfungen von historischen Ergebnissen und offenen Nachweisen.
Nicht erneut bauen, was bereits in der gemeinsamen Vorschau enthalten ist.

Stand der folgenden Codekarte: 2. Oktober 2026 (Codekarte um Download und Updates, vorher um Start und Einrichtung aus der zweiten Fremdprobe, um Kreis und private Akten ergänzt, M4, dazu Geburtstage, Wiederkehrendes,
Sammelbestätigung, PDF-Anhänge und Cloud-Ordner; um Microsoft 365 (M5), den lesbaren Quellenhinweis und Google ohne
Cloud-Projekt; am 30. September um die Abschnitte langer Quellen; sonst 29. September, einschließlich PR #124). Veröffentlichte Basis: `main`.
Kingfisher ist ein aktiver lokaler Pilot, kein fertig qualifizierter autonomer CoS.
Ziel sind verlässliches Gedächtnis, Mail, Kalender und Aufgaben mit einfacher
Bedienung. Ein belegter Hinweis ist noch keine bestätigte Tatsache.

## Zuerst lesen

1. [Produktvision](00-produktvision.md) und [Beitragsregeln](../CONTRIBUTING.md).
2. [Plan vom Gedächtnis zum Stabschef](26-plan-stabschef.md): Reihenfolge der
   Arbeit und Entscheidungen des Nutzers. Danach die
   [Memory-first-Roadmap](release/MEMORY-FIRST-ROADMAP.md).
3. [Aktueller Abnahmestand und Grenzen](64-cos-abnahme-status-2026-10-09.md),
   anschließend das dort verlinkte neueste Lieferprotokoll. Der
   [Mailaufnahme-Nachweis vom 29. September](runs/mail-intake-20260929/README.md)
   bleibt als historischer Beleg erhalten.
4. [Freigegebener Aufnahmeentwurf](superpowers/specs/2026-09-29-mail-memory-intake-design.md).

Ältere `docs/runs/`, Evaluierungen und Roadmap-Prozentzahlen sind datierte
Nachweise. Sie belegen nicht die heutige Produktqualität. Icarus ist der Name
des vorhandenen Kerns; dessen Paketnamen müssen nicht umbenannt werden.

## Codekarte

| Bereich | Einstieg |
|---|---|
| Aktuelle Oberfläche | `app/kingfisher/src/` (React/TypeScript/Vite) |
| API und Verdrahtung | `sidecar/icarus_memory/server.py` |
| Wiederaufnehmbare Mailaufnahme | `mail_intake.py`, `mail_intake_routes.py`, `connectors/mail.py` im Python-Paket |
| Termine im Gedächtnis (Episoden der Art `event`) | `calendar_memory.py`, `calendar_memory_routes.py`, [Doku](28-termine-im-gedaechtnis.md) |
| Suchindex über alle Rohquellen (FTS5, Wortteile, BM25) und Fusion mit der Wortsuche; Einstellung „Wortteile für die letzten N Jahre“ (zweiter, wortbasierter Index für ältere Quellen) | `source_index.py`, `source_candidates.py`, `suchindex_routes.py`, [Doku](29-suchindex.md); Oberfläche `SuchindexSettings.tsx` (Einstellungen → Gedächtnis) |
| Frage verstehen (strukturierte Anfrage mit Modell der Rolle `frage` oder Rückfall), Auflösen der Sachen, Rückfrage mit allen Bedeutungen, Weg der Frage | `frage.py`, `frage_weg.py`, `bedeutungen.py`, `memory_routing.py`, [Doku](31-frageverstaendnis.md) |
| Lokal oder Cloud über Ollama (Inventar je Modell aus `/api/tags`, 30 s gemerkt, fail closed; Rollenanbieter `ollama-cloud` nur mit Einwilligung, nie für Hintergrund und Einbettung) | `ollama_inventar.py`, `model_roles.py`, `model_roles_routes.py`, `local_model_guard.py`; [Doku](40-messplan-modelle.md#cloud-über-ollama) |
| Speicherbedarf des Orchesters (Tag, Nacht, Festplatte; Ausweichwahl in `empfehle_alle`; freier Platz vom Helfer auf dem Rechner, Platzprüfung vor dem Laden) | `model_recommendation.py` (`orchester_bedarf`), `device_profile.py`, `scripts/report_device.py`, `model_roles_routes.py`; Oberfläche `ModelRecommendation.tsx`, `modelSetup.ts`; [Doku](40-messplan-modelle.md#speicherbedarf-des-orchesters) |
| Kategorien und belegte Hinweise | `sidecar/icarus_memory/memory_categories.py` |
| Beteiligte und Identität (Adresse als Anker, Aliasse, „ich“) | `kontakte.py`, `identitaet.py`, `personen.py`, `personenfrage.py`; Nachweis in `docs/evaluations/messlatte/C3-identitaet.md` |
| Bezüge und Akten je Sache (Person, Organisation, Projekt, Ort, Thema), Fristen | `bezuege.py`, `akten.py`, `fristen.py`, `akten_routes.py`; [Doku](30-akten.md); Oberfläche `AkteAbschnitte.tsx`, `SachenListe.tsx`, `SourceBezuege.tsx` |
| Akten als Markdown-Ordner (nur lesend, für Obsidian; Klartext, aus bis zur Wahl eines Ordners; nichts fließt zurück) | `akten_markdown.py`, `akten_export_routes.py`, `atomic.ordner_tauschen`, Mac-Helfer `scripts/mac_folder_worker.py --role akten`; [Doku](43-akten-als-ordner.md); Oberfläche `AktenOrdnerSettings.tsx` (Einstellungen → Erweitert → Für Techniker); Browserprobe `scripts/probe_akten_ordner_ui.py` |
| Gespräche und Meetings (Transkript-Eingangsordner, Zuordnung zum Termin, Nachfrage ohne Mitschrift) | `transkript_eingang.py`, `transkript_zuordnung.py`, `transkript_routes.py`, `folder_sync.py`, `scripts/mac_folder_worker.py`, `nachbereitung.py`; [Doku](34-gespraeche.md); Oberfläche `TranscriptSettings.tsx`, `CalendarFollowup.tsx` |
| Morgenbriefing (Tageslage), Terminvorbereitung aus Akten, Fristen, Packliste, Wegezeit (Apple Karten, Kartendienst) | `terminvorbereitung.py`, `tagesbriefing.py`, `fristlage.py`, `einpacken.py`, `wegezeit.py`, `tag_routes.py`, `wegezeit_routes.py`; [Doku](33-briefing-und-vorbereitung.md); Oberfläche `TagesLage.tsx` |
| Wetter (Wohnort und Ort des nächsten auswärtigen Termins, Open-Meteo) und eine Meldung aus der Welt im Briefing (Feeds, Abgleich mit den Akten, abbestellbar) | `wetter.py`, `wetter_routes.py`, `welt_feeds.py`, `welt_meldungen.py`, `welt_briefing_routes.py`; [Doku](36-welt-und-wetter.md); Oberfläche `WeltSettings.tsx`, `TagesLage.tsx` |
| Logbuch: anhängende Chronik (`logbuch.sqlite3`, kein Rohtext), drei Zeilen „Seit gestern Abend: …“ im Tages- und Morgenbriefing, Verlauf nach Tagen, Lieferant für Lint-Befunde | `logbuch.py`, `logbuch_routes.py`, Aufrufe in `mail_intake.py`, `ingest.py`, `proposals.py`, `akten_routes.py`, `scheduler.py`; [Doku](44-logbuch.md); Oberfläche `Logbuch.tsx`, `TagesLage.tsx`; Browserprobe `scripts/probe_logbuch_ui.py` |
| Zweites Tor der Satzprüfung: Prüfmodell (Rolle `pruefung`, lokal) urteilt je Satz ja/nein/unklar, fail closed, Zeitbudget 2 s je Satz und 6 s gesamt, Adapter je Modellfamilie; Verlässlichkeit je Satz (gut, einfach, dünn) | `satzpruefung_modell.py`, `verlaesslichkeit.py`, `agent_verdrahtung.pruef_tor`, Schalter in `model_roles_routes.py`; Oberfläche `pruefHinweis.ts`, `SatzAntwort.tsx`, `AntwortZeiten.tsx`; Messlatte `--modell-pruefung`, `skript.py`, Kategorie `inhalt`; Browserprobe `scripts/probe_pruefmodell_ui.py`; [Doku](35-belegte-antworten.md#zweites-tor-prüfmodell) |
| Lage (Ebene 3) und Satzprüfung ohne Modell (Sätze gegen Belege; auch für E3) | `lage.py`, `lage_routes.py`, `satzpruefung.py`; [Doku](32-lage.md); Oberfläche `AkteAbschnitte.tsx` |
| Lint über alle Akten (M2): Widersprüche zwischen Akten, angenommene Aussagen gegen jüngere Quellen, veraltete Lage-Sätze, Waisen, fehlende Querverweise; Befunde in `lint.sqlite3`, Widersprüche nur als Vorschläge; Zählung `lint.zusammenfassung(app)` fürs Logbuch | `lint.py`, `lint_routes.py` (Hintergrund über `akten_routes.nachlauf_anmelden`); [Doku](42-lint.md); Oberfläche `BefundeAnsicht.tsx`, `befunde.ts` (Einstellungen → Gedächtnis); Messlatte `python -m messlatte lint`; Browserprobe `scripts/probe_lint_ui.py` |
| Namensvettern (andere Person gleichen Namens) und Zeiträume im Antwortkontext kennzeichnen, Satzprüfung dazu | `kennzeichnung.py`, `personenfrage.gemeinte_unter_namensvettern`, `time_scope.kalenderzeitraum`; [Doku](39-kennzeichnung.md) |
| Suchen von oben (Akten der genannten Sachen), Überholtes im Kontext kennzeichnen (E2); belegte Antwort in Sätzen mit Satzprüfung und Weg nach unten (E3); zweistufige Auswahl (lange Quellen nur mit den passenden Absätzen im Kontext, Budget, Vermerk „gekürzt“) | `akten_kontext.py`, `satzantwort.py`, `relative_zeit.py`, `absatzauswahl.py`, Hook in `working_memory_answers.py`; [Doku](35-belegte-antworten.md); Oberfläche `SatzAntwort.tsx`; Browserproben `scripts/probe_satzantwort_ui.py`, `scripts/probe_antwortzeit_ui.py` (Antwortzeit: `zeitmessung.py`, `zeiten_routes.py`, `AntwortZeiten.tsx`) |
| Quellenhinweis der belegten Gedächtnisantwort in Alltagssprache („Gespräch vom 1. Oktober 2026, 12:25 Uhr“, Mail mit Betreff und Absender, Termin mit Titel und Tag; Zeit beim Nutzer), Kennungen als Datenfeld `context.quellen`, ein Klick zur Quelle | `quellenhinweis.py`, `datumstext.zeitpunkt_text`, `evidence_answer.render_readable`/`.quellen`, `Agent._quellen_angaben`; Oberfläche `BelegQuellen.tsx`, `quellenWeg.ts`; Vertragstest `scripts/verify_container.py` (`evidence_reply`), `scripts/verify_browser.py`; Browserprobe `scripts/probe_quellen_ui.py`; [Doku](35-belegte-antworten.md#quellenhinweis-der-gedächtnisantwort) |
| Erststart-Assistent (`/willkommen`), leere Startseite, „Kingfisher lernt gerade“ | `einrichtung_routes.py` (Fortschritt in der Einstellung `einrichtung`), `app/kingfisher/src/Einrichtung/` (`schritte.ts`, `lernt.ts`, `Erststart.tsx`), [Doku](09-einrichtung.md) |
| Hintergrund ohne Nacht: Reihenfolge nach Nutzen (morgen, neu, Rückstand neu nach alt), Pause bei Eingabe und Antwort, Drosselung, Modellampel (ein lokaler Aufruf zugleich), Fortschritt mit Schätzung; Autostart als Frage (Mac: Launch Agent über Helfer) | `hintergrund.py` (Einbau in `create_app`, Anschluss an `scheduler.py`, Ampel in `providers.OpenAICompatible`), `autostart.py`, `scripts/mac_autostart.py`; [Doku](46-hintergrund.md); Oberfläche `Einrichtung/KingfisherLernt.tsx`, `Einrichtung/lernt.ts`, `Einrichtung/AutostartSchritt.tsx`, `aktivitaet.ts`; Browserprobe `scripts/probe_hintergrund_ui.py` |
| Rückkanal für Fehler („Stimmt nicht?“ unter jeder Antwort, Liste unter Einstellungen, Export als Messlatte-Fälle; schreibt nichts ins Gedächtnis) | `rueckmeldung.py`, `rueckmeldung_faelle.py`, `rueckmeldung_routes.py`, `messlatte/faelle.py`; [Doku](38-rueckkanal.md); Oberfläche `RueckmeldungAnsicht.tsx`; Browserprobe `scripts/probe_rueckkanal_ui.py` |
| „In die Akte übernehmen“ (Sätze einer gelungenen Antwort werden Vorschläge mit Beleg; Annahme über die Vorschlagskarte; Abschnitt „Angenommen“ in der Akte, als überholt gekennzeichnet, wenn eine jüngere Quelle den Gegenstand anders nennt; schreibt nie selbst Wissen) | `uebernehmen.py`, `uebernehmen_routes.py`, `akten_aussagen.py`; [Doku](45-uebernehmen.md); Oberfläche `UebernehmenKarte.tsx`, `AkteAbschnitte.tsx`; Browserprobe `scripts/probe_uebernehmen_ui.py` |
| Einstellungen in zwei Ebenen (M3): vorne Zugänge, Was Kingfisher darf (fünf Schalter), Kingfisher und du, Sicherung; hinten „Für Techniker“ mit eingeklappten Abschnitten; Quellenvorgaben zum Anklicken; Seite ohne Mindestbreite von 1280 px; Regel „vorne Alltag, hinten Technik“ mit Wortlistentest | `app/kingfisher/src/Einstellungen/` (`gliederung.ts`, `Seite.tsx`, `Zugaenge.tsx`, `Darf.tsx`, `Ich.tsx`, `Technik.tsx`, `CloudSchalter.tsx`), `weltVorgaben.ts`, `sidecar/icarus_memory/welt_vorgaben.py`; Tests `einstellungen-gliederung.test.mjs`, `welt-vorgaben.test.mjs`, `test_welt_vorgaben.py`; Browserprobe `scripts/probe_einstellungen_ui.py`; [Doku](47-einstellungen.md) |
| Lange Quellen in Abschnitten einordnen (Abschnitte von 3.000 bis 6.000 Zeichen mit einer Einheit Überlappung, Sprecherwechsel und Zitatgrenzen, Häppchen je Paket mit Zwischenstand im Speicher, Obergrenze 200.000 Zeichen mit Logbuch-Hinweis, höchstens ein Verweis je Quelle im Kandidatenpool) | `abschnitte.py`, `working_memory_analysis.interpret_abschnitt`, `working_memory_worker.py` (`Zwischenstand`, `ABSCHNITTE_JE_PAKET`), `working_memory_store.py` (`MAX_SOURCE_CHARS`, `search(je_quelle=…)`); [Doku](35-belegte-antworten.md#lange-quellen-in-abschnitten); Tests `test_abschnitte.py`, `test_abschnitte_einordnung.py` |
| Kreis je Person (M4: innerer Kreis, Kollegen, Kontakte) als Vorschlag mit Begründung, Fakt erst nach Klick, nie automatisch geändert; Wirkung im Briefing (Fristen bestätigter Kontakte nicht ungefragt), im Antwortkontext (Feld `kreis`) und im Export; private Akten-Arten (Haushalt, Familie, Gesundheit, Verträge) aus dem Absender, Kündigungs- und Zahlungsfristen als Aufgabenvorschläge mit Beleg | `kreis.py`, `kreis_routes.py`, `akten_arten.py`, `akten_arten_routes.py`, Migration 16 in `episodes.py`, `fristlage.ohne_kontakte`, `akten_kontext.hinweis_kreis`; [Doku](49-kreis-und-privat.md); Oberfläche `KreisKarten.tsx`, `kreis.ts` (Akte, Einstellungen → Kingfisher und du), `TaskSuggestions.tsx`; Messlatte Stufe Privat `messlatte/privat.py`, Szenario `privat`; Browserprobe `scripts/probe_kreis_ui.py` |
| Rest von M4: Geburtstage (Glückwunsch, eigene Angabe, Kalender; nur innerer Kreis) und Wiederkehrendes (Rhythmus und Gegenstand, Kalender-Serien) als Wissenskandidaten, Briefingzeile „Morgen hat … Geburtstag.“; Sammelbestätigung der Kollegen mit Rückfrage und „Liste zurücknehmen“; PDF-Anhänge als eigene Quelle mit „Seite N“, Fristen daraus, gescannt ehrlich „noch nicht gelesen“, OCR nur mit lokalem `glm-ocr`/`deepseek-ocr`; OneDrive, Google Drive, iCloud Drive als Ordner zum Anklicken | `wiederkehrendes.py`, `wiederkehrendes_routes.py`, `anhaenge.py`, `pdf_text_worker.py --seiten`, `document_text.pdf_seiten`, `connectors/mail.message_mit_anhaengen`, `kreis.sammel_bestaetigen`, `ordner_lokal.cloud_orte`, `tagesbriefing._geburtstag_zeile`; Oberfläche `WiederkehrendKarte.tsx`, `wiederkehrendes.ts`, `KreisKarten.tsx`, `OrdnerImBrowser.tsx`; Messlatte `messlatte/pdf.py`, Stufe Privat; Browserprobe `scripts/probe_privat_ui.py`; [Doku](49-kreis-und-privat.md#rest-von-m4-geburtstage-sammelbestätigung-anhänge-cloud-ordner) |
| Einrichtung ohne Fachwissen (Fremdprobe Befunde 6, 7, 8, 10, 11, 19, 25, 26, 27, 31): Kalender wie Mail (Anbieter an der Adresse, Kalender selbst finden, vorher anmelden), Ordner im Browser wählen (Sidecar liest selbst), Sicherung als Download ohne Helfer, „Dieser Rechner“ mit Fähigkeiten statt Modellnamen und „Anderes Modell nehmen“, Ausstattung selbst gemessen, Wegezeit erst wenn sie rechnen kann, Verweise in die Einstellungen, „Beim Anmelden“ nur mit Helfer | `kalender_anmeldung.py`, `ordner_lokal.py` (mit `folder_sync.py`: `…/orte`, `…/lokal`), `sicherung_download.py`, `device_profile.eigene_ausstattung`, `model_recommendation.ausweichwahl`, `wegezeit_routes.was_fehlt`; Oberfläche `KalenderMitAdresse.tsx`, `kalenderWeg.ts`, `OrdnerImBrowser.tsx`, `ordnerWahl.ts`, `RecoverySettings.tsx`, `sicherung.ts`, `Einrichtung/RechnerKarte.tsx`, `Einrichtung/rechner.ts`, `wegezeitSchalter.ts`, `VerweisLink.tsx`, `verweis.ts`; Attrappe `sidecar/tests/caldav_attrappe.py`; Browserprobe `scripts/probe_einrichtung_ui.py`; [Doku](48-fremdprobe.md#stand-je-befund), [Zugänge](47-einstellungen.md#zugänge-ohne-fachwissen-fremdprobe-oktober-2026) |
| Google ohne eigenes Cloud-Projekt (Fremdprobe, Befund 2): Gmail über IMAP mit App-Passwort („App-Passwort nötig“ bei Googles Ablehnung), Workspace-Domain am Mailserver (MX) erkannt (eine Erkennung mit Microsoft 365), Kalender über die geheime iCal-Adresse (Probeabruf mit Zeitgrenze, Adresse im Schlüsselbund), „Mit Google anmelden“ vorne nur, wenn eingerichtet | `providers_mail.py` (`help_label`, `kalender_ical`), `mail_anmeldung.GOOGLE_SATZ`, `anbieter_erkennen.py` (die eine Anbieter-Erkennung), `dns_abfrage.py`, `kalender_abo.py`, `POST /api/v1/integrations/calendar/abo`, `GET …/mail-providers/erkennen` in `server.py`; Oberfläche `GoogleKalenderAdresse.tsx`, `googleWeg.ts`, `useAnbieter.ts`, `kalenderWeg.ts`, `Einrichtung/MailSchritt.tsx`, `Einrichtung/KalenderSchritt.tsx`, `Einstellungen/Zugaenge.tsx`; Attrappen `sidecar/tests/ical_attrappe.py`, `dns_attrappe.py`, `imap_attrappe.py` (`google_ablehnen`); Browserprobe `scripts/probe_google_ui.py`; [Doku](47-einstellungen.md#zugänge-ohne-fachwissen-fremdprobe-oktober-2026) |
| Auf welchem System Kingfisher läuft (Mac-App, Docker im Browser, Linux, Windows) und die Sätze, die davon abhängen („Auf diesem Rechner gespeichert“; was nur ein Mac-Helfer kann, sagt das ehrlich) | `laufumgebung.py` (`GET /api/v1/system`, Feld `system` in `GET /api/v1/setup`); Oberfläche `system.ts` (`fuerSystem`, `nurAufDemMac`), `useSystem.ts`; Tests `test_laufumgebung.py`, `system.test.mjs`; [Fremdprobe, Befund 18](48-fremdprobe.md) |
| Posteingang lesen ohne Warten: Wanduhr je Abruf, Grund in einem Satz („Probe-Post antwortet gerade nicht“), ein schweigendes Postfach wird zwei Minuten gemerkt und sofort gemeldet, im Hintergrund neu versucht; Heute holt den Gruß ohne Post (`post=false`) und die Post danach | `postfach_lage.py` (in `GET /api/v1/messages` und `/dashboard`), `mail_anmeldung.einordnen`, `zeitgrenze.py`; Oberfläche `Messages.tsx`, `App.tsx` (`Morning`); Test `test_postfach_lage.py`; [Fremdprobe, Befunde 14 und 22](48-fremdprobe.md) |
| Seitenbreite aller Seiten (keine Mindestbreite; Stufen 1100/900/700 px), leerer Zustand im Gedächtnis | `app/kingfisher/src/Seitenbreite.css` (zuletzt geladen in `main.tsx`), `GedaechtnisLeer.tsx`; Test `seitenbreite.test.mjs`; Browserprobe `scripts/probe_seiten_ui.py` (alle Seiten bei 390, 768, 1280 px und die Befunde der Fremdprobe); [Doku](16-gestaltung.md), [Fremdprobe](48-fremdprobe.md) |
| Microsoft 365 (M5, erster Teil): „Mit Microsoft anmelden“ mit Gerätecode (öffentlicher Client, nur lesende delegierte Rechte, Refresh-Token im Schlüsselspeicher), Erkennen an der Adresse über die eine Anbieter-Erkennung (DNS), Outlook-Post über die Delta-Abfrage durch dieselbe Aufnahme wie IMAP, Kalender über `calendarView`, Teams-Mitschriften (VTT) wie Dateien aus dem Transkript-Ordner mit Sprecher und Uhrzeit | `microsoft_anmeldung.py`, `microsoft_graph.py`, `microsoft_routes.py`, Erkennen in `anbieter_erkennen.py` mit `dns_abfrage.py` (`GET …/mail-providers/erkennen`), Verzweigungen in `server._configured_mail`/`_configured_calendar`; Oberfläche `MicrosoftAnmeldungKarte.tsx`, `microsoftAnmeldung.ts`, `MicrosoftZugang.tsx`, `MicrosoftVorbereiten.tsx`, `Einrichtung/MailSchritt.tsx` (über `useAnbieter.ts`); Attrappen `sidecar/tests/graph_attrappe.py`, `dns_attrappe.py`, Netzsperre `tests/microsoft_hilfen.py`; Browserprobe `scripts/probe_microsoft_ui.py`; [Doku](50-microsoft-365.md) |
| Erste Stunde ohne Widerspruch (Fremdprobe 2, Befunde 10 bis 22, 26 bis 29): Zähler und Uhr auf Heute, Tastenhinweis je Gerät, „Gestützt auf“ oder „ohne Beleg“ unter jeder Antwort, Meldung mit Satz, Hintergrundfehler in Alltagssprache, eine Aussage je Postfach an allen Stellen, Rückmeldung nach „Aktualisieren“, Verarbeitung in Alltagssprache, Kreis in jeder Personenakte, bestätigter Geburtstag in Kalender und Akte, Kontakte nur mit Beteiligung, widerspruchsfreie Angaben unter „Für Techniker“ | `mail_stand.py` (`GET /api/v1/mail/stand`, `stand` in `…/mail/intake`, `mail_stand` und `kosten_modell` in `…/schedule`), `logbuch.fehler_satz`, `EpisodeStore.neue_von_aussen`, `episodes.ist_eigene_quelle`, `personen.ist_kontakt`, `wiederkehrendes.bestaetigter_geburtstag`/`kalender_eintraege`, `GET /api/v1/geburtstag`, `kreis.stand` (`ohne_vorschlag`), `device_profile.mit_eigener_messung`; Oberfläche `heute.ts`, `beleg.ts`, `verarbeitung.ts`, `technik.ts`, `system.ts` (`tastenHinweis`, `ausstattungSatz`), `PostfachStand.tsx`, `KreisKarten.tsx` (`GeburtstagKarte`); Tests `test_fremdprobe2_alltag.py`, `heute`/`beleg`/`verarbeitung`/`technik.test.mjs`; Browserprobe `scripts/probe_fremdprobe2_alltag_ui.py`; [Doku](51-fremdprobe-2.md#8-stand-je-befund-alltag) |
| Start und Einrichtung ohne Nachschlagen (Fremdprobe 2, Befunde 1 bis 9, 23 bis 25, 30): Doppelklick-Starter (Docker Desktop finden und starten, Schlüssel ohne `openssl`, Ollama-Hinweis); Mailserver einer eigenen Domain selbst finden (SRV, Autoconfig, MX gegen den Katalog), nur Passwort; Kalender per `_caldavs._tcp` oder `/.well-known/caldav` auf dem Mailserver; Fehler am Knopf; Modelle im Hintergrund laden (ein Lauf im Sidecar, Fortschritt auf Heute, ehrliche Antwort solange); Briefing in der eingestellten Zeitzone; Ordner per Auswahl | `Kingfisher starten.command`, `scripts/kingfisher_starten.py`, `server_finden.py`, `dns_abfrage.py` (SRV), `anbieter_erkennen.py`, `kalender_anmeldung.eigener_kalender`, `mail_anmeldung.anbieter_name`, `model_pull.PullManager.starte_reihe`, `POST/GET /api/v1/models/laden` in `model_roles_routes.py`, `agent_verdrahtung.modell_laedt_satz`, `ordner_lokal.unterordner`; Oberfläche `PostfachMitAdresse.tsx`, `postfachWeg.ts`, `adresseEntwurf.ts`, `useImBlick.ts`, `KalenderMitAdresse.tsx`, `kalenderWeg.ts`, `Einrichtung/RechnerKarte.tsx`, `Einrichtung/rechner.ts`, `Einrichtung/lernt.ts`, `OrdnerImBrowser.tsx`; Attrappen `sidecar/tests/autoconfig_attrappe.py`, `dns_attrappe.py` (SRV); Browserprobe `scripts/probe_fremdprobe2_einrichtung_ui.py`; [Doku](51-fremdprobe-2.md#8-stand-je-befund), [Zugänge](47-einstellungen.md#eigene-domain-ohne-servereingabe-fremdprobe-2-oktober-2026) |
| Mailaufnahme ohne stilles Scheitern (Fremdprobe 3, Befunde 1, 2, 3, 8, 9, 12, 13, 15): Grund je gescheiterter Mail (Migration 17), Satz und „Erneut versuchen“ in „Kingfisher lernt gerade“, Sortieren nach der Einrichtung vorgemerkt, Abruf alle 30 Minuten, Herkunftskennungen nur für Techniker, kein Zähler als Priorität | `mail_intake_grund.py`, `mail_intake.py`, `mail_stand.py` (`gescheitert`), `memory_routes.py` (`vormerken`), `config._abstand`, `scheduler.SICHERUNG_ABSTAND`; Oberfläche `Einrichtung/MailErneut.tsx`, `Einrichtung/lernt.ts`, `Einrichtung/fertig.ts`, `HerkunftAnzeige.tsx`, `verarbeitung.ts`; Attrappe `sidecar/tests/imap_attrappe.py` (`probe_postfach`); Tests `test_mailaufnahme_ende_zu_ende.py`, `test_mail_intake_grund.py`, `test_fremdprobe3_hintergrund.py`; Browserprobe `scripts/probe_fremdprobe3_ui.py`; [Doku](52-fremdprobe-3.md#stand-je-befund-1-2-3-8-9-12-13-15) |
| Retrieval und Antwortkontext | `sidecar/icarus_memory/agent.py` |
| Aufnahmeoberfläche | `app/kingfisher/src/MailIntake.tsx`, `SourceCategories.tsx` |
| Mac-Fenster (einzige Hülle): ladbare App `Kingfisher.dmg` (erster Start ohne Terminal, Update nur über die Brücke `kingfisher`) und Fenster für die Arbeitskopie | `macos/App/` (reine Logik in `macos/App/Logic/`), `macos/Shared/`, `macos/build_dmg.sh`, `.github/workflows/mac-app.yml`, `macos/KingfisherApp.swift`, `scripts/build_mac_window.py`; Tests `macos/test_mac_app.py`, `macos/tests/main.swift`; [Anleitung](../macos/README.md), [ADR 0008](adr/0008-docker-und-mac-fenster.md#nachtrag-download-als-dmg) |
| Auslieferung | `Dockerfile`, `compose.yaml`, `make start` |
| Download und Updates: Fassung (`VERSION`, `KINGFISHER_FASSUNG`), tägliche Prüfung von `latest.json` (eine GET-Anfrage ohne Kekse und Kennung, Manifest streng geprüft, im Faden des Zeitplans), Angebot auf Heute mit Brücke zur Mac-App, Fassung unter „Kingfisher und du“, `make aktualisieren`, Release-Workflow mit Bild, DMG und Download-Seite über Pages | `fassung.py`, `fassung_routes.py`, `scheduler.nebenbei_setzen`, `deploy/compose.app.yaml`, `scripts/kingfisher_aktualisieren.py`, `scripts/release_seite.py`, `.github/workflows/release.yml`, `site/index.html`, `docs/fassungen/`; Oberfläche `Fassung.tsx`, `fassungsAngebot.ts`; Tests `test_fassung.py`, `test_compose_vertrag.py`, `test_kingfisher_aktualisieren.py`, `test_release_seite.py`, `fassung.test.mjs`; Browserproben `scripts/probe_fassung_ui.py`, `scripts/probe_download_seite.py`; [Doku](53-download-und-updates.md) |
| Designvertrag | `design-source/`, `scripts/check_asset_manifest.py` |
| Tests | `sidecar/tests/`, `scripts/test_*.py`, `app/kingfisher/tests/` |
| Messlatte (Gedächtnisqualität; `--lange-quellen` für Mails und Transkripte in Alltagslänge, Kennzahlen „Kontext abgeschnitten“ und „ohne tragende Textstelle“) | `messlatte/` (`python -m messlatte lauf --welt messlatte/welt`), Protokolle in `docs/evaluations/messlatte/` |

`entwurf/`, `entwurf2/` und `entwurf3/` sind erhaltene Vorarbeiten, nicht der
Einstieg für die aktuelle React-UI. Nicht pauschal löschen oder parallel neu
bauen. Es gibt genau eine Oberfläche (`app/kingfisher/`) und einen
Auslieferungsweg (Docker, auf dem Mac mit nativem Fenster,
[ADR 0008](adr/0008-docker-und-mac-fenster.md)). Tauri, PyInstaller-Bündel und
die frühere Oberfläche `app/src/` sind entfernt; ohne `ICARUS_UI_DIR` liefert
der Sidecar die gebaute React-UI aus `app/dist` (`npm run build`), sonst nur die
API.

## Lokal prüfen

Python 3.12 ist eine getestete Entwicklungsbasis; CI prüft zusätzlich 3.10.
Für die TypeScript-Tests Node 22.18+ verwenden. Aus einem frischen Checkout:

```sh
make sidecar-dev
.venv/bin/python -m pytest sidecar/tests -q
cd app/kingfisher
npm ci
node --experimental-strip-types --test tests/*.test.mjs
npm run build
cd ../..
python3 scripts/check_asset_manifest.py
```

**Schnellprüfung vor dem Push.** `scripts/install_hooks.sh` legt im Hook-Verzeichnis des Repositorys (es gilt für
alle Worktrees, eingestellt wird nichts global) einen `pre-push`-Hook an. Er prüft in wenigen Sekunden vier Dinge
und bricht den Push mit einem Satz ab, wenn eines fehlschlägt:

1. die JavaScript-Syntax (`node --check app/src/main.js`, solange die Datei existiert),
2. die Python-Syntax (`python -m compileall -q sidecar/icarus_memory messlatte`),
3. Zeichenketten mit falschen deutschen Anführungszeichen (`scripts/pruefe_anfuehrungszeichen.py`; die Regel aus
   `CLAUDE.md`: immer „…“, nie mit ASCII-Anführungszeichen geschlossen),
4. die statischen Sperren, also die Tests, die Kopien einer Definition im Code verbieten.

Die Tests des Sidecars gehören nicht dazu: Sie brauchen auch parallel rund 8 Minuten. **Die volle Prüfung ist
`scripts/ci_lokal.sh`** (dieselben Jobs wie die CI, in UTC). Ein schon vorhandener fremder Hook wird nie
überschrieben (`--ersetzen` sichert ihn nach `pre-push.alt`, `--entfernen` nimmt den angelegten wieder weg); im
Notfall überspringt `git push --no-verify` die Prüfung.

Den benutzbaren Container mit `make start` starten (Docker Compose erforderlich,
Port 8890). Auf einem Rechner mit vorhandener Kingfisher-Installation zuerst
deren Container/Volumes prüfen: Der Compose-Projektname ist fest vorgegeben;
ein zweiter Checkout schafft keine getrennte Dateninstanz. Für Review und
Experimente ausdrücklich getrennte Volumes und Ports verwenden.

Am 29. September bestanden 2.630 Backendtests, anschließend 111 gezielte Tests
nach letzten Integrationskorrekturen, 30 UI-Tests, Build und Assetprüfung.
GitHub Actions startete bei PR #124 wegen Billing-/Spending-Limit nicht. Das
ist kein grüner CI-Nachweis. Keine wiederholten Neustarts ohne behobene Ursache;
neue fachliche Testfehler nicht pauschal als Billingproblem abtun.

## Was als Nächstes sinnvoll ist

Die Etappen A bis F aus [`26-plan-stabschef.md`](26-plan-stabschef.md) sind
gebaut und ohne Modell gemessen; der Stand steht dort in „Stand der Etappen“.
Was fehlt, lässt sich nur auf dem Zielgerät klären:

1. **Modelle messen.** Drei Läufe, ein Befehl je Lauf, und woran man den Gewinner
   erkennt: [`40-messplan-modelle.md`](40-messplan-modelle.md). Kurz: Auf dem Mac mit Ollama die Messlatte mit Modell laufen
   lassen (`python -m messlatte lauf --welt messlatte/welt --modell ollama:NAME
   --modell-hintergrund ollama:NAME --modell-frage ollama:NAME`) und danach
   `python -m messlatte lokal` mit eigenen Fragen. Erst dann entscheiden, welches
   Modell welche Rolle bekommt; die Namen im Katalog (`model_recommendation.py`)
   gegen die Ollama-Bibliothek prüfen. Danach die Antwortzeit ansehen (Einstellungen, Lokale KI, oder der
   Messlatte-Bericht) und entscheiden: Sätze an oder aus; der Schalter steht dort, siehe
   [Antwortzeit](35-belegte-antworten.md#antwortzeit).
2. **Mac-Helfer prüfen.** Kalender (`CalendarReader`), Wegezeit über Apple Karten
   und die Transkriptwahl sind in Swift geschrieben und hier nicht getestet.
3. **Eine Woche Alltag.** Fertig heißt für F: keine übersehene oder falsche
   Information. Was dabei auffällt, wird zuerst als Fall in die Messlatte
   aufgenommen und dann behoben. Der Weg dafür steht: „Stimmt nicht?“ unter der
   Antwort, dann `python -m messlatte faelle --aus <Datenordner>/rueckmeldungen.sqlite3`
   und `python -m messlatte lokal --fragen rueckmeldungen-faelle.json`
   ([`38-rueckkanal.md`](38-rueckkanal.md); die Datei enthält Frage- und
   Antworttexte und bleibt auf dem Rechner).

Keine Behauptung eines fehlerfreien Gedächtnisses: Die Zahlen gelten für die
synthetische Welt der Messlatte.

## Zusammenarbeit und Daten

Ein Arbeitspaket pro Branch/PR, getesteten Commit und offene Grenzen nennen.
Vor Änderungen vorhandene Tests, Entwurf und jüngste Run-Dokumentation lesen.
Widersprüche zwischen Altanleitungen und aktuellem Code sichtbar auflösen.
Keine Testwiederholungen ohne Anlass und keine automatischen Check-in-Schleifen.

Repositoryzugang gibt Zugriff auf Code und eingecheckte Historie. Er benötigt
keine privaten `.env`-Dateien, OAuth-Dateien, Tokens, Docker-Volumes, Mailtexte
oder Sicherungen. Diese nicht weitergeben und nicht in Cloud-Agenten laden.
Einen privaten Repositoryzugang für den Reviewer nutzen; nicht öffentlich
schalten. Diese Einstiegskontrolle ersetzt keinen vollständigen Secrets-Audit
der Git-Historie.

Laufzeitmigrationen benötigen vorherige Sicherung. Schema 17 ist aktuell (Grund gescheiterter Mails; davor 16, Kreis und private Akten-Arten);
älteren Code nicht gegen das migrierte Datenvolume starten. Rückkehr nur über
passenden Snapshot auf einer getrennten Instanz. Quellenentzug, menschliche
Korrekturen, Identitätstrennung und Aktionsfreigaben müssen erhalten bleiben.
