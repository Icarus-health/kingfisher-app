# Unabhängiger Prüfsatz (Holdout 2) für die regelbasierte Fristerkennung.
# Alle Sätze, Namen und Beträge sind erfunden. Bezugszeitpunkt jeder Mail:
# Donnerstag, 3. September 2026. Jeder Satz steht für sich (ein Absatz).
#
# Die Spalte „bereich“ nennt bei allen 70 Sätzen den Lebensbereich, auch bei
# Sätzen ohne Frist; ob ein Satz eine Frist enthält, steht allein in den
# beiden letzten Feldern (leere Liste und 0 heißt: keine Frist).
#
# (bereich, text, erwartete Kalendertage als ISO-Liste, Zahl der Fristen ohne Kalendertag)
HOLDOUT = [
    # --- Bank und Kredit ---
    ('bank', 'Bis zum 30.09.2026 können Sie der Änderung unserer Kontoführungsentgelte widersprechen; ohne Widerspruch gilt die Änderung als angenommen.', ['2026-09-30'], 0),
    ('bank', 'Bitte reichen Sie die fehlenden Gehaltsnachweise für Ihren Kreditantrag bis Freitag, den 11. September, nach, damit wir die Finanzierungszusage aufrechterhalten können.', ['2026-09-11'], 0),
    ('bank', 'Damit die Umschuldung noch in diesem Quartal greift, muss uns der unterschriebene Darlehensvertrag spätestens Ende September vorliegen.', [], 1),
    ('bank', 'Für den Kontowechsel brauchen wir noch zwei Dinge: die unterschriebene Kontowechselhilfe bis zum 15.09. und die Liste Ihrer Daueraufträge innerhalb von 14 Tagen.', ['2026-09-15', '2026-09-17'], 0),
    ('bank', 'Die Sollzinsbindung Ihres Baudarlehens läuft noch bis zum 30.06.2031.', [], 0),
    ('bank', 'Die nächste Rate von 385,20 Euro wird am 15.09. automatisch von Ihrem Girokonto abgebucht, Sie müssen dafür nichts veranlassen.', [], 0),
    ('bank', 'Wegen Umbauarbeiten bleibt die Filiale am Lindenplatz bis einschließlich 18. September geschlossen.', [], 0),

    # --- Krankenkasse und Pflege ---
    ('krankenkasse', 'Die Rücksendung des ausgefüllten Fragebogens zur Pflegebegutachtung wird bis zum 21. September erwartet.', ['2026-09-21'], 0),
    ('krankenkasse', 'Wir bitten Sie, die ärztliche Bescheinigung für die Zahlung des Krankengeldes binnen drei Wochen nachzureichen.', ['2026-09-24'], 0),
    ('krankenkasse', 'Bitte reichen Sie den Kostenvoranschlag des Hörakustikers zeitnah ein, damit wir über die Versorgung entscheiden können.', [], 1),
    ('krankenkasse', 'Lade bitte bis übermorgen ein aktuelles Foto in der App hoch, sonst können wir deine neue Gesundheitskarte nicht rechtzeitig verschicken.', ['2026-09-05'], 0),
    ('krankenkasse', 'Ihre Arbeitsunfähigkeitsbescheinigung für die Zeit bis zum 4. September ist am Montag bei uns eingegangen.', [], 0),
    ('krankenkasse', 'Die Kostenzusage für die Haushaltshilfe gilt bis zum 31.12.2026.', [], 0),
    ('krankenkasse', 'Ihre Pflegeberaterin ist vom 7. bis 18. September nicht im Haus; die Vertretung erreichen Sie unter pflege@example.org.', [], 0),

    # --- Jobcenter, Arbeitsagentur, Rentenversicherung ---
    ('behoerde', 'Weisen Sie uns bitte binnen zwei Monaten nach, dass Sie sich um eine günstigere Wohnung bemüht haben; andernfalls übernehmen wir künftig nur noch die angemessenen Unterkunftskosten.', ['2026-11-03'], 0),
    ('behoerde', 'Falls Sie den Beratungstermin am 22. September nicht wahrnehmen können, sagen Sie ihn bitte bis zum 15. September ab.', ['2026-09-15'], 0),
    ('behoerde', 'Bitte reichen Sie den unterschriebenen Arbeitsvertrag innerhalb von drei Werktagen bei uns ein.', [], 1),
    ('behoerde', 'Um die Lücken in Ihrem Versicherungsverlauf zu schließen, senden Sie uns die Nachweise über Ihre Ausbildungszeiten bitte bis Mitte Oktober zu.', [], 1),
    ('behoerde', 'Ihre Rente für Oktober 2026 wird wie bisher zum Monatsende gutgeschrieben; Sie müssen dafür nichts tun.', [], 0),
    ('behoerde', 'Ihr neuer Bewilligungszeitraum läuft vom 1. Oktober 2026 bis zum 31. März 2027.', [], 0),
    ('behoerde', 'Die Informationsveranstaltung zur Weiterbildung in der Pflege findet am Dienstag, 15. September, um 10 Uhr in Raum 214 statt.', [], 0),

    # --- Kfz und Werkstatt ---
    ('kfz', 'Ihr Wagen ist fertig – holen Sie ihn bitte bis morgen 17 Uhr ab, danach berechnen wir Standgebühren.', ['2026-09-04'], 0),
    ('kfz', 'Die Hauptuntersuchung ist überfällig; vereinbaren Sie bitte spätestens in KW 40 einen Termin bei uns.', [], 1),
    ('kfz', 'Den Unfallbericht mit Fotos müssen Sie Ihrer Versicherung innerhalb einer Woche vollständig übermitteln.', ['2026-09-10'], 0),
    ('kfz', 'Bitte bestätigen Sie den Kostenvoranschlag für die neuen Bremsen bis Montag, den 15. September, damit wir die Teile bestellen können.', [], 1),
    ('kfz', 'Ihr Leihwagen steht Ihnen während der Reparatur voraussichtlich bis Mittwoch zur Verfügung.', [], 0),
    ('kfz', 'Der Kostenvoranschlag über 640 Euro ist bis zum 30. September gültig.', [], 0),
    ('kfz', 'Die Rückrufaktion betrifft nur Fahrzeuge, die bis zum 31.03.2025 gebaut wurden.', [], 0),

    # --- Umzug und Nebenkosten ---
    ('umzug', 'Zur Wohnungsübergabe: Zählerstände bis übermorgen melden, Schlüssel bis zum 30.09. beim Hausmeister abgeben.', ['2026-09-05', '2026-09-30'], 0),
    ('umzug', 'Die Nachzahlung aus der Betriebskostenabrechnung 2025 in Höhe von 312,40 Euro ist innerhalb von 30 Tagen nach Zugang dieser Abrechnung zu überweisen.', [], 1),
    ('umzug', 'Teilt uns bitte bis Freitag mit, wer von euch nach dem Auszug von Jonas im Mietvertrag bleibt.', ['2026-09-04'], 0),
    ('umzug', 'Schicken Sie dem Umzugsunternehmen bis Ende der Woche die Zahl der Kartons und beantragen Sie die Halteverbotszone spätestens zwei Wochen vor dem Umzugstag.', [], 2),
    ('umzug', 'Die Halteverbotszone vor dem Haus ist am 18. und 19. September jeweils von 7 bis 18 Uhr eingerichtet.', [], 0),
    ('umzug', 'Der Abschlag für Strom wird ab Oktober monatlich zum 15. abgebucht.', [], 0),
    ('umzug', 'Die Kaution in Höhe von 2.400 Euro ist am 1. September vollständig bei uns eingegangen.', [], 0),

    # --- Gericht und Anwalt ---
    ('recht', 'Bitte schicken Sie mir Ihre Anmerkungen zum Entwurf der Klageerwiderung bis Montag, damit ich sie noch einarbeiten kann.', ['2026-09-07'], 0),
    ('recht', 'Gegen dieses Urteil kann binnen eines Monats nach Zustellung Berufung eingelegt werden.', [], 1),
    ('recht', 'Der Kostenvorschuss von 438 Euro ist bis spätestens 24.09.2026 an die Gerichtskasse zu zahlen.', ['2026-09-24'], 0),
    ('recht', 'Für die Vorbereitung der Güteverhandlung reichen Sie mir bitte die Fotos der Mängel bis Donnerstag ein.', [], 1),
    ('recht', 'Die mündliche Verhandlung ist auf Mittwoch, den 14. Oktober 2026, 9:30 Uhr, Saal 3, anberaumt.', [], 0),
    ('recht', 'Ich bin bis zum 11. September auf einer Fortbildung und lese meine Mails nur unregelmäßig.', [], 0),
    ('recht', 'Die Gegenseite hat auf unser Schreiben vom 12. August bis heute nicht reagiert.', [], 0),

    # --- Hochschule und Prüfungsamt ---
    ('hochschule', 'Ihr Thema gilt ab heute als ausgegeben; die Masterarbeit ist innerhalb von sechs Monaten beim Prüfungsamt einzureichen.', ['2027-03-03'], 0),
    ('hochschule', 'Melde dich bis Mittwoch im Prüfungsportal für die Wiederholungsklausur an, sonst kannst du erst im nächsten Semester mitschreiben.', ['2026-09-09'], 0),
    ('hochschule', 'Abgabe der Seminararbeit: Anfang Oktober, den genauen Tag gibt der Lehrstuhl noch bekannt.', [], 1),
    ('hochschule', 'Für die Zulassung reichen Sie das Anmeldeformular bis 18.09. ein und laden das Exposé spätestens in vier Wochen im Portal hoch.', ['2026-09-18', '2026-10-01'], 0),
    ('hochschule', 'Die Klausur „Statistik II“ findet am Freitag, 25. September, von 9 bis 11 Uhr im Hörsaal B statt.', [], 0),
    ('hochschule', 'Die Bibliothek ist in der vorlesungsfreien Zeit bis zum 11. Oktober nur werktags von 9 bis 16 Uhr geöffnet.', [], 0),
    ('hochschule', 'Ihr Semesterbeitrag ist bis zum 31. August bei uns eingegangen, die Rückmeldung ist damit abgeschlossen.', [], 0),

    # --- Sportverein und Ehrenamt ---
    ('verein', 'Meldet eure Kinder bitte bis zum 20. September für das Herbstturnier an, damit wir die Mannschaften einteilen können.', ['2026-09-20'], 0),
    ('verein', 'Gib mir bitte bis nächste Woche Bescheid, ob du beim Kuchenverkauf am 27. September mithilfst.', [], 1),
    ('verein', 'Wer den Mitgliedsbeitrag für das zweite Halbjahr nicht per Lastschrift zahlt, überweist ihn bitte bis zum Monatsende.', [], 1),
    ('verein', 'Gebt eure Abrechnungen für die Übungsleiterpauschale bitte bis nächsten Freitag beim Kassenwart ab.', [], 1),
    ('verein', 'Das Training der D-Jugend fällt bis Freitag wegen der Hallensanierung aus.', [], 0),
    ('verein', 'Die Jahreshauptversammlung findet am Freitag, 16. Oktober 2026, um 19:30 Uhr im Vereinsheim statt.', [], 0),
    ('verein', 'Die Ehrenamtskarte, die Sie im Juli beantragt haben, ist drei Jahre lang gültig.', [], 0),

    # --- Kunden und Aufträge eines Selbstständigen ---
    ('kunden', 'Wie besprochen liefere ich Ihnen die überarbeiteten Entwürfe bis Dienstag, den 8. September.', ['2026-09-08'], 0),
    ('kunden', 'Bitte prüfen Sie die Lieferung innerhalb von fünf Arbeitstagen und begleichen Sie die Rechnung binnen 14 Tagen nach Rechnungsdatum.', [], 2),
    ('kunden', 'Bitte senden Sie den unterschriebenen Rahmenvertrag bis zum 01.09. an vertrag@example.org zurück.', [], 1),
    ('kunden', 'Teilen Sie mir bitte umgehend mit, ob der Folgeauftrag kommt, und schicken Sie mir die Texte für die Startseite bis zum 21.09.', ['2026-09-21'], 1),
    ('kunden', 'Die vereinbarten Stundensätze gelten unverändert bis Ende 2027.', [], 0),
    ('kunden', 'Ihre Rechnung Nr. 2026-117 haben wir bis auf einen Posten geprüft und am 2. September zur Zahlung angewiesen.', [], 0),
    ('kunden', 'Das Projekt läuft voraussichtlich bis Mitte November und umfasst drei Workshops.', [], 0),

    # --- Reisen und Buchungen ---
    ('reise', 'Restzahlung für Ihre Pauschalreise: 1.480 Euro, zu überweisen bis spätestens 02.10.2026.', ['2026-10-02'], 0),
    ('reise', 'Bitte checken Sie spätestens 24 Stunden vor Abflug online ein, sonst wird am Schalter eine Gebühr fällig.', [], 1),
    ('reise', 'Kostenlos stornieren können Sie Ihre Zimmerbuchung noch bis zum 10.09.', ['2026-09-10'], 0),
    ('reise', 'Die Belege für die Erstattung der ausgefallenen Zugfahrt reichen Sie bitte innerhalb von 10 Tagen bei uns ein.', ['2026-09-13'], 0),
    ('reise', 'Ihr Rückflug am 19. September startet um 6:40 Uhr; das Gate schließt 20 Minuten vor Abflug.', [], 0),
    ('reise', 'Der Reisegutschein über 50 Euro ist bis zum 31.12.2027 für alle Buchungen einlösbar.', [], 0),
    ('reise', 'Wegen Bauarbeiten ist die Strecke auf Ihrer Verbindung bis übermorgen gesperrt; Ihre Fahrkarte gilt auch im Ersatzbus.', [], 0),
]
