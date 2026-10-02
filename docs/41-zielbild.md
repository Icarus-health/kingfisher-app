# Zielbild und Meilensteine

Stand: 30. September 2026, festgelegt mit dem Nutzer. Dieses Dokument sagt,
wie ein Tag mit Kingfisher aussehen soll und in welchen Schritten es dorthin
geht. Die Produktvision (`00-produktvision.md`) und der Etappenweg
(`24-weg-zum-jarvis.md`) bleiben gültig; hier steht die Reihenfolge ab jetzt.

## Der Auftrag in einem Satz

Die Welt ist kompliziert und schnell. Kingfisher soll verlässlich Druck
herausnehmen: erinnern, vorbereiten, einordnen, damit der Mensch weniger
ausführen muss. Beruflich und privat, denn beides drückt.

## Ein Tag mit Kingfisher

**7:10, Briefing.** Drei Zeilen oben: „Über Nacht 41 Mails, 2 neue Akten,
1 Widerspruch (Frist Stiftung). Heute: 3 Termine, Abfahrt 8:20 nach Mainz,
35 min, Regen.“ Darunter je Termin: wer kommt, was die Person zuletzt wollte,
was offen ist, was mitzunehmen ist. Dann die Fristen: Steuerberater bis
Freitag, Versicherung kündbar bis 30.11., Impftermin noch nicht gebucht.

**Im Auto.** Nichts. Kingfisher meldet sich nicht, weil er nicht dran ist.

**11:40, vor dem Termin.** Die Akte: Lage in drei Sätzen, Verlauf, wer schon
abgesagt hat. „Was hatte Anna zuletzt zum Budget gesagt?“ Zwei Sätze, jeder mit
Beleg, gekennzeichnet, ob überholt.

**14:00, nach dem Termin.** „Wie war das Gespräch mit Anna Keller?“ Zwei Sätze
getippt oder das Transkript aus dem Ordner. Daraus zwei Vorschläge: eine
Zusage, eine Frist. Ein Klick je Vorschlag. Erst dann sind es Fakten.

**18:30, privat.** „Was ist mit dem Zahnarzt?“ Rückfrage: „Dein Termin am
12.10. oder die Rechnung vom September?“ Ein Klick. Die Rechnung ist bezahlt,
Beleg: Überweisung vom 14.09.

**22:00, nachts.** Kingfisher ordnet ein, pflegt Akten, prüft sie gegen sich
selbst, schreibt das Logbuch. Morgen früh stehen drei Zeilen da.

**Wenn er sich irrt:** „Stimmt nicht?“, ein Klick, und der Fall landet in der
Messlatte. Beim nächsten Mal nicht mehr.

**Ein Jahr später:** „Wer war die Beraterin von der Stiftung, damals?“ Er
findet sie, mit Adresse, mit dem letzten Stand.

**Nie:** eine Zahl, die in keiner Quelle steht. Eine Mail, die ohne den
Menschen hinausgeht. Ein Fakt, den niemand angenommen hat. Daten, die den
Rechner verlassen, ohne dass je gefragt wurde.

## Meilensteine

| | Meilenstein | Inhalt | Fertig heißt |
|---|---|---|---|
| **M1** | **Verlässlich mit Modell** | Runde 1 (`26-plan-stabschef.md`) in `main`; die drei Messläufe aus `40-messplan-modelle.md`; zweite Satzprüfung mit einem Prüfmodell (`bespoke-minicheck`, `tev1`, `nimble`, gemessen); Unsicherheit je Satz (eine Quelle, alt; mehrere, jung); Ollama-Cloud-Modelle als Cloud erkannt; Speicherbedarf des Orchesters geprüft | Messlatte mit echtem Modell: 0 falsche Aussagen, Median unter 8 s |
| **M2** | **Buchführung** | Runde 2: Lint über alle Akten; Akten als Markdown (Obsidian, nur lesend); Logbuch im Briefing; „In die Akte übernehmen“; Einordnung im Hintergrund mit einem Extraktionsmodell (`nuextract`) statt Regeln, gemessen; lange Transkripte in Abschnitten einordnen; **Hintergrund ohne Nacht** (Reihenfolge nach Nutzen, Drosselung, sichtbarer Fortschritt) | Eine Woche Alltag ohne übersehene Frist; Lint findet alle Widerspruchsfälle der Messlatte ohne Fehlalarm |
| **M3** | **Für Nicht-Techniker** | Zwei Ebenen in den Einstellungen (fünf Schalter vorne, Technik hinten); Feed-Vorgaben zum Anklicken; Autostart beim Anmelden; Fremdprobe durch einen Agenten, der das Produkt nie gesehen hat; Seitenbreite unter 1280 px | Ein Nicht-Techniker richtet Kingfisher in 15 Minuten ein, ohne etwas nachzuschlagen |
| **M4** | **Privat ist gleichberechtigt** | Akten-Arten Haushalt, Familie, Gesundheit, Verträge; **Kreis je Person** (innerer Kreis, Kollegen, Kontakte) als Vorschlag mit Bestätigung; Unterlagen aus synchronisierten Cloud-Ordnern; Kündigungs- und Zahlungsfristen aus Rechnungen; Geburtstage und Wiederkehrendes; Anhänge lesen (OCR für Rechnungen und Verträge, `glm-ocr`/`deepseek-ocr`) | Die Messlatte bekommt eine private Welt; Fristen aus PDF-Rechnungen werden gefunden. **Erreicht** (1.10.2026, gemessen: Szenario `privat` mit 43 Quellen, Fristen aus PDF-Rechnungen 2 von 2, alle Fristen 6 von 6, 0 Zahlen ohne Beleg, auch mit 10.000 Rauschquellen; [`49`](49-kreis-und-privat.md#messung-1)) |
| **M5** | **Gespräche ohne Umweg** | Microsoft 365 zuerst (Graph: Outlook der Hochschule, Teams-Transkripte, OneDrive), dann Meet über Google Drive; lokale Transkription (`gemma4` mit Audio) statt Export; Telefonnotiz per Nachfrage | Ein Meeting erscheint ohne Handgriff als Quelle mit Vorschlägen |
| **M6** | **Handeln als Vorschlag** | Mail-Entwurf, Terminvorschlag, Aufgabe delegieren: dieselbe Karte, dieselbe Annahme mit einem Klick; MCP-Tür für Werkzeuge; jede Aktion protokolliert und rückgängig | Kein Vorgang geht hinaus, den der Mensch nicht mit einem Klick freigegeben hat; jede Aktion im Logbuch |
| **M7** | **Zweiter Rechner** | Windows-Start ohne Terminal; Sicherung und Umzug; ein Kollege richtet es selbst ein | Ein zweiter Mensch nutzt Kingfisher ohne den ersten |

M3 steht bewusst vor M4: Erst muss es einfach sein, dann breiter. Jeder
Meilenstein ist erst fertig, wenn die Messlatte oder die Alltagswoche es sagt,
nicht wenn der Code steht.

## Entscheidungen des Nutzers (30.09.2026)

**Zugänge.** Kalender bei Google und Apple; Post bei Google, bei Microsoft 365
(Hochschule) und in zwei IMAP-Postfächern. Google gibt es, Apple läuft über den
Mac-Helfer, IMAP ist da. Die Lücke ist Microsoft 365: Hochschul-Tenants lassen
oft kein einfaches IMAP-Passwort zu; die Microsoft-Anmeldung (Graph) bringt
Outlook, Teams-Transkripte und OneDrive über einen Zugang. Das ist der erste
Teil von M5.

**Unterlagen.** Liegen in OneDrive, Google Drive und iCloud, alle als
synchronisierte Ordner auf dem Mac. Kingfisher liest diese Ordner (Ordner-
Adapter), die Dateien bleiben, wo sie sind; nichts geht zusätzlich hinaus. Ein
späterer Wechsel des Anbieters ist für Kingfisher nur ein anderer Ordner. Seit
M4 stehen die Ordner zum Anklicken da, und PDF-Anhänge werden gelesen; Bilder und
gescannte Seiten nur mit einem lokalen OCR-Modell.

**Akten zu anderen Menschen.** Ja, Familie und Kollegen. Jede Person bekommt
einen **Kreis** (innerer Kreis, Kollegen, Kontakte): Kingfisher schlägt ihn vor
(Häufigkeit, privater oder Firmenanbieter, Kalender), der Nutzer bestätigt mit
einem Klick. Der Kreis steuert, wie viel im Briefing steht und wie zurückhaltend
Kingfisher über die Person formuliert. Nichts verlässt den Rechner. (M4)

**Hintergrundarbeit ohne Nacht.** Viele schalten den Rechner nachts aus.
„Nachts“ war nie die Bedingung, nur der bequemste Fall. Die Regel:

- Der Hintergrund läuft **immer, wenn der Rechner läuft**, mit niedriger
  Priorität, gedrosselt bei Arbeit im Vordergrund, ohne den Schlaf des Rechners
  zu verhindern und ohne spürbare Last.
- **Reihenfolge nach Nutzen:** erst, was morgen zählt (Termine der nächsten
  Tage, Post von heute), dann der Rückstand. Das Briefing stimmt auch, wenn der
  Rückstand noch nicht abgearbeitet ist.
- **Erstbefüllung sichtbar:** „Kingfisher lernt gerade: 2.400 von 18.000,
  fertig etwa morgen Mittag“, mit dem Hinweis, dass es schneller geht, wenn der
  Rechner anbleibt, ohne Zwang.
- **Autostart** ist eine Frage im Einrichtungsassistenten, an oder aus, keine
  stille Vorgabe.

Das ist ein eigener Punkt in M2; ohne ihn ist die Alltagswoche für die meisten
Rechner nicht ehrlich messbar.

## Beantwortete Fragen (zur Nachvollziehbarkeit)

1. Welche Postfächer und Kalender werden wirklich genutzt (Microsoft 365,
   Gmail, iCloud, mehrere)?
2. Wo landen private Unterlagen heute (PDF im Anhang, Ordner, Fotos)?
3. Soll Kingfisher Termine und Fristen anderer Menschen im Haushalt kennen
   (Schule, Arzt, Kita) oder nur die eigenen? Das ist auch eine Datenschutzfrage.
