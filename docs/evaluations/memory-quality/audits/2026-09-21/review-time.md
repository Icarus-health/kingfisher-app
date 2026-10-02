# Unabhängiges Review: Personen- und Zeit-Patch

Stand 21.09.2026. Geprüft nach Stabilmeldung von `audit_identity_time`, einschließlich seiner letzten ignored/removed-Race-Regression. Lesendes Review der Produktionsänderungen, API/UI-Verbraucher und neuen Tests; keine Änderungen am Patch, keine erneute Vollsuite, kein Browser-/Modellaufruf. Eine gezielte synthetische Gegenprobe wurde ausgeführt.

## Reviewentscheidung

**Kein neuer blockierender Fehler im geprüften Patch gefunden.** Die begrenzte Korrektur trennt unbekannte Ereigniszeit von Aufnahme- und Claim-Erfassungszeit konsistent. Ein unabhängig gefundener, schon vor dem Patch vorhandener Source-Entzugsfehler wurde anschließend von `audit_identity_time` behoben und mit derselben unabhängigen Gegenprobe verifiziert. Eine allgemeine Abwesenheit von Source-Entzugsrennen wird weiterhin nicht behauptet.

## Geprüfte Eigenschaften

- `personen.py:149-156`: Ohne ausdrückliches `wartet_auf` wird aus dem Aufgabentitel keine Zuständigkeit mehr abgeleitet. Aufgaben werden nicht verändert. Die neue Ann/Joanna-Gegenprobe trifft einen realen früheren Fehler; bloße Wortgrenzen wären keine fachliche Lösung gewesen.
- `personen.py:225-242`: Nur tatsächliches `episode.occurred_at` setzt den letzten Kontakt. Unbekannt bleibt `None`; die vorhandenen Renderer/Sortierer in `Person.to_dict`, `_bauen` und `alle` behandeln None bereits. Ein späterer Import ohne Datum verdrängt keinen früheren belegten Kontakt.
- `graph.py:212-221,542-559,601-640`: Episode-Metadaten und Personen-/Projektprofile liefern nullable `occurred_at` sowie separates `recorded_at`. `last_interaction` wird nur bei bekanntem Ereigniszeitpunkt aktualisiert. Der Directory-Adapter (`graph.py:129-137,156-160`) sortiert/serialisiert Nullwerte ebenfalls ohne Fehler. Keine Änderung an den SQLite-Indexschemata oder kanonischen Quellen erforderlich.
- `person_digest_context.py:55-59,65-87`: Rohquelle und bestätigte Aussage nehmen Ereignis-/Aufnahmezeit aus der Originalepisode. `claim_created_at` bezeichnet separat die spätere Claim-Aufnahme. Der Fallback auf Aufnahmezeit wird ausschließlich zum Sortieren benutzt. Die neue zusätzliche Primärquellenabfrage hat einen Fehler-/Verfügbarkeitsguard, statt bei Concurrent Removal mit 500 abzubrechen.
- `person_digests.py:47-49`: Cache-Fingerprint-Version 3 invalidiert auch gespeicherte Ergebnisse mit alter Zeitsemantik. Zusätzlich gehen neue Zeitfelder in den Kontext-Fingerprint ein. Vorhandene API prüft beim Lesen den Fingerprint und nach der Modellgenerierung nochmals den aktuellen Kontext (`person_digest_api.py:23-28,53-60`). Ein alter Cache ohne `recorded_at` wird daher nicht als ready zurückgereicht.
- `person_digests.py:56-60,98-99,123`: Modell erhält die explizite Zeitunterscheidung; unbekannte Zeiten erzeugen weder ein erfundenes Quellenintervall noch einen None-Slicing-Fehler. Zitate übernehmen nullable Ereigniszeit und reale Aufnahmezeit aus dem serverseitigen Kontext.
- `app/kingfisher/src/api.ts:316-320,349-370`: Betroffene Typen sind nullable und tragen `recorded_at`. `MemoryProfile.tsx:18-21` hatte bereits einen Nullguard; alle betroffenen Anzeigen nutzen ihn. `PersonDigest.tsx:26` ruft den Datumformatierer nur mit einer tatsächlich vorhandenen Ereigniszeit auf und zeigt sonst „Ereigniszeit nicht angegeben“. Das Quellenintervall heißt jetzt ausdrücklich „Zeitraum datierter Quellen“. Kein ungeguardeter neuer UI-Datumzugriff gefunden.
- `test_person_identity_time.py`: API-Tests für fehlende/alte Ereigniszeit, rohe Graphmetadaten, tatsächliche Aufgabenzuordnung; Provider-Payload/Validator für unbekannte Zeiten; spätere Claim-Annahme und Race vor der neuen zusätzlichen Quelle-Abfrage. Erwartungswerte sind explizite Zeitpunkte statt Rückberechnung aus den Produktionshelfern.

Die von `audit_identity_time` gemeldeten 137 fokussierten Tests vor dem finalen Guard und 23 Tests nach dem finalen Guard wurden als dessen Nachweise gelesen, nicht als eigener neuer Testlauf ausgegeben. Root übernimmt Gesamttests und Browserprüfung. `git diff --check` war in diesem Review sauber.

## Im Review gefundener P1-Rest, nachweislich geerbt — Folgefix verifiziert

**Stelle:** `person_digest_context.py:55-62` (Rohquelle wurde bereits zu `sources` hinzugefügt; `_evidence_available` liefert inzwischen False und führt nur zu `continue`). Die neue Behandlung bei `primary_available=False` in Zeile 73-77 wird in diesem früheren Entzugsfenster nicht erreicht.

**Ablauf:** Synthetische Episode und bestätigter Claim einer Person; `collect` liest die Episode für den Raw-Kontext. Unmittelbar vor `_evidence_available` wird sie auf `ignored` gesetzt. Der echte Check erkennt den Entzug und verwirft den Claim. Der bereits erfasste Raw-Kontext bleibt aber bestehen und `messages(context)` enthält den inzwischen entzogenen Originaltext. Dies betrifft den nächsten vorbereiteten lokalen Modellrequest; ein tatsächlicher Modellaufruf war für den Nachweis nicht nötig.

**Baseline-Abgrenzung:** Dieselbe Gegenprobe lädt die ursprüngliche `person_digest_context.py` via `git show HEAD:...` und die aktuelle Fassung in getrennten synthetischen Apps. Beide ergeben:

```json
{"source_state":"ignored","raw_retained":true,"claim_retained":false,"revoked_text_in_model_messages":true}
```

Ausgangsnachweise: `review-time-race.py`, **before-only** `review-time-race-before-fix.json`; Originalmodulkopie nur als Scratch in `person-digest-context-baseline.py`. Damit ist dies **kein durch den Zeit-Patch eingeführter Fehler** und sollte nicht als dessen Regression bezeichnet werden.

**Folgefix:** `person_digest_context.py:61-66` verwirft bei negativem Kettencheck schon gesammelte Quellenzeilen, deren Episode-IDs zu diesem Claim gehören. Ich habe diesen vierzeiligen Patch erneut gelesen und exakt dieselbe unabhängige Gegenprobe wiederholt. `review-time-race-after-fix.json` hält fest: Baseline weiterhin `raw_retained=true` und `revoked_text_in_model_messages=true`; aktuelle Fassung für beide Werte **false**. `claim_retained=false` bleibt korrekt. Der ausführende Agent ergänzt zudem eine echte HTTP→FakeProvider-Regression mit unabhängiger gültiger Quelle, sodass der Kontext nicht bloß pauschal geleert wird; sein abschließender fokussierter Lauf meldet 24 bestandene Tests. Diese Tests wurden hier gelesen, nicht nochmals als eigene Suite ausgeführt.

Das konkrete Entzugsfenster ist damit geschlossen. Source-Withdrawal über jeden möglichen Zeitpunkt und jeden Quellenpfad benötigt weiterhin einen umfassenderen konsistenten Zugriffsnachweis; aus zwei geschlossenen Race-Fenstern folgt kein globaler Transaktionsbeweis.

Wiederholung aus dem Audit-Checkout:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts python ../memory-audit-evidence-20260921/review-time-race.py
```

Unveränderte Grenzen des Patches: Namensgruppen sind noch keine bewiesenen Personenidentitäten; Modellprosa kann trotz korrekter nullable Metadaten semantisch falsch sein. Das Patch verbessert die belegte Zeitgrundlage, liefert aber keinen semantischen oder globalen Concurrency-Nachweis.
