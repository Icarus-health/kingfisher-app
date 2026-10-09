# Unabhängiges Review: Gesamtbudget für Kategorisierungsdiagnosen

Isolierte Kopie `/private/tmp/kingfisher-category-diagnostics-20261009/repo`; Basis `ce39f71046581567d9915d1b06a73e991072f1f3`. Geprüfter Patch SHA256 **`0d0c1ea484858d1ff272feebe45f245a6980c0fed9cf7ff98130116e5078a003`**. Patchdatei und tatsächlich gestagter Diff stimmen überein. Keine Änderungen am Produkt, keine privaten Daten, Modelle, Downloads oder Netzwerkaufrufe. Alle nachfolgenden Daten sind synthetisch.

**Ergebnis: Das neue Budget begrenzt die zusätzlichen Originalprojektionen nachweislich. Vor Integration bleibt eine bestätigte P2-Bedienlücke für ausschließlich ungeprüfte Restfälle; der Anzeigetext sollte ebenfalls korrigiert werden.**

## P2: Restfehler verlieren ihren erneuten Prüfweg; Neuladen bewegt das Budget nicht weiter

`app/kingfisher/src/MailIntake.tsx:195` berechnet `retryFailed` nur aus Abruf-, Analyse- und frisch bestätigten Kategoriefehlern sowie `account.error`. `categoriesUnverified` fehlt. Die Aktion bei `:212` erscheint deshalb nicht, wenn nur ungeprüfte Restfälle übrig sind.

Über echte Intake-/Store-Methoden und GET-Endpunkte reproduziert:

1. 19 verschiedene synthetische Mails aufnehmen; kontrolliert gültige persistierte Kategoriefehler setzen.
2. Die ersten 16 vom Status geprüften Quellen über `WorkingMemoryStore.dismiss` ausschließen, drei weitere Fehler bestehen lassen; Postfach pausieren.
3. Einzelquellen-GET einer der letzten drei: **`status=failed`, `failure_code=provider_error`**.
4. Intake-GET: **`excluded=16`, `categories_failed=0`, `categories_unverified=3`, Gründe leer**. Alle übrigen `retryFailed`-Eingaben und Filterzähler sind null/0.
5. Dieselbe GET-Abfrage erneut ausführen: unveränderter Restbestand. Die ersten 16 dauerhaft gespeicherten, inzwischen ausgeschlossenen Fehlzeilen verbrauchen erneut das Budget. Der Client bekommt keinen Fortschritt durch bloßes „Stand neu laden“.

Die echte `deriveIntakeProgress`-Funktion liefert hierfür `complete=false`, `stage=paused`, Gesamtfortschritt 76 %. Der fehlende Knopf folgt aus dem gelesenen JSX-Prädikat; kein Browser-Rendering als zusätzlich geprüft behauptet. Pause wurde durch die GET-Prüfungen nicht aufgehoben, kein Store-Schreibzugriff ausgelöst.

**Kleine Korrektur:** ungeprüfte Restfälle müssen einen ausdrücklich ausgelösten Prüf-/Wiederholungsweg erhalten. Dabei weder automatische Wiederaufnahme noch eine bestätigte aktuelle Fehlerursache behaupten. Ein bloßer Neuladen-Hinweis genügt nicht, solange die Auswahl keinen Cursor/Fortschritt besitzt. Keine unbeschränkten Originalprüfungen als Lösung; das neue Gesamtbudget erhalten.

## Anzeigetext behauptet gespeicherte Ursachen und erläutert Technik

`MailIntake.tsx:65` nennt „gespeicherte Fehlerursachen … in dieser Statusabfrage“. Die neue Spalte ist nullable; alte Fehlschläge haben häufig keinen gespeicherten Grund. `categories_unverified` zählt persistierte Fehlstatus-Kandidaten, nicht gespeicherte Ursachen. Passender wäre etwa: **„Bei 3 früheren Einordnungen ist der aktuelle Stand noch ungeprüft.“** Dazu der konkrete Prüfweg aus dem P2-Befund. Aus diesem Text darf nicht folgen, dass weitere Polls automatisch andere Quellen prüfen.

## Budget und Frische unabhängig bestätigt

- Echter synthetischer Mail-Intake mit **7 eindeutigen, über Provider-ID geteilten Quellen in 2 Ordnern / 14 Intakezeilen**, Testfenster 2: Budget **0 / 1 / 16** erzeugt genau **0 / 1 / 7** `Categories.list_for`-Aufrufe und genau gleich viele `WorkingMemoryStore._snapshot`-Aufrufe. Eine Quelle wird pro Kontoabfrage nur einmal geöffnet, auch bei späterem Vorkommen im zweiten Ordner. Pro Ordner korrekt **0/7, 1/6, 7/0** aktuell fehlgeschlagen/ungeprüft; Gründe nur für geprüfte Quellen. Keine Datenbankänderung.
- Synthetischer größerer Bestand mit **1001 eindeutigen Originalen, 2002 Intakezeilen, 2 Ordnern und je zwei produktiven 1000er-Fenstern**: exakt **16** verschiedene Quellenprojektionen und **16** Original-Snapshots während des echten GET, **191 SQL-Anweisungen**, **0,016 s**, **0 Datenbankschreibzugriffe**. Je Ordner 16 bestätigte Fehler plus 985 ungeprüfte Kandidaten. Die fixturebedingte Anlage aller Originale liegt außerhalb der gezählten Statusabfrage; der Status lädt nicht alle Originalkörper.
- Die Grenze gilt pro `Intake.status(account)`, daher über alle Ordner/Fenster dieses Kontos. Eine API-Antwort mit mehreren Konten hat entsprechend mehrere solche Budgets. Die bisherigen Metadatenaggregate laufen weiterhin über alle Fenster; dies ist kein Gesamtbudget für sämtliche SQL-/Metadatenarbeit.
- Frühere echte GET-Gegenproben erneut bestanden: gezielte Taxonomieänderung → pending ohne Grund; Dismiss/Ignore/Source-Head-Ersatz → ausgeschlossen ohne Grund; Supportgeneration geändert → pending; aktuelle Quelle → provider_error; unbekannter bzw. alter NULL-Code → fester generischer Schlüssel `unknown`. Einzelquelle und Intake sind in diesen frisch geprüften Fällen konsistent.
- Unbekannter Rohcode wurde ausschließlich in einer temporären Testdatenbank unter vorübergehend deaktivierter CHECK-Prüfung erzeugt und gelangte nicht in die API. Kein behaupteter normaler Provider-Schreibpfad.
- Pause, `preserve_on_failure` ohne Status-/Diagnoseschreibzugriff und die vorhandenen Frischeprüfungen wurden durch die unabhängig ausgeführten fokussierten Tests bestätigt: **41 Backendtests** (`test_category_diagnostics`, `test_mail_intake`, `test_mail_intake_routes`) und **26 Frontendtests** bestanden. Eine bekannte Starlette-Abkündigungswarnung. Keine Vollsuite, kein UI-Build und keine private Lastmessung durch diesen Reviewer.
- Die vorhandene Zählweise eindeutiger Quellen pro Fenster und anschließender Ordnersummen wurde beibehalten; die Anzeige ist keine kontoübergreifend deduplizierte Quellgesamtzahl. Der requestlokale Cache macht den Status weiterhin nicht atomar. Beides ist von der jetzt nachgewiesenen Original-Ladegrenze getrennt.

## Evidenz

- `/private/tmp/kingfisher-category-budget-review-probes-20261009.json`: Budgetgrenzen, Mehrordner-/Fenster-Cache, echte GET-Restfehler und Lastmessung.
- `/private/tmp/kingfisher-category-budget-probe-20261009.py`: reproduzierbarer synthetischer Runner.
- `/private/tmp/kingfisher-category-budget-freshness-20261009.json`: acht erneut geprüfte Frische-/NULL-/Unknown-Szenarien.
- `/private/tmp/kingfisher-category-budget-ui-status-20261009.json`: tatsächliche API-Antwort für den fehlenden erneuten Prüfweg.

Keine Gegenproben laufen mehr auf dieser Archivfassung. Produkt und Reviewarchiv wurden nicht geändert; lediglich diese Review-/Evidenzdateien unter `/private/tmp` erstellt.
