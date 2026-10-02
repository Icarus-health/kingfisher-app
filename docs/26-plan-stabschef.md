# Plan: vom Gedächtnis zum Stabschef

Stand: 29. September 2026. Gemeinsam mit dem Nutzer festgelegt nach einer
vollständigen Code- und Dokumentationsprüfung. Dieses Dokument ersetzt keine
Produktvision (`00-produktvision.md`) und keinen Etappenweg (`24-weg-zum-jarvis.md`),
es legt die **Reihenfolge der Arbeit** fest und hält die Entscheidungen fest, die
dafür getroffen wurden.

## Das Ziel in einem Absatz

Ein Stabschef, eine Mischung aus Jarvis und Pepper: ein einziger Ort, an dem
Mails, Termine, Gespräche, Aufgaben und Notizen zusammenfließen, eingeordnet
werden und vorbereitet zur Verfügung stehen. Er liefert **nie falsche
Informationen**, findet auch die Person von vor drei Jahren, klärt „Was ist mit
Mainz los?“, baut Akten über Menschen, Projekte und Themen, erinnert an Fristen,
bereitet Termine vor und legt morgens ein Briefing vor: wohin, wie lange, was
mitnehmen, wer will was, mit welchem Hintergrund. Er läuft lokal. Er handelt viel
selbst und fragt nur an den wichtigen Punkten.

## Warum die Reihenfolge so ist

Die Prüfung vom 29. September ergab: Die Sicherheitslinie ist stark (Belege,
Vorschlag statt Fakt, Widerruf mit Kaskade). Aber das Fundament trägt den
Anspruch noch nicht:

- Antworten bestehen aus Originalwortlaut. Das ist sicher, aber es ist ein
  Archivar, keine Pepper.
- Kontext entsteht erst im Moment der Frage, über deutsche Suchmuster.
- Personen werden über Namenstexte erkannt, nicht über Adressen.
- Über die Rohquellen gibt es keinen dauerhaften Suchindex.
- Es gibt keinen Maßstab, der sagt, ob eine Änderung das System besser macht.

Deshalb zuerst messen, dann das Fundament, dann die Akten, dann der Stabschef.

## Der Kern: vorbereiten statt nachschlagen

Kingfisher pflegt im Hintergrund **Akten** zu Personen, Projekten, Themen und
Orten: Lage, Verlauf, offene Punkte, Fristen, Beziehungen.

- Jeder Satz einer Akte trägt einen Quellverweis und wird maschinell gegen seine
  Quelle geprüft. Was sich nicht belegen lässt, fällt heraus.
- Akten sind eine **abgeleitete Ansicht**, kein Bestand, und jederzeit neu
  erzeugbar (wie der Graph). Sie entstehen automatisch.
- Nur **echte Fakten** im Bestand brauchen die Bestätigung des Nutzers
  (`10-verdichtung.md` gilt unverändert).
- Fragen, Briefing und Terminvorbereitung lesen aus denselben Akten. Das hält
  die Antworten kurz und schnell, weil das Modell eine vorbereitete Akte liest
  statt tausend Mails.

## Etappen

Jede Etappe ist fertig, wenn die Messlatte es sagt, nicht wenn der Code steht.

| Etappe | Inhalt | Fertig heißt |
|---|---|---|
| **A – Vertrauen sichern** | MCP-Tür standardmäßig aus und abgedichtet; `recall`-, Zusammenfassungs- und Einstellungsfehler behoben; Tauri und Altoberfläche entfernt | Belegte Fehler haben Regressionstests mit Sabotageprobe; ein Auslieferungsweg, eine Oberfläche |
| **B – Messlatte** | Synthetische Welt (drei Jahre einer erfundenen Person) mit Fragen je Kategorie; Stufen Aufnahme, Abruf, Antwort; Rauschen für 10k/50k Quellen; Modus für eigene Fragen auf echten Daten, der nur Zahlen ausgibt | Ein Befehl misst den Ist-Stand; falsche Aussagen stehen als erste Zahl im Bericht |
| **C – Fundament** | Identität über Anker (Adresse, Nummer), Namen als Aliasse; dauerhafter Index (Volltext + Embeddings) über alle Rohquellen; schnelle Mailaufnahme; Filter im neuen Aufnahmeweg | „Kontakt vor drei Jahren“ und Personenfragen bestehen die Abrufstufe auf 50k Quellen |
| **D – Akten** | Personen, Projekte, Themen, Orte; im Hintergrund gepflegt; Satzbelege geprüft; ruhige Aktenansicht | Aktenfragen der Messlatte ohne falsche Aussage |
| **E – Fragen verstehen** | Frageverständnis über die Kartei statt Suchmuster; Mehrdeutigkeit als Ein-Klick-Rückfrage; Antworten aus Akten und Quellen mit Satzprüfung | Mehrdeutigkeit, Paraphrase, Zeitraum bestehen; Antwortzeit im Ziel |
| **F – Stabschef** | Fristen und Zusagen aus allen Quellen; Terminvorbereitung; Morgenbriefing mit Wegezeit; Transkripte; Wetter und Nachrichten | Eine Woche Alltag auf dem Mac ohne übersehene oder falsche Information |

Die Oberfläche wächst parallel: Jede Etappe bekommt ihre Oberfläche, sobald die
Messlatte grün ist. Einrichtungsassistent und Start ohne Terminal gehören dazu.

Bewusst später: Aktionen nach außen über die MCP-Tür, Sprache, Browsersteuerung.

## Entscheidungen des Nutzers (29.09.2026)

**Modelle.** Zielgerät heute ist ein M2 Max mit 32 GB, später auch andere
Rechner und Kollegen mit eigener Installation. Cloud-Modelle dürfen angeschlossen
werden, wenn der jeweilige Nutzer das für seinen Datenschutz vertretbar findet.
Das heutige 4B-Modell ist nicht gesetzt. Richtung: Modelle nach **Rolle**
kombinieren statt ein Modell für alles.

| Rolle | Anforderung | Ansatz |
|---|---|---|
| Frageverständnis | schnell (< 1 s), strukturierte Ausgabe | kleines lokales Modell |
| Antwort formulieren | belegt, kurz, wenige Sekunden | mittleres lokales Modell, optional Cloud |
| Akten, Einordnung, Fristen | gründlich, darf langsam sein | größtes vertretbares lokales Modell, nachts |
| Suche nach Bedeutung | dauerhaft, lokal | Embedding-Modell (heute bge-m3) |
| Satzprüfung | streng, billig | deterministische Belegprüfung, ggf. kleines Modell |

Welche konkreten Modelle, entscheidet die Messlatte, nicht eine Annahme.

**Gespräche und Meetings.** Telefonate werden nicht aufgezeichnet. Meetings
(z. B. MacWhisper, Teams, Meet) liefern Transkripte. Weg: ein
**Transkript-Eingangsordner**, in den jede App exportieren kann; später direkte
Anbindungen, wo ein Dienst Transkripte ablegt (Meet in Google Drive, Teams über
Microsoft Graph). Für Telefonate: Nach einem Anruf- oder Kalendertermin fragt
Kingfisher knapp nach, was herauskam; die Antwort wird eine Quelle.

*Umgesetzt in Etappe F3, siehe [`34-gespraeche.md`](34-gespraeche.md).*

**Wegezeit.** Adressen dürfen dafür den Rechner verlassen. Plattformunabhängig
über eine Anbieter-Schnittstelle: auf dem Mac Apple Karten über den Mac-Helfer
(ohne Schlüssel), sonst ein Kartendienst mit optionalem Schlüssel, ohne Dienst
ein Hinweis ohne Zeitangabe.

**Akten** entstehen automatisch, nur echte Fakten brauchen Bestätigung.

**Wetter und Nachrichten** sind gewünscht, kommen in Etappe F.

## Ergänzung vom Abend des 29.09.2026

**Schichten im Gedächtnis.** Der Nutzer denkt das Gedächtnis als Schichtablage:
unten alles, darüber immer stärker verdichtet, oben die grobe Lage. Das ist der
richtige Aufbau; er wird **nach Sache** geordnet, nicht nur nach Zeit:

| Ebene | Inhalt | Heute vorhanden |
|---|---|---|
| 0 – Rohmaterial | Mail, Transkript, Termin, Notiz, unverändert | Episoden (ohne Termine) |
| 1 – Auszug je Quelle | wichtige Punkte mit exakter Textstelle | Arbeitsgedächtnis (`working_memory_*`) |
| 2 – Akte je Sache | Verlauf, offene Punkte, Fristen je Person, Projekt, Thema, Ort | Mappe ohne Modell (`mappe.py`), nur Projekt/Person |
| 3 – Lage | zwei, drei Sätze | fehlt |

Jede Ebene verweist nach unten bis zum Original. Die Suche läuft von oben
(schnell) und von unten (vollständig) zugleich. Ebenen 1–3 sind abgeleitet und
jederzeit neu erzeugbar; jeder Satz wird gegen seine Quelle geprüft.

**Markierungen.** Jede Quelle trägt beliebig viele Bezüge: Person, Projekt,
Thema, Ort und die Art (Frist, Zusage, Entscheidung, Termin). Aus den Bezügen
entstehen die Akten. Das baut auf den vorhandenen Themen
(`memory_categories.py`) und der Einordnung auf, statt ein zweites System zu
schaffen.

**Modelle nach Aufgabe, lokal und schnell.** Die schwere Arbeit (Einordnen,
Akten, Lage) läuft im Hintergrund mit dem größten vertretbaren Modell. Zur
Frage liest ein kleines Modell die Frage, ein mittleres liest fertige Akten.
Kandidaten für einen Mac mit 32 GB sind Mixture-of-Experts-Modelle mit wenigen
aktiven Parametern (etwa die Qwen3.6-35B-A3B-Klasse). Entschieden wird mit der
Messlatte auf dem Zielgerät. Cloud bleibt je Aufgabe zuschaltbar.

**Modellempfehlung per Geräte-Scan.** Kingfisher erkennt Chip und
Arbeitsspeicher (`device_profile.py` gibt es für den Mac bereits), schlägt je
Aufgabe das passende Modell vor und lädt es nach einem Klick. Kommt mit den
Modellrollen.

**Windows.** Der Kern läuft im Container und damit auch unter Windows. Neue
Teile dürfen den Kern nicht an den Mac binden; Mac-Helfer bleiben optionale
Zusätze.

## Stand der Etappen (Nacht zum 30.09.2026)

Alle Etappen sind gebaut und ohne Modell gemessen. „Fertig heißt“ ist damit
für den Teil erfüllt, der sich hier messen lässt; der Rest braucht das Zielgerät.

| Etappe | Umgesetzt | Messung ohne Modell | Offen, braucht den Mac |
|---|---|---|---|
| A | MCP-Tür aus und abgedichtet (auch für `gedaechtnis_vorschlagen`), Fehler behoben, Tauri entfernt | Regressionstests mit Sabotageprobe | – |
| B | Messlatte: Welt v1 (14 Szenarien, 176 Quellen, 77 Fragen), Rauschen, `lokal`-Modus | ein Befehl misst | Antwortstufe mit echtem Modell |
| C | Termine im Gedächtnis, Suchindex über alle Rohquellen, Identität über Adressen, schnelle Aufnahme ([28](28-termine-im-gedaechtnis.md), [29](29-suchindex.md)) | Belege 95 → 121 von 136, mit 10k Rauschen 85 → 99 | 50k auf echten Mails, Indexgröße (etwa 5,5 × Text) |
| D | Bezüge und Akten je Person, Projekt, Thema, Ort; Lage mit Satzprüfung ([30](30-akten.md), [32](32-lage.md)) | Stufe Akten: 5 von 5 Fällen, überholter Wert nie als Stand (Regel-Einordnung statt Modell) | Lage mit echtem Hintergrundmodell |
| E | Frageverständnis mit Ein-Klick-Rückfrage, Antworten aus Akten, Sätze mit Belegprüfung ([31](31-frageverstaendnis.md), [35](35-belegte-antworten.md)) | Rückfragen 0 → 7 von 7, unnötige 0 von 70; ungekennzeichnete veraltete Belege 21 → 15 | Satzqualität, Paraphrasen, Antwortzeit |
| F | Terminvorbereitung, Morgenbriefing, Fristen, Packliste, Wegezeit, Transkripte und Nachfragen, Wetter und Nachrichten, Modellrollen mit Geräte-Scan, Einrichtungsassistent ([33](33-briefing-und-vorbereitung.md), [34](34-gespraeche.md), [36](36-welt-und-wetter.md)) | Tests und Browserproben mit synthetischen Daten | eine Woche Alltag; Swift-Teile (Kalender, Karten, Transkriptwahl); Ollama-Modellnamen im Katalog |

Unabhängige Prüfung der Etappen D und F: [37-pruefbefunde.md](37-pruefbefunde.md).

## Runde 1 nach den Etappen: Alltag (30.09.2026)

Vor der ersten Alltagswoche, in der Reihenfolge des Nutzens; alles ohne Modell
messbar, PR #128:

1. **Rückkanal für Fehler** – „Stimmt nicht?“ unter jeder Antwort, Export als
   Fall für die Messlatte ([38-rueckkanal.md](38-rueckkanal.md)). *Fertig.*
2. **Namensvettern und Zeiträume** im Antwortkontext kennzeichnen.
3. **Antwortzeit** messen, zeigen, Schalter „Sätze an/aus“.
4. **Zweistufige Auswahl** für lange Mails (erst Kandidaten, dann Absätze).
5. Freemail-Listen zusammenlegen; Indexgröße als Einstellung; Push-Hook.

*Runde 1 ist in `main` (PR #128), alle fünf Punkte.*

## Runde 2: Buchführung (nach Runde 1) — *in `main` seit 30.09.2026, PR #129*

Das Zielbild und die Meilensteine M1 bis M7 stehen in [`41-zielbild.md`](41-zielbild.md); Runde 2 ist dort M2.

Angeregt durch Karpathys „LLM Wiki“-Muster (Rohquellen → gepflegtes Wiki →
Schema; Ingest, Query, Lint, Log). Der Kern deckt sich mit den Akten: Wissen
wird gepflegt, nicht bei jeder Frage neu erzeugt. Der Unterschied bleibt: Bei
uns schreibt das Modell keine Wahrheit, jeder Satz trägt einen Beleg, Fakten
nimmt ein Mensch an. Übernommen wird, was dazu passt:

| Schritt | Inhalt | Fertig heißt |
|---|---|---|
| **Lint** | Regelmäßiger Gesundheitslauf über alle Akten: Widersprüche zwischen Akten zum selben Gegenstand, veraltete Sätze, Sachen ohne Akte, Akten ohne Quellen seit einem Jahr, fehlende Querverweise. Ergebnis sind Vorschläge, keine Änderungen. | Die Messlatte enthält Widerspruchsfälle; Lint findet sie alle, ohne Fehlalarm auf der Welt |
| **Akten als Markdown** | Nächtlicher Export der Akten als lesbarer Ordner mit `index.md` und Rückverweisen, nur lesend, für Obsidian oder jeden Editor. Nichts fließt zurück. | Ein Vault öffnet sich in Obsidian, jede Akte verweist auf ihre Quellen |
| **Logbuch** | Eine Chronik in drei Zeilen für das Briefing: was über Nacht aufgenommen, welche Akten neu, was Lint fand. Gebaut: [`44-logbuch.md`](44-logbuch.md). | Steht morgens im Briefing, ohne Fachwörter |
| **In die Akte übernehmen** | Ein Klick unter einer gelungenen Antwort macht daraus einen Vorschlag für die Akte; das Gegenstück zu „Stimmt nicht?“. Gebaut: [`45-uebernehmen.md`](45-uebernehmen.md). | Vorschlag, Annahme, Beleg bleibt |

## M3: Für Nicht-Techniker — Befunde der Fremdprobe

Die Fremdprobe ([`48-fremdprobe.md`](48-fremdprobe.md)) fand, dass der Erststart
Erfolg meldete, wo nichts funktionierte. Behoben sind die Befunde 3, 4, 5, 9, 17,
21, 23, 27, 29 und 30: „Postfach verbinden“ meldet sich wirklich an und nennt sonst
den Grund in einem Satz (`mail_anmeldung.py`, IMAP-Attrappe `sidecar/tests/imap_attrappe.py`);
„Mails einlesen“ und die Fertig-Seite sagen nach höchstens einer Viertelminute,
wenn das Postfach nicht antwortet, mit Knopf zum Mail-Schritt; die lokale KI hat
eine einzige Statusquelle (`lokale_ki.py`); die Fertig-Seite bietet Einlesen und
Sortieren einmal an, vorausgewählt (Sortieren erzeugt nur Vorschläge); dazu Name
mitnehmen, Briefing direkt, stimmige Schrittzählung, „Heute:“ am ersten Tag und
„Verbindungen prüfen“ direkt nach Einstellungen → Zugänge. Browserprobe:
`scripts/probe_fremdprobe_ui.py`. Die übrigen Befunde sind in der Fremdprobe als
offen oder anderswo in Arbeit vermerkt.

## M4: Privat ist gleichberechtigt

Gebaut ([`49-kreis-und-privat.md`](49-kreis-und-privat.md)): **Kreis je Person** (innerer Kreis, Kollegen,
Kontakte) als Vorschlag aus Richtung und Dauer des Mailwechsels, privatem oder Firmenanbieter, gemeinsamen
Terminen und Anrede, mit Begründung in einem Satz; Fakt erst nach dem Klick in der Akte, nie automatisch geändert.
Wirkung nur auf Sortierung und Formulierung: Fristen aus der Akte eines bestätigten Kontakts stehen nicht
ungefragt im Briefing, der Antwortkontext trägt den Kreis. **Private Akten-Arten** Haushalt, Familie, Gesundheit,
Verträge aus dem Absender; **Kündigungs- und Zahlungsfristen** aus solchen Mails als Aufgabenvorschläge, nur mit
ausgeschriebenem Datum und wörtlichem Betrag. Die Messlatte hat eine private Welt (Szenario `privat`, Stufe
Privat): 9 von 9 Kreisen, 0 falsche innere Kreise, 7 von 7 Akten-Arten, 4 von 4 Fristen, Abruf der übrigen Welt
unverändert.

Rest von M4 ([`49-kreis-und-privat.md`](49-kreis-und-privat.md#rest-von-m4-geburtstage-sammelbestätigung-anhänge-cloud-ordner)):
**Geburtstage** (eigener Glückwunsch, eigene Angabe, Kalender) nur für den inneren Kreis und **Wiederkehrendes**
(Abschläge, Beiträge, Müllabfuhr, Elternabend, Kalender-Serien) als Vorschläge mit Beleg, Briefingzeile „Morgen hat
Gabriele Geburtstag.“ erst bei bestätigtem Kreis und angenommenem Geburtstag; **Sammelbestätigung** der Kollegen
mit einer Rückfrage in einem Satz und „Liste zurücknehmen“; **PDF-Anhänge** als eigene Quelle mit Seite, Fristen
daraus mit wörtlichem Beleg, gescannt ohne lokales OCR ehrlich „noch nicht gelesen“; **Cloud-Ordner** (OneDrive,
Google Drive, iCloud Drive) als Orte zum Anklicken. Gemessen (Stufe Privat, auch mit 10.000 Rauschquellen): Fristen 4 → 6 von 6,
davon aus PDF-Rechnungen 0 → 2 von 2, PDF-Anhänge 0 → 3 von 3, Geburtstage 0 → 3 von 3 und keiner ohne Erwartung,
Wiederkehrendes 0 → 8 von 8, Zahlen ohne Beleg 0, Briefing „Morgen hat Gabriele Geburtstag.“, Abruf unverändert
(130 von 142 · 10k: 115). Damit ist „Fertig heißt“ von M4 erfüllt (`41-zielbild.md`).

## M5: Gespräche ohne Umweg — erster Teil „Microsoft 365 zuerst“

Gebaut ([`50-microsoft-365.md`](50-microsoft-365.md)): **Mit Microsoft anmelden** über den Gerätecode (Code, Kopierknopf,
Link zu microsoft.com/devicelogin, Stand mit Restzeit), nur lesende delegierte Rechte, Teams-Mitschriften als zweiter
Klick, weil Microsoft dafür immer die Zustimmung der IT verlangt. Microsoft 365 wird an der Adresse über DNS erkannt,
ohne Microsoft zu fragen. **Outlook-Post** läuft durch dieselbe Aufnahme wie IMAP (Stände, Drosselung, Reihenfolge),
der **Kalender** über `calendarView`, **Teams-Mitschriften** vergangener Online-Besprechungen kommen ohne Handgriff
alle zehn Minuten als Quelle mit Sprecher und Uhrzeit, werden dem Termin zugeordnet und eingeordnet (Vorschläge wie
bei jeder Quelle). Ehrliche Sätze für Zustimmung der IT, abgelaufenen Code, Abbruch, kein Netz, fehlende App-Kennung.
Offen in M5: Prüfung mit einem echten Hochschul-Tenant (Fehlercodes, Conditional Access gegen den Gerätecode,
Mitschriften als Teilnehmer), eine vom Projekt veröffentlichte App-Kennung, OneDrive über Graph, weitere Kalender
des Kontos, Meet über Google Drive, lokale Transkription, Telefonnotiz.

## Arbeitsweise

- Ein Agententeam arbeitet parallel in getrennten Arbeitsbäumen; jede Änderung
  wird von einem zweiten Durchgang gegengelesen und lokal vollständig geprüft.
- GitHub Actions läuft derzeit nicht (Minutenkontingent). Maßgeblich ist
  `scripts/ci_lokal.sh`; das Ergebnis steht im PR.
- Kein Spaghetti-Code: neue Fähigkeiten als eigene Module mit einer Aufgabe und
  klaren Datenklassen an den Grenzen. `server.py` wächst nicht weiter; neue
  Routen kommen in eigene `*_routes.py`.
