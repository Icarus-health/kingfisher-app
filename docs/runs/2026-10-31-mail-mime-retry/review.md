# Unabhängiges enges Review: Altbestand-MIME-Retry

Stand: eingefrorener Owner-Patch vom 31.10.2026, 19:20:42 UTC, `/private/tmp/kf-mime-retry-review-20261031.patch`, gegen den vom Root genannten Stand 808085e. Root erteilte anschließend die Testfreigabe. Kein Git-Aufruf, keine Produkt-/Repositoryänderung, keine privaten Dateien, Anbieter-, Netz-, Modell- oder Dockeraufrufe. Eigene synthetische Probe ausschließlich unter `/private/tmp`.

## Aktueller Schlussstand

**P2 geschlossen, keine offenen Befunde in diesem engen Review.** Die Nachprüfung am finalen Freeze 19:26:38 UTC bestätigt getrennte Anzeigen für verbleibende MIME-Lücken und verbleibende Abrufmöglichkeiten. Die konservative Identitätssperre bleibt bestehen. Details und eigene aktuelle Tests stehen im Nachtrag am Ende.

## Ursprüngliches Ergebnis vor der Statuskorrektur

**Im ersten Stand blieb ein bestätigter P2 offen; nach der unten dokumentierten Schlussprüfung ist er geschlossen.** Der normale Nachladeweg einschließlich aktueller Quellenbindung, Entzug/Pause und persistenter Einmalmarkierung funktioniert in den geprüften Fällen. Eine schon vorhandene UIDVALIDITY-Aliasbindung wird jedoch als reparierbar angeboten, nach erfolglosem Nachladen still terminal als Dublette abgeschlossen und anschließend nicht mehr angeboten. Findings-Zahl nach der substanziellen Prüfung: **1**; keine weitere breite Suche.

### P2: Generationsalias verbraucht die Reparatur ohne Reparatur und ohne Fehlerzustand

Betroffene Stellen: `sidecar/icarus_memory/mail_intake.py:203` (Kandidatenauswahl), `:191` (persistenter Marker), `:488` (exakter Quellenvergleich), `:239` (Abschluss als duplicate ohne Grund). UI-Folge: `app/kingfisher/src/mailIntakeProgress.ts:49` verwendet den anschließend auf null fallenden Kandidatenzähler für Retry/Abschluss.

Der bereits bestehende Aufnahmeweg darf nach einem UIDVALIDITY-Wechsel dieselbe Mail anhand seiner bestehenden Kriterien auf ihre alte Episode verknüpfen. Dadurch zeigt die aktuelle Intake-Zeile Generation 8 auf den Source-Head aus Generation 7. Der neue Retry-Kandidatensucher akzeptiert diese aktuelle Zeile. Beim erneuten Abruf wird hingegen aus der aktuellen UID ein anderer Quellenschlüssel berechnet. Der Sicherheitsvergleich verwirft die vollständige Antwort zu Recht, weil für diesen Reparaturpfad keine belastbare Aliasfreigabe vorliegt. Problematisch sind das vorherige Reparaturangebot und der anschließende lautlose terminale Abschluss.

Unabhängige reproduzierbare Probe: `/private/tmp/test_kf_mime_retry_independent.py`, `test_same_source_refresh_after_generation_alias[True]`. Sie verwendet den vorhandenen synthetischen Reader `tests.test_mail_intake.NeueKennung` und tatsächliche Intake-/Ingestion-/Quellenversionierungsfunktionen. Die Aliasbeziehung wird durch den echten bestehenden Generationswechselpfad erzeugt; keine manipulierte DB-Quellenbindung.

1. Unvollständige Quelle unter `7.1` erfassen.
2. Reader auf Generation 8 umstellen, vorhandene Inventur/Deduplizierung laufen lassen. Beide Intake-Zeilen zeigen auf dieselbe Episode.
3. `mime_refreshable == 1`; Reader liefert nun eine vollständige Antwort mit vollständiger Zuordnung.
4. Retry holt `8.1`, liefert aber `[]`. Der alte Head bleibt `source:truncated`. Aktuelle Zeile ist `duplicate`, Marker 1; `mime_refreshable == 0`.
5. Nach Store-Neustart und nochmals explizitem Retry erfolgt kein weiterer Abruf. Der Inhalt bleibt unvollständig.

Kontrolle ohne Generationswechsel: derselbe vollständige Nachladeinhalt erzeugt korrekt eine vollständige neue Fassung. Wirkung des Fehlers: Eine legitime Teilgruppe des Altbestands bleibt unvollständig; der neue bestehende UI-Weg kann sie nicht beheben und verliert seine Reparaturanzeige. Kein nachgewiesenes Reaktivieren entzogenener Quellen oder Vermischen fremder Quellen.

Minimal verantwortbare Korrekturrichtung: exakten finalen Identitätsguard **beibehalten**. Der konkrete Kennungsmismatch muss über den vorhandenen Rückmeldeweg als terminal unvollständig sichtbar bleiben. `mime_refreshable == 0` darf hier nur „kein weiterer automatischer Versuch“ bedeuten und nicht erfolgreiche Vollständigkeit. Quelle und Einmalmarker bleiben erhalten; keine wiederholten IO-Versuche. Eine sichere Vorab-Abgrenzung kann unnötigen IO vermeiden, ist für die minimale Korrektur aber nicht erforderlich. Eine automatische Reparatur durch bloßes Akzeptieren der Intake-Aliasbeziehung oder fremder Message-ID wäre nicht durch dieses Review gedeckt. Falls automatische Reparatur auch dieser Fälle zwingendes Ziel ist, braucht sie einen gesondert bewiesenen Identitätsweg.

## Eigene Verifikation

Arbeitsverzeichnis bei allen Befehlen: `/private/tmp/kf-skill-categories-20261031`.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:. /private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python -m pytest -q -p no:cacheprovider sidecar/tests/test_mail_mime_retry.py sidecar/tests/test_mail_intake_routes.py sidecar/tests/test_migrations.py
```

**93 bestanden, 13,35 s.** Einschließlich MIME-Retry-Neustart, vollständiger neuer Quelle/Anlage, Entzug/Metadaten-/Headänderung während IO, abweichendem Anbieterkey, Gmail-Label-Deduplikation, Pause/leichter Takt, Budget, terminalem Partial und Schema25→26 mit Originalerhalt.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:. /private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python -m pytest -q -p no:cacheprovider sidecar/tests/test_update_backup.py::test_outdated_database_is_saved_before_it_is_rebuilt sidecar/tests/test_restore_boundary.py::test_full_snapshot_restore_marks_before_operational_reopening sidecar/tests/test_restore_boundary.py::test_bundle_boots_inspection_before_any_provider_or_connector
```

**3 bestanden, 0,76 s.** Beide Gruppen melden nur die bestehende Starlette/httpx-Abkündigung.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:. /private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python -m pytest -q -s -p no:cacheprovider /private/tmp/test_kf_mime_retry_independent.py
```

**1 fehlgeschlagen, 5 bestanden.** Rot ist ausschließlich der beschriebene Aliasfall; grüne unabhängige Kontrollen: derselbe Nachladeweg ohne Rotation, Kontopause während IO, Ordnergenerationsänderung während IO, Neustart nach Einreihung vor Abruf, reine Textgrenze bei vollständig gemeldeter MIME. Log: `/private/tmp/kf-mime-retry-independent-repros-20261031.log`.

Der erste eigene Probeentwurf hatte keinen ClaimStore für Quellenwechsel übergeben und scheiterte dadurch zusätzlich an zwei positiven Kontrollen. Nach Korrektur dieses Testaufbaus auf den tatsächlichen Laufzeitvertrag bleibt nur der Aliasfehler. Diese anfänglichen Kontrollfehler sind keine Produktbefunde.

## Grenzen und sonstige Bewertung

Die Auswahl überspringt ignorierte und nicht aktuelle Quellen. Vor/nach IO bleiben Freigabe, Readerstand über den bestehenden `allowed`-Callback, Foldergeneration und konsistenter Quellensnapshot maßgeblich. Der exakte Anbieter-/Konto-/Ordner-Quellenschlüsselvergleich vor Persistenz bleibt erhalten. Retry aktiviert weder Zeitplan noch globale/Kontopause. Die neue Warteschlangenarbeit nutzt vorhandene Batchgrenzen und wird im `nur_neu`-Takt auch bei früheren live-Zeilen ausgespart.

Migration26 ist additiv und erhält die historischen Verifier; Restore wird weiterhin in den eingeschränkten Inspektionsmodus gesetzt. Das aktuelle Schema und der konkrete Upgrade wurden geprüft; nicht jede historische Sicherung oder externe Installation.

Unveränderte Logoquellen behalten laut eigenem Lauf der neuen Tests ihren Quellensupportfingerabdruck; kein neues Screeningmodell. Der tatsächliche Aufrufpfad kann weiterhin eine ID in normale nachgelagerte Warteschlangen stellen, deren bestehende Fingerprint-Gates unverändert sind. Keine echte Modell-/Leistungsbehauptung aus diesen Offlineprüfungen.

Dies ist keine Freigabe eines persönlichen Bestands, einer Live-Mailbox, eines Releases oder der vollständigen Anwendung. Kein Browser- oder TypeScript-Typecheck durch dieses Review. Keine vollständige Suite. Die Originaltexte werden durch diesen Patch nicht umgeschrieben; erfolgreiche Reparatur nutzt bestehende neue Quellenversionen.


## Enge Schlussprüfung der P2-Statuskorrektur – Freeze 19:26:38 UTC

**Befund geschlossen.** Geprüft wurde ausschließlich die neue Statusableitung und ihre Wirkung im bereits reproduzierten UIDVALIDITY-Aliasfall. Kein weiterer Audit-Scope, keine weiteren Produktänderungen.

`mail_intake.py:227` zählt aktuelle, nicht ausgeschlossene MIME-Lücken jetzt unabhängig vom Einmalmarker und von der aktuellen Ordnergeneration; `DISTINCT e.id` verhindert Mehrfachzählung der identischen Episode über alte/neue Aliaszeilen. Vollständig abgerufene MIME mit einem weiterhin nicht unterstützten Logo und reine Textbegrenzungen werden durch `include_unsupported=False` nicht als MIME-Lücke ausgegeben. Die Retry-Kandidaten und der exakte finale Quellenvergleich wurden dabei nicht gelockert.

`mailIntakeProgress.ts:50` trennt `mimeIncomplete` von `mimeRefreshable`: verbleibende Lücke verhindert `complete`, ergibt den Aufmerksamkeitszustand und hält den Gesamtfortschritt unter 100 Prozent. Sie aktiviert allein keinen erneuten Retry. `MailIntake.tsx:258` zeigt ausdrücklich „Einige gespeicherte Mails sind noch unvollständig erfasst.“ Der bisherige Abrufmarker verhindert weiterhin neue IO bei wiederholtem Retry oder Neustart.

Eigene Wiederholung des exakten ursprünglichen Szenarios in `/private/tmp/test_kf_mime_retry_independent_final.py`: die tatsächlich erzeugte Aliasbindung 7→8 bleibt bestehen, vollständige neue Antwort wird weiterhin konservativ verworfen; Originalepisode und Head bleiben exakt erhalten. Nach Neustart plus Retry keine weiteren Abrufe, `mime_refreshable == 0`, aber nun `mime_incomplete == 1`. Vergleich ohne Alias wird weiterhin vollständig repariert und zählt anschließend null MIME-Lücken. Die alte Repro samt rotem Log wurde unverändert aufbewahrt; nur die neue Kopie prüft die ausdrücklich vereinbarte konservative Soll-Erwartung.

Aktuelle eigene Befehle/Ergebnisse:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:. /private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python -m pytest -q -s -p no:cacheprovider /private/tmp/test_kf_mime_retry_independent_final.py
```

**6 bestanden, 0,64 s.** Einschließlich Alias/Restart/kein IO, Vergleich ohne Rotation, Pause und Generationswechsel während IO, Neustart nach Queue sowie vollständiger MIME bei Textcap.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:. /private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python -m pytest -q -p no:cacheprovider sidecar/tests/test_mail_mime_retry.py -k 'attempted_mime_gap or pure_text_limit or legacy_unsupported or still_partial or same_source_gmail'
```

**7 bestanden, 17 abgewählt, 2,09 s.** Deckt die neue terminale Partial-/Aliasanzeige, Logo-/DOCX-Kontrollen und vorhandene Label-/Einmalmechanik ab.

Im Verzeichnis `app/kingfisher`:

```sh
node --experimental-strip-types --test tests/intake-progress.test.mjs
```

**27 bestanden, 0,14 s.** Insbesondere unresolved MIME: kein erneuter Retry, `complete=false`, Aufmerksamkeitszustand, Fortschritt kleiner 100. Nur bestehender Node-MockTimers-Experimentalhinweis.

Keine automatische Aliasreparatur behauptet: gleicher Body und gleiche Message-ID nach Generationswechsel beweisen keine identischen Anlagen. Diese Quellen bleiben korrekt unvollständig und sichtbar. Keine neue Modell-, Anbieter-, Browser- oder Vollsuiteaussage. Finaler Finding-Stand: **1 ursprünglicher P2, geschlossen; 0 offen.**
