# Automatik vom 26.10.2026: so wenig selbst tun wie nötig

Stand: 26. Oktober 2026. Entscheidung des Nutzers nach der Abnahme von 1.0.28.

## Der Wunsch

> „Das der Nutzer so wenig wie möglich selber machen muss, nur so viel wie notwendig.“

Dazu vier Beobachtungen aus dem Alltag:

1. Antworten im Gespräch kommen sehr langsam.
2. Postfach und Kalender sollen verlässlich und einfach sein, auch mit mehreren Konten.
3. Privat und Arbeit (oder andere Bereiche) sollen sich in Kalender und Aufgaben
   unterscheiden lassen.
4. Projekte und Aufgaben sollen von selbst entstehen und sich selbst zuordnen,
   Personen ebenso.

## Was heute ist (gemessen und gelesen)

- **Tempo.** Eine Gedächtnisfrage braucht lokal 51 bis 66 Sekunden. Den größten Teil
  nimmt die Auswahl der Quellen durch das lokale Modell (44 bis 59 Sekunden bei 16
  Quellen und rund 12.000 Eingabe-Token,
  [Protokoll](runs/2026-10-12-personal-core-flow/README.md)). Die Gedächtnisantwort
  läuft nur lokal, auch wenn „Cloud für Fragen und Antworten“ eingeschaltet ist
  (`agent.answer_memory`, `working_memory_answers.prepare`, `satzantwort`). Das Modell
  wird nach 15 Sekunden entladen. Die Antwort kommt erst ganz am Ende, ohne
  Zwischenstand.
- **Konten.** Beliebig viele Postfächer und Kalender sind möglich. Ein Name lässt sich
  aber nicht ändern; zwei Gmail-Konten heißen beide „Gmail / Google Workspace“. Es gibt
  keinen Bereich je Konto.
- **Bereiche.** Aufgaben haben kein Feld dafür. Projekte haben ein freies Feld `area`,
  das die Oberfläche nicht setzt.
- **Automatik.** Ohne Klick geschieht heute nur, dass eine Aufgabe der Post folgt
  (erledigt oder wieder bei dir, mit Rückgängig). Akten, Aufgaben und Zuordnungen
  brauchen je einen Klick; „Alle übernehmen“ gibt es nicht. Personen sind Projekten
  nur abgeleitet zugeordnet, Aufgaben gar nicht.

## Die Entscheidungen

| Frage | Entscheidung |
|---|---|
| Tempo | Mit eingeschalteter „Cloud für Fragen und Antworten“ beantwortet die Cloud auch Gedächtnisfragen; der bestehende Einwilligungssatz deckt das ab (Frage und gefundene Textstellen gehen an den Anbieter). Ohne Schalter bleibt alles lokal, wird aber schneller und zeigt seinen Zwischenstand. |
| Aufgaben | Eindeutige Bitten an dich und eigene Zusagen werden **automatisch angelegt**, mit „Von Kingfisher angelegt · Rückgängig“. Projekt und Person werden dabei zugeordnet. Unsichere bleiben Vorschläge, mit „Alle übernehmen“. |
| Projekte | Ein Projekt, das sich in den Mails klar bildet, legt Kingfisher **selbst an** und ordnet die Mails zu, mit Rückgängig. Unklare bleiben Frage. |
| Bereiche | **Je Postfach und Kalender.** Kingfisher schlägt „Privat“ oder „Arbeit“ vor, der Nutzer bestätigt einmal. Mails, Termine, Aufgaben und Projekte erben den Bereich; Filter in Kalender und Aufgaben. Eigene weitere Bereiche sind möglich. |

Diese Tabelle ersetzt in [`17-stabschef.md`](17-stabschef.md) den Satz „Angelegt wird
nur mit diesem Klick“ für eindeutige Aufgaben und den Projektvorschlag für klare Fälle.

## Was unverändert gilt

- **Verdichtung schlägt vor, sie schreibt nicht.** Eine Aufgabe und ein Projekt sind
  Ablage, kein Fakt über einen Menschen ([`30-akten.md`](30-akten.md): „Ein Projekt ist
  Ablage, kein Fakt“). Aussagen über Personen, Entscheidungen und Wissen entstehen
  weiter nur mit Annahme.
- **Was automatisch geschieht, lässt sich sehen und zurücknehmen.** Jede automatische
  Anlage steht mit Grund und „Rückgängig“ da, und Kingfisher merkt sich das
  Zurücknehmen, damit es nicht wiederkommt.
- **Nichts Außenwirksames ohne Freigabe.** Keine Mail, keine Zusage, kein Termin geht
  ungefragt hinaus.
- **Cloud nur mit Einwilligung.** Ohne Schalter verlässt keine Frage den Rechner.

## Pakete

| Paket | Inhalt |
|---|---|
| **T Tempo** | Cloudantwort mit Einwilligung auch für Gedächtnisfragen; lokal schneller (Modell bleibt warm, kleinere Auswahl, Vorwärmen beim Öffnen); die eigene Frage steht sofort da, dazu der Zwischenstand; bei langsamer lokaler Antwort ein Satz mit einem Klick zum Schalter. |
| **K Konten und Bereiche** | Name und Bereich je Postfach und Kalender, mit Vorschlag; Doppelte werden erkannt; Stand je Konto sichtbar; ausgeblendete Kalender bleiben ausgeblendet. Bereich vererbt sich auf Mails, Termine, Aufgaben und Projekte; Filter in Kalender, Aufgaben und Heute. |
| **A Aufgaben von selbst** | Eindeutige Bitten und Zusagen werden Aufgaben, mit Projekt, Person, Frist und Rückgängig; unsichere bleiben Vorschläge mit „Alle übernehmen“; Heute übernimmt den Projekthinweis. |
| **P Projekte von selbst** | Klare Projekte werden angelegt, Mails zugeordnet (auch die Absenderregel ohne Klick), Personen dem Projekt zugeordnet; Heute meldet es mit Rückgängig. |
