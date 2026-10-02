# Filter in Nachrichten

2026-09-08: Nachrichten bietet Posteingang, Ungelesen, Newsletter, Spamverdacht und Alle sowie eine Kontenauswahl. Standard ist Posteingang; unklare oder nicht klassifizierte Mails bleiben darin sichtbar. Spamverdacht umfasst auch ausdrücklich gesperrte Absender. Ungelesen und Alle berücksichtigen sämtliche Kategorien.

Der Kontofilter wird vor dem Abruflimit angewandt. Zähler und Kategorien beziehen sich auf höchstens 30 neueste Mails in INBOX, nicht auf das gesamte Postfach; eigene Spamordner werden nicht abgerufen. Die Oberfläche weist darauf hin. Teilfehler einzelner Konten bleiben sichtbar.

Die reine Anzeige nutzt Mailkopf-Markierungen, aktuelle Aufnahmefilter und vorhandene KI-Prüfhinweise. Kein neuer Modellaufruf, keine automatische Aufnahme, keine Mutation beim Mailanbieter. Bestehende KI-Prüfhinweise werden nur bei passendem Konto, UID, Absender, Betreff und Vorschau als Hinweise angezeigt. Sie sind keine neue vollständige Prüfung der aktuellen Mail.

Browserprüfung im isolierten Docker-Container mit zwei künstlichen Konten: Posteingang 4/8 inklusive unklarer Mails; Newsletter 2/8, Spamverdacht 2/8; nach Kontoauswahl 4 gesamte Mails, davon 2 ungelesen und je ein Newsletter/Spamverdacht. Alle Ansichten umschaltbar, keine Browserwarnungen/-fehler. API-Regressionen prüfen zusätzlich unbekanntes Konto, Kontentrennung, Teilfehler und readonly IMAP BODY.PEEK.

Frontendbuild und Asset-Vertrag bestanden. Vollständige Testsuite und GitHub-CI werden vor Merge geprüft; abschließende Ergebnisse im PR. Keine Änderung der dokumentierten Roadmapquote (75 %).
