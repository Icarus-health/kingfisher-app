# P2 · Regressionsexport bei wechselndem Mailaufnahmestand

Basis `6731dd5faf24b0d829a9054143e025d473309ae6`. Die Reproduktion und Prüfung verwendeten einen künstlichen Posteingang, eine synthetische Provider-Antwort und temporäre Datenbanken.

## Reproduktion und Ursache

1. Über den authentifizierten Gesprächsendpunkt eine Gedächtnisfrage zur künstlichen Bogenpresse stellen. Die projizierte Antwort enthält einen Quellenbeleg und endet mit dem Mailaufnahmehinweis für noch nicht vollständig eingelesene Nachrichten.
2. Die Nachricht per `POST /api/v1/rueckmeldungen` als falsch melden. Der Server antwortet mit 201. Ein anschließendes `GET /api/v1/rueckmeldungen` bestätigt denselben angezeigten Antworttext mit Hinweis und Quellenkennung.
3. Über `GET /api/v1/rueckmeldungen/faelle` den Fall exportieren. Der Fall enthält den verbotenen Beleg und unter `verboten.aussagen` die Antwort einschließlich Hinweis. Die Messlatte findet diese Fassung mit `gefundene_verbotene`.
4. Zwei synthetische Nachrichten erfassen und danach einordnen. Dieselbe Gesprächsnachricht zeigt zuerst den geänderten Hinweis und anschließend keinen Hinweis mehr. Der fachliche Text ist in allen drei Fassungen bytegleich. Die Messlatte liefert auf der Basis beim geänderten Hinweis trotzdem `()`, weil ihre normalisierte Teiltextsuche auch den früheren Hinweis erwartet.

Die Projektion liefert Hinweis und Text gemeinsam. Bei keiner oder mehreren Satzstrukturen exportierte die Rückmeldung den gesamten gespeicherten Anzeigetext als verbotene Aussage. Der Fehler lag in dieser Verwendung des Snapshots.

## Änderung und Grenzen

Die Rückmeldungsroute übernimmt den serverseitig erzeugten Hinweis aus den Metadaten derselben projizierten Nachricht in das bestehende JSON-Feld `struktur`. Die Aufnahmegrenze der Rückmeldung wird vor der Übernahme berücksichtigt, damit eine bei 20.000 Zeichen gekürzte Meldung keinen zufällig gleichlautenden Teil des eigentlichen Textes verliert. Der Export entfernt bei der ganzen Antwort exakt ein abschließendes `\n\n` plus den gespeicherten Hinweis. Fehlt ein gültiger Hinweis oder stimmt er mit dem Ende nicht überein, verwendet der Export den bisherigen Text. Der einzelne strukturierte Satz behält Vorrang.

Anzeigetext, Satz- und Belegstruktur und Quellenkennungen bleiben im Snapshot. Die Gesprächsprojektion bleibt die Quelle für die Meldung. Bestehende Einträge ohne das Feld behalten ihr bisheriges Exportverhalten. Das bestehende erneute Melden derselben Nachricht behält den ursprünglichen Snapshot. Arbeitsweisen bleiben ausdrücklich markiert und die vorhandenen Lernkontrollen gelten. Der Fix benötigt keine Schemaänderung und keinen zusätzlichen Modellaufruf.

Die neuen Prüfungen decken den authentifizierten API-Rundlauf mit wechselndem und verschwundenem Hinweis, einen einzelnen strukturierten Satz, mehrere strukturierte Sätze, einen echten gleichlautenden Textteil, fehlende, abweichende, leere und typfremde Metadaten sowie einen an der Speichergrenze gekürzten Snapshot ab. Die abgesicherte Messung betrifft wörtlich wiederkehrende Antworten gemäß der vorhandenen Messlatten-Normalisierung. Modellqualität und Bedienung waren außerhalb dieser synthetischen Prüfung.

## Prüfbefehle und Ergebnisse

Python 3.12.13 aus `/private/tmp/kf-core-20261104-env/bin/python`. Das Plugin unter `/private/tmp` sperrt Socket-Verbindungen für diese Pytest-Läufe.

```zsh
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:.:/private/tmp \
  /private/tmp/kf-core-20261104-env/bin/python -m pytest \
  -p kf_completion_confirmation_refused_socket -q \
  sidecar/tests/test_rueckmeldung.py::test_export_erkennt_gleiche_falsche_antwort_bei_geaendertem_mailaufnahmestand \
  | tee /private/tmp/kf-feedback-intake-20261105-red.log

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:.:/private/tmp \
  /private/tmp/kf-core-20261104-env/bin/python -m pytest \
  -p kf_completion_confirmation_refused_socket -q \
  sidecar/tests/test_rueckmeldung.py sidecar/tests/test_workflow_learning.py \
  sidecar/tests/test_cloud_workflow_learning.py sidecar/tests/test_intake_coverage_recall.py \
  | tee /private/tmp/kf-feedback-intake-20261105-green.log

git diff --check
```

- RED, Exit 1. Der Matcher findet die bytegleich wiederholte fachliche Antwort beim gewechselten Hinweis nicht. 1 fehlgeschlagen in 1,56 Sekunden.
- GREEN, Exit 0. 94 bestanden in 39,51 Sekunden. Beide Läufe zeigten die bestehende Starlette-Warnung zu `httpx` mit `TestClient`.
- `git diff --check`, Exit 0.

## SHA-256 der Änderungen

```text
d7d9aab50ef09e181c34c46d292021b2f54c4892589de22deccddd0965b0350b  sidecar/icarus_memory/rueckmeldung_routes.py
9e857ed27a054a818a7b732a2ab2354b96cf0f608d7b0f066805111f300bc160  sidecar/icarus_memory/rueckmeldung_faelle.py
faa155d8f567b53868882af444727cff16b70e96c369469dc074afceac9a5b5d  sidecar/tests/test_rueckmeldung.py
```

## Nachbesserung 01 · Review I1

Der erste Fix schützte einen gleichlautenden Teil der Antwort, wenn der Snapshot vor dem echten Hinweis endet. Bei 19.970 Zeichen Antworttext plus Hinweis speichert die Datenbank jedoch auch die ersten 30 Zeichen des echten Zusatzes. Der erste Fix erfasste für diesen Fall keine Metadaten. Die Messlatte fand deshalb die identische Antwort ohne Hinweis nicht.

Die Route prüft jetzt zunächst den vollständigen, exakten Zusatz am Ende der ungekürzten Gesprächsprojektion. Anschließend bestimmt sie anhand der bestehenden Speichergrenze und derselben Leerraumbehandlung, welcher Teil des Hinweises tatsächlich im Snapshot steht. Das JSON-Feld enthält nur diesen Teil. Der Export entfernt wie zuvor höchstens das passende Ende samt Trennzeile. Der gegenteilige Grenzfall mit echtem hinweisartigem Text bleibt abgedeckt. Ein zusätzlicher Test prüft, dass abweichende Projektionsmetadaten keinen Text entfernen. Snapshot, Einzelsatzregel, Altbestand und Lernsteuerung behalten ihre bisherige Behandlung.

```zsh
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:.:/private/tmp \
  /private/tmp/kf-core-20261104-env/bin/python -m pytest \
  -p kf_completion_confirmation_refused_socket -q \
  sidecar/tests/test_rueckmeldung.py::test_gekuerzte_meldung_exportiert_antwort_ohne_hinweisfragment \
  | tee /private/tmp/kf-feedback-intake-20261105-fix01-red.log

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:.:/private/tmp \
  /private/tmp/kf-core-20261104-env/bin/python -m pytest \
  -p kf_completion_confirmation_refused_socket -q \
  sidecar/tests/test_rueckmeldung.py sidecar/tests/test_intake_coverage_recall.py \
  | tee /private/tmp/kf-feedback-intake-20261105-fix01-green.log

git diff --check
```

- RED, Exit 1. Der Snapshot enthält nachweislich die ersten 30 Zeichen des Zusatzes. Der Matcher liefert für die Antwort ohne Hinweis `()`. 1 fehlgeschlagen in 0,73 Sekunden.
- GREEN, Exit 0. 35 bestanden in 7,29 Sekunden. Die bestehende Starlette-Warnung erschien in beiden Läufen. Die bereits im ersten Lauf geprüften Workflow-Learning-Suiten wurden für diese Korrektur an der Snapshot-Grenze gemäß Prüfumfang nicht erneut ausgeführt.
- `git diff --check`, Exit 0.

### SHA-256 nach Nachbesserung 01

```text
0cf4b3ea8136bc44a4c2ba3592d24fe044ea0f4ed571a7f19d43bb85444e7ec4  sidecar/icarus_memory/rueckmeldung_routes.py
9e857ed27a054a818a7b732a2ab2354b96cf0f608d7b0f066805111f300bc160  sidecar/icarus_memory/rueckmeldung_faelle.py
61cedfe424022b77fe1d63e91ccc00a406830dfc931d0ccdd6010fe708b18c62  sidecar/tests/test_rueckmeldung.py
```
