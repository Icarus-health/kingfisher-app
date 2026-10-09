# Automatische Aufgaben bleiben an den geprüften Quellenkontext gebunden

Code **d0733c6adf1e87b93548df78d9802cf43ba4a99b**, Ausgangspunkt main `3667e4e18b9e255780c755889370b46368cf0a6d`.

Eine Mail konnte bereits geprüft sein und als eigene Zusage im Briefing stehen, obwohl ihre Absenderzuordnung später zurückgenommen wurde. Eine abgeschlossene leere Erkennung wurde nach Kontaktkorrektur nicht erneut verarbeitet. Textdigest und Originalzitat allein erfassen diese Veränderung nicht.

## Verhalten

Neue Worker-Jobs und Vorschläge binden die bestehende Quellengeneration und den Metadaten-Digest. Kontextänderungen blenden alte gebundene Vorschläge sofort in Briefing/Queue aus und verhindern ihre erstmalige Annahme. Der Worker kann auch eine vormals leere Erkennung nach der Änderung neu prüfen; vor Review und vor Commit wird die aktuelle Bindung kontrolliert. Ein geänderter und wiederhergestellter Kontakt bleibt über die Generation als Änderung erkennbar.

Die Abdeckungsanzeige zählt eine Prüfung des alten Kontextes nicht weiter als aktuell abgeschlossen. Sie liest dazu nur die Kopfdaten, keine Volltexte. Alte ungebundene Abschlussjobs erscheinen konservativ als noch nicht im heutigen Kontext geprüft. Dies verliert keine Originalquellen oder bestätigten Aufgaben; es kann den angezeigten noch zu prüfenden Umfang erhöhen. Der Import wird hierdurch nicht eingeschaltet, kein Cloudanbieter aktiviert und kein eigener sofortiger Modelllauf angefordert.

Alte ungebundene gültige Vorschläge bleiben manuell prüfbar, im Briefing mit review_required. Ungültige Quellenköpfe, Anhang- und Berichtigungsbezüge werden auch für sie abgewiesen. Eine frische passende Prüfung ersetzt einen alten offenen Vorschlag atomar, statt zwei anzuzeigen. Alte explizite Ablehnungen bleiben erhalten; bereits angenommene Aufgaben derselben Episode/Originalstelle werden nicht wieder angeboten. Bestätigte Aufgaben, deren Bearbeitung und ihr Verlauf werden nicht automatisch geändert oder gelöscht.

Es gibt keine SQL-Migration: Der vorhandene Versionswert des Worker-Jobs bekommt die Kontextbindung; das Vorschlagsdokument erhält optional task_context. Alte Dokumente behalten beim Lesen/Schreiben ihre bisherige Form ohne diesen optionalen Schlüssel. Das Feld ist keine Selbstmodell-/Faktautorisierung und kein Bedeutungsbeweis.

## Tatsächliche Nachweise

- Ausgangszustand: **4 Fehler bei 1 bestandenem Schutzfall** (Rücknahme, nachträgliche eigene Identität nach leerem Ergebnis, Wiederherstellung, veralteter Fertigstand).
- **18 neue Fälle bestanden**: einschließlich Modellantwort-Negativurteilen, Kontextwechsel im Review, Altentscheidungen, Duplikatvermeidung, tatsächlichem korrigiertem Quellenbezug, Cursor und atomarem Rollback.
- Sauberes Git-Archiv des festen Codecommits: **217 betroffene Fälle bestanden** (Aufgaben, Queue/Pagination, Zeitlinien, Modellprotokoll, Abdeckung, Vorschlagsrelationen, Quellenstützung und Berichtigungen). Keine neue Backend-Gesamtsuite behauptet.
- Mutationen nur in zwei getrennten Archiven: konstante Quellengeneration löst **6 Fehler** aus; wieder eingeführter Legacy-Bypass löst die **3 Quellenbezugsfehler** aus. Produktcode unverändert während dieser Versuche.
- Enges unabhängiges Review fand und bestätigte die genannte Bypass-Korrektur. Protokolle und Prüfhashes erhalten.

Die erste Umsetzung lehnte auch direkte vorhandene Record-Wege ohne publizierten Quellenkopf ab: 23 betroffene Fälle scheiterten. Der Guard wurde präzisiert: ein fehlender Kopf allein ist kein Ersatz; ein bekannter abweichender Kopf wird abgewiesen. Ein breiterer Aufruf benannte versehentlich eine nicht existente Testdatei und sammelte keine Tests; dieses Protokoll ist kein Nachweis. Bestehender Starlette/httpx-Hinweis bleibt sichtbar.

## Grenzen und Lieferung

Die kontrollierten Modellantworten belegen die Weiterverarbeitung von Absage-/Bedingungs-/Fremdzusage-/nicht getragenen Titelurteilen; sie belegen **nicht**, dass ein echtes Modell diese Bedeutungen zuverlässig erkennt. Quellen können erst beim nächsten Scan-Durchlauf erneut ausgewertet werden, wenn sie hinter dem gespeicherten Cursor liegen. Ein deterministischer Zwei-Quellen-Fall zeigt diese Verzögerung. Bis dahin bleibt der alte gebundene Vorschlag blockiert; es wird keine sofortige Reanalyse versprochen. Ein großer noch unvollständiger Backlog kann die erneute Prüfung verzögern.

Keine persönlichen Texte, Kalender oder Mikrofone, keine Ollama-/Cloudinferenz oder Kosten. Kein Fenstertest, keine Installation und keine Aktivierung des pausierten Imports. UI-/Nativecode unverändert; kein neuer UI-/Mac-Bau dieses Einzel-Fixes. Der bekannte falsche Grafikprüfblocker von main wird getrennt durch PR #45 korrigiert und nicht diesem Fix zugerechnet. Kein CI-Neustart, Watcher oder Check-in.
