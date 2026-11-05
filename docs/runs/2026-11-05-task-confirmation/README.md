# Aufgaben: ausdrückliche Erledigung und verlässlicher Verlauf

Stand 05.11.2026, Codecommit `5d65ed77ca025cda418c7f2ac7ab857a6072b1df`.

Die [ursprüngliche Ablaufprobe](task-completion-recall-report.md) zeigte zwei
getrennte Lücken: Ein Modell konnte eine Aufgabe ohne zusätzliche Freigabe
erledigen. Außerdem wurde ein gespeicherter Aufgabenstand beim strengen
Gedächtnisabruf nicht als eigener Beleg berücksichtigt. Dieses Paket behebt
die erste Lücke und bereitet den Belegvertrag für die zweite vor.

## Geändertes Verhalten

Eine vom Modell verlangte Erledigung benötigt standardmäßig eine Freigabe.
Die lokale Bestätigung zeigt Titel und Kennung. Wird die Aufgabe zwischen
Vorschlag und Ausführung geändert, verfällt die Freigabe; die Prüfung und die
Änderung erfolgen gemeinsam in der vorhandenen Aufgabendatenbank. Das gilt
auch für zwischenzeitliches Erledigen und Wiederöffnen sowie Änderungen durch
eine zweite Store-Instanz. Das bloße Zurückändern eines Titels macht eine alte
Freigabe nicht wieder gültig.

Der direkte Klick auf „Erledigt“ bleibt eine einzelne Aktion. Neue ausdrückliche
Bestätigungen erhalten einen eigenen Verlaufseintrag. Ein wiederholter Klick
erzeugt keine doppelte Bestätigung. War die Aufgabe vorher schon als erledigt
gespeichert, bleibt ihr Erledigungszeitpunkt erhalten; die spätere Bestätigung
hat ihren eigenen Aufzeichnungszeitpunkt.

Bewusst eingerichtete Dauerregeln bleiben möglich. Solche Ausführungen, alte
Erledigungen und mailgestützte Zustandsänderungen werden nicht nachträglich zu
ausdrücklichen Nutzerbestätigungen umgedeutet. Der Verlauf behauptet weiterhin
keine verifizierte handelnde Person. Bestehende Daten bleiben unverändert.

Externe MCP-Aufrufe erhalten weder den neuen lokalen Titelvorschautext noch
interne Aufgabenstände über die Freigabeliste. Der tatsächliche MCP-Aufruf und
das spätere Lesen seiner Freigabeliste sind in den Tests getrennt geprüft.

## Nachweise und Grenzen

- [Implementierungsbericht](completion-confirmation-report.md) mit Befehlen,
  fehlgeschlagenen Gegenproben vor der Änderung und finalen Dateihashes.
- [Unabhängiges Review](completion-confirmation-review.md): Spezifikation und
  Codequalität bestanden; kein kritischer oder wichtiger Befund.
- 393 verschiedene betroffene Fälle bestehen über zwei Offline-Läufe. Im
  breiten Lauf unterbrach eine strenge Socket-Sperre zwei erwartete lokale
  Verbindungsversuche. Genau diese zwei Fälle bestanden anschließend mit
  simuliertem Verbindungsfehler, weiterhin ohne Netzwerk. Keine Addition
  überlappender Tests und kein vollständiger neuer Backendtest.
- TypeScript-Prüfung mit vorhandenen Abhängigkeiten bestanden.
- [Maschinenlesbarer Nachweis](validation.json).

Ein kleiner MCP-Bedienhinweis bleibt offen: Die bisherige Antwort verweist auf
„Gespräch“, obwohl eine ausschließlich über MCP erzeugte Anfrage keiner
Gesprächskarte zugeordnet ist. Sie ist über die authentifizierte lokale API
auflösbar; eine passende normale Bedienoberfläche ist noch nicht abgenommen.

Der [Entwurf für Aufgabenstatus im Abruf](task-status-recall-design.md) ist
**noch nicht implementiert**. Die normale Gedächtnisantwort kann den aktuellen
Aufgabenstand deshalb weiterhin auslassen. Geplant sind eigene überprüfbare
Aufgabenbelege, eindeutige Auswahl und Entwertung alter Antworten bei
Zustands- oder Quellenänderung; allgemeine Umschreibungen bleiben ein eigener
Qualitätsschritt. Ein Status im TaskStore wird nicht als erfundene Mailquelle
oder bestätigte Wissensaussage ausgegeben.

Es gab keine echte Modell-, Mac-Fenster- oder Alltagsabnahme, keine persönlichen
Daten in dieser Probe, keine Cloudaufrufe und keine Änderung der installierten
App. Der Großimport bleibt pausiert.
