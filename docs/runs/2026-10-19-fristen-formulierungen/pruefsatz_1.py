# Unabhängiger Prüfsatz (Holdout) für die regelbasierte Fristerkennung.
# Alle Sätze sind erfunden. Bezugszeitpunkt jeder Mail: Donnerstag, 3. September 2026.
# Bei Sätzen ohne Frist steht der Lebensbereich als Kommentar hinter dem Eintrag.
#
# (bereich, text, erwartete Kalendertage als ISO-Liste, Zahl der Fristen ohne Kalendertag)
HOLDOUT = [
    # --- Rechnungen und Mahnungen ---
    ('rechnung', 'Offener Betrag 240,00 Euro – Zahlungseingang bis 18.09.2026.', ['2026-09-18'], 0),
    ('rechnung', 'Neue Zahlungsfrist: 11.09.2026. Danach müssen wir leider weitere Schritte einleiten.', ['2026-09-11'], 0),
    ('rechnung', 'Sollte der Betrag nicht binnen zehn Tagen bei uns eingegangen sein, geben wir die Forderung an ein Inkassobüro ab.', ['2026-09-13'], 0),
    ('rechnung', 'Bitte zahlen Sie die erste Rate bis Ende September und die zweite bis zum 15.10.2026.', ['2026-10-15'], 1),

    # --- Behörden und Steuer ---
    ('behoerde', 'Die Einkommensteuererklärung für 2025 muss bis zum 2. November 2026 beim Finanzamt eingegangen sein.', ['2026-11-02'], 0),
    ('behoerde', 'Füllen Sie den beiliegenden Fragebogen vollständig aus und senden Sie ihn innerhalb eines Monats an uns zurück.', ['2026-10-03'], 0),
    ('behoerde', 'Wir bitten um Rückmeldung bis zum Ablauf des 15. Oktober 2026.', ['2026-10-15'], 0),
    ('behoerde', 'Reichen Sie die fehlenden Belege bitte bis zum 25.08. nach, andernfalls müssen wir Ihre Einkünfte schätzen.', [], 1),

    # --- Vermieter, Verträge, Kündigungen ---
    ('vertrag', 'Falls Sie den Vertrag nicht verlängern möchten, kündigen Sie bitte bis zum 30.09. schriftlich.', ['2026-09-30'], 0),
    ('vertrag', 'Die Nachzahlung aus der Nebenkostenabrechnung in Höhe von 312 Euro ist bis Monatsende zu leisten.', [], 1),
    ('vertrag', 'Die unterschriebene Zustimmung zur Mieterhöhung erbitte ich bis Donnerstag.', [], 1),
    ('vertrag', 'Geben Sie mir bitte bis Freitag Bescheid, ob der Schornsteinfeger die Wohnung betreten darf.', ['2026-09-04'], 0),

    # --- Versicherungen ---
    ('versicherung', 'Wir erwarten die Rechnung der Werkstatt innerhalb von 14 Tagen, damit wir den Schaden regulieren können.', ['2026-09-17'], 0),
    ('versicherung', 'Schicken Sie das unterschriebene Formular bitte bis Montag, den 14. September 2026, zurück.', ['2026-09-14'], 0),
    ('versicherung', 'Um den Beitragsnachlass zu erhalten, reichen Sie den Nachweis bis Dienstag, den 17. September, ein.', [], 1),
    ('versicherung', 'Das ärztliche Attest muss uns in zwei Monaten vorliegen, sonst erlischt der Leistungsanspruch.', ['2026-11-03'], 0),
    ('versicherung', 'Ihre Stellungnahme zum Unfallhergang benötigen wir bis nächste Woche.', [], 1),

    # --- Schule, Kita, Verein ---
    ('schule', 'Bitte überweist den Mitgliedsbeitrag für das zweite Halbjahr bis spätestens KW 40.', [], 1),
    ('schule', 'Gebt die Rückmeldung zum Elternabend bitte bis Mittwoch ab; der Elternabend selbst findet am 22. September statt.', ['2026-09-09'], 0),
    ('schule', 'Wer beim Vereinsturnier mitspielen will, trägt sich bis morgen in die Liste am Schwarzen Brett ein.', ['2026-09-04'], 0),

    # --- Arzt und Praxis ---
    ('arzt', 'Falls Sie Ihren Termin am 21. September nicht wahrnehmen können, sagen Sie ihn bitte spätestens 24 Stunden vorher ab.', [], 1),
    ('arzt', 'Lassen Sie uns die Überweisung Ihres Hausarztes bis zum 8.9. zukommen.', ['2026-09-08'], 0),
    ('arzt', 'Die Laborergebnisse schicken wir Ihnen bis Ende der Woche zu.', [], 1),
    ('arzt', 'Den ausgefüllten Anamnesebogen benötigen wir spätestens drei Werktage vor Ihrem Termin.', [], 1),

    # --- Handwerker ---
    ('handwerker', 'Wir sagen Ihnen verbindlich zu, die neuen Fenster bis zum 2. Oktober 2026 einzubauen.', ['2026-10-02'], 0),
    ('handwerker', 'Das Angebot schicke ich Ihnen zeitnah; die Materialpreise gelten allerdings nur bis 30.09.', [], 1),
    ('handwerker', 'Räumen Sie den Flur bitte bis Montag frei, damit wir am Dienstag mit dem Estrich beginnen können.', ['2026-09-07'], 0),

    # --- Arbeit und Projekte ---
    ('arbeit', 'Ich liefere den ersten Entwurf in drei Wochen und die Endfassung bis zum 30. Oktober 2026.', ['2026-09-24', '2026-10-30'], 0),
    ('arbeit', 'Die Zuarbeit für den Quartalsbericht muss bis Mitte Oktober vorliegen.', [], 1),
    ('arbeit', 'Ihre Antwort erwarten wir bis Donnerstag, den 10. September.', ['2026-09-10'], 0),

    # --- Veranstaltungen und Anmeldungen ---
    ('veranstaltung', 'Anmeldeschluss für den Workshop am 10. Oktober ist der 25.09.2026.', ['2026-09-25'], 0),
    ('veranstaltung', 'Die Teilnahmegebühr ist spätestens zwei Wochen vor Beginn der Tagung zu überweisen.', [], 1),
    ('veranstaltung', 'Bitte gebt bis nächsten Freitag Bescheid, wie viele Personen ihr zum Sommerfest mitbringt.', [], 1),

    # --- Online-Bestellungen und Widerruf ---
    ('bestellung', 'Sie können Ihre Bestellung innerhalb von 14 Tagen ab Erhalt der Ware ohne Angabe von Gründen widerrufen.', [], 1),
    ('bestellung', 'Senden Sie den defekten Artikel bis einschließlich 12.09.2026 mit dem beigelegten Retourenschein zurück.', ['2026-09-12'], 0),
    ('bestellung', 'Ihre Bestellung wird bis spätestens 10.9. geliefert.', ['2026-09-10'], 0),

    # --- Keine Frist (knifflige Gegenbeispiele) ---
    ('keine', 'Die Praxis bleibt vom 7. bis 18. September wegen Urlaub geschlossen.', [], 0),  # arzt: Schließzeit
    ('keine', 'Die Sprechstunde am Freitag, 4. September, entfällt.', [], 0),  # arzt: Ausfall
    ('keine', 'Das Angebot für die Badsanierung gilt bis zum 30.09.2026.', [], 0),  # handwerker: Gültigkeit
    ('keine', 'Die Gewährleistung auf die Arbeiten beträgt fünf Jahre ab Abnahme.', [], 0),  # handwerker: Dauer
    ('keine', 'Die Handwerker kommen am Dienstag, den 8. September, zwischen 8 und 10 Uhr.', [], 0),  # handwerker: Termin
    ('keine', 'Ich bin bis einschließlich 14.09. im Urlaub und lese meine Mails erst danach.', [], 0),  # arbeit: Abwesenheit
    ('keine', 'Herr Muster ist bis 21.09. auf Dienstreise; in dringenden Fällen schreiben Sie bitte an vertretung@example.org.', [], 0),  # arbeit: Abwesenheit
    ('keine', 'Der Mietvertrag läuft noch bis zum 31. Dezember 2027.', [], 0),  # vertrag: Laufzeit
    ('keine', 'Die Kündigungsfrist beträgt drei Monate zum Monatsende.', [], 0),  # vertrag: Vertragsregel, Dauer
    ('keine', 'Die Bauarbeiten vor Ihrem Haus dauern voraussichtlich bis Mitte Oktober.', [], 0),  # vertrag (Vermieter): Dauer
    ('keine', 'Die Abschlagszahlung von 85 Euro wird ab Oktober jeweils zum Monatsersten eingezogen.', [], 0),  # vertrag: Abbuchung
    ('keine', 'Der Rechnungsbetrag von 59,90 Euro wird am 15.09. von Ihrem Konto abgebucht.', [], 0),  # rechnung: Abbuchung
    ('keine', 'Ihre Zahlung ist vor zwei Wochen bei uns eingegangen, vielen Dank.', [], 0),  # rechnung: vergangen
    ('keine', 'Der Versand innerhalb Deutschlands dauert in der Regel zwei bis drei Werktage.', [], 0),  # bestellung: Dauer
    ('keine', 'Ihr bis zum 31.10.2026 gültiger Rabattcode lautet HERBST10.', [], 0),  # bestellung: Gültigkeit
    ('keine', 'Wegen Inventur bleibt unser Lager bis einschließlich Montag geschlossen.', [], 0),  # bestellung: Schließzeit
    ('keine', 'Das Sommerfest der Kita findet am Samstag, 19. September, ab 14 Uhr statt.', [], 0),  # schule: Veranstaltung
    ('keine', 'Die Elternversammlung ist am Mittwoch, 16. September 2026, um 19:30 Uhr in der Aula.', [], 0),  # schule: Veranstaltung
    ('keine', 'Das Hallenbad ist bis zum 13. September wegen Revision geschlossen, das Training fällt so lange aus.', [], 0),  # verein: Schließzeit
    ('keine', 'Unser Bürgerbüro ist montags bis freitags von 8 bis 16 Uhr für Sie da.', [], 0),  # behoerde: Öffnungszeit
    ('keine', 'Ihr Antrag vom 12.08.2026 ist am 28. August bei uns eingegangen.', [], 0),  # behoerde: vergangen
    ('keine', 'Ihr Vertrag ist bis zum 31.12.2026 beitragsfrei gestellt.', [], 0),  # versicherung: Laufzeit
    ('keine', 'Der Reiseschutz gilt weltweit für Reisen bis zu 56 Tagen.', [], 0),  # versicherung: Dauer
    ('keine', 'Der Kurs „Erste Hilfe am Kind“ beginnt am 5. Oktober und dauert sechs Wochen.', [], 0),  # veranstaltung: Termin, Dauer
]
