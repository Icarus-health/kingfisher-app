# Unabhängiges Backend-Review Mail → Kalender, 2026-10-09

Read-only Prüfung des laufenden Patches gegen `main 9944ab3`. Keine Produktänderung, kein Git-Commit, kein Docker, kein echter Anbieter, Modell, Netzwerk oder private Quelle. Synthetische HTTP-/Store-Gegenproben verwenden die vorhandenen Testfixtures und deren isolierende `tests.conftest`.

## Ergebnis

**Noch keine Freigabe:** ein Quellenentzugsfehler und zwei begrenzte Funktionslücken wurden konkret reproduziert. Normale Kalenderregressionen in den fokussierten Tests wurden nicht beobachtet.

### P1 — Ausführungswiederholung zeigt entzogene Mail-Vorschau erneut

`sidecar/icarus_memory/calendar_actions.py:315–320`: `_claim` meldet bei `done` „nicht erneut beansprucht“, und `execute` gibt sofort `_public(record)` zurück. Dieser Weg liegt vor `_mail_guard`.

Echter synthetischer HTTP-Weg: Mail im EpisodeStore erinnern → öffnen → lokalen Entwurf erstellen → Angaben prüfen → Kalender-Vorschau → ausdrücklich ausführen → Original ignorieren. Danach ist `GET /api/v1/calendar-actions/drafts/{id}` korrekt 409. Derselbe `POST .../execute` mit gespeichertem Stand liefert dagegen **200, status=done und die alten aus der Mail übernommenen Daten**. Provider-Schreibzahl bleibt 1; der Fehler ist die erneute ungeprüfte Anzeige, kein doppeltes Anlegen. Ein fehlender Guard nach Neustart hat denselben frühen Rückgabeweg.

Korrekturrichtung: Jede öffentliche Rückgabe eines mailgebundenen Datensatzes braucht die aktuelle Quellen-/Standprüfung, auch ein bereits abgeschlossener idempotenter Aufruf. Der abgeschlossene Journalstatus und sein Doppelwirkungsschutz dürfen bei einem reinen Anzeigeverbot erhalten bleiben.

### P2 — Erneute Kalenderfreigabe macht unveränderte Mailvorbereitung dauerhaft unbenutzbar

`calendar_actions.py:204–228` und `321–323`: Die stabile ID enthält die Mailvorbereitung, aber nicht den Kalenderzugangsstand. Bei einer erneuten OAuth-Freigabe gibt `INSERT OR IGNORE` den alten, an die vorige Freigabe gebundenen Datensatz zurück.

Reproduktion: Mailvorbereitung mit `grant-one` anlegen; Schlüssel auf `grant-two` ändern; unveränderte Vorbereitung erneut übergeben. Die ID bleibt gleich, Execute scheitert mit „Kalenderzugang wurde geändert“. Nach `CalendarActions`-Neustart liefert jede erneute Übergabe denselben `blocked`-Datensatz; Execute scheitert weiter. Keine Provideraktion wurde vorgenommen.

Korrekturrichtung: Einen tatsächlich noch nicht extern ausgeführten Entwurf nach erneuter Rechteprüfung wieder benutzbar machen, ohne bei `done`/`uncertain`/laufenden Aktionen eine zweite Kalenderanlage zu ermöglichen. Bloß die Freigabe in die Provider-ID aufzunehmen wäre kein vollständiger Schutz: Ein bereits angelegter oder unklarer Termin könnte dann erneut angelegt werden. Tests sollten erneute Freigabe vor Ausführung, nach `done` und bei unklarem Ausgang unterscheiden.

### P2 — Bereits bekannte Gegenangaben werden beim Zeitvorschlag übergangen

`sidecar/icarus_memory/mail_calendar_preparations.py:63–74`: Absage-/Alternativprüfung liest nur die Texte, nicht die Betreffzeilen. Die Zeit-Eindeutigkeit wird nur in der geöffneten Mail geprüft.

Zwei synthetische HTTP-Belege:

1. Betreff **„Absage: Treffen“**, Text mit `2026-10-12T10:00:00+02:00 bis 2026-10-12T11:00:00+02:00`: Beide Zeitfelder werden übernommen; es erscheint keine gezielte Absagewarnung.
2. Geöffnete ältere Einladung mit 10–11 Uhr; bereits erinnerte jüngere direkte Threadantwort mit 12–13 Uhr, beide als vollständige ISO-Zeitintervalle: Kontext enthält beide Quellen, vorgeschlagen werden dennoch 10–11 Uhr. Einzige Warnung ist der generische Hinweis auf einen begrenzten Verlauf.

Die explizite menschliche Prüfung verhindert einen automatischen externen Effekt. Dennoch ist die behauptete Eindeutigkeit vor der Vorschlagsübernahme nicht gegeben. Enger Fix: verfügbare Betreffzeilen in die bereits vorhandene Signalprüfung einbeziehen und unterschiedliche vollständige Zeitintervalle im bekannten Verlauf als prüfbedürftig behandeln; keine Auswahl der vermeintlich richtigen Alternative und kein freies Datumsschätzen.

## Nachweise

Eigene eingefrorene Gegenproben: `/private/tmp/kingfisher-mail-calendar-backend-probes-20261009/test_review.py`.

- `test_done_replay_after_ignore_discloses_original_preview`
- `test_reauthorization_same_preparation_permanently_returns_old_bound_preview`
- `test_subject_cancellation_still_proposes_dates`
- `test_known_newer_explicit_time_conflict_still_selects_opened_old_time`

**4 passed, 1 warning in 1.49s**: Diese Tests bestätigen ausdrücklich das fehlerhafte Verhalten und sind keine Abnahme-Greens. Vor Verwendung als permanente Regression müssen ihre Enderwartungen auf das sichere Verhalten geändert werden.

Fokussierter Produktlauf mit `test_calendar_actions.py`, `test_calendar_preparation.py`, `test_mail_calendar_action_binding.py`, `test_mail_calendar_preparation_api.py`, `test_mail_calendar_preparations.py`: **56 passed, 12 subtests passed, 1 warning in 12.14s**. Ein erster Aufruf nannte eine nicht vorhandene `test_calendar_action_api.py`; dabei liefen keine Tests, der korrigierte Lauf ist der hier berichtete. Warnung ist die vorhandene Starlette/httpx-Deprecation.

Runner: `/private/tmp/kingfisher-review-20261006-venv/bin/python`; `PYTHONPATH=sidecar`. Keine Vollsuite.

## Positiv geprüfter enger Vertrag

- Lokale Vorbereitung ruft keinen Kalenderanbieter und kein Modell auf, erzeugt weder Tasks noch EpisodeStore-Importe.
- Normale Kalender-GET-/Execute-Routen blockieren den nicht ausführbaren `mail_preparation`-Journalzustand.
- Öffnungsbindung enthält Volltext, relevante Metadaten und begrenzten kontogebundenen Verlauf; Ignore→Reopen/Supportgeneration, neue bekannte Antwort und Mailänderungen werden im vorgesehenen Lesepfad abgewiesen.
- Der Quellenprüfer liest vor dem eigentlichen Provider-Create erneut und hält dabei die gemeinsame Sperre. Der vorhandene Gegenfall „Quelle ändert sich während Provider-Read“ blockiert die externe Wirkung.
- Gleiche Vorbereitung/Prüfstand erzeugt über Prozessneustart hinweg dieselbe Vorschau/Provider-ID. Normaler Doppelaufruf schreibt einmal.
- Normale manuelle Kalenderaktionen behalten ihre ETag-, Rechte-, ausdrückliche Bestätigungs- und unklarer-Ausgang-Prüfungen in den geprüften Fällen.

## Eingefrorene Dateifingerprints der Befundfassung

Die parallele Implementierung war noch nicht eingefroren. Diese Werte identifizieren genau die überprüfte Backendfassung; spätere Korrekturen sind ein gesonderter Nachtrag.

| Datei | SHA-256 |
|---|---|
| calendar_actions.py | c891b3ca1a3465d83e7a27e9399e4c7e6f511d037d38ff0621a6934e6921131d |
| mail_calendar_preparations.py | 2b5439a12145d12f1c83761d25083efcedd02502ca215fdad786a1854c55880c |
| mail_calendar_routes.py | 8594795db73561fcc28117a35e29e63fd97250d7f5dc35ea96578e7d134fb5ed |
| server.py | 34f5a60e51f40289ab464d6d3235e97acb3eadc00ff4ad8837cbc1bbb74427dd |

## Grenzen

Kein Nachweis realer Google-/Mailanbieter, vollständiger Postfachhistorie, freier Sprachinterpretation oder nativer Bedienung. UI wird parallel separat geprüft. Ein direktes Quellreread ist eine Momentaufnahme; Änderungen im externen Postfach unmittelbar danach lassen sich mit der lokalen Sperre nicht ausschließen. Die bekannten Wörter und strikten ISO-Zeiten sind bewusst ein begrenzter Vorschlagsmechanismus, kein allgemeiner Terminparser. Die Befunde beruhen auf vorhandenen eindeutigen Daten und bestehenden Lebenszykluswegen, nicht auf spekulativer NLP-Erweiterung.


## Gezielte Nachprüfung 1 — ursprüngliche drei Befunde korrigiert, später Anzeigeweg noch offen

Die sichere Variante der eigenen vier Ursprungsproben und zusätzliche Lebenszykluskontrollen liegt in `test_corrected_review.py` im bisherigen Probeordner. Ergebnis: **11 passed, 1 warning in 6.20s**. Der erste Versuch hatte zwei Fixturefehler, weil das tatsächliche API-Rebuild nach `done` den nur künstlich injizierten Mailreader entfernt; der Test stellt diesen nicht dauerhaft konfigurierten Fake danach ausdrücklich wieder her. An der Produktprüfung wurde nichts gelockert.

Nachgewiesen:

- Execute-Replay nach Ignore sowie bei fehlendem Guard liefert 409, zeigt keine alten Werte und erhält den abgeschlossenen Journalstatus `done`.
- Erneute Freigabe vor erstem Write funktioniert nach echtem `create_app`-Neustart sowohl direkt als auch nach einem zunächst blockierten alten Execute. Aktions-ID **und Provider-ID bleiben gleich**, der Prüfstand wechselt, die alte Bestätigung wird abgewiesen, die neue schreibt genau einmal.
- Nach `done` wird durch erneute Freigabe/Neustart keine zweite Kalenderanlage möglich.
- Nach unklarem Ausgang bleibt der Entwurf auch mit erneuter Freigabe/Neustart und erneutem Handoff gesperrt. Dies wurde sowohl mit noch sichtbarem als auch mit fehlendem Providertermin geprüft. Der vor Write dauerhaft gesetzte Marker bleibt erhalten.
- Absage im aktuellen oder historischen Betreff lässt beide Zeitfelder leer und erzeugt einen gezielten Hinweis.
- Abweichende vollständige bekannte ISO- oder deutsche Zeitintervalle lassen die Zeiten leer. Derselbe Zeitpunkt mit anderem ausdrücklich angegebenem Offset ist als Positivkontrolle weiterhin zulässig.

Enger Produktlauf (normale Aktionen und drei Mail-Kalender-Testdateien): **52 passed, 26 subtests passed, 1 warning in 5.30s**.

**Weiter offen: P1 desselben Quellenentzugsvertrags bei späteren Rückgaben aus Execute.** Auf zusätzlichen Root-Prüfauftrag wurde Entzug synchron unter `conversation_lock` während `provider.event` reproduziert. Alle drei sicheren HTTP-Erwartungen in `test_late_read_review.py` sind rot:

| Provider-Read-Ausgang nach Entzug | Tatsächlich | Sicher erwartet |
|---|---|---|
| vorhandener passender Termin | 200 / done mit alter Vorschau | 409 ohne alte Quellwerte |
| reconciliation-only, Termin nicht sichtbar | 200 / uncertain mit alter Vorschau | 409 ohne alte Quellwerte |
| Read wirft synthetischen OSError | 200 / uncertain mit alter Vorschau | 409 ohne alte Quellwerte |

**3 failed in 1.56s**, keine neue Kalenderwirkung nach Entzug. Die frühen Prüfungen und der Guard vor Create schließen diese öffentlichen Rückgaben nicht ein. Betroffene Stellen der Nachprüffassung: `calendar_actions.py:338–344`, `376–378`; derselbe Abschlussvertrag gilt auch für andere öffentliche Abschlusszweige. Journalzustand zuerst korrekt bewahren, danach Anzeige abschließend prüfen; die Anzeigeverweigerung darf einen bewiesenen Abschluss nicht nachträglich in ein wieder ausführbares Journal verwandeln. Nicht pauschal `_write` mit einem verschachtelten Quellen-Guard versehen: `_write(... running)` wird bereits innerhalb der nicht rekursiven Quellsperre aufgerufen.

Fingerprints dieser Nachprüfung:

- calendar_actions.py: `4f5a1463419ac2c825c69f0d1a043d2ed2d0c56d5af5d6cb3ae73c16e33686d7`
- mail_calendar_preparations.py: `7e239b114be5b3143892a5d88b6f6521238a240f8200f7c19d1a9de5f5242edf`
- mail_calendar_routes.py: `8594795db73561fcc28117a35e29e63fd97250d7f5dc35ea96578e7d134fb5ed`
- server.py: `34f5a60e51f40289ab464d6d3235e97acb3eadc00ff4ad8837cbc1bbb74427dd`
- test_corrected_review.py: `1698fb52cbd39781a70ef24d390ba5fd58ab38c8176a8641d405fceeb15d3cbc`
- test_late_read_review.py: `8db5f3ffc25e35c1ec86ab823821ad2995ea4b161ced88e4c45e36eb574ae117`

Read-only Produktprüfung; weiterhin ausschließlich künstliche Quellen und Fakeprovider. Keine vollständige Freigabe, bis der konkret nachgewiesene späte Anzeigeweg geschlossen ist.


## Abschließende gezielte Nachprüfung — alle gemeldeten Befunde geschlossen

**Für den überprüften Backendumfang kein verbleibender Blocker.** Alle drei ursprünglichen Befunde einschließlich des nachträglich reproduzierten späten Anzeigewegs sind in der aktuellen Fassung geschlossen. Das ist eine begrenzte Code-/HTTP-Testfreigabe; keine Bestätigung realer Anbieter, Installation oder nativer Bedienung.

`execute` trennt nun die interne dauerhafte Ergebnisaufzeichnung (`_execute`) von der abschließenden öffentlichen Ausgabe (`get`). Der vorhandene Quellen-Guard wird dabei außerhalb der internen Fehlerbehandlung angewandt. Damit werden die drei späten Varianten bei Quellenentzug mit 409 ohne alte Mailwerte abgewiesen. Der nachgewiesene Journalzustand bleibt jeweils `done` oder `uncertain`; ein Anzeigeverbot macht keine neue Kalenderwirkung möglich.

Unabhängige erneute Läufe:

- Alle eigenen ursprünglichen Korrektur-/Neustart-/Reauth-/Vorschlagsproben plus die drei späten Varianten: **14 passed, 1 warning in 7.42s**.
- Normale Kalenderaktionen separat: **21 passed, 1 warning in 0.81s**.
- Die drei späten Varianten danach zusätzlich mit expliziter Datenbankprüfung auf Erhalt von `done`/`uncertain`: **3 passed** (abschließender eigener Kontrolllauf).

Ein erster kombinierter Aufruf aus Scratch- und Produkttestverzeichnis brach vor Tests wegen doppelter Registrierung von `tests.conftest` ab. Deshalb wurden beide Testverzeichnisse getrennt ausgeführt; nur die oben genannten erfolgreichen getrennten Läufe tragen das Ergebnis.

Finale überprüfte Produkt-SHA-256:

| Datei | SHA-256 |
|---|---|
| calendar_actions.py | 07cd03d59f7a4a79e2a85348eb1b6f2d61fe2314ceed100d84845ad25b008192 |
| mail_calendar_preparations.py | 7e239b114be5b3143892a5d88b6f6521238a240f8200f7c19d1a9de5f5242edf |
| mail_calendar_routes.py | 8594795db73561fcc28117a35e29e63fd97250d7f5dc35ea96578e7d134fb5ed |
| server.py | 34f5a60e51f40289ab464d6d3235e97acb3eadc00ff4ad8837cbc1bbb74427dd |

Finale eigene `test_late_read_review.py` einschließlich Journalstatusprüfung: `ca154d7af20ded68a106b32ce701bb15682c648f3d73ed1e76b53f60adb51494`. `test_corrected_review.py` unverändert mit SHA `1698fb52cbd39781a70ef24d390ba5fd58ab38c8176a8641d405fceeb15d3cbc`.

Die oben genannten Grenzen gelten weiter. Die ergänzte deutsche Datumsgrammatik wurde hier nur mit einem vollständigen Gegenintervall geprüft; kein umfassender Sprachparser-Audit. Keine weiteren Produktänderungen, Livezugriffe oder Vollsuite durch diesen Reviewer.
