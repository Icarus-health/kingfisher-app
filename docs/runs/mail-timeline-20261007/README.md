# Maildatum und heutige Aufgaben · 7. Oktober 2026

## Problem und begrenzte Korrektur

Quelldatum (`occurred_at`) und Erfassung (`recorded_at`) waren vorhanden, wurden aber bei der Auswahl unbestätigter Aufgaben auf Heute nicht ausreichend unterschieden. Eine heute importierte Bitte aus 2015 konnte dadurch als heutige Arbeit erscheinen.

Die Auswahl berücksichtigt jetzt den historischen Erstbestand (`mail_intake_items.lane=history`), fehlende/naive und zukünftige Quelldaten sowie eine Sieben-Tage-Grenze. Solche Vorschläge bleiben unverändert zur ausdrücklichen Prüfung erhalten; sie werden weder gelöscht noch als erledigt behauptet. Bestätigte Aufgaben laufen unabhängig von diesem Fenster weiter. Bei nicht-Mail-Quellen bleibt die bisherige Auswahl erhalten.

Bekannte weitere Nachrichten werden über exakte Message-ID-/In-Reply-To-/References-Header verknüpft, kontogebunden gehasht. Kein Raten anhand Betreff oder Person. Bei älteren Elternquellen ist die bereits gespeicherte Message-ID-Herkunft nutzbar. Der Link bevorzugt das neueste Quelldatum, nicht die Importreihenfolge. Eine weitere Nachricht erzwingt Kontextprüfung, behauptet aber nicht automatisch Absage oder Erledigung. Neue Header ergänzen nur Metadaten; Original, ID, Erfassungszeit, Bestandszuordnung und ausgeschlossene Quellen bleiben erhalten. Anhänge und Beteiligtennachtrag bleiben im bestehenden Ablauf.

Kandidaten werden in 200er-Batches gelesen. Mehr als 200 historische Vorschläge blockieren neue Quellen nicht. Ein geteilter ReplyIndex liest Header-Hinweise höchstens einmal pro Anfrage und hält maximal 50.000 verschiedene Referenzen; bei unvollständiger Prüfung ist ausdrückliche Prüfung erforderlich. Das ersetzt keinen allgemeinen skalierbaren Zeitgraphen. Die manuelle Prüfliste zeigt weiterhin bis zu 100 gültige Vorschläge gleichzeitig.

## Prüfung

- Betroffene Backend-Tests auf dem finalen Stand: 182 bestanden (54,24 Sekunden).
- Nach dieser Verbesserung: 52 Timeline-/Mailbriefing-Tests bestanden, einschließlich rot/grün belegter Auswahl nach Quelldatum und Prüfung auf genau einen Header-Scan über mehrere Batches.
- Weitere Briefing-, Zeitzonen-, Sicherungs-, Wiederherstellungs- und Mailimport-Tests: 98 bestanden.
- Release-/Updater-/Mac-Start-Vertragstests: 98 bestanden, ein bereits bedingter Test übersprungen. Der zusätzliche Swift-Logiktest ist lokal durch Compiler-/SDK-Versionskonflikt blockiert (auch mit explizitem vorhandenem SDK); keine Swift-Änderungen in diesem Patch. Der Release-Workflow muss den Mac-Build bestätigen. Lokale Socket-Tests bestanden nach Freigabe des lokalen Testservers.
- UI: 292 Tests bestanden; Typprüfung und Produktionsbuild bestanden. Bekannte Bundlegrößenwarnung unverändert.
- Unabhängiges Review: Fehler beim Headernachtrag (Identität/Ausschluss), Beteiligten und Anhängen behoben und geprüft; final keine Blocker.
- Isolierte native Mac-App auf Port 8893, ausschließlich künstliche Daten: 2015, unbekanntes Datum, frischer Bestandsimport und spätere Absage erscheinen als vier ungeklärte Vorschläge; nur eine echte zeitnahe Bitte steht auf Heute. Prüfliste zeigt beide Zeiten, unbekanntes Datum ausdrücklich und die verknüpfte Absage im Original. Geöffnete 2015-Mail zeigt historischen Hinweis und Originalauszug; manuelles Festhalten bleibt verfügbar, schnelle Übernahme fehlt. Lokales Modell, keine echten Konten, kein Versand, keine Cloud.

## Grenzen

Das ist eine Korrektur der zeitlichen Aufgabenauswahl, keine Behauptung eines fehlerfreien Gedächtnisses. Historische Quellen ohne gespeicherte Referenzheader werden nicht vollständig nachträglich verkettet. Auch eine zeitnahe Bitte ist nur ein Vorschlag. Bereits bestätigte Aufgaben werden nicht automatisch aufgrund einer Antwort geschlossen. Es gibt keine neue allgemeine Timeline-Seite und keine pauschale Neuauswertung aller Bestandsmails.

## Auslieferung

Version 1.0.5 für den vorhandenen Updater vorbereitet. Tatsächliche Veröffentlichung, Installation und Datenprüfung werden nach erfolgreicher Durchführung ergänzt.
