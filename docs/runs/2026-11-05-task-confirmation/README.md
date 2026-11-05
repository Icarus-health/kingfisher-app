# Aufgaben: ausdrückliche Erledigung und verlässlicher Verlauf

Stand 05.11.2026. Teil A: `5d65ed77ca025cda418c7f2ac7ab857a6072b1df`.
Teil B (lokaler Aufgabenabruf): `2e47086e8d4706e8fa6c4d21d8fe8877c6b27755`.

Die [ursprüngliche Ablaufprobe](task-completion-recall-report.md) zeigte zwei
getrennte Lücken: Ein Modell konnte eine Aufgabe ohne zusätzliche Freigabe
erledigen. Außerdem wurde ein gespeicherter Aufgabenstand beim strengen
Gedächtnisabruf nicht als eigener Beleg berücksichtigt. Teil A behebt
die erste Lücke. Teil B ergänzt einen begrenzten, lokal geprüften Aufgabenabruf.

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

## Teil B: aktueller Aufgabenstand im Gespräch

Fragen wie „Ist Atlas Wartung erledigt?“ können die eindeutig benannte Aufgabe
jetzt direkt in der vorhandenen Aufgabenablage nachschlagen. Auch ein genauer
Aufgabenbezeichner ist möglich. Gleiche Namen, verworfene Aufgaben und alte
Einträge werden bei der Eindeutigkeit berücksichtigt; bei unklarer Zuordnung
erscheint kein geratener Stand.

Die Antwort unterscheidet gespeicherte Erledigung, Mailbezug und ausdrückliche
Bestätigung. „Aufgabe und Verlauf ansehen“ führt zum zugehörigen Eintrag, auch
wenn dieser außerhalb der letzten 100 Änderungen liegt. Die Antwort wird beim
erneuten Lesen gegen Aufgabe, Verlauf und Quellen geprüft. Wiederöffnen,
Quellenentzug und Archivieren entwerten die alte Antwort; Wiederzulassung macht
sie nicht automatisch erneut gültig. Ein neuer Abruf kann wieder einen gültigen
Stand zeigen. Statusfragen erzeugen keine neuen Gedächtnisquellen und rufen auf
diesem Weg kein Modell auf.

Das [erste unabhängige Review](task-status-recall-review01.md) fand zwei Fehler
bei wiederhergestellten Aufgaben und archivierten Quellen. Beide sind im
[Nachreview](task-status-recall-fix01-review.md) geschlossen; Spezifikation und
Codequalität des begrenzten Pakets sind freigegeben. Die Quellenablage erhält
dafür mit Migration 27 einen privaten Archivierungszähler. Originale,
Quellenköpfe, bestehende Belegfingerabdrücke und bestätigte Aussagen bleiben
unverändert. Upgrade einer echten v26-Testdatenbank, fehlgeschlagene Migration,
Triggerprüfung und Sicherungsfälle sind geprüft. Eine persönliche Migration
findet erst im normalen gesicherten Updateweg statt.

Der [Implementierungsbericht](task-status-recall-implementation-report.md)
enthält die chronologischen Gegenproben und Dateihashes. Vor dem Review bestanden
406 betroffene Backendtests, 18 UI-Tests und TypeScript. Nach den Korrekturen
bestanden 194 Kern-/Migrationsfälle und 19 gezielte Schema-Nachbarfälle. Diese
Zahlen überschneiden sich und werden nicht addiert. Die UI-Dateien blieben in
der Korrekturrunde unverändert. Eine bestehende Starlette-Warnung ist separat
ausgewiesen. [Maschinenlesbarer Nachweis für Teil B](task-status-validation.json).

Der begrenzte Weg verlangt den vollständigen Titel oder einen eindeutigen
Aufgabenbezeichner. Freie Umschreibungen, gemischte Aufgaben-/Quellenfragen und
die unabhängige semantische Qualitätsprobe bleiben offen. Die UI-Probe prüft
Rendering und den echten HTTP-Zielweg; der Klick mit Rücknavigation im nativen
Fenster ist noch nicht abgenommen. Bestehendes lokales Vorwärmen beim Öffnen
eines Gesprächs wurde durch dieses Paket nicht geändert oder als lastfrei
bestätigt. Der [ursprüngliche Entwurf](task-status-recall-design.md) bleibt als
Entscheidungsverlauf erhalten; die aktualisierte [Umsetzungsanforderung](task-status-recall-implementation-brief.md)
enthält die Reviewentscheidungen.

Es gab keine echte Modell-, Mac-Fenster- oder Alltagsabnahme, keine persönlichen
Daten in dieser Probe, keine Cloudaufrufe und keine Änderung der installierten
App. Der Großimport bleibt pausiert.
