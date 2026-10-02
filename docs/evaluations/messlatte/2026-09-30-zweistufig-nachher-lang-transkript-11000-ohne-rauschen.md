# Messlatte: Bericht

| Kopf |  |
|---|---|
| Commit | 4a1a48307c36d244011bf3a03fc9fdb739dfa3c7 |
| Modell | keins |
| Modell (Rolle „frage“) | keins (Rückfall) |
| Welt | welt v1 (14 Szenarien, 176 Quellen, 77 Fragen) |
| Rauschen | 0 Quellen (seed 1) |
| Stichtag der Welt | 2026-09-29T07:30:00+02:00 |
| Datum der Messung | 2026-09-30T09:31:13+00:00 |
| Dauer | 23.8 s |
| Lange Quellen | Mails auf 3000, Transkripte auf 11000 Zeichen |

## Ergebnis auf einen Blick

- **Falsche Aussagen: nicht gemessen** (Stufe „Antwort“ ohne Modell nicht möglich)
- **Richtig: nicht gemessen**
- **Nicht gemessen: 77 von 77 Fragen** (kein Modell angegeben (--modell); die Stufe „Antwort“ wurde übersprungen)
- **Antwortzeit im Ziel: ≤ 8 s Median: nicht gemessen (kein Modell lief)**

Suche ohne Modell (Stufe „Abruf“), gemessen:

- Erwartete Belege gefunden: 119 von 136
- Fragen mit allen erwarteten Belegen: 59 von 71
- Erwartete Belege auf Rang 1: 32 von 136, bis Rang 5: 87 von 136, bis Rang 12: 104 von 136
- Fragen, bei denen verbotene Belege im Kontext waren: 21 von 77 (35 verbotene Belege)
- davon **ungekennzeichnet** (der Kontext nennt die Quelle weder als überholt noch als andere Person noch als außerhalb des Zeitraums): 4 von 77 Fragen (4 von 35 Belegen)
- die übrigen, **gekennzeichnet nach Art** (Belege; einer mit zwei Arten zählt in beiden): überholt 23, andere Person 7, außerhalb des Zeitraums 10
- **Kontext abgeschnitten** (Budget voll; gefunden, aber nicht im Kontext): 1 von 71 Fragen mit mindestens einer erwarteten Quelle (1 von 136 Belegen); weitere erwartete Belege, die das Arbeitsgedächtnis wegen ihrer Länge nie einordnet: 0 (0 Fragen)
- **Erwartete Belege im Kontext ohne tragende Textstelle** (keine Pflichtaussage der Quelle mehr zu sehen): 1 Belege in 1 von 71 Fragen
- Gekürzte Quellen im Kontext (Zweistufige Auswahl): 685 Quellen in allen Fragen, davon gezeigt 1753 von 5111 Absätzen
- Kontext der Auswahl: im Mittel 35190 Zeichen (Median 35846, Höchstwert 38045), im Mittel 13.4 Quellen
- Rückfragen, die das Produkt mit allen Bedeutungen anbietet: 6 von 7
- Unnötige Rückfragen bei eindeutigen Fragen: 0 von 70
- Fragen, die im Gespräch in den freien Chat gingen (statt in den belegten Gedächtnisweg): 1 von 77
- Frage verstanden mit Modell: 0 von 77, mit Rückfall: 77 von 77 (kein Modell: 77)

## Aufnahme

| Zähler |  |
|---|---|
| Quellen der Welt (mit Rauschen) | 176 |
| Episoden aufgenommen | 176 |
| dupliziert | 0 |
| fehlgeschlagen | 0 |
| Termine in der Live-Anzeige des Kalenders (laufendes Jahr) | 15 |
| Termine außerhalb des Gedächtnisfensters (3 Jahre zurück, 1 Jahr voraus) | 0 |
| Einordnung | 176 von 176 eingeordnet (Modell regel-einordnung) |
| Dauer | 2.839 s |

## Antwort

Nicht gemessen. kein Modell angegeben (--modell); die Stufe „Antwort“ wurde übersprungen.

### Antwortzeit

Antwortzeit im Ziel: ≤ 8 s Median: nicht gemessen (kein Modell lief)

| Stufe | Antworten | Median (s) | 90-Prozent-Wert (s) |
|---|---|---|---|
| Abruf je Frage (Suche ohne Modell) | 77 | 0.258 | 0.343 |

## Abruf je Kategorie

| Kategorie | Fragen | Belege gefunden | Fragen mit allen Belegen | verbotene Belege im Kontext | davon ungekennzeichnet |
|---|---|---|---|---|---|
| aktualitaet | 11 | 20 von 20 | 11 von 11 | 8 von 11 | 1 von 11 |
| falle | 5 | 0 von 0 | 0 von 0 | 3 von 5 | 0 von 5 |
| fremde_anweisung | 3 | 3 von 3 | 2 von 2 | 0 von 3 | 0 von 3 |
| frist | 9 | 12 von 13 | 8 von 9 | 4 von 9 | 3 von 9 |
| identitaet | 5 | 8 von 8 | 5 von 5 | 3 von 5 | 0 von 5 |
| mehrdeutigkeit | 8 | 17 von 18 | 7 von 8 | 0 von 8 | 0 von 8 |
| paraphrase | 5 | 7 von 9 | 3 von 5 | 0 von 5 | 0 von 5 |
| profil | 5 | 12 von 14 | 3 von 5 | 0 von 5 | 0 von 5 |
| rueckblick | 12 | 17 von 19 | 10 von 12 | 0 von 12 | 0 von 12 |
| vorbereitung | 5 | 9 von 14 | 2 von 5 | 0 von 5 | 0 von 5 |
| wartet_auf | 5 | 6 von 10 | 4 von 5 | 0 von 5 | 0 von 5 |
| zeitraum | 4 | 8 von 8 | 4 von 4 | 3 von 4 | 0 von 4 |

## Fehlerliste Abruf (33 von 77)

- **adresse-geaendert-01** (aktualitaet, kritisch): Frage „An welche Adresse soll ich die Rechnung für Frau Krüger schicken?“; Weg: arbeitsstand/chat
  - verbotene Belege im Kontext: adresse-geaendert-003 (ungekennzeichnet: keiner; gekennzeichnet: überholt: adresse-geaendert-003)
- **adresse-geaendert-02** (aktualitaet, kritisch): Frage „Welche E-Mail-Adresse nutze ich für Jasmin Krüger?“; Weg: arbeitsstand/memory_evidence
  - verbotene Belege im Kontext: adresse-geaendert-001, adresse-geaendert-003, adresse-geaendert-005 (ungekennzeichnet: keiner; gekennzeichnet: überholt: adresse-geaendert-001, adresse-geaendert-003, adresse-geaendert-005)
- **adresse-geaendert-03** (aktualitaet, normal): Frage „Wo arbeitet Jasmin Krüger jetzt?“; Weg: arbeitsstand/memory_evidence
  - verbotene Belege im Kontext: adresse-geaendert-001 (ungekennzeichnet: keiner; gekennzeichnet: überholt: adresse-geaendert-001)
- **adresse-geaendert-04** (aktualitaet, normal): Frage „Wer ist bei der Kreisklinik Rheingau jetzt für die Küche zuständig?“; Weg: arbeitsstand/memory_evidence
  - verbotene Belege im Kontext: adresse-geaendert-001 (ungekennzeichnet: keiner; gekennzeichnet: überholt: adresse-geaendert-001)
- **falle-02** (falle, kritisch): Frage „Was hat das Angebot für die Klinik Vogelsberg für 2026 gekostet?“; Weg: arbeitsstand/memory_evidence
  - verbotene Belege im Kontext: falle-005 (ungekennzeichnet: keiner; gekennzeichnet: überholt: falle-005)
- **falle-04** (falle, kritisch): Frage „Was wurde beim Treffen mit Herrn Lorenzen im Juli 2026 besprochen?“; Weg: arbeitsstand/memory_evidence
  - verbotene Belege im Kontext: falle-007, falle-010 (ungekennzeichnet: keiner; gekennzeichnet: überholt: falle-007; außerhalb des Zeitraums: falle-007, falle-010)
- **falle-05** (falle, normal): Frage „Wann findet der nächste Kongress zur Klinischen Ernährung statt?“; Weg: arbeitsstand/memory_evidence
  - verbotene Belege im Kontext: falle-001 (ungekennzeichnet: keiner; gekennzeichnet: überholt: falle-001)
- **frist-verschoben-01** (frist, kritisch): Frage „Bis wann muss ich den Förderantrag NutriBrücke einreichen?“; Weg: arbeitsstand/memory_evidence
  - erwartete Belege fehlen: frist-verschoben-008 (gefunden: keine)
  - verbotene Belege im Kontext: frist-verschoben-004
- **frist-verschoben-02** (aktualitaet, kritisch): Frage „Wurde die Frist bei der Stiftung Zukunft Gesundheit geändert und wann ist sie jetzt?“; Weg: arbeitsstand/memory_evidence
  - verbotene Belege im Kontext: frist-verschoben-001 (ungekennzeichnet: keiner; gekennzeichnet: überholt: frist-verschoben-001)
- **frist-verschoben-04** (rueckblick, normal): Frage „Wie hoch darf die Förderung für unseren Antrag höchstens sein?“; Weg: arbeitsstand/memory_evidence
  - erwartete Belege fehlen: frist-verschoben-006 (gefunden: keine)
- **kontakt-vor-jahren-01** (rueckblick, kritisch): Frage „Wir hatten doch vor ein paar Jahren mal Kontakt zu jemandem, der was mit Küchensoftware gemacht hat. Wer war das?“; Weg: arbeitsstand/memory_evidence
  - erwartete Belege fehlen: kontakt-vor-jahren-003 (gefunden: kontakt-vor-jahren-001)
- **mainz-06** (mehrdeutigkeit, kritisch): Frage „Wie hoch ist mein Angebot?“; Weg: bedeutungsfrage/memory_evidence
  - Bedeutungen nicht angeboten: Albanus/Mainz
- **meeting-protokoll-01** (frist, kritisch): Frage „Was hat mir Frau Koch beim Projekttreffen im September zugesagt?“; Weg: arbeitsstand/memory_evidence
  - verbotene Belege im Kontext: meeting-protokoll-003 (ungekennzeichnet: keiner; gekennzeichnet: außerhalb des Zeitraums: meeting-protokoll-003)
- **meeting-protokoll-02** (frist, kritisch): Frage „Bis wann hat Herr Roth den Entwurf der Texturstufen versprochen?“; Weg: arbeitsstand/memory_evidence
  - verbotene Belege im Kontext: meeting-protokoll-003
- **meeting-protokoll-03** (frist, kritisch): Frage „Welche Zusage habe ich selbst im letzten Treffen zum Handbuch gemacht?“; Weg: arbeitsstand/memory_evidence
  - verbotene Belege im Kontext: meeting-protokoll-003
- **namensgleich-01** (identitaet, kritisch): Frage „Was kostet das Catering von Alex Winter pro Person?“; Weg: arbeitsstand/memory_evidence
  - verbotene Belege im Kontext: namensgleich-003, namensgleich-006, namensgleich-009, namensgleich-010 (ungekennzeichnet: keiner; gekennzeichnet: überholt: namensgleich-003, namensgleich-009, namensgleich-010; andere Person: namensgleich-006, namensgleich-009, namensgleich-010)
- **namensgleich-02** (identitaet, kritisch): Frage „Bis wann soll ich Alex Winter vom Institut Feedback zum Fragebogen geben?“; Weg: arbeitsstand/memory_evidence
  - verbotene Belege im Kontext: namensgleich-004, namensgleich-005 (ungekennzeichnet: keiner; gekennzeichnet: andere Person: namensgleich-004, namensgleich-005)
- **namensgleich-05** (identitaet, kritisch): Frage „Welche E-Mail-Adresse hat Alex Winter vom Catering?“; Weg: arbeitsstand/memory_evidence
  - verbotene Belege im Kontext: namensgleich-006, namensgleich-009 (ungekennzeichnet: keiner; gekennzeichnet: überholt: namensgleich-009; andere Person: namensgleich-006, namensgleich-009)
- **paraphrase-01** (paraphrase, kritisch): Frage „Wie viel kostet uns das Catering für die Tagung?“; Weg: arbeitsstand/memory_evidence
  - erwartete Belege fehlen: paraphrase-010 (gefunden: paraphrase-009)
- **paraphrase-02** (paraphrase, normal): Frage „Wie viele Leute kommen zu der Veranstaltung, die ich im November ausrichte?“; Weg: arbeitsstand/memory_evidence
  - erwartete Belege fehlen: paraphrase-008 (gefunden: keine)
- **profil-01** (profil, kritisch): Frage „Wer ist eigentlich Dr. Reinhardt, und was haben wir miteinander zu tun?“; Weg: arbeitsstand/memory_evidence
  - erwartete Belege fehlen: profil-014 (gefunden: profil-001, profil-005, profil-013, profil-015)
- **profil-02** (profil, normal): Frage „Seit wann kenne ich Claudia Reinhardt?“; Weg: arbeitsstand/memory_evidence
  - erwartete Belege fehlen: profil-001 (gefunden: profil-014)
  - davon vom Zeichenbudget verdrängt (gefunden, nicht im Kontext): profil-001
- **terminvorbereitung-01** (vorbereitung, kritisch): Frage „Was muss ich für morgen mit Frau Engel und Herrn Odenthal wissen?“; Weg: arbeitsstand/memory_evidence
  - erwartete Belege fehlen: terminvorbereitung-002 (gefunden: terminvorbereitung-007, terminvorbereitung-005, terminvorbereitung-008)
- **terminvorbereitung-02** (vorbereitung, kritisch): Frage „Wann und wo ist mein Termin morgen?“; Weg: arbeitsstand/memory_evidence
  - erwartete Belege fehlen: terminvorbereitung-008, terminvorbereitung-007 (gefunden: keine)
- **terminvorbereitung-04** (aktualitaet, kritisch): Frage „Welches Budget hat Frau Engel für das Projekt genannt?“; Weg: arbeitsstand/memory_evidence
  - verbotene Belege im Kontext: terminvorbereitung-004
- **terminvorbereitung-06** (vorbereitung, kritisch): Frage „Was steht morgen bei mir an?“; Weg: arbeitsstand/memory_evidence
  - erwartete Belege fehlen: terminvorbereitung-008, meeting-protokoll-012 (gefunden: meeting-protokoll-009)
  - im Kontext ohne tragende Textstelle: meeting-protokoll-009
- **wartet-auf-01** (wartet_auf, kritisch): Frage „Worauf warte ich noch?“; Weg: arbeitsstand/memory_evidence
  - erwartete Belege fehlen: wartet-auf-003, wartet-auf-004, wartet-auf-011, wartet-auf-012 (gefunden: keine)
- **zeitraum-01** (zeitraum, kritisch): Frage „Was lief letzte Woche mit dem Angebot für das Klinikum Rheingau-Süd?“; Weg: arbeitsstand/memory_evidence
  - verbotene Belege im Kontext: zeitraum-003, zeitraum-005 (ungekennzeichnet: keiner; gekennzeichnet: überholt: zeitraum-003, zeitraum-005; außerhalb des Zeitraums: zeitraum-003, zeitraum-005)
- **zeitraum-04** (zeitraum, normal): Frage „Was ist im Frühjahr mit dem Angebot für das Klinikum Rheingau-Süd passiert?“; Weg: arbeitsstand/memory_evidence
  - verbotene Belege im Kontext: zeitraum-009, zeitraum-010, zeitraum-011, zeitraum-013 (ungekennzeichnet: keiner; gekennzeichnet: überholt: zeitraum-009, zeitraum-011; außerhalb des Zeitraums: zeitraum-009, zeitraum-010, zeitraum-011, zeitraum-013)
- **zeitraum-05** (zeitraum, normal): Frage „Was ist diese Woche beim Klinikum Rheingau-Süd Neues eingegangen?“; Weg: arbeitsstand/memory_evidence
  - verbotene Belege im Kontext: zeitraum-011 (ungekennzeichnet: keiner; gekennzeichnet: überholt: zeitraum-011; außerhalb des Zeitraums: zeitraum-011)
- **zusage-abgesagt-01** (aktualitaet, kritisch): Frage „Findet der Workshop bei der Akademie Taunus am 28. Oktober statt?“; Weg: arbeitsstand/memory_evidence
  - verbotene Belege im Kontext: zusage-abgesagt-001, zusage-abgesagt-002, zusage-abgesagt-003 (ungekennzeichnet: keiner; gekennzeichnet: überholt: zusage-abgesagt-001, zusage-abgesagt-002, zusage-abgesagt-003)
- **zusage-abgesagt-04** (aktualitaet, normal): Frage „Muss ich noch etwas wegen des Hotels in Bad Homburg tun?“; Weg: arbeitsstand/memory_evidence
  - verbotene Belege im Kontext: zusage-abgesagt-006 (ungekennzeichnet: keiner; gekennzeichnet: überholt: zusage-abgesagt-006)
- **zusage-abgesagt-06** (mehrdeutigkeit, normal): Frage „Was ist eigentlich mit dem Workshop?“; Weg: bedeutungsfrage/memory_evidence
  - erwartete Belege fehlen: namensgleich-004 (gefunden: zusage-abgesagt-008, adresse-geaendert-011)

## Hinweise der Weltprüfung

- szenarien/kontakt-vor-jahren.json [kontakt-vor-jahren-03]: Pflichtaussage ['Oktober 2023', 'Okt. 2023', '10.2023', 'Herbst 2023', 'Okt 2023', '10/2023', '2023-10', 'Oktober und November 2023', 'Oktober/November 2023'] kommt in keinem Beleg wörtlich vor (ein Modell müsste sie umformulieren).
- szenarien/meeting-protokoll.json [meeting-protokoll-05]: Pflichtaussage ['18.09.2026', '18. September 2026', '18.09.', '18. September', '18. Sep.', '2026-09-18', '18.09', '18.9.'] kommt in keinem Beleg wörtlich vor (ein Modell müsste sie umformulieren).
- szenarien/wartet-auf.json [wartet-auf-03]: Pflichtaussage ['25.09.2026', '25. September 2026', '25.09.', '25. September', '25. Sep.', '2026-09-25', '25.09', '25.9.'] kommt in keinem Beleg wörtlich vor (ein Modell müsste sie umformulieren).

## Was diese Messung nicht sagt

- Sie misst eine erfundene Welt; sie ist kein Beleg für die Qualität am echten Postfach (dafür `python -m messlatte lokal`).
- Null beobachtete Fehler beweisen keine Fehlerwahrscheinlichkeit von null; die Fallzahl steht immer daneben.
- Termine liegen als Episoden im Bestand, aber nur im Gedächtnisfenster (3 Jahre zurück, 1 Jahr voraus); ältere oder fernere Termine sind unsichtbar.
