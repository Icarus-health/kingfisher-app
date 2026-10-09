# Unabhängiges Installerreview Mail → Kalender — 2026-10-09

**Status: Kompaktimage-Pins abschließend abgeglichen; synthetische Ablaufprüfung erneut bestanden.** Aktuell geprüft ist Image `930ef4d…` gemäß Abschlussnachtrag unten. Der erste Abschnitt dokumentiert die überholte Vorbereitungsfassung `38f563…`. Keine Installation oder reale Laufzeitprüfung wurde durch diesen Reviewer ausgeführt. Tatsächliche Speicher-, Paket- und breite Produkttests bleiben gesonderte Voraussetzungen.

**Kein verbleibender Blocker im eng geprüften Schema-20→20-Installationsweg.** Dies ist eine statische und synthetische Ablaufprüfung. Der Reviewer hat weder Docker noch reale HTTP-Routen, private Daten, Modelle, Netzwerk oder die Installation aufgerufen. Die breite Produktsuite und reale Paket-/Macnachweise bleiben getrennte Voraussetzungen.

## Geprüfte Fassung und Einstieg

Unter `/private/tmp/kingfisher-mail-calendar-install-20261009` ist **`install.py` der geprüfte Einstieg**. Es überschreibt die Versions-/Imagekonstanten des gehashten Hilfsmoduls und verwendet dessen Vorbereitung/Isolation/Proof-Funktionen. Es ruft nicht dessen altes migrationsfähiges `execute` auf.

Konkreter Vergleich von `orchestrator.py` mit `/private/tmp/kingfisher-category-install-copy-20261009/orchestrator.py`: Änderungen an Revision/Version und zweimal 264→266 Python-Dateien; keine weitere Ablaufänderung. `data_proof.py` und `wal_finalize.py` sind bytegleich zur zuvor geprüften Vorlage. Das im Hilfsmodul allein noch alte `IMAGE_ID` wird vom geprüften Einstieg vor Instanzerzeugung auf die neue feste Image-ID gesetzt; der synthetische Ablauf hat genau diese neue ID verwendet.

Gepinnt:

- Revision `d431383b551c6a65254c93331819998f86a685eb`, Version `1.0.6-local.d431383`.
- Neues Image `sha256:38f56309bbe7b7e0b6aabde0dd173e8a8018817a767c914f4d4338e74211d629`.
- Erwartetes Altimage `sha256:c6bc20a9a39f8759dc7f987462378e41c109afb6b87d754555c14dc3d557176b`.
- Feste Datenvolume-Kennung `kingfisher_kingfisher-data`.
- Manifest enthält tatsächlich 266 Python- und 112 UI-Dateien und die gepinnte Revision/Version. Aktuelle Manifest- und Checker-Bytes passen zu den Konfigurationshashes. Kein Dockerbeleg über die Imageinhalte wird daraus abgeleitet.

## Tatsächlicher Ablauf und Schutz

Vor Dienststopp prüft `prepare` die Wartungszusicherung, Native-/Launcherbeobachtung, Zielpins, Paketmanifest/-checker, Bundle, laufenden alten Container, dieselbe Datenvolume-Kennung, Reserveplatz und das eindeutige Image-/Token-Layout der bestehenden Env. App und Env werden gesichert. Die spezifische Altimageprüfung liegt anschließend noch vor dem einzigen Stop.

Nach Stop/Quiet wird zuerst der **vollständige rohe Datenbaum einschließlich Journale** kopiert. Ein netzloser, portloser, read-only Daten-One-Shot vergleicht dessen komplettes Dateimanifest. Erst danach wird eine zweite lokale Arbeitskopie angelegt und SQLite WAL-bewusst gelesen. Vor Freigabe werden Schema 20, 17 Datenbanken, Originaldigests, Einstellungen, Pause, kein Inspectionmarker und Tabellenprojektion zwischen Quelle und Kopie verglichen; der rohe Quellbaum wird erneut kontrolliert. Nativechecks im gestoppten Abschnitt sind statisch; der Runtimeprobe bleibt im vorbereitenden laufenden bzw. abschließend wieder laufenden Zustand.

Die freigegebene Änderung ist anschließend nur der Imagewert der Env, atomar über eine temporäre Datei ersetzt. Vor Compose ist der Zustand bereits als veröffentlicht markiert. Ein Fehler ab dort führt deshalb zu notwendiger Vorwärtsreparatur; der geprüfte Weg startet kein Altimage und stellt keine historischen Daten wieder her. Nach normalem Start folgen Health/Version/Read-only-Route/Pause, Image-/Volumeidentität, Originale/Settings, Env und Bundle sowie Unverändertheit des rohen Backups.

In diesem Ablauf gibt es **keinen Aufruf von preflight.py, WAL-finalize, Schema-Migration oder Restore**. Der vorhandene Preflight wird lediglich als unveränderter Hilfsbestandteil gehasht. Datenprüfungen laufen mit read-only Mount; der paketprüfende One-Shot hat nur die begrenzte `/data`-tmpfs und kein Datenvolume.

## Unabhängige Verhaltensproben

Eigene Datei: `/private/tmp/kingfisher-mail-calendar-install-review-probes-20261009/test_review.py`. Sie lädt den echten neuen `Install.execute`-Pfad und verwendet einen angepassten bestehenden FakeSystem. Jede Datendatei ist eigens synthetisch erzeugt. Keine Ersetzung der Installationsentscheidung durch bloße Textsuche.

**13 passed in 0.55s**, Runner `/private/tmp/kingfisher-review-20261006-venv/bin/python`:

1. Erfolgsweg Schema20→20 mit 17 synthetischen DBs, Original, vorhandenen nicht-NULL Kategoriefehlerdaten, Pause, zusätzlicher Originaldatei und unveränderter Gesamtdatenprojektion.
2. Falsche neue Image-ID stoppt vor Stop/Envwechsel.
3. Falscher Manifesthash stoppt vor Stop/Envwechsel.
4. Falscher Checkerhash stoppt vor Stop/Envwechsel.
5. Falsche Dateianzahl im Manifest stoppt vor Stop/Envwechsel.
6. Falsche vom Checker gemeldete Pythonanzahl stoppt vor Stop/Envwechsel.
7. Falsche vom Checker gemeldete Version stoppt vor Stop/Envwechsel.
8. Unerwartetes Altimage stoppt vor Stop/Envwechsel.
9. Manipulation der rohen Sicherung blockiert Veröffentlichung; alter Dienst wird nicht eigenmächtig gestartet.
10. Fehlende Pause blockiert Veröffentlichung.
11. Healthfehler nach Veröffentlichung lässt das neue Image in der Env stehen; kein Restore/Altstart.
12. Weiterer Volume-Writer nach Stop verhindert bereits die Datenkopie und Veröffentlichung.
13. Geänderte Volumeidentität nach Stop verhindert bereits die Datenkopie und Veröffentlichung.

Der positive Weg prüft zusätzlich Reihenfolge `Stop < vollständige Kopie < Dateibaumprüfung < SQLite-Proof < Compose`, genau einen Stop, alle konkreten Mountparameter, keine Ports/Bindmounts, `network none`, `restart no`, feste Image-ID, private Env-Sicherung sowie Gleichheit von rohem Backupmanifest und überprüfter Arbeitskopie. Die anfängliche Testadapterfassung verwechselte `data_proof.py` mit `proof.py` wegen einer zu breiten Suffixprüfung; nur dieser eigene Fake wurde korrigiert. Der Installer blieb unverändert.

## Bekannte Test-/Nachweisgrenzen

`test_preparation.py` enthält noch die vom Root bereits benannte veraltete Erwartung von `ROOT_MUST_PIN`-Platzhaltern in der inzwischen korrekt gepinnten Konfiguration. Diese Stringtests sind kein Laufzeitbeleg; das obige Ergebnis beruht auf den eigenen Verhaltensproben. Die alte Platzhaltererwartung sollte für einen sauberen Archivteststand aktualisiert werden; sie belegt keinen Fehler im gepinnten Installationsweg.

Die Wartungszusicherung und wiederholte Writer-/Nativebeobachtung sind keine atomare Betriebssystem-Sperre gegen einen Menschen, der zwischen Beobachtungen eine App startet. FakeSystem beweist Kontrollfluss und Abbruchbedingungen, nicht reale Docker-/Colima-/SQLite-Mountsemantik, Codesign oder Native-UI. Die Helper-Bytes wurden verglichen, deren gesamter früherer Audit wurde nicht wiederholt. Der nach Start laufende Tabellenvergleich ist bewusst `all_rows=False`; Originale/DB-Satz/Settings/Pause werden nachgewiesen, nicht Unveränderheit aller legitimen Betriebsdaten während eines laufenden Servers.

## SHA-256 des geprüften Bestands

| Artefakt | SHA-256 |
|---|---|
| install.py | fc2a9eb4075e7f854cf5ce1df2a687673c766ef6e1709958e2ab24c6ba65dedd |
| orchestrator.py | 4e52cb1dfaa026f8e223788c77d75448e21e9baab02a49052cb383ada5ddfba2 |
| config.json | f3196f8a9bc34d40c1edf4c47c98d40c01e01e4f8a2f8c365733353c2e5c9588 |
| data_proof.py | 1316a92cf90edb21c89c59a1ea31a3f6b57f3437cff6994c62ab00ac5a56ce71 |
| wal_finalize.py | a1cfd9ce698420f63dc9dd0f2a6111a80d960e81285613367341c79189a8d20b |
| proof.py | 60255487ccb49804d66867e4b9e864f8758cf1ae89431f6674b58393be2286fb |
| tree.py | 71e767c970f84596dadce06cb7d4b235a2a92dcc2545a698f4a70e0e0e5bfa21 |
| Paket expected.json | 81a7327525b2d97c85964c34f5620ed4516a388a628b3434efcdbd16e9621dbc |
| Paket installed-check.py | 181b9d4158aec6afabac920942098b18f74e15900dc62428052c9dcfa8a66298 |
| Eigene test_review.py | b276c65036ac235a5c272cf68462c3d34876ed3f20084e0c8f323c0dbc17feed |

Keine Quelländerung am Installer, Hilfsbestand oder Produkt; keine Liveausführung durch diesen Reviewer.


## Abschlussnachtrag — Kompaktimage, finaler Pinabgleich

**Kein neuer Ablaufblocker.** Derselbe echte Installerpfad wurde nach dem Repin erneut mit den unveränderten eigenen Verhaltensproben geprüft: **13 passed in 0.57s**. Hilfsmodul, Datenproof, WAL-Helfer, Proof-/Tree-One-Shots sind bytegleich zur vorigen Reviewfassung. Der Installer verändert nur den gepinnten Imagewert; Schema20→20 und der veröffentlichungsbezogene Kontrollfluss bleiben unverändert.

Abgleich durch Read-only-Dateiprüfung:

- `install.py`, `config.json` und der gesonderte frische Verifier referenzieren `sha256:930ef4d708d93668dcb79a54cbaac678444283e769addac1b9c3914fd511b858`.
- Checkerdatei tatsächlich `3aba0b0ffb3c9cc3e2e98f0dcba284f8427228000df8323a717a3cd361227b3b`, identisch zum Konfigurationspin.
- Manifestdatei tatsächlich `e5b4fb5ed3a53abde3f96ffb8094a7b296ee5d5a34d36b2801c5263ab2821aaf`, identisch zum Konfigurationspin.
- Manifestrevision weiterhin `d431383b551c6a65254c93331819998f86a685eb`, Version `1.0.6-local.d431383`, 266 Python- und 112 UI-Dateien.
- Altimage bleibt `c6bc20a9…`; unveränderte FakeSystem-Gegenproben verhindern neue/alte Imageabweichung vor dem Dienststopp.

Aktuelle SHA-256 gegenüber den oben historischen Artefaktwerten:

| Artefakt | Final überprüfter SHA-256 |
|---|---|
| install.py | 50b49820e1fac09eaa9dd216ecf4f7ddda7373062b80b7a01b6740d2228066ba |
| config.json | 6a9b37e39d932663cbd1ffbffd2bea7fc2fc887b02f11de1fb7e1ca89a37170e |
| Paket expected.json | e5b4fb5ed3a53abde3f96ffb8094a7b296ee5d5a34d36b2801c5263ab2821aaf |
| Paket installed-check.py | 3aba0b0ffb3c9cc3e2e98f0dcba284f8427228000df8323a717a3cd361227b3b |
| kingfisher-mail-calendar-fresh-verifier-20261009.py | 895e0629306fdbad832a52f5bd8c50c0a17c2bfa24e1c29711e9954e83aeb1f6 |

Archivhinweis, an Root gemeldet: `helper-sha256.txt` nennt beim aktuellen Read noch den alten Installersha `daae22…`; die tatsächliche Datei hat `50b498…`. Das beeinflusst die ausgeführte Selbstprüfung des gepinnten Hilfsmoduls nicht, sollte aber vor Archivierung korrigiert werden. Die bekannte veraltete Platzhaltererwartung in `test_preparation.py` besteht ebenfalls noch; diese Datei trägt nicht den unabhängigen Laufzeitkontrollflussnachweis.

Keine neue Aussage über tatsächlich freien Dockerplatz oder erfolgreichen Nativeprobe. Der gemeldete reale Speicherengpass kann den Installer weiterhin bewusst vor Dienststopp abbrechen lassen. Eine mögliche gesonderte Sicherungsduplikat-Verlagerung ist **nicht** Gegenstand dieser Freigabe und benötigt eine eigene Prüfung. Keine Docker-, Live- oder Private-Datenaktionen durch den Reviewer.
