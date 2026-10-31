# Enges unabhängiges Review: manuelle Aufbewahrung eigener Zusagen

31.10.2026, Worktree `/private/tmp/kf-skill-categories-20261031`, neue Änderungen in `task_review.py`, `task_detection.py` und `test_own_promise_retention.py`.

**Abschließendes Urteil nach enger Nachprüfung: Beide konkreten P2-Gruppen sind geschlossen. Kein verbleibender nachweisbarer Blocker im geprüften Retentionsumfang. Die ursprünglichen Befunde bleiben unten dokumentiert; die abschließende Nachprüfung steht am Ende.**

## P2: Explizite Nichtzusage mit nie/niemals wird aufbewahrt

`_direct_own_delivery` verwendet `_FRAME_QUALIFIER`, das nicht/kein erfasst, aber nie/niemals nicht. Die Versandregex nimmt diese Wörter als Teil des Objekts an.

Unabhängig mit synthetischem EpisodeStore und tatsächlichem `review_tasks`, eindeutig eigenem strukturiertem Absender und Judge `information/false` reproduziert:

- `Ich werde dir die Kalkulation nie senden.`
- `Ich werde dir die Kalkulation niemals senden.`

Beide werden als RAW-Titel und Quote mit `requires_review=True` zurückgegeben. Es entsteht keine automatische Aufgabe, aber eine ausdrückliche Nichtzusage wird entgegen dem beauftragten Ausschluss negierter Aussagen erneut als Aufgabenvorschlag angeboten. Enge Negationskontrolle erforderlich; keine Erweiterung positiver Interpretation.

## P2: Aufhebender Betreff wird bei der Aufbewahrung ignoriert

Ebenfalls tatsächlich reproduziert: Betreff `Absage meiner Zusage`, Body der unveränderte öffentliche PROMISE-Text, eigener strukturierter Absender, Judge `information/false`. Die Retention liefert dennoch den positiven PROMISE-Text als Titel/Quote mit `requires_review=True`.

Der Helper prüft den Betreff auf Gleichheit mit der Episode und auf Weiterleitungsmarker, berücksichtigt aber seinen ausdrücklich aufhebenden Rahmen nicht. Damit ist die Behauptung einer vollständigen ungerahmten Zusage nicht erfüllt. Der positive RAW-Vorschlagstitel enthält die entscheidende Absage aus dem Betreff nicht; die Originalquelle selbst bleibt unverändert erreichbar. Auch hier verhindert die manuelle Kennzeichnung eine Autoanlage, aber der falsche positive Vorschlag sollte im engen Fallback gar nicht entstehen.

Beide Befunde wurden vor Abschluss an Root gemeldet. Eine enge konservative Ausschlussprüfung genügt; kein allgemeiner neuer Sprachparser ist gefordert.

## Geprüfte Grenzen ohne weiteren Befund

- Der Helper verlangt Episode, übereinstimmenden vollständigen Body und Betreff, aktive E-Mail-Message, genau einen strukturierten Absender mit `ich is True` und lesbarer Adresse. `own_source=True` oder Kopfmetadaten allein reichen nicht.
- Vollständiger Körper muss bis auf Rand-Whitespace der Originalquote entsprechen. Forward-/Zitat-/Gruß-/Signatur-/Zusatztext und die geprüften Nebensatz-/Bedingungs-/Unsicherheitsformen passen nicht in den engen Vollmatch. Datum/Uhrzeit werden lediglich zur Syntaxprüfung maskiert; zurückgegeben wird unverändert die Originalquote.
- `TaskReviewResult` bleibt listenkompatibel. Nur der neue Retentionszweig setzt `requires_review=True`. Der Detector übernimmt dies vor Speicherung und vergibt keinen positiven `/task-review-v1`-Marker. Das Briefing markiert Prüfung erforderlich; die tatsächliche Autoanlageprüfung stoppt mit `ungeprueft`.
- Konservativ gilt die fehlende positive Markierung für das gesamte Ergebnis dieser Prüfrunde. Das kann zusätzliche manuelle Prüfung bedeuten, erweitert aber keine automatische Berechtigung.
- Positive Judgepfade behalten ihren bisherigen gestützten Titel und Review-Marker. Die Frischeprüfung nach dem Review schützt weiterhin gegen Quellenentzug, Kontaktänderung und ersetzte Quellenversion. Keine Originaländerung oder neue bestätigte Verpflichtung.

## Eigene Verifikation

**35 gezielte Tests bestanden in 2,13 s**, ausschließlich das neue Testmodul. Dazu die drei oben bezeichneten unabhängigen Review-Reproduktionen (nie, niemals, Absage-Betreff). Ein weiterer Versuch mit einem zweiten Betreff im selben synthetischen Store wurde von dessen korrekter Source-head-Prüfung abgewiesen; daraus wird kein zusätzlicher Produktbefund abgeleitet.

Keine privaten Dateien, Modell-/Netzaufrufe, Produktedits, Commits oder Vollsuite. Die gemeldeten 153 Workerprüfungen sind nicht als eigene Ausführung gezählt. Ohne Versionsänderung werden abgeschlossene alte Jobs nicht automatisch neu geöffnet; der geplante J-Lauf muss auf seinem ausdrücklich vorgesehenen Aufgaben-Prüfstand separat erfolgen. Echte Modellqualität ist aus diesen geskripteten Fällen nicht abgenommen.

## Abschließende enge Nachprüfung

Geprüfte SHA-256 von `task_review.py`: `e5ccbd8883564bb2bb1b74d5b5a1037611e9efeb913d4f73a930fe717adb0306`, exakt wie angekündigt. Die Ergänzungen beschränken sich auf Ausschlüsse im neuen manuellen Retentionspfad: nie/niemals/weder und eindeutig aufhebende Betreffrahmen. Die gemeinsam verwendete allgemeine `_FRAME_QUALIFIER`-Regel und der positive Judgepfad wurden dafür nicht erweitert.

Die beiden ursprünglichen Negationsformulierungen und der exakte Betreff `Absage meiner Zusage` wurden mit dem tatsächlichen `review_tasks`-Pfad unabhängig erneut geprüft: **jeweils leere Ergebnisliste**. Zusätzliche enge Kontrollen `... weder senden noch schicken` und Betreff `Widerruf meiner Zusage` werden ebenfalls abgewiesen. Insgesamt fünf eigene synthetische Reproduktionen mit getrennten temporären Stores.

Die gezielten Basiskontrollen bestanden zusätzlich: **2 Tests grün in 0,33 s**. Das öffentliche m11-Original bleibt als unveränderter RAW-Vorschlag mit exakter Evidence und ohne positiven Review-Marker erhalten; Briefing verlangt Prüfung, und die tatsächliche Autoanlageprüfung blockiert mit `ungeprueft`. Ein wirklich positiver Judge behält weiterhin seinen gestützten Titel und Review-Marker.

Damit sind die beiden gemeldeten P2-Gruppen geschlossen. Kein erneuter breiter Audit, keine Modelle, privaten Daten oder Produktänderungen. Freeze für den geplanten getrennten J-Modell-/Semantiklauf aus diesem Reviewumfang möglich; dessen Ergebnis wird hier nicht vorweggenommen.
