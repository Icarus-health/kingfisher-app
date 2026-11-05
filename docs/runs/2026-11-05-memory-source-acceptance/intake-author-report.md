# P1 · Quellenaufnahme des eingefrorenen Holdouts v2

## Ergebnis

Der isolierte Offline-Lauf hat 109 Produkt-Episoden aus 110 geprüften Fixture-Einträgen angelegt. 105 Belege sind als `admitted` ausgewiesen, vier als `partial` und N06 als `withheld`. Der Mailfortschritt meldet 94 Aufnahmen in INBOX einschließlich der beiden nativen EML und acht in Sent. Kein Mail-Eintrag blieb offen oder fehlgeschlagen. Das Wiederholungsexperiment in derselben Instanz lieferte dieselben Episoden-IDs und keinen zusätzlichen Eintrag.

- `product_quality = NOT EVALUATED`
- `bulk_import_authorized = false`
- Bewertungsdaten und Zustandsphasen sind als Bytes gegen den Freeze geprüft. Der Loader parst daraus ausschließlich `sources.json` für Eingabemetadaten und hält die verifizierten nativen Originalbytes bereit. Der Manifest-Hash ist im Adapter gepinnt.

## Aufnahmepfade

| Eingabe | Echter Produktpfad | Befund |
| --- | --- | --- |
| 100 Maildatensätze | Bestehender RFC822-Renderer der Messlatte → synthetischer IMAP-Transport → `MailConnector.message_mit_anhaengen` → `Intake.step` | Originaltexte bis auf den abschließenden Transport-Zeilenumbruch, Maildaten, Absender und Empfänger, eigene Identität, stabile Nachrichten- und Ordnerzuordnung gespeichert. Der eingefrorene Satz enthält keine ausdrücklichen Reply-Header. Eine separate künstliche Sent-Nachricht prüft In-Reply-To, References und Cc über den echten Connector. |
| N01/N03 und N02/N04 | Unveränderte EML-Bytes im gleichen Abruf → vollständiger Produkt-MIME-Parser → Produkt-PDF-Leser und Anlagenaufnahme | Beide Anlagen mit lesbarer Seite 1 und Produkt-Elternlink. Dekodierte PDF-Bytes stimmen exakt mit den eingefrorenen Vergleichsdateien überein. Die PDF-Dateien werden ausschließlich als MIME-Kinder aufgenommen. |
| N05 | `connectors.calendar.parse_events` → `KalenderGedaechtnis.abgleichen` | Ein bestätigter Termin. UID aus ICS, Terminbeginn 27.11.2026, 10:00 Uhr Berlin. Der Beleg trennt die ursprüngliche DTSTAMP-Angabe, die fachliche Terminzeit und die Zeit der Aufnahme. |
| N06 | Im Basislauf ausschließlich Hashprüfung | Die Absage ist einer späteren Zustandsphase vorbehalten. Beim getesteten Basisstand verwirft der ICS-Parser `STATUS:CANCELLED`; der Kalenderabgleich entzieht bei leerem Abschnitt vorsorglich nichts. Die Absage ist auf diesem Stand als alleinige Datei über diesen Abgleich nicht wirksam. |
| N07 | `ingest_directory(dateien)` mit unveränderten TXT-Bytes | Dokument gespeichert. Der Fließtext liefert dem Dateiadapter keine strukturierte Quellenzeit. |
| N08/N09 | `ingest_directory(transkripte)` mit unveränderten TXT-Bytes und Produkt-Transkriptleser | Mitschriften gespeichert. Die Textangaben zur sicheren beziehungsweise unklaren Sprecherzuordnung bleiben erhalten. Strukturierte Ereigniszeit fehlt in beiden Episoden. |
| N10 | `POST /api/v1/sources/documents/preview-docx` → `POST /api/v1/sources/documents` | Der echte DOCX-Parser liest den Haupttext aus den Originalbytes. Der Upload speichert Text und Dateinamen. Strukturierte Quellenzeit fehlt. |

Die externe Quellenzeit der vier Dateiquellen N07 bis N10 steht im jeweiligen Aufnahmebeleg. In allen vier Episoden ist `occurred_at` leer. Die Instanzuhr 04.11.2026 16:00 Uhr Berlin steht getrennt als `recorded_at`. Dokument-, EML- und PDF-Dateihashes bleiben im Bericht von den Digests des im Produkt gespeicherten Texts unterscheidbar.

Der CLI-Lauf baut die vorhandene Messinstanz mit eigenen Stores und injiziertem Modellwächter. Der Scheduler wird nicht gestartet. DNS und ausgehende Python-Socket-Aufrufe sind im Lauf gesperrt. Der Integrationstest blockiert den Zugriff auf den Host-Schlüsselbund und den Schedulerstart zusätzlich ausdrücklich. Klassifizierung, Extraktion durch ein Modell, Embeddings, Mailfilter, Aufgaben- und Abrufqualität bleiben unbewertet.

## Reproduktion und Prüfstand

Repo-HEAD `ff2f07513a64dab09735d3dc7831f25000cc9af7`. Der Kalender-Basislauf verwendete die unveränderten SHA-256-Dateistände aus diesem HEAD.

- `sidecar/icarus_memory/connectors/calendar.py` · `f0c12a2398fca4c08f470940a11c5ccf4cb04f717347092a409cce45c3acad7b`
- `sidecar/icarus_memory/calendar_memory.py` · `c89bca51b69d09601b418f2dfbf338bb62e613573717325e443ab5a07f9eb5dc`
- `sidecar/icarus_memory/connectors/collections.py` · `9f94c6f728de9ea1d7a69449a3a106b87dd97440365bda70789fcedd5a2ad686`

```sh
export PYTHONPATH=sidecar:scripts:. PYTHONDONTWRITEBYTECODE=1
/private/tmp/kf-core-20261104-env/bin/python -m pytest -q -p no:cacheprovider scripts/test_memory_acceptance_intake.py
/private/tmp/kf-core-20261104-env/bin/python scripts/memory_acceptance_intake.py > /private/tmp/kf-heldout-v2-offline.qjxiP1/baseline.json
git diff --exit-code -- docs/fixtures/memory-acceptance-20261104/heldout-v2
```

- 12 gezielte Tests bestanden. Die Tests verwerfen geänderte oder fehlende Dateien, zusätzliche Dateien und ein beschädigtes Manifest. Ein Parse-Wächter verhindert die semantische Nutzung der Bewertungsartefakte. Die Integrationsprobe prüft alle 100 Mailtexte, den echten Produktabruf für alle nativen Baseline-Quellen, Replay, N06-Sperre und die unveränderten Datei-Hashes. Eine Starlette-TestClient-Deprecation-Warnung blieb sichtbar.
- Standalone-Basislauf Exit 0. JSON unter `/private/tmp/kf-heldout-v2-offline.qjxiP1/baseline.json`, SHA-256 `d78da82d6e6126f644e0a590db5113883b0f65c51ec7d3d048eac91bb4076b0a`.
- Freeze SHA-256 `5f9e54252b0513d58dffaa0e943e471431e0f3759866af171f559b37e289a39e`. SHA-256 der beiden dekodierten PDF-Anlagen `e7c11812ace436d5e2fde772c6768e8d39dac2c678ede5ce8b254e8215a5b505` und `cec9c46b3eebe397a861a7d5a44de224a954759c56bd38e4fb5e9fcc59a72129`.
- Fixture-Diff leer. Eigener Codeumfang sind `scripts/memory_acceptance_intake.py` und `scripts/test_memory_acceptance_intake.py`. Das Protokoll liegt im lokalen, ignorierten `.superpowers`-Pfad.

### Betroffene Produkttests

Erster breiter Lauf mit den nachstehenden Dateien und dem ganzen `sidecar/tests/test_ical_termine.py` anstelle der beiden letzten Testselektoren. Ergebnis 371 bestanden, 15 fehlgeschlagen. Elf Fehler entstanden durch den eigenen N06-Spion, weil er vor dem Start der Messinstanz gesetzt wurde und ein später importiertes Kalendermodul seine Referenz behielt. Der Test setzt den Spion jetzt erst nach dem Instanzstart und stellt ihn innerhalb desselben Testkontexts zurück. Die drei Loopback-Fälle `test_caldav_klappt_serien_im_abgefragten_fenster_aus` und `test_caldav_liest_den_kalender_aus_dem_xml_nicht_aus_dem_rohtext[False|True]` scheiterten bereits am Socket-Bind mit `PermissionError: [Errno 1] Operation not permitted`. Der bestehende Serienfall `test_jede_serie_ist_in_unter_einer_sekunde_entschieden[20260101T090000-regel17-nie]` brauchte im breiten Lauf 1,24 s bei einer Grenze von 1 s.

Gezielte Folgeprüfung mit Adapter, betroffenen Produktpfaden und Kalendertests, die den zuvor betroffenen Modulalias nutzen. Ergebnis 224 bestanden, Exit 0, 22,94 s und eine Starlette-TestClient-Deprecation-Warnung. Der komplette ICS-Testlauf wurde nach der gezielten Korrektur nicht erneut angesetzt.

```sh
PYTHONPATH=sidecar:scripts:. PYTHONDONTWRITEBYTECODE=1 /private/tmp/kf-core-20261104-env/bin/python -m pytest -q -p no:cacheprovider \
  scripts/test_memory_acceptance_intake.py \
  sidecar/tests/test_mail_intake.py sidecar/tests/test_mail_bounded_mime.py sidecar/tests/test_attachment_coverage.py \
  sidecar/tests/test_transkript_eingang.py sidecar/tests/test_kalendergedaechtnis.py sidecar/tests/test_ingest.py \
  sidecar/tests/test_document_text.py sidecar/tests/test_document_upload.py \
  sidecar/tests/test_ical_termine.py::test_abo_und_einrichten_lesen_den_zeichensatz_der_antwort \
  sidecar/tests/test_ical_termine.py::test_ein_termin_mit_unmoeglichem_datum_kippt_die_quelle_nicht
```

- Adapter SHA-256 `b4814ff0aabfc2fe73eae166ad92cb01a330a685127b051100cbc3894ea9bbb8`.
- Testdatei SHA-256 `a14231972c90281014cf9cb82c153fcce2558c998be358295cfc3764a0093612`.

## Reviewrunde 1 · Grenzen und persistierte Identitäten

Die Nachprüfung betrifft ausschließlich die beiden Aufnahmeskripte. Der ursprüngliche Bericht und sein Basislauf oben bleiben als eigene Nachweise erhalten.

- Die JSON-Quelleneingaben sind rekursiv eingefroren. Zuweisungen an Sender, Empfänger und native Anlagenzuordnungen werden im Regressionstest abgelehnt.
- Die Mailbelege lesen Konto, Ordner, UID und UIDVALIDITY aus dem persistenten Intake-Laufzeitdatensatz. Für Anlagen steht die Transportidentität der tatsächlichen Elternmail separat. Jede gespeicherte Episode liest den Produktschlüssel aus dem vorhandenen Support-Snapshot. Beim allgemeinen DOCX-Upload N10 ist der Beleg ausdrücklich `source_key: null` und `source_key_status: unversioned`.
- Das CLI löst sein Ziel auf und lehnt Ziele innerhalb des Freeze-Baums vor dem Instanzaufbau ab. Die Tests prüfen einen direkten Pfad und einen Alias über einen Verzeichnis-Symlink. Der Verzeichnisbestand bleibt in beiden Fällen identisch.
- `source_only_instance` baut eine Messinstanz mit Modellwächter für Antwort, Frage und Satzprüfung. `prepare_baseline` prüft den zugehörigen aktiven Kontext und setzt seine eigene Netzsperre. Ein direkt übergebener anderer Anbieter wird vor der Aufnahme abgelehnt. Zwei gezielte Tests lösen jeweils einen Modell- und einen Socket-Versuch aus dem Mailabruf eines direkten Aufrufs aus. Beide brechen hörbar ab, bevor eine Episode gespeichert wird. Die Netzsperre gilt für Python-Aufrufe dieses Laufs.

Der erneute Adapteraufruf belegt stabile gespeicherte Episoden- und Transportidentitäten. Der Intake-Cursor überspringt dabei bereits erfasste Mails. Das erneute Vorlegen der exakt identischen MIME-Bytes unter der gleichen Mailidentität bleibt Teil der späteren S08-Zustandsprobe. Die separate künstliche Reply-Probe belegt RFC822-Header und Cc im Produkt-Connector. Die persistierte kontogebundene Reply-Beziehung wurde in dieser Runde nicht geprüft.

```sh
export PYTHONPATH=sidecar:scripts:. PYTHONDONTWRITEBYTECODE=1
/private/tmp/kf-core-20261104-env/bin/python -m pytest -q -p no:cacheprovider scripts/test_memory_acceptance_intake.py
/private/tmp/kf-core-20261104-env/bin/python scripts/memory_acceptance_intake.py > /private/tmp/kf-heldout-v2-offline-round1.6CuxvC/baseline.json
git diff --exit-code -- docs/fixtures/memory-acceptance-20261104/heldout-v2
```

- Rotprobe vor Korrektur: 7 fehlgeschlagen, 11 bestanden. Nach Korrektur: 18 bestanden, Exit 0, 3,68 s und eine Starlette-TestClient-Deprecation-Warnung.
- CLI-Pythonlauf Exit 0. 110 Belege, 109 Episoden, 105 `admitted`, vier `partial`, N06 `withheld`. 102 persistierte Mail-Transporttupel, 108 Episoden mit persistentem Produktschlüssel und eine unversionierte Episode.
- E09-01 verwendet `heldout-v2 / INBOX / 76 / 1`, N01 `heldout-v2 / INBOX / 93 / 1`. N02 trägt denselben Elterntransport wie N01 und den gespeicherten Kindschlüssel mit Suffix `:anhang:1`. N05 ist der einzige Kalenderbeleg mit Episode.
- Freeze SHA-256 `5f9e54252b0513d58dffaa0e943e471431e0f3759866af171f559b37e289a39e`. Neuer JSON-Bericht SHA-256 `a899e4c3a95846008989609fe921bfc88d2f8ec760b2c28cac629d6f21b9a25c`. Fixture-Diff leer.
- Adapter SHA-256 `48c4ad404d88baf93f4d245f3a59d2f1f3e5673a2e2bf28cb38a185bb283d6ca`. Testdatei SHA-256 `66fc255cccd99ddad9e636eb0cbbbec7a18c00c8e463a7e407a578bf524a60bf`.
- Die Arbeitskopie stand weiterhin auf HEAD `ff2f07513a64dab09735d3dc7831f25000cc9af7`. Sie enthielt beim zweiten CLI-Lauf den separat bearbeiteten Kalenderparser mit SHA-256 `ec230147b598d3f2d741eb4c7ac76b4231ed4dee06074457402312e2d0c7df41`. `calendar_memory.py` und `connectors/collections.py` entsprachen den oben protokollierten BASE-Hashes. In diesem Lauf wurde weiterhin ausschließlich N05 geparst.
- `product_quality = NOT EVALUATED`, `bulk_import_authorized = false`.
