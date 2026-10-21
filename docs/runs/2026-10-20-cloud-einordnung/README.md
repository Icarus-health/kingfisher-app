# Paket A: Neue Mails in der Cloud einordnen (Anthropic, eigene Einwilligung)

Stand 20.10.2026, Branch `feat/cloud-sprachschritte-20261020` auf `main` = 1.0.26. Geprüft wurde
ausschließlich mit synthetischen Daten und Attrappen (Ollama-Attrappe, Claude API als
`httpx.MockTransport`, Schlüsselspeicher als Datei); kein echtes Postfach, kein echter Schlüssel,
kein bezahlter Modellaufruf. VERSION unverändert.

## Was gebaut wurde

* `sidecar/icarus_memory/model_roles.py`: `RolleSpec.cloud_anbieter`; die Rolle `hintergrund` kennt
  eine Cloud nur für Anthropic, ihr Anbieter (`provider("hintergrund")`) bleibt lokal oder None
  (`anbieter_nur_lokal`); `Rollen.hintergrund_cloud_wahl()`; `TAGESBUDGET = 300`.
* Neu `sidecar/icarus_memory/hintergrund_cloud.py`: Anbieter nur mit Einwilligung und vorbereitetem
  Zugang, `Einordnung` mit eingegrenztem Anbieter je Quelle (`ExplicitSourcePolicy`), Freigabe bei
  jedem Aufruf (Einwilligung, Zugangsfassung, Zeitplan, Pause, nur Mails, Vorfilter, Fassung),
  Tagesbudget in `hintergrund_cloud.sqlite`, `stand(app)`.
* `source_processing_policy.ScopedProvider` (vorher `cloud_memory._ScopedProvider`).
* `working_memory_worker.run`, `memory_categories.Categories.run`, `task_detection.TaskDetector.run`:
  `quellenfilter`, Quellen ohne Policy bleiben beim Cloudanbieter unberührt; Kennung `anthropic:MODELL`
  beim Speichern; `memory_analysis.interpret` und `task_review.review_tasks` mit `policy`/`episode`.
* `server._wire_scheduler`: `run_working_memory` und `run_task_detection` mit Cloudzweig (nur Mails,
  Rest lokal oder wartend), `with_model` auch bei aktiver Cloud-Einordnung; Vormerk-Sperren über
  `hintergrund_cloud.einordnung_moeglich`.
* Routen: `put_role` (nur Anthropic, Zugang nötig, lokales Modell bleibt, vorbereitetes Modell statt
  Vorgabe), `rollen_zustand` (`cloud_anbieter`, `cloud_einordnung`), `cloud_access_routes` (Hintergrund
  behält sein lokales Modell beim Zurücksetzen), `memory_routes.automation_status` (`cloud_aktiv`),
  `hintergrund.stand`, `mail_intake_routes.analysis_active`.
* Oberfläche: `Einstellungen/CloudEinordnungSchalter.tsx`, `cloudEinordnung.ts`, `gliederung.ts`
  (`SCHALTER.cloud_einordnung`), `ModelRolesExpert.tsx` (Anbieter je Rolle), Texte in
  `MemoryAutomationSettings.tsx`, `MailIntake.tsx`, `CloudMemory.tsx`, Typen in `api.ts`.

## Prüfungen

| Prüfung | Vorher | Nachher |
|---|---|---|
| Gezielte Tests (`test_hintergrund_cloud.py` neu, 16 Fälle; angepasste Fälle in `test_model_roles.py`, `test_model_roles_routes.py`, `test_cloud_access.py`, `test_model_roles_cloud_ollama.py`) | 5 rot, Sammeln von `test_hintergrund_cloud.py` scheitert (Modul fehlt) | alle grün |
| Volle Backend-Suite (`pytest sidecar/tests -n auto`, Python 3.13) | – | **7752 bestanden, 0 fehlgeschlagen, 3 übersprungen**, 26 Unterfälle, 31 min |
| UI-Tests (`npm test`, node --test) | 763/764 (neue Prüfung rot: Modul ohne `.ts`) | **767 bestanden, 0 fehlgeschlagen** |
| `npx tsc --noEmit` | – | ohne Fehler |
| `npm run build` | – | gebaut (bestehende Warnung zur Chunk-Größe) |
| Browserprobe `scripts/probe_cloud_einordnung_ui.py` (Chromium, 1280 und 390 px) | – | ok, Konsole leer, 7 Bilder |

Unverändert grün geblieben (laut Bauplan): `test_hintergrund_lokal.py`, `test_pruefbefunde_0929.py`,
`test_cloud_memory.py`, `test_working_memory_analysis.py`, `test_pruefrolle.py`, `test_local_model_guard.py`,
`test_model_roles_cloud_routes.py` (in der vollen Suite enthalten).

Die neuen Fälle in `test_hintergrund_cloud.py`: ohne Einwilligung kein Anbieter, Einwilligung der
Antwort gilt nicht, andere Anbieter 422; Zugang nötig; Schlüsselwechsel löscht die Einwilligung und
lässt das lokale Modell; eine Mail geht vollständig durch Einordnung, Themen, Bitten und Prüfung (vier
Aufrufe, voller Text, Kennung `anthropic:claude-synthetic`, ein Dokument wartet); Werbemail und Dokument
gehen nicht; Pause kein Aufruf; Widerruf mitten im Lauf stoppt jeden weiteren Aufruf; Policy prüft
Quelle, Zeitplan und Rücknahme bei jedem Aufruf; Aufruf 301 wird abgewiesen, Zähler bleibt bei 300,
der Lauf nennt den Grund, am nächsten Tag geht es weiter; Logbuch einmal je Tag; Verdichtung, Lage und
Mailhilfe (503) bekommen den Cloud-Anbieter nie; mit lokalem Modell: Mails in die Cloud, Dokumente lokal;
Automatik `cloud_aktiv` und Einschalten ohne lokales Modell; vorbereitetes Modell statt Vorgabe.

## Sabotageproben

Je Probe wurde die Zusicherung absichtlich gebrochen, die gezielten Dateien liefen
(`test_hintergrund_cloud.py`, `test_model_roles.py`, `test_model_roles_routes.py`, `test_cloud_access.py`,
`test_model_roles_cloud_ollama.py`, `test_hintergrund_lokal.py`), danach wurde die Änderung zurückgenommen.

| Probe | Gebrochene Zusicherung | Rot | Lauf |
|---|---|---|---|
| S1 | `Einordnung.freigegeben` gibt immer True | `test_eingegrenzt_prueft_quelle_und_fassung_bei_jedem_aufruf`, `test_widerruf_mitten_im_lauf_stoppt_jeden_weiteren_aufruf` | 2 rot, 102 grün |
| S2 | Budgetzähler wird nie erhöht | `test_tagesbudget_weist_den_aufruf_301_ab_und_zaehlt_am_naechsten_tag_neu`, `test_das_budget_wird_einmal_je_tag_im_logbuch_vermerkt` | 2 rot, 102 grün |
| S3 | Policy im Worker weggelassen (`policy=None` an `interpret_abschnitt`) | `test_eine_neue_mail_geht_vollstaendig_durch_einordnung_themen_und_zusagen`, `test_ein_lokales_modell_bearbeitet_andere_quellen_und_mails_gehen_in_die_cloud`, `test_bei_pause_kein_aufruf` | 3 rot, 101 grün |
| S4 | Dokument statt Mail durchgelassen (`ist_mail` immer True) | `test_eine_neue_mail…`, `test_werbemail_und_dokument_gehen_nicht_in_die_cloud`, `test_eingegrenzt…`, `test_ein_lokales_modell…`, `test_anthropic_import_route_preview_start_and_key_revocation_are_source_scoped` | 5 rot, 99 grün |
| S5 | Verdichtung an den Cloud-Anbieter gehängt (`hintergrund_anbieter` liefert ihn) | `test_verdichtung_lage_und_mailhilfe_bekommen_den_cloud_anbieter_nie`, `test_einschalten_braucht_den_vorbereiteten_zugang` | 2 rot, 102 grün |
| S6 | Einwilligung der Antwort gilt für den Hintergrund | `test_ohne_einwilligung_kein_anbieter_und_fremde_einwilligung_gilt_nicht`, `test_hintergrund_cloudwahl_wird_nie_zum_anbieter_der_rolle` | 2 rot, 102 grün |
| S7 | Anbieterliste der Rolle in `einwilligung_gueltig` nicht geprüft | `test_hintergrund_cloudwahl_wird_nie_zum_anbieter_der_rolle` | 1 rot, 103 grün |
| S8 | Einschalten ohne vorbereiteten Zugang erlaubt | `test_einschalten_braucht_den_vorbereiteten_zugang`, `test_hintergrund_braucht_den_vorbereiteten_claude_zugang_nicht_nur_einen_schluessel` | 2 rot, 102 grün |
| S9 | Freigabe ohne freigegebenen Zeitplan (`plan.enabled`/`with_model` ignoriert) | `test_eingegrenzt_prueft_quelle_und_fassung_bei_jedem_aufruf` | 1 rot, 103 grün |
| S10 | Kennung im Bestand nicht `anthropic:modell` | `test_eine_neue_mail_geht_vollstaendig_durch_einordnung_themen_und_zusagen` | 1 rot, 103 grün |
| S11 | Pause in der Freigabe ignoriert | zuerst **0 rot** (der Lauf stoppt schon über `permitted()`); Test `test_eingegrenzt…` um die Pause erweitert, danach `test_eingegrenzt…`, `test_tagesbudget…` | 2 rot, 17 grün (nur `test_hintergrund_cloud.py`) |
| S12 | Vorfilter in der Freigabe ignoriert | zuerst **0 rot** (`eingegrenzt` sortiert vorher aus); Test `test_eingegrenzt…` um einen gesperrten Absender erweitert, danach `test_eingegrenzt…`, `test_tagesbudget…` | 2 rot, 17 grün (nur `test_hintergrund_cloud.py`) |

Ergebnis: zwölf Proben, jede nach der Nachbesserung von zwei Tests gefangen. S11 und S12 zeigten, dass die innere Freigabe (`freigegeben`) für Pause und Vorfilter nur über die äußeren Schichten geprüft war; `test_eingegrenzt_prueft_quelle_und_fassung_bei_jedem_aufruf` prüft beide jetzt direkt an der Policy. Nach jeder Probe war der Quellbaum unverändert (`git status`). Nebenbefund beim Datumswechsel auf den 21.10.: der Fall „am nächsten Tag geht es weiter“ setzte den Folgetag fest auf den 21.10. und fiel nach Mitternacht UTC um; er rechnet ihn jetzt aus `heute()`.

## Browserprobe

Bilder unter dem Probeverzeichnis (`cloud-einordnung-aus-1280.png`, `-ohne-zugang-1280.png`,
`-frage-1280.png`, `-an-1280.png`, `-wieder-aus-1280.png`, `-frage-390.png`, `-an-390.png`).
Geprüft: Schalter aus, Satz zum Rechnerverlassen, kein Fachwort vorne; ohne Zugang der Satz mit
Verweis `#ki`, nichts gespeichert; mit Zugang (Attrappe über `PUT /api/v1/models/cloud-access/anthropic`)
Knopf erst nach angehaktem Satz des Sidecars („… 300 Aufrufe am Tag … Ich willige ein.“); Statuszeile
„Neue Mails werden über Anthropic (claude-synthetic) eingeordnet. Heute 0 von 300 Aufrufen.“; die Rolle
trägt die Einwilligung, ihr Anbieter bleibt lokal; nach Neuladen weiter an; aus mit einem Klick
(„Einordnen läuft wieder nur auf diesem Rechner.“); bei 390 px kein Überlauf. Konsole ohne Fehler.

## Offen und Grenzen

* Kein echter Anbieteraufruf: Die Claude API war eine Attrappe. Format der Anfragen entspricht dem
  bestehenden Mailpaket (`cloud_memory.py`), das am 19.10. mit echtem Zugang lief.
* `hintergrund_cloud.anbieter(app)` baut den Anbieter je Aufruf neu und liest dafür den Schlüsselspeicher
  (nur bei gesetzter Einwilligung). Auf dem Mac ist jeder Zugriff ein `security`-Aufruf; das Polling von
  `GET /api/v1/hintergrund` macht dann zwei Aufrufe je Abfrage. Falls das stört: kurzes Merken je Zugangsfassung.
* Die drei Vormerk-Sperren (Terminnotiz, Gesprächsquelle, Dokument) nehmen die Cloud-Einordnung nur für
  Mails als Grund (`einordnung_moeglich(app, episode)`): Diese Quellen sind nie Mails und würden sonst als
  „läuft“ vorgemerkt, ohne je bearbeitet zu werden.
* Das Tagesbudget zählt nach UTC-Kalendertag.
* Mit aktiver Cloud-Einordnung und lokalem Modell gehen Mails nur in die Cloud; ist das Budget
  aufgebraucht, warten sie bis zum nächsten Tag, auch wenn ein lokales Modell da wäre.
* Der Satz zur Einwilligung in der Oberfläche kommt vom Sidecar; der Satz des Schalters selbst sagt
  „Anthropic (Claude)“ ohne „API“, weil „API“ vorne als Fachwort gilt (`FACHWOERTER`).
