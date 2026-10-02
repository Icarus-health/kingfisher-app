# Messlatte: Messprotokolle

Jede Messung liegt hier als Markdown (für Menschen) und JSON (für den
Vergleich). Wie gemessen wird, steht in [`messlatte/README.md`](../../../messlatte/README.md),
das Format der Welt in [`messlatte/FORMAT.md`](../../../messlatte/FORMAT.md).

## Verlauf auf einen Blick (Stufe Abruf, ohne Modell)

| Stand | Belege gefunden (von 136) | Fragen vollständig (von 71) | Rückfragen mit allen Bedeutungen (von 7) | Fragen mit verbotenen Belegen (von 77) |
|---|---|---|---|---|
| Basis (vor C) | 95 · 10k: 85 | 42 · 10k: 37 | 0 | 15 · 10k: 15 |
| nach C1–C4 zusammen | **121** · 10k: **99** | **62** · 10k: **51** | 2 | 21 · 10k: 18 |
| nach E1 (Frage verstehen, Rückfall ohne Modell) | 121 · 10k: 103 | 62 · 10k: 53 | **7** | 21 · 10k: 18 |
| nach E2/E3 (16 Plätze, Akten im Kontext; konstante Einordnung) | 123 · 10k: 106 | 63 · 10k: 55 | 7 | 21 · 10k: 18 (alle ungekennzeichnet, ohne Arten) |
| dito mit Regel-Einordnung (`--einordnung regel`): vorher → nachher | 120 → 124 · 10k: 105 → 109 | 61 → 64 · 10k: 54 → 57 | 7 | 21 → 21 · 10k: 18 → 18; **ungekennzeichnet 21 → 15 · 10k: 18 → 13** |
| **Endstand** nach Aufräumen (Regel-Einordnung), Commit `64bf811` | 124 · 10k: 109 | 64 · 10k: 57 | 7 | 21 · 10k: 18; ungekennzeichnet 15 · 10k: 13 |
| **Namensvettern und Zeiträume gekennzeichnet** (Regel-Einordnung), Commit `2391d82` | 124 · 10k: 109 | 64 · 10k: 57 | 7 | 21 · 10k: 18; **ungekennzeichnet 8 · 10k: 8**; gekennzeichnet nach Art (Belege, ohne Rauschen): überholt 10, andere Person 7, außerhalb des Zeitraums 12 |
| Suchindex-Einstellung `wortteile_jahre` = 0 (Vorgabe), Regel-Einordnung, gemessen vor der Kennzeichnung | 124 · 10k: 109 (keine Frage weicht ab) | 64 · 10k: 57 | 7 | 21 · 10k: 18; ungekennzeichnet 15 · 10k: 13 |
| dito mit `--wortteile-jahre 2` (Versuch, nicht Vorgabe) | 124 · 10k: **110** | 64 · 10k: 57 | 7 | 21 · 10k: 18; ungekennzeichnet 15 · 10k: 13 |
| **Zweistufige Auswahl** (Regel-Einordnung), Berichte `2026-09-30-zweistufig-*`: kurze Welt wie bisher; lange Welt (`--lange-quellen`) vorher → nachher | 124 · 10k: 109 (unverändert); **lang 114 → 117 · 10k: 106 → 109** | 64 · 10k: 57 (unverändert); lang 55 → 57 · 10k: 51 → 54 | 7 (lang 6 → 6, 10k 5 → 5) | 21 · 10k: 18 (unverändert), ungekennzeichnet 8 · 10k: 8; lang 16 → 18 · 10k: 11 → 15 (ungekennzeichnet 2 · 2); **Kontext abgeschnitten lang 3 → 0 Fragen (auch mit 10k)**, Quellen im Kontext 9,9 → 13,4 |
| **Endstand Runde 1** (Regel-Einordnung), Commit `bd90b1f`, Berichte `2026-09-30-runde1-endstand-*` | 124 · 10k: 109 | 64 · 10k: 57 | 7 (unnötige 0 von 70) | 21 · 10k: 18; ungekennzeichnet 8 · 10k: 8; Kontext abgeschnitten 0 |
| **Lint über alle Akten** (M2, Welt + Szenario `widersprueche`, 188 Quellen), Regel-Einordnung, vorher (`807bbc9`) → nachher, Berichte `2026-09-30-lint-*` | 124 → 124 · 10k: 109 → 109 (gleiche Fehlerliste; Rang 1: 26 → 27) | 64 → 64 · 10k: 57 → 57 | 7 → 7 | unverändert. **Stufe Lint: erwartete Befunde 5 von 5, Fehlalarme 0** (auch mit 10k), Fakten unverändert; konstante Einordnung ebenfalls unverändert (123 · 10k: 106) |
| **Zweites Tor (Prüfmodell)** und sechs Fragen der Kategorie `inhalt`, Berichte `2026-09-30-pruefmodell-*` (Regel-Einordnung); die alten 77 Fragen getrennt ausgewertet, das Rauschen ist Quelle für Quelle gleich | alte Fragen 124 · 10k: 109 (unverändert); neue 6 von 6 · 10k: 6 von 6; gesamt 130 von 142 · 10k: 115 | alte 64 · 10k: 57; neue 6 von 6 | 7 (unnötige 0 von 76) | alte 21 · 10k: 18, ungekennzeichnet 8 · 10k: 8; neue 0. **Stufe Antwort, Skriptmodelle, nur `inhalt`:** sorgfältig mit Prüfmodell 6 von 6 richtig, 0 verworfen; unaufmerksam mit Prüfmodell 6 von 6 richtig, 0 falsche Aussagen, **6 Sätze vom Prüfmodell verworfen**, 0 von der Satzprüfung ohne Modell; unaufmerksam ohne Prüfmodell **6 von 6 falsche Aussagen** (die Lücke, die das Tor schließt) |
| **Endstand Runde 2** (Regel-Einordnung), Commit `c1ba712`, Berichte `2026-09-30-runde2-endstand-*` | 130 · 10k: 115 (von 142) | 70 · 10k: 63 (von 77) | 7 (unnötige 0 von 76) | 21 · 10k: 18 (von 83); ungekennzeichnet 8 · 10k: 8; Kontext abgeschnitten 0; Stufe Lint 5 von 5, 0 Fehlalarme |
| **Lange Quellen in Abschnitten** (M2), Berichte `2026-09-30-abschnitte-*` (Regel-Einordnung, ohne Modell), vorher (`c1ba712`) → nachher; 142 Belege, Fragen der Kategorie `inhalt` eingerechnet; Beschreibung in [`docs/35-belegte-antworten.md`](../../35-belegte-antworten.md#lange-quellen-in-abschnitten) | kurz 130 → 130 · 10k: 115 → 115 (unverändert); **lang 123 → 127 · 10k: 114 → 117**; „wegen Länge nie eingeordnet“ 5 → **0** (beide langen Läufe) | kurz 70 → 70 · 10k: 63 → 63; lang 63 → 67 · 10k: 59 → 61 (von 77) | unverändert | Kontext abgeschnitten 0 → 0; unnötige Rückfragen 0 (lang 10k: 1, wie vorher). Netto +4 statt +5 auf der langen Welt: `meeting-protokoll-009` in fünf Fragen gewonnen, `terminvorbereitung-008` an allgemeine Treffer der jetzt einordenbaren Transkripte verloren; neu auf der langen Welt: 1 erwarteter Beleg im Kontext ohne tragende Textstelle (`meeting-protokoll-009`, vorher 0). Nachgemessen auf dem Merge-Stand `4973b9e`: gleiche Zahlen |
| **Kreis und Privat** (M4, Szenario `privat` mit 29 Quellen ohne Fragen, Stufe Privat), Regel-Einordnung, Berichte `2026-10-01-privat-*`; vorher: Produkt `fa6c03e` mit Messlatte und Welt dieses Zweigs (der Kopf nennt den Commit der Messlatte), nachher `cb42da3`; Beschreibung in [`docs/49-kreis-und-privat.md`](../../49-kreis-und-privat.md) | 130 → 130 · 10k: 115 → 115 (das private Szenario gibt dem Rauschen keine Wörter; Rang 1: 33 · 10k: 30, unverändert) | 70 → 70 · 10k: 63 → 63 | 7 → 7 (unnötige 0 von 76) | 21 · 10k: 19 (unverändert), ungekennzeichnet 8 · 10k: 8. **Stufe Privat: Kreise wie erwartet mit Merkmalen 0 → 9 von 9, falsche innere Kreise 0 (66 Personen · 10k: 2.717 Personen), Akten-Arten 0 → 7 von 7, Fristen 0 → 4 von 4, Zahlen ohne Beleg 0, Fristen aus Quellen ohne Frist 0, nichts bestätigt, keine Aufgabe** (auch mit 10k); Stufe Lint weiter 5 von 5, 0 Fehlalarme |
| **Rest von M4** (Geburtstage, Wiederkehrendes, Sammelbestätigung, PDF-Anhänge, Cloud-Ordner; Szenario `privat` mit 43 Quellen), Regel-Einordnung, Berichte `2026-10-01-m4-rest-*`; vorher: Produkt `a73a291` mit Messlatte und Welt dieses Zweigs, nachher `18360dd`; Beschreibung in [`docs/49-kreis-und-privat.md`](../../49-kreis-und-privat.md#rest-von-m4-geburtstage-sammelbestätigung-anhänge-cloud-ordner) | 130 → 130 · 10k: 115 → 115 | 70 → 70 · 10k: 63 → 63 | 7 → 7 (unnötige 0 von 76) | 21 · 10k: 19 (unverändert), ungekennzeichnet 8 · 10k: 8. **Stufe Privat: Fristen 4 → 6 von 6 (aus PDF-Rechnungen 0 → 2 von 2), PDF-Anhänge 0 → 3 von 3 (ein Scan ehrlich „noch nicht gelesen“), Geburtstage 0 → 3 von 3 und 0 ohne Erwartung, Wiederkehrendes 0 → 8 von 8, Zahlen ohne Beleg 0, Briefing-Probe „Morgen hat Gabriele Geburtstag.“ ohne Kontakt, nichts bestätigt** (auch mit 10k; die erste 10k-Messung fand Wiederkehrendes 7 von 8, behoben) |

Wortteile nur für die letzten zwei Jahre: [`docs/29-suchindex.md`](../../29-suchindex.md), Berichte `2026-09-30-wortteile-2-jahre-*` (Stichtag der Welt 29.09.2026; elf Quellen älter als zwei Jahre; mit 10.000 Rauschquellen verliert `kontakt-vor-jahren-04` den Beleg `-003`, dessen „Küchensoftware“ nur der Trigramm-Index als Wortteil findet).

E2/E3: [`docs/35-belegte-antworten.md`](../../35-belegte-antworten.md), Berichte `2026-09-30-*`. Namensvettern und Zeiträume: [`docs/39-kennzeichnung.md`](../../39-kennzeichnung.md), Berichte `2026-09-30-namensvettern-regel-*`. Zweistufige Auswahl: [`docs/35-belegte-antworten.md`](../../35-belegte-antworten.md#zweistufige-auswahl-für-lange-quellen). Endstand: `2026-09-30-endstand-regel-*`; die Refaktorierung ließ jede Abrufkennzahl unverändert.

Protokolle: `2026-09-29-nach-c-ohne-rauschen.md`, `2026-09-29-nach-c-10k-rauschen.md`; E1: `2026-09-29-vor-e1-*` und `2026-09-29-nach-e1-*` (Einzelheiten in [`docs/31-frageverstaendnis.md`](../../31-frageverstaendnis.md): Rückfragen 2 → 7 von 7, Fragen im freien Chat 12 → 1 von 77, unnötige Rückfragen 0 von 70).
Mehr verbotene Belege im Kontext heißt: Die Suche findet jetzt auch veraltete
Fassungen. Sie auszusortieren oder als „vorher“ zu kennzeichnen ist Aufgabe von
D (Stand in der Akte) und E (Antwort).

## Basis, 29. September 2026 (vor Etappe C)

Welt v1: 14 Szenarien, 176 Quellen, 77 Fragen. Ohne Modell, also nur die Stufe
„Abruf“: Findet die Suche die Quellen, die ein Modell für die richtige Antwort
bräuchte?

| Kennzahl | ohne Rauschen | mit 10.000 Rauschquellen |
|---|---|---|
| Erwartete Belege gefunden | 95 von 136 | 85 von 136 |
| Fragen mit allen erwarteten Belegen | 42 von 71 | 37 von 71 |
| Erwartete Belege auf Rang 1 | 29 von 136 | 29 von 136 |
| Fragen mit verbotenen Belegen im Kontext | 15 von 77 | 15 von 77 |
| Rückfragen mit allen Bedeutungen | 0 von 7 | 0 von 7 |

Die Antwortqualität ist noch **nicht gemessen**: In der Entwicklungsumgebung
läuft kein Modell. Das erste Modell misst der Nutzer auf seinem Mac.

## Nach C1 (Termine im Gedächtnis), 29. September 2026

Erwartete Belege 95 → 101 von 136 (mit 10.000 Rauschquellen 85 → 91), Fragen mit allen
Belegen 42 → 47 von 71 (37 → 41), Rang 1 29 → 26 (Termine rücken vor), verbotene Belege
15 → 15 von 77 (mit Rauschen 15 → 14). Einzelheiten, betroffene Fragen und Sabotageprobe:
[`docs/28-termine-im-gedaechtnis.md`](../../28-termine-im-gedaechtnis.md).

## Nach C2 (Suchindex über alle Rohquellen), 29. September 2026

| Kennzahl | ohne Rauschen (C1 → C2) | 10.000 Rauschquellen | 50.000 Rauschquellen |
|---|---|---|---|
| Erwartete Belege gefunden | 101 → 119 von 136 | 91 → 97 | 87 → 95 |
| Fragen mit allen Belegen | 47 → 60 von 71 | 41 → 49 | 39 → 46 |
| Belege bis Rang 12 | 99 → 117 von 136 | 89 → 95 | 85 → 93 |
| Fragen mit verbotenen Belegen im Kontext | 15 → 21 von 77 | 14 → 18 | 12 → 18 |

Mehr Vollständigkeit heißt hier auch mehr Kontext: Die Auswahl zeigt im Mittel 11,6
statt 8,3 verschiedene Quellen, und darunter sind mehr veraltete Fassungen und
Namensvetter (die Zahl der Fragen mit verbotenem Beleg im Kontext steigt). Belege
schwanken von Lauf zu Lauf um etwa ±2. Einzelheiten, betroffene Fragen,
Kosten (Größe, Dauer) und Sabotageproben:
[`docs/29-suchindex.md`](../../29-suchindex.md). Berichte:
`2026-09-29-nach-c1-*` (Stand mit Terminen, vor dem Index), `2026-09-29-nach-c2-*`
und `2026-09-29-basis-50k-rauschen` (Basis mit 50.000 Rauschquellen).

## Befunde am Produkt aus dem Bau der Messlatte

1. **Termine liegen nicht im Gedächtnis** (behoben mit C1, siehe oben). Das Produkt liest Termine bei jeder
   Frage aus dem Kalender, ±30 Tage im laufenden Jahr. Vergangene Treffen sind
   für Rückblicke unsichtbar, Terminnotizen gehen verloren.
2. **Offene Fragen werden eng erkannt.** „Was ist eigentlich mit Mainz los?“
   gilt nicht als offene Frage; `bedeutungen.begriff_aus_frage` erwartet genau
   „Was ist mit X los?“. *Behoben in E1: `frage.py`, siehe
   [31-frageverstaendnis.md](../../31-frageverstaendnis.md).*
3. **Rückfragen bieten nicht alle Bedeutungen an.** Private Bedeutungen gehen in
   „Weitere Erwähnungen“ unter. *Behoben in E1: 7 von 7 Rückfragen bieten alle Bedeutungen an.*
4. **Veraltete Quellen bleiben im Abrufkontext** (alte Fristen, alte Adressen).
5. **Komposita und Paraphrasen** werden nicht gefunden („Stromrechnung“ gegen
   „Rechnung Strom“, „bezahlt“ gegen „Überweisung“). Komposita behoben mit C2
   (Suchindex), Paraphrasen mit E1 als Umschreibungen der Rolle `frage`
   (nur mit Modell messbar, ohne Modell unverändert offen).
6. **Mails speichern nur den Absender als Teilnehmer**; Empfänger und Cc fehlen.
   Damit fehlt die Hälfte der Beziehungen. *Behoben in Etappe C3, siehe
   [C3-identitaet.md](C3-identitaet.md).*
7. **Mailaufnahme baut je Mail einen TLS-Kontext** (rund 23 ms) und je Mail eine
   Verbindung. *Behoben in C4, siehe unten.*
8. **Der Ordner-Adapter bricht bei 5.000 Dateien ab**, Duplikate zählen mit.
   *Behoben in C4: nur Neues zählt gegen die Grenze.*
9. **Gleiche Zeitstempel** von Frage und Antwort machen die Reihenfolge im
   Gespräch unbestimmt (nur bei eingefrorener Uhr beobachtet).

## Etappe C4: Aufnahme schnell und vollständig (29. September 2026)

Was sich am Produkt geändert hat (Befunde 7 und 8 und ihre Nachbarn):

- **Eine IMAP-Verbindung je Aufnahmedurchgang.** `MailConnector.session()`
  hält Verbindung und gewählten Ordner für alle Abrufe eines Durchgangs
  (`Intake.step` öffnet sie). Bricht die Verbindung ab, verbindet die Sitzung
  einmal neu; ein zweiter Abbruch in Folge wird als Fehler gemeldet und der
  Eintrag geht in die bekannte Wiederholung mit Wartezeit. Die Sitzung gehört
  dem Thread, der sie öffnet: Antworten im Gespräch nutzen weiter eigene
  Verbindungen. Der TLS-Kontext wird je Verbindungsobjekt einmal gebaut.
- **Zugriffstoken-Speicher** in `google_oauth.access_token`: bis 120 s vor
  Ablauf wiederverwendet, je Konto ein Refresh auch bei gleichzeitigen
  Aufrufern, der Netzaufruf läuft **nicht** unter der gemeinsamen Sperre. Der
  Speicher gilt nur für genau den Zugang, der ihn erzeugt hat: Entfernt oder
  neu verbunden, gibt es nie das alte Token.
- **Filter im neuen Aufnahmeweg** (`mail_filter.intake_screen`): gesperrte
  Absender, Spam-Kopf, Newsletter nach Einstellung, ohne Modellaufruf.
  Ausgefiltertes wird **nicht aufgenommen, aber gezählt**: Status
  `filtered:<Kategorie>` je Eintrag, im Aufnahmestatus als `filtered` und
  `filtered_by`. „Erneut versuchen“ prüft es nach geänderten Regeln neu.
  Papierkorb, Spam und Junk-Ordner lehnt `Intake.start` ab.
- **Prüfbereich** (alter Pfad): Ein voller Bereich (500) bricht die Aufnahme
  nicht mehr ab, sondern zählt `overflow` (sichtbar in `GET /api/v1/mail-filter`).
  Unverändert Vermerktes schreibt die Einstellungsdatei nicht erneut.
- **Ordner-Adapter:** Die Grenze (5000) zählt nur **neue** Einträge; jeder
  Lauf kommt weiter, der Quellenabgleich (Entfernen) läuft erst im
  vollständigen Lauf.
- **`Intake.status`** liest in Fenstern zu 1000 Einträgen mit je eigener
  kurzer Sperre statt unter einer Sperre über den ganzen Bestand.
- **Hintergrundtakt:** 25 statt 8 Nachrichten je 30 Sekunden. Der Rückstau-Stopp
  (200 nicht eingeordnete Mails) bleibt: Er schützt die Nachanalyse, nicht die
  Verbindung.

Messung (Welt v1, ohne Modell, Produktpfad mit Fake-IMAP). Die Maschine war
mit Last 8 bis 17 auf 4 Kernen geteilt, die Wandzeit schwankt deshalb um den
Faktor 2 (Basis derselben Änderung: 86 bis 270 s bei 10.000). Verglichen wird
die CPU-Zeit des Messprozesses:

| Rauschen | CPU vorher | CPU nachher | Abrufkennzahlen |
|---|---|---|---|
| 10.000 | 65,4 s | 61,8 s | identisch |
| 50.000 | 430,1 s | 420,5 s | identisch |

Abrufkennzahlen (gefundene Belege, Rang, verbotene Belege) sind in beiden
Größen bitgleich; nur die Dauer unterscheidet die Berichte. Die Messlatte
kann den Hauptgewinn nicht zeigen: Ihre Attrappe ersetzt TLS-Kontext und
Anmeldung. Ein Mikrotest mit echtem `ssl.create_default_context()` und
derselben Attrappe (200 Abrufe): **25,2 ms je Mail vorher, 0,14 ms nachher**.
Im Netz kommen Handshake, Anmeldung und OAuth-Refresh je Mail hinzu, die die
Sitzung und der Token-Speicher ebenfalls sparen.

Offen: Die Prüfung mit KI (`ai_enabled`) gilt weiter nur im alten Pfad; der
Hintergrundtakt läuft ohne Modell. Ausgefilterte Nachrichten haben in der neuen
Aufnahme keine Einzelansicht zum „Doch aufnehmen“, nur die Sammelwiederholung.
