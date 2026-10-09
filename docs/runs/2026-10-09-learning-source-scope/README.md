# Gewohnheiten und Lernprüfung ohne Laden des Mailarchivs

Code **9f18408c8d6c8b0fd55c334cfc3ab184d933bb42**, Version **1.0.6-preview.9f18408**. Ergänzung der gemeinsamen Draft-Vorschau #46, ausgehend von `a70aaf0`. Keine neue Oberfläche, kein Modell, kein Neuimport und keine Schemaänderung.

Die Gewohnheitsanzeige lud bisher zweimal pro Gewohnheit sämtliche Quellen. Die Lernprüfung wiederholte dies und lud zusätzlich alle Quellen sowie wiederholt alle Vorschläge. Bei einem großen Mailarchiv verursachte schon dieser rein regelbasierte Weg unnötige Textobjekte und Arbeit, obwohl nur explizite Check-ins gebraucht werden.

Jetzt filtert SQLite vor dem Laden in Python nach exakten Gewohnheitsmarken. Die Wochenanzeige nutzt eine gemeinsame Datensatzliste für Zählung und einzelne Check-ins. Der Lernlauf lädt nur Belege aktiver Gewohnheiten und einmal die eigenen Lernvorschläge. Wiederholung eines Check-ins sucht nach dem exakten Herkunftsbezug, auch bei alten Quellen ohne die heutige Marke und auch nach Rücknahme. Dadurch entstehen weder Dubletten noch eine stille Wiederzulassung. Alte abgelehnte/angenommene Vorschläge bleiben sichtbar und werden nicht neu erzeugt. Der vorhandene Lernweg bleibt ein Vorschlag mit menschlicher Annahme.

Die Rohquellen-Getter erhalten alle Arten/Zustände und die bisherigen Sortierfolgen. Ausschluss, Zukunft, Summaries, Betrachtungszeitraum und Beleggültigkeit prüft weiterhin der fachliche Aufrufer. Matching verwendet weder LIKE-Wildcards noch eine erste allgemeine Quellenseite. Passende Belege werden nicht durch ein neues stilles Limit abgeschnitten; die bestehende Grenze der Mustererkennung bleibt erhalten.

## Nachweise

- Sieben neue Regressionen: fünf zeigen vor der Korrektur tatsächlich das Laden unbeteiligter Rohtexte/Vorschläge; zwei prüfen die zuvor fehlenden Getter. Die erste Testfassung hatte ungültige Fixture-Angaben (`EpisodeKind.EMAIL`, fehlende Aussagenart); sie ist ausdrücklich kein Fehlernachweis. Der gesicherte korrigierte RED-Lauf trifft die erwarteten Ursachen. Danach alle sieben bestanden.
- **141 betroffene Fälle** auf dem sauberen Codearchiv bestanden: Gewohnheiten, Mustererkennung, Service, tatsächliche Routes, Zeitplan, Episoden, öffentliche Speicherzugriffe, Vorschlagsbezüge, Welt-Lifecycle, Quellenfassungen und Migrationen. Eine bestehende Starlette/httpx-Warnung bleibt sichtbar. Kein frischer Backend-Gesamtlauf dieses neuen Standes behauptet; der vorherige breite Lauf ist im vorherigen Mail-Protokoll getrennt dokumentiert.
- Isolierte Mutation: alte drei aufrufende Module wieder eingesetzt, neue Getter erhalten. Genau die fünf Tests gegen unbeteiligte Textobjekte schlagen fehl; die beiden Getter-Kontrollen bestehen. Produktiver Arbeitscode wurde für diese Probe nicht verändert.
- [Enges unabhängiges Review](independent-review.md) ohne konkreten Blocker. Kein eigener Testlauf durch den Reviewer.
- Eine Vergleichsprobe auf bytegleichen künstlichen Datenbankkopien mit **5.000 unbeteiligten Mailquellen, 3 Check-ins und 1.000 anderen Vorschlägen**: gleicher angezeigter Tag, ein Lernvorschlag und drei Belege; Originale vor/nach unverändert und ihre Prüfsummen in beiden Varianten gleich. Geladene Episode-Objekte **25.018 → 12**, Proposal-Objekte **2.001 → 0**. Unter Python-Tracemalloc: rund **20,90 MB → 28,8 kB**, Laufdauer **1,3942 s → 0,0333 s**. Ein einzelner synthetischer Vergleich, keine Tages-, Akku-, Gesamt-RAM- oder Modellmessung. Vorher/nachher laufen mit derselben Tracemalloc-Instrumentierung.
- Fertiges lokales Abbild aus vorhandener Basis ohne Pull/Netzwerk gebaut; **269 Python-/112 UI-Dateien** gegen Manifest, 109 unveränderte Designquellen separat geprüft. Sieben künstliche Paketabläufe bestanden: alle vorherigen Gesundheits-/Quellen-/Kontakt-/Mailaufgaben-/Restore-Fälle plus tatsächliche Gewohnheits-/Lern-API mit unbeteiligtem Archiv, Wiederholung, expliziter Annahme, Quellenrücknahme und entwerteter historischer Aussage. Keine automatische Aussage, kein echtes Modell.
- Frische gepaarte ARM64-App/DMG mit gleicher Vorschauversion. Strenge tiefe Ad-hoc-Signatur und DMG-Integrität bestanden; die App im nur lesend eingehängten DMG ist dateigleich und ebenfalls gültig signiert. Nicht notarisiert, Intel nicht geprüft. UI/native Quellen unverändert; frühere Browser-/UI-/native Testzahlen bleiben historische Nachweise.

## Grenzen

SQLite kann unbeteiligte JSON-Dokumente weiterhin beim Filtern untersuchen; diese Änderung fügt keinen Index hinzu und behauptet keine konstante CPU-Zeit. Viele tatsächlich passende Check-ins/Vorschläge können weiterhin Aufwand verursachen. Die bestehende Quellen-/Mustergrenze wird nicht heimlich umgangen. Kein Nachweis echter Erkennungs-, Gedächtnis- oder persönlicher Lernqualität.

**Nicht installiert. Fenstertest ausdrücklich später.** Keine persönliche Mail-/Kalendertexte, EventKit-/Mikrofon-Nutzung, Cloudaufrufe, Modelle, Kosten oder Fortsetzung des pausierten Erstimports. Keine neue Atlas-Inventarisierung oder automatische Weltquellenaktivierung. Das Gesamtziel bleibt offen bis zur persönlichen Qualitäts- und Alltagsabnahme.

Vor tatsächlicher Installation ist eine geprüfte Sicherung des persönlichen Bestands erforderlich. Die Vorschau erbt EpisodeStore v21; die ältere persönliche App kann diesen Bestand nicht direkt öffnen. Eine Rückkehr braucht die geprüfte Sicherung von vor der Umstellung. Die synthetische Restore-Prüfung ersetzt keine persönliche Sicherung.

Dauerhafte Ablage: `/Users/sorenkube/Documents/Codex/Kingfisher-Pruefpakete/2026-10-09-learning-scope-9f18408/`. Ältere Pakete bleiben erhalten. Lokales Abbild `sha256:ede4448a83055a5a1e65b4000dc39cd91f0f5d9e08bc483f88f4e96a51421187`, nur lokaler Tag `ghcr.io/icarus-health/kingfisher-app:1.0.6-preview.9f18408`, nicht hochgeladen.

`freeze.json`, `package-inputs.json`, `verification.json`, `artifact-sha256.json`, Probe und komprimierte Rohlogs binden den Nachweis. Reproduktion des isolierten Paketablaufs nur mit lokal vorhandenem Abbild:

```sh
docker run --rm --network none --read-only \
  --tmpfs /data:rw,uid=1000,gid=1000 --tmpfs /tmp:rw,uid=1000,gid=1000 \
  -e ICARUS_DATA_DIR=/data --entrypoint python -i \
  ghcr.io/icarus-health/kingfisher-app:1.0.6-preview.9f18408 - < probe.py
```
