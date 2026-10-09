# Unabhängiges Schlussreview: ungeprüfte Kategorie-Restfälle

**Begrenzt freigegeben: Der bestätigte fehlende Prüfweg ist behoben; kein neuer Blocker in den vereinbarten Gegenproben.** Geprüfter finaler Patch SHA256 **`25244a13586375dc9366aaad8d68adf4cd4867174bd9a2b207afacb44ad907b8`** aus `category-diagnostics-unverified-retry.patch`. Die Patchdatei stimmt mit dem tatsächlich gestagten Diff der isolierten Kopie `/private/tmp/kingfisher-category-diagnostics-20261009/repo` überein. Maßgeblich ist `source-manifest-unverified-retry.json`; die ältere `source-manifest.json` beschreibt weiterhin ausdrücklich den vorherigen 0d0c1ea-Stand.

## Bestätigte Korrektur

`deriveIntakeProgress.retryAvailable` berücksichtigt jetzt `categoriesUnverified`. `MailIntake.tsx` verwendet dieses Ergebnis für die Aktionssichtbarkeit; beim alleinigen Restbestand lautet die Aktion **„Weitere Einordnungen prüfen“**. Der Erklärungstext behauptet keine gespeicherten Fehlerursachen mehr und erläutert keine Statusabfrage-Implementierung: „Bei … weiteren Einordnungen ist der aktuelle Fehlerstand noch ungeprüft.“

Unabhängige Gegenprobe über echte synthetische Intake-/Store- und HTTP-Wege:

1. 19 Mails aufnehmen, für ihre Kategorieversuche gültigen Fehlerstatus mit künftigem Retry-Zeitpunkt setzen.
2. Die zuerst projizierten 16 Quellen über `WorkingMemoryStore.dismiss` ausschließen. Ohne Retry wählt `_pending` keine Quelle aus.
3. Postfach und Hintergrund pausieren. GET meldet 0 aktuell bestätigte Kategoriefehler, 3 ungeprüfte Fälle und Analyse inaktiv.
4. Die echte Frontend-Ableitung auf dieser API-Antwort liefert `retryAvailable=true`, `complete=false`, `stage=paused`, 76 % Gesamtfortschritt. Das tatsächliche JSX-Prädikat ist erfüllt; ohne anderen aktuellen Fehler gilt das Label „Weitere Einordnungen prüfen“.
5. Echter POST `/api/v1/mail/intake/a/retry` → HTTP 200. Der vorhandene Scheduler-Weckpfad wird genau einmal aufgerufen. Postfachpause, globale Pause und deaktivierter Zeitplan bleiben erhalten; kein Modell läuft an.
6. Der anschließend ausdrücklich als Diagnose aufgerufene normale begrenzte `Categories._pending(limit=20)` wählt **genau die drei übrigen aktuellen Quellen**, keine der 16 ausgeschlossenen. Einzelquellen-GET bestätigt für alle drei weiterhin `failed/provider_error`.

Das beweist Erreichbarkeit und Auswahlbereitschaft des erneuten Arbeitsgangs. Es behauptet keine bereits erfolgreiche Neueinordnung: Während der Hintergrund pausiert ist, bleibt die Ausführung entsprechend aus. Der explizite Wiederholungsweg nutzt den bestehenden Worker; es wurde kein eigener Modell-/Netzwerkaufruf der Statusanzeige eingeführt.

## Budget, Frische und verbleibende Grenzen

Die produktive Backenddatei `mail_intake.py` ist gegenüber dem unabhängig geprüften 16er-Budgetstand bytegleich. Die früher belegten Grenzen gelten unverändert: höchstens 16 verschiedene zusätzliche Originalprojektionen pro `Intake.status(account)`, gemeinsamer Cache über Ordner und Fenster, kein Gesamtbudget für alle Konten oder die Metadatenaggregate. Die vorherige synthetische Messung mit 1001 Originalen ergab 16 Projektionen/16 Snapshots; diese Lastmessung wurde hier nicht unnötig wiederholt.

Bloßes Neuladen prüft weiterhin denselben vorderen Diagnosebestand. Das ist keine fortschreitende Vollprüfung. Die jetzt sichtbare ausdrückliche Wiederholung erreicht die Restfälle jedoch über den separaten vorhandenen Worker-Auswahlpfad. Quellen außerhalb des Diagnosebudgets behalten zu Recht den ungeprüften Status ohne konkrete Ursache.

Die bereits geprüften Regeln zu aktueller Quellfassung, Entzug, Taxonomie, unbekanntem/NULL-Grund und schreibfreiem `preserve_on_failure` wurden nicht gelockert. **42 fokussierte Backendtests** (`test_category_diagnostics`, `test_mail_intake`, `test_mail_intake_routes`) und **26 Frontendtests** bestanden unabhängig. Eine bekannte Starlette/httpx-Abkündigungswarnung sowie Nodes vorhandene MockTimers-Hinweismeldung. Kein voller Regressionstest, Browserlauf, Build, echtes Modell oder private Daten durch diesen Reviewer.

Kleiner Dokumentationsrest ohne Produktblocker: `README-budget-followup.md` beschreibt im älteren Absatz weiterhin „how many saved reasons were not checked … during this status request“. Das entspricht nicht mehr dem korrigierten UI-Text bzw. den möglichen alten NULL-Gründen. Den Satz beim nächsten Dokumentationsabgleich an „ungeprüfte frühere Einordnungen“ angleichen. Die spätere Retry-Erklärung und das neue Manifest beschreiben den Funktionsstand korrekt.

## Fingerprints und Evidenz

- `sidecar/icarus_memory/mail_intake.py`: `820f9000e1dd641ff01061abb83ca68c998331570e74b51619d4ee7441204f75`
- `sidecar/icarus_memory/memory_categories.py`: `6687e729977eb967df4815bfc36d47adf1872fb6a2b638a2c42f9623a97b537d`
- `app/kingfisher/src/MailIntake.tsx`: `d9c6510d001b53bfeeaaf9211baa36b930e8873a7e6db5f0896f2a9cdbbb42c3`
- `app/kingfisher/src/mailIntakeProgress.ts`: `a48a2d99ba8ece791363d87a831930901f05b527d2681af7490fe57a8092af2b`

Echter API-/Store-Runner und Ergebnis: `/private/tmp/kingfisher-category-final-retry-review-20261009.py` und `.json`. Tatsächliche API-Antwort: `/private/tmp/kingfisher-category-final-retry-ui-state-20261009.json`; Frontend-Ableitung: `/private/tmp/kingfisher-category-final-retry-ui-review-20261009.json`. Der zuvor bestätigte Befund und die Budgetmessung bleiben in `/private/tmp/kingfisher-category-budget-review-20261009.md` erhalten.

Produkt und Archiv wurden nicht verändert. Es laufen keine weiteren Prüfungen auf dieser Fassung.
