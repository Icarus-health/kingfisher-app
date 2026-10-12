# Ausführbare Einordnungsprobe, 11. Oktober 2026

Spätere Fortsetzung: [tatsächliche lokale 4B-Messung und fehlende Gewichte der eingestellten Modelle](../2026-10-11-live-category-quality/README.md). Der Offline-Bericht unten bleibt der ursprüngliche erste Aufruf.

Die acht [künstlichen Inhaltsfälle](../2026-10-10-native-and-category-boundary/quality-cases.json) können jetzt über `scripts/probe_category_quality.py` tatsächlich gegen ein lokales Ollama-Modell laufen. Persönliche Daten, App-Einstellungen und laufender Import werden nicht verwendet oder geändert. Der heutige echte Aufruf ergab **nicht ausgeführt**, nicht acht bestandene Fälle: Ollama ist nicht erreichbar. Keine Inferenz gestartet.

## Umfang und Bewertung

Der Läufer ruft dieselben `Categories.run`- und `list_for`-Funktionen auf wie Kingfisher, je Fall in einem eigenen temporären EpisodeStore. Es gibt keinen zweiten nachgebauten Klassifikator. Der unveränderte Originaldatensatz wird nach der Einordnung verglichen.

Gemessen werden ausschließlich Themenkategorien und wörtliche Personenerwähnungen. Die manuell vorgegebenen `required_categories` und `required_people` gelten für diese Probe als genaue Sollmengen; jede zusätzliche Kategorie oder Person ist eine Abweichung, auch wenn sie nicht zusätzlich unter `forbidden_categories` aufgelistet ist. Das ist eine strenge Prüfung gegen acht manuelle Beispiele, keine statistische Genauigkeit für einen persönlichen Mailbestand. Namenserkennung ist keine Identitätsauflösung. Bedingungen, Absagen, korrekte Aufgaben, Fristen, Quellenzeiten und spätere Antworten werden durch diesen Läufer nicht geprüft; entsprechende Notizen im Katalog sind zusätzliche Abnahmeanforderungen.

Eine gültige Blockreferenz allein reicht nicht zum Bestehen. Fehlende und zusätzliche Kategorien/Personen werden gesondert gemeldet. Ungültige Modellbelege zählen als Qualitätsfehler. Ein fehlender Dienst, ein Modell ohne nachgewiesene lokale Gewichte oder ein Inferenz-/Produktfehler zählen dagegen nicht als abgeschlossene Modellmessung. Versuchte Fälle, auswertbare Fälle und bestandene Sollmengen sind getrennte Zähler. Ein vollständig ausgeführter Lauf kann vollständig durchfallen.

Vor jeder künstlichen Quelle wird die vorhandene Produktionsprüfung `OllamaInventar` ohne Cache verwendet: GGUF-Gewichte, Digest, keine Cloud-/Remote-Kennzeichnung. Zugelassen ist ausschließlich ein HTTP-Loopback-Endpunkt ohne Zugangsdaten, Query oder Fragment. Metadaten- und Inferenztransport folgen keinen Redirects und übernehmen keine Umgebungs-Proxys. Kein Modelldownload, kein Dienststart, keine Cloud-Ausweichroute. Dies setzt wie die App voraus, dass der lokale Ollama-Dienst vertrauenswürdig ist.

## Aufruf und heutiges Ergebnis

Mit den Sidecar-Entwicklungsabhängigkeiten aus dem Repository, beispielsweise:

```sh
PYTHONPATH=sidecar:scripts python scripts/probe_category_quality.py \
  --model kingfisher-qwen3.5:9b-32k \
  --output /tmp/kingfisher-category-quality-new.json
```

Der Ausgabeordner muss existieren. Einen neuen Dateinamen verwenden; bestehende Berichte werden nicht überschrieben. Exit 0: alle acht exakten Sollmengen erfüllt; Exit 1: Lauf abgeschlossen, mindestens eine Abweichung; Exit 2: nicht ausgeführt/unterbrochen oder ungültiger Aufruf. Ein erneuter Lauf mit einem anderen Modell ist eine eigene Messung.

Tatsächlicher Aufruf mit dem finalen Läufer und dem in Kingfisher gewählten lokalen Einordnungsmodell, gespeichert in [local-offline.json](local-offline.json):

- Exit 2, `status: not_run`, `reason: ollama_unreachable`.
- Acht Fälle geplant, null versucht, null ausgewertet, null Modellaufrufe.
- `model_run_completed: false`, `personal_data_used: false`.
- Katalog- und Produktkategorien-SHA-256 im Bericht; keine privaten Texte, Zugangsdaten oder Kalenderinhalte.

## Frische Prüfung und unabhängiges Review

19 Läufertests und 104 betroffene bestehende Tests: **123 bestanden**, eine bestehende Starlette/httpx-Abkündigungswarnung.

```sh
PYTHONPATH=sidecar:scripts python -m pytest -q \
  scripts/test_probe_category_quality.py \
  sidecar/tests/test_memory_categories.py \
  sidecar/tests/test_category_diagnostics.py \
  sidecar/tests/test_local_category_quotes.py \
  sidecar/tests/test_category_feedback.py \
  sidecar/tests/test_people_mentions.py \
  sidecar/tests/test_ollama_inventar.py
```

Für diese Prüfung wurde eine getrennte, dauerhafte Python-3.12-Testumgebung unter `Kingfisher-Pruefpakete/Python-Testumgebung-20261011` mit den Sidecar-Entwicklungsabhängigkeiten erstellt, weil der alte temporäre Interpreter teilweise bereinigt war. `PYTHONPATH` lädt ausdrücklich den aktuellen Checkout. Das verändert keine Abhängigkeiten der installierten App.

Die positive Testantwort wird aus dem Katalog erstellt: Sie beweist, dass der reale Produktpfad alle acht Sollmengen passieren kann, und ist ausdrücklich keine echte Modellmessung. Weitere Tests prüfen gültige, aber sachlich falsche Antworten, unbelegte Blockreferenzen, Dienst-/Cloud-Ablehnung vor Anbieteranlage, Cloud-Wechsel während des Laufs und unveränderte Originale.

Das unabhängige Review fand zunächst zwei Messfehler: unaufgelistete zusätzliche Kategorien wurden akzeptiert; Ausfälle bei der Antwort wurden als abgeschlossener Lauf gezählt. Beide wurden mit drei neu fehlschlagenden Regressionstests reproduziert und korrigiert. Die Nachprüfung fand zusätzlich fehlende Mindest-Sollwerte; auch diese wurden zuerst fehlschlagend reproduziert und korrigiert. Vier Katalogtests verhindern Erfolg mit leerem, dupliziertem oder unvollständigem Katalog und leeren Kategorie-Sollmengen. Finaler Testlauf oben; kein kompletter Backend-Lauf und kein CI-Neustart.

## Persönliche App und offene Abnahme

Das installierte Paket bleibt `1.0.6-preview.6979131`; dieser Schritt ergänzt Prüfwerkzeuge, keinen neuen App-Build. Die [Kalender-/Installationsprüfung](../2026-10-11-daily-ux-installation/README.md) wurde lesend nachgeprüft: Kalenderfreigabe `granted`, Helfer online, 490 Termine, kein Fehler. Hintergrund-Gedächtnisübernahme weiter pausiert (`memory_allowed: false`). Computersteuerung meldet erneut einen gesperrten Mac, daher keine zusätzliche native Bedienabnahme.

Offen sind der tatsächliche Lauf mit erreichbarem Ollama, die Prüfung gegen persönliche Originale mit klar begrenztem Umfang, der Dateiimport im echten Fenster und der vollständige persönliche Mail→Gedächtnis→Aufgabe→Kalender-Arbeitstag. Ein bestandener Acht-Fälle-Lauf allein würde diese Abnahme nicht ersetzen. Keine neue Cloudfreigabe, keine Kosten und kein Merge nach main.
