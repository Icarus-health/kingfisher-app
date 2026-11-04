# Optionale Mistral-Prüfung eigener Arbeitsweisen

Stand: 04.11.2026. Basis `dec5dcb335eff33d50a7bd6f00bd509fbf6fbc92` (PR #120).
Unabhängig geprüfter Implementierungssnapshot: `112fad264fedaf46a665e2511792b19ab735ac5e`.
Die nachfolgende Korrekturrunde behebt die vier wichtigen Reviewbefunde.
Geprüfter Implementierungsstand nach Korrekturen: `22f1d4490d7348c3bbc331b4b1d0dcd3507c2bc2`.
GitHub-Lieferung: [Draft-PR #121](https://github.com/Icarus-health/kingfisher-app/pull/121), zunächst auf dem Branch der offenen Abhängigkeit #120. Noch kein Merge, Release oder Mac-Update.

## Ergebnis und Grenzen

Wiederholte, ausdrücklich markierte eigene Arbeitskorrekturen können optional mit Mistral geprüft werden. Die Vorschau zeigt das vollständige vorgesehene Paket aus Nutzeraufträgen, Korrekturen und relevanten Katalogmetadaten. Status und Vorschau lösen keinen Anbieteraufruf aus. Erst der einmalig bestätigte Start darf dieses Paket senden.

Verwendet werden der vorhandene Small-4-Adapter (`mistral-small-2603`), der regionale EU/EFTA-Endpunkt, die vorhandene Zugangsspeicherung und **dieselbe laufende Budgetinstanz wie beim Quellenimport**. Höchstens zwei Aufrufe, keine automatische Wiederholung nach Neustart, kein automatischer Wechsel von lokal zu Cloud. Ein Schlüssel oder Budget allein ist keine Datenfreigabe.

Quellen, Korrekturen, Katalog, Schlüssel, Budget und Modell bleiben an die Vorschau gebunden. Änderungen verhindern weiteren Versand oder Ergebnisübernahme. Der Cloudpfad prüft die externe Sensitivitätsgrenze unabhängig vom lokal konfigurierten Hauptmodell. Abbrechen verhindert weitere Verarbeitung; bereits verursachte Kosten bleiben verbucht.

Neue Entwürfe bleiben inaktiv und verwenden dieselben Prüf-, Aktivierungs- und Entzugsregeln wie lokale Vorschläge. Wiederverwendete Abläufe behalten Herkunft, Quellenbindung und tatsächlichen Zustand. Herkunft liegt im bestehenden, gesicherten Ablaufdatensatz; Ausführungsfreigaben und Kostenkontrollen werden nicht durch Wiederherstellen eines Inhaltsbackups zurückgesetzt.

**Keine echte Mistral-Anfrage durchgeführt:** Es gibt noch keinen API-Schlüssel. Die Tests beweisen die Kontroll- und Speicherabläufe mit künstlichen Daten und simuliertem Transport, nicht Mistrals Extraktionsqualität, aktuelle Modellverfügbarkeit oder tatsächlich berechnete API-Kosten. Keine persönlichen Inhalte übertragen, keine Mac-Alltagsinstallation geändert, Großimport weiter pausiert.

## Unabhängiges Review und Gegenproben

| Befund | Reparatur und Nachweis |
| --- | --- |
| Herkunft ging beim Wiederherstellen verloren | Herkunft beim Anlegen unveränderlich im Ablauf speichern; echtes `snapshot_all`/`restore_all` in ein frisches Datenverzeichnis geprüft. Jobfreigaben und Kostenbuch bleiben außerhalb dieses Inhaltsbackups. |
| Bereits vorhandene manuelle Abläufe erschienen als neue Mistral-Entwürfe | Wiederverwendung ändert keine Urheberschaft oder Quellen. Pending/aktive Fälle separat geprüft; Ergebnis nennt Wiederverwendung und tatsächlichen Zustand. |
| Geöffnete Detailansicht blieb nach Quellenänderung scheinbar gültig | Neuer Katalogstand entwertet Details sofort und liest sie neu. Übernahme bleibt gesperrt; Filter, offene Zeile und Bearbeitungsentwurf bleiben erhalten. |
| Ergebnis blieb nach Übernahme, Ablehnung oder Rücknahme auf „nicht aktiv“ | Status liest den tatsächlichen Ablaufzustand und die gespeicherte Herkunft. Anzeige aktualisiert sich auch bei Katalogänderung und Wiederöffnung. |

Sechs Backend-Regressionsfälle scheiterten vor den Reparaturen, danach bestanden sie. Die UI-Gegenprobe zeigte ebenfalls sechs erwartete Fehler vor dem Fix. Keine weitere unveränderte Vollprüfung als Ersatz für die fehlende echte Modellprobe.

## Abschließende Prüfungen

| Prüfung | Ergebnis |
| --- | --- |
| Kombinierte betroffene Backendtests einschließlich Backup/Wiederherstellung | 384 bestanden, 68,48 s; eine vorhandene Starlette/httpx-Abkündigungswarnung |
| Betroffene UI-Regressionen | 40 bestanden |
| Gesamte Frontendsuite | 1.050 bestanden |
| TypeScript, Produktionsbuild, `git diff --check` | bestanden; bestehender Hinweis auf große Build-Chunks |
| Gerenderter künstlicher Browserablauf, 1.280 und 390 Pixel | 20 Prüfungen bestanden; keine Konsolenfehler oder horizontalen Überläufe; null Anbieteraufrufe |

Die Backendtests verwenden den echten App-/Store-/Budgetpfad mit simuliertem Mistral-HTTP. Die Browserprüfung simuliert die App-API. Geprüft wurden Vorschau, explizite Zustimmung, einmaliger Start, Abschluss, Wiederöffnung, Abbruch, Übernahme/Rücknahme, Quellenentzug, Entwurfserhalt und Wiederverwendung eines manuell angelegten Ablaufs.

Backendaufruf:

```sh
PYTHONPATH=sidecar python -m pytest \
  sidecar/tests/test_cloud_workflow_learning.py \
  sidecar/tests/test_workflow_learning.py \
  sidecar/tests/test_mistral_import_provider.py \
  sidecar/tests/test_mistral_source_credentials.py \
  sidecar/tests/test_mistral_source_routes.py \
  sidecar/tests/test_mistral_source_jobs.py \
  sidecar/tests/test_cloud_import_budget.py \
  sidecar/tests/test_procedure_runtime.py \
  sidecar/tests/test_procedures.py \
  sidecar/tests/test_procedure_model.py \
  sidecar/tests/test_procedure_choice.py \
  sidecar/tests/test_rueckmeldung.py \
  sidecar/tests/test_chat_procedure_choice.py \
  sidecar/tests/test_mail_procedure_choice.py \
  sidecar/tests/test_procedure_categories.py \
  sidecar/tests/test_complete_recovery.py \
  sidecar/tests/test_backup.py -q
```

Frontend: im Verzeichnis `app/kingfisher` jeweils `npm test`, `npm run typecheck`, `npm run build`.
Lokale Browsernachweise: `/private/tmp/kf-cloud-learning-review-qa-20261104/` (`check.mjs`, `result.json`, Screenshots). Kein dauerhafter externer Previewdienst.

## Noch offen

- Schlüssel, konkret freigegebene kleine Mistral-Stichprobe und tatsächlicher Qualitäts-/Kostenvergleich.
- Direkte neue Lernbitten im Gespräch bleiben lokal/manuell. Dieser zusätzliche Cloud-Eingang ist hier nicht implementiert.
- Automatische Verwendung persönlicher Skills in Cloudantworten benötigt weiterhin einen gesonderten Datenfreigabepfad; keine bestehende lokale Grenze aufgeweicht.
- Native Mac-Bedienprüfung, normaler Updateweg und Alltagsabnahme. Diese Teillieferung schließt P2/P5 des Gesamtprodukts nicht ab.
