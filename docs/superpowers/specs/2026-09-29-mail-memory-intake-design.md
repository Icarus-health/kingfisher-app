# Nachvollziehbare Erstaufnahme in das Kingfisher-Gedächtnis

Status: vom Nutzer freigegeben; umgesetzt. Abnahme und verbleibende Grenzen: ../../runs/mail-intake-20260929/README.md.

## Ziel und bestehende Grenzen

Verbundenen Mailbestand schrittweise und wiederaufnehmbar erschließen, neue
Nachrichten parallel aktuell halten und jederzeit verständlich zeigen, welche
Quellen bereits abrufbar, eingeordnet oder noch ungeprüft sind. Die Daten sollen
über Updates erhalten bleiben. Kategorien dienen der Orientierung; Originale und
Belege bleiben die Grundlage von Antworten. Eine fertige Verarbeitung ist keine
Garantie vollständiger oder fehlerfreier Erkenntnis.

Vorhanden sind Mailaufnahme mit kontoabhängigem Cursor, Duplikatschutz,
Quellenversionen, lokale blockweise Einordnung und getrennte Wissensvorschläge.
Der bisherige Cursor verarbeitet nur INBOX in aufsteigender UID-Reihenfolge.
`mail_sync_status` hält Ergebnisse des letzten Laufs, keine belastbare Gesamtmenge.
`MailSyncSettings` zeigt bislang den globalen Zeitplan als aktiv, auch ohne
ausgewähltes Mailkonto. Diese Teile werden erweitert, nicht ersetzt.

## Gewählter Ansatz

Persistente lokale Aufnahmeaufträge in der bestehenden SQLite-Datenhaltung.
Kein zusätzlicher Queue-Dienst, kein Cloud-Modell und keine neue Modellebene.
Ein großer synchroner Import scheidet aus: Er blockiert, ist schwer abbrechbar
und kann aktuellen Posteingang hinter historischem Bestand verhungern lassen.
Bloße häufigere Ausführung des bisherigen Cursors löst dieses Problem ebenfalls
nicht. Deshalb getrennte Fortschritte für Erstbestand und neue Nachrichten.

## Ablauf in der Oberfläche

1. **Bestand erfassen:** pro verbundenem Konto verfügbare Mailbereiche und deren
   Umfang ermitteln. Der Nutzer sieht vor dem Start, was enthalten ist.
2. **Quellen aufnehmen:** Inhalt in begrenzten Paketen abrufen und dauerhaft
   quellengebunden speichern. Bereits vorhandene Quellen wiederverwenden.
3. **Inhalte einordnen:** gespeicherte Quellen lokal auswerten. Neue Nachrichten
   erhalten regelmäßig Verarbeitungskapazität neben dem historischen Bestand.
4. **Ergebnisse prüfen:** Themen, Personenhinweise und Aufgaben-/Wissensvorschläge
   mit ihren Belegen anzeigen; Unklarheiten gesammelt zur Klärung vorlegen.

Der Nutzer startet die ausgewiesene Erstaufnahme einmal. Pause/Fortsetzen bleibt
jederzeit möglich. Konto verbunden, Abruf eingerichtet und Einordnung aktiv sind
drei getrennte Zustände. Ein aktivierter Zeitplan ohne ausgewählte Mailquelle
wird als „Noch kein Mailkonto zur Aufnahme ausgewählt“ angezeigt.

## Umfang der ersten Lieferung

Gmail-Posteingang, gesendete und archivierte Nachrichten sollen abgedeckt sein.
Gmail-Spezialordner werden anhand ihrer Servermerkmale ermittelt, nicht anhand
eines angenommenen deutschen oder englischen Namens. „Alle Nachrichten“ kann
den historischen Bestand abdecken; identische Nachrichten in mehreren Labels
dürfen keine mehrfachen Quellen erzeugen. Dafür providerstabile Kennungen
nutzen; Message-ID allein ist kein verlässlicher Primärschlüssel. Fehlt eine
solche Kennung, unterschiedliche Ordnerquellen nicht still zusammenführen.

Spam und Papierkorb bleiben ausgeschlossen. Anhänge sind in dieser Lieferung
sichtbar als nicht ausgewertet gekennzeichnet. Weitere Datenquellen können
denselben Auftragsstatus später verwenden; sie werden nicht nebenbei angebunden.

## Sinnvolle Einordnung

Zwei getrennte Ebenen: Aussageart (bestehende Bitte, Zusage, Änderung, Status,
Fakt, unklar, historisch, irrelevant) und optionale Themenkategorien
(Arbeit/Projekte, Termine/Buchungen, Finanzen/Verträge, Persönliches,
Information/Newsletter, Unklar). Mehrere Themen sind möglich. Kategorien werden
als automatisch vorgeschlagen markiert, korrigierbar und versioniert gespeichert.
Sie dürfen Treffer nicht aus der Suche entfernen oder Belegtext verändern.

Personen, Organisationen und Projekte sind eigene belegte Zuordnungsvorschläge,
keine Kategorienamen. Erwähnte Person und Absender bleiben unterscheidbar.
Gleiche Namen bewirken keine automatische Identitätsverschmelzung. Allgemeine
Postfächer wie info@ und technische Absender erzeugen keine unbestätigte Person;
ihre Inhalte bleiben verarbeitbar. Newsletter werden als solche behandelt und
im Umfang ausgewiesen, statt unbemerkt aus dem Vollständigkeitsbild zu fallen.
Jeder Vorschlag verweist auf aktuelle Originalstellen. Unsichere Zuordnungen
bleiben offen. Nutzerkorrekturen dürfen spätere Modellläufe nicht überschreiben.

## Fortschritt ohne Scheingenauigkeit

Für einen Erstlauf eine endliche Inventarversion mit Obergrenze je Mailbereich
erfassen. Zähler beruhen auf realen eindeutigen Arbeitseinheiten, nicht auf der
Differenz von UIDs. Neue Nachrichten gehören zum getrennten laufenden Abruf.
Bei noch unvollständiger Inventarisierung nur Aktivität und gezählte Nachrichten
anzeigen, keinen erfundenen Prozentwert.

Pro Konto und insgesamt getrennt anzeigen: inventarisiert, gespeichert, bereits
bekannt, eingeordnet, zurückgestellt, fehlgeschlagen und bewusst ausgeschlossen.
Beispielanzeige ausdrücklich nur als Muster: „Quellenaufnahme: 800 von 2.000;
Einordnung: 520 von 800 gespeicherten Quellen; 12 benötigen Aufmerksamkeit“.
Kein einziges „100 % fertig“, wenn noch Einordnung oder Wiederholungen ausstehen.
Restzeit erst aus gemessenem Durchsatz schätzen, als Schätzung kennzeichnen.
Inaktive Ansicht beendet keine Hintergrundarbeit. Neuladen und App-Neustart
stellen den gespeicherten Stand wieder her.

## Verarbeitung und Wiederaufnahme

Kleine Pakete, ein begrenzter lokaler Modellarbeiter und Rückstaugrenzen halten
RAM, Abruflast und Auswertung kontrollierbar. Vor jedem historischen Paket neue
Nachrichten berücksichtigen; ein fester fairer Anteil verhindert zugleich, dass
der Erstbestand bei dauerhaftem Neuzugang nie fertig wird. Auswertung ebenfalls
zwischen neuen und historischen Quellen aufteilen.

Aufträge speichern Konto, Mailbereich, Inventarversion, UIDVALIDITY, getrennte
Fortschritte, Zustände, Versuche und sichere Fehlercodes. Schreiben und
Fortschrittsbestätigung erfolgen atomar; wiederholte Pakete sind idempotent.
Einzelne defekte Nachrichten bleiben sichtbar wiederholbar und blockieren nicht
den gesamten Bestand. UIDVALIDITY-Wechsel erzwingt einen kontrollierten Neuabgleich.
Quellenänderung macht eine alte Auswertung ungültig. Bei Berechtigungsentzug
stoppen weitere Aufnahme und Modellaufrufe; vorhandene Regeln für Quellenentzug
gelten auch für Kategorien und Vorschläge. Pausieren löscht keine Quellen.

## Abnahme und Auslieferung

- Synthetische Postfächer mit Archiv, Gesendet, überlappenden Labels, neuen Mails
  während des Imports, generischen Absendern und gleichnamigen Personen.
- Neustart zwischen Schreiben und Fortschrittsbestätigung erzeugt keine
  Duplikate; Pause, Entzug, Einzelfehler und UIDVALIDITY-Wechsel nachweisen.
- Großer synthetischer Bestand: beschränkter Speicherbedarf, faire Verarbeitung,
  richtige Zähler und keine vollständige Mailbox als Modellprompt.
- Rückstau, lange/unvollständige Quellen und fehlgeschlagene Auswertungen bleiben
  sichtbar. Suchbarkeit und Vorschläge anhand der tatsächlichen Belege prüfen.
- Oberflächenprüfung vom verbundenen Konto bis zur auffindbaren Quelle,
  nachvollziehbaren Kategorie und offenen Rückfrage, einschließlich Neuladen.
- Bestehenden Pilotbestand sichern; Migration und Wiederaufnahme separat prüfen.
  Erst danach aktualisieren. Kein Zurücksetzen bestehender Konten oder Quellen.

Die Umsetzung wird in überprüfbare Teile zerlegt: zuerst Auftragsdaten und
Inventarisierung, dann fairer Abruf und Einordnung, danach Kategorien und
Fortschrittsoberfläche. Vor einer breiten Erstaufnahme einen begrenzten realen
Durchlauf mit den vorhandenen Konten prüfen. Testerfolge allein gelten nicht als
Beleg, dass das Gedächtnis im Alltag zuverlässig antwortet.
