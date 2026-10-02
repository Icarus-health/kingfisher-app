# M1d: Belegbindung und ausdrückliche Neubewertung

19. September 2026. Wiederaufnahme des erhaltenen Worktrees nach Abbruch der alten
Codex-Aufgabe. Basis `732ae59`; die Produktionsdateien entsprechen dabei dem bereits
integrierten PR #47. Die laufende private App wurde nicht verändert.

## Verhalten

Episode-gestützte Profilaussagen binden alle Originalzitate, Quelldigests, den
aktuellen Quellenkopf und die monotone Entzugsgeneration. Die lokale Freigabe
liegt getrennt von portablen Daten. Migration und gewöhnlicher Import erfinden
keine Zustimmung. Ein Ausschluss mit anschließender Wiederzulassung belebt keine
alte Freigabe. Mehrdeutige historische Quellenzuordnungen bleiben unverwendbar.

Unter Gedächtnis → Aussagen prüfen lassen sich Aussage und sämtliche Originalzitate
prüfen. Eine ausdrückliche Neubewertung erlaubt anschließend wieder lokale Antworten,
wenn alle Grundlagen verfügbar sind. Aussage, Bestätigungszeit und fachlicher
Zeitbezug bleiben unverändert. Veraltete, abgelaufene oder bereits verwendete
Vorschautokens können keine Freigabe erteilen. Ein Fehler beim nachgelagerten
Audit wird als Warnung angezeigt, wenn die lokale Freigabe bereits dauerhaft ist.

## Prüfumgebung und Grenzen

Alle neu angelegten Daten sind synthetische ORION-Beispiele. Native Testinstanz auf
Loopback-Port 18992 mit deterministischem RecordingProvider; eigener Docker-Container
auf 18993 mit separatem Volume. Die privaten Instanzen auf 8890/8891 blieben unverändert.
Der RecordingProvider zeichnet die tatsächlich an ihn übergebenen Nachrichten auf;
er ist kein Sprachmodell und qualifiziert weder Interpretation noch Antwortqualität.

Browserablauf: echte API und gebaute Kingfisher-Oberfläche, zwei Originalbelege,
Altbestand zunächst ausgeschlossen, ausdrückliche Neubewertung, unveränderte
Aussagedaten, Entzug des zweiten Belegs, veraltete Vorschau, Wiederzulassung ohne
Wiederbelebung, Ausschluss älterer Assistentenableitungen, Einmal-Token sowie Wechsel
zum externen Provider. Zusätzlich eigener Docker-Build, Bedienung der Belegprüfung
im Container und Neustart mit erhaltenem Belegstatus. Ergänzende isolierte UI-Tests
prüfen fehlschlagenden Graphabruf, verzögerte Bestätigung, Navigation während der
Bestätigung, Auditwarnung und schmale Darstellung der neuen Komponente.

Die unabhängige Codeprüfung fand zusätzlich eine mehrdeutige Altquellenzuordnung
und einen Umweg über `gedaechtnis_suchen`. Zusätzlich zitierte eine Policy-Ablehnung eine geschützte Regel. Alle Befunde wurden
mit roten Regressionen reproduziert, behoben und unabhängig nachgeprüft; die restriktive
Policy bleibt bestehen und gibt die Ablehnung ohne das geschützte Zitat aus.

## Abschlussnachweis

- Gesamte Backend-Suite: **1.540 bestanden**, zwei bestehende Deprecation-Warnungen,
  124,50 Sekunden (`.venv/bin/pytest sidecar/tests -q --tb=short`).
- Synthetische Diagnose-Runner: **143 bestanden** (`PYTHONPATH=sidecar .venv/bin/python
  -m pytest scripts/test_memory_probe_support.py scripts/test_memory_probe_agent.py
  scripts/test_probe_memory_pipeline.py -q`).
- TypeScript/Vite-Build, Asset-Vertrag (14 Dateien, 17 Icons), Legacy-JavaScript-Syntax,
  JSON-Schema und Beispiel sowie `git diff --check` bestanden.
- [Prüfansicht](Kingfisher-Belegpruefung.png), [13 Browser-/API-/Providerkontrollen](browser-checks.json), [nativer Neustart](native-restart.json),
  [Docker-Bedienung](docker-ui.json) und [Docker-Neustart](docker-restart.json) bestanden.
  Docker-Image: `f3c28f696747be51a9aae0a8b69b768ae2c155a2d6b45cc8cd0d3eeae84285eb`.
- [Unabhängiges Review](independent-review.md): alle Befunde geschlossen; 291 Regressionstests
  plus 114 Tests nach der letzten engen Korrektur bestanden. Diese Mengen überlappen.
- [Backend-Prüfmatrix](backend-report.md), [Frontend-Prüfung](frontend-report.md) und
  [SHA-256 des geprüften Codes und der Tests](reviewed-source-sha256.json) erhalten.

Die Browser-Gesamtprüfung lief vor der letzten engen Änderung an der nichtzitierenden
Policy-Ablehnung; deren eigene drei Produktionspfad-Regressionen, die vollständige Suite
und der finale Docker-Build liefen danach. Frontend und Belegprüfungsrouten blieben dabei
unverändert. Die Quellprüfsummen wurden nach allen Änderungen gegen den tatsächlichen
Worktree abgeglichen. GitHub-CI und PR-Status stehen im Pull Request; diese lokalen
Nachweise behaupten keine vorweggenommene CI- oder Produktfreigabe.

## Nachprüfung der Python-3.10-Kompatibilität

GitHub-CI am ersten Commit `7424101` bestand für Python 3.12, Desktop, UI und den
vollständigen Containerablauf. Unter Python 3.10 scheiterten 38 Tests an derselben
Ursache: `datetime.fromisoformat` akzeptiert dort das vom bestehenden Serializer
verwendete UTC-Suffix `Z` noch nicht. Der native Python-3.12-Lauf konnte diesen
Versionsunterschied nicht erkennen.

Die enge Korrektur normalisiert ausschließlich ein abschließendes `Z` zu `+00:00`.
Zeiten ohne Zeitzone und fehlerhafte Zeichenfolgen bleiben abgelehnt; die kanonische
Identität bleibt über äquivalente Zeitzonen hinweg gleich. Zehn Regressionen prüfen
UTC, positiven Offset, fehlende Zeitzone und fehlerhafte Suffixe. Der Fehler wurde
mit tatsächlichem Python 3.10.21 reproduziert (ein fehlgeschlagener, neun bestandene
neue Fälle vor Korrektur). Dabei zeigte sich zusätzlich, dass Python 3.10 ein
doppeltes `Z` nach bloßer Ersetzung zu großzügig interpretiert; die enge Normalisierung
weist deshalb eingebettete `Z` und ein Suffix ohne vorangehende Ziffer zurück.
**93 Beleg-/Verdichtungstests bestanden anschließend unter tatsächlichem Python 3.10.21**
im isolierten Container (4,44 Sekunden). Die [unabhängige Nachprüfung](python310-review.md) ist abgeschlossen; 61
Belegtests bestanden dort unter Python 3.12.13. Die erneute vollständige GitHub-Matrix wird am neuen
PR-Head geprüft; der PR enthält den finalen CI-Status.

## Verbleibende Produktgrenzen

- Alte Gesamtsicherungen können frühere Widerrufszustände zurückbringen. Der vollständige
  Lösch-/Restore-Vertrag und eine Restore-Quarantäne bleiben ein eigenes Arbeitspaket.
  Das Neubinden des Prüfdiensts nach Restore löst dieses historische Problem nicht.
- M2c: vollständige kanonische Aussagefelder und getrennte Ereignis-/Importzeiten im
  ClaimStore-Modellkontext bleiben offen.
- Reale Modellqualifikation, belastbare Antwortqualität, Geschwindigkeit und Alltagstest
  bleiben offen. M1d verändert weder die alte Funktionsquote noch die Produktfreigabe.
- Die neue Prüfansicht ist keine allgemeine mobile Neugestaltung und keine erneute
  Abnahme aller kanonischen Screens.
