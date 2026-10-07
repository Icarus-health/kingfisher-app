# Ein durchgehender Alltag mit Kingfisher

Freigegeben am 7.10.2026 im Gespräch: bestehende Oberfläche behalten, Wissen lokal und beleggebunden halten, weniger Klicks und brauchbare Mail-/Kalender-/Aufgabenabläufe. Keine neuen Cloud-Aufrufe, Kosten oder Kontoanmeldungen ohne die dafür fehlenden Angaben. Maßgeblich bleiben `docs/00-produktvision.md` und `docs/41-zielbild.md`.

## Fertig bedeutet

Die nächste nutzbare Lieferung verbindet vorhandene Abläufe, statt weitere Kanäle zu bauen. Quellenprobleme und Zeitpunkt des Überblicks stehen sichtbar oben. Nachrichten lassen sich direkt aus Heute öffnen. Aufgabenvorschläge benötigen eine zweite, begrenzte inhaltliche Prüfung; Newsletterthemen, allgemeine Empfehlungen, fremde Verpflichtungen und unbelegte Zusätze dürfen nicht durch bloße Zitatgleichheit als Handlungsbedarf erscheinen. Originale bleiben zugänglich, auch wenn Prüfung/Modell ausfallen. Eine geprüfte vorgeschlagene Aufgabe kann nach einem ausdrücklichen Klick lokal angelegt werden; Fristen/Personen/Projekte werden nicht geraten. Versand bleibt im bestehenden Freigabeablauf.

## Globale Grenzen

- Keine Änderung oder Löschung persönlicher Bestände/Zugänge. Isolierte künstliche Daten für Bedienprüfung.
- Keine Aussage, dass ein zweiter Modellaufruf Wahrheit garantiert; weiterhin Vorschläge.
- Bestehende Quellen-/Modellwechsel-, Widerrufs- und Digest-Prüfungen erhalten.
- Vordergrund höchstens drei Kandidaten; bestehende Hintergrundextraktion bis zu 31 Kandidaten gemeinsam in einer begrenzten Prüfung; nur prüfen, wenn Kandidaten vorhanden sind; bestehender Cache verhindert wiederholte Arbeit.
- Vorhandene lokale Modellgewichte nacheinander verwenden; keine zusätzlichen großen Modelle laden.
- Vorhandene freigegebene UI-Assets und Layouts verwenden.

## Task 1: Aufgabenerkennung fachlich absichern

Gemeinsame zweite Prüfung für Mailüberblick und Hintergrundvorschläge. Nur ausdrücklich beurteilte Kandidaten übernehmen; vollständigen Mailkontext und Originalzitat zur Prüfung geben. Fehler/ungültige Ausgabe: keine Aufgaben, sichtbarer Prüfhinweis beim Mailüberblick. Keine erneute Generierung von Titeln. Tests zuerst: Newsletter, echte Bitte, fremde Zusage, erfundener Titelzusatz, unvollständige Prüfausgabe, Modellfehler, Negation, unveränderte Quellen-/Cache-Grenzen.

## Task 2: Heute als Einstieg in die tatsächliche Arbeit

Sichtbarer Quellen-/Aktualitätsstreifen mit eindeutiger Kalender-/Mail-Lücke, direktem Reparaturlink und Aktualisierung. Keine Aussage „alles erledigt“, wenn Quellen fehlen. Neu-im-Blick-Mails direkt im vorhandenen Leser öffnen. Bestehende Wissenshinweise führen zu ihren Quellenansichten; eine neue allgemeine Kläransicht gehört nicht zu dieser Lieferung. Begrenzte automatische Aktualisierung bei Rückkehr/Intervall ohne parallele Abruflawine; Antworten älterer Abrufe dürfen jüngere nicht überschreiben.

## Task 3: Weniger Klicks aus der Nachricht zur Aufgabe

Neben Bearbeiten eines Vorschlags direkte ausdrückliche Übernahme als lokale Aufgabe. API prüft Original/Digest erneut; keine automatische Frist oder Identitätszuordnung. Busy-/Fehler-/Erfolgzustände, keine Doppelübernahme, nach Erfolg Aufgabenlink. Manuelle Aufgabe und Antwortentwurf bleiben möglich. Wiederholte Vorschlagserzeugung in einem bereits vorausgefüllten Formular vermeiden.

## Task 4: Unabhängige Prüfung und Mac-Test

Reproduzierbare künstliche Alltagsszenarien für Mail → Überblick → Aufgabe → Heute, Newsletternegativfall, fehlender Kalender, veränderte Quelle. Betroffene Tests, komplette UI-Tests, Typecheck/Build, Backendregression. Ein unabhängiger Review des gesamten Diffs, Funde gezielt korrigieren. Bedienprüfung im getrennten Testfenster auf dem Mac; keine echte Mail senden. Auslieferungsstand und offene Konto-/Cloudschritte exakt dokumentieren.

## Review Focus

Ein Modellurteil darf keine bestätigte Tatsache werden. Prüfer darf keinen unvollständigen Kontext als vollständige Prüfung behandeln. Quellenwechsel während des zweiten Aufrufs und verspätete UI-Antworten dürfen keine alte Aufgabe erzeugen. Direkte Übernahme braucht einen echten Nutzerklick und erneute Quellengleichheit. Unverbundener Kalender ist nicht „keine Termine“. Automatische Aktualisierung darf nicht teuer werden oder bearbeitete Eingaben überschreiben.
