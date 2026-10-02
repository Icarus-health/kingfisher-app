# Kreis je Person und private Akten (M4)

Stand: 1. Oktober 2026. Meilenstein M4 „Privat ist gleichberechtigt“: erster Teil (Kreis, Akten-Arten, Fristen aus
Mails) und, ab [„Rest von M4“](#rest-von-m4-geburtstage-sammelbestätigung-anhänge-cloud-ordner), Geburtstage und
Wiederkehrendes, Sammelbestätigung, PDF-Anhänge und Cloud-Ordner
([`41-zielbild.md`](41-zielbild.md), Abschnitt „Akten zu anderen Menschen“). Die Regel des Gedächtnisses gilt
unverändert ([`10-verdichtung.md`](10-verdichtung.md)): **Kingfisher schlägt vor, ein Mensch bestätigt.**

Code: `sidecar/icarus_memory/kreis.py` (Merkmale, Vorschlag, Begründung, Ablage), `kreis_routes.py`,
`akten_arten.py` (Arten, Vorschlag, Fristen, Ablage), `akten_arten_routes.py`; Wirkung in `fristlage.py`,
`akten_kontext.py`, `working_memory_answers.py`, `terminvorbereitung.py`, `akten.py`, `akten_markdown.py`;
Migration 16 in `episodes.py`. Oberfläche: `app/kingfisher/src/Kreis.tsx`, `kreis.ts`, `Kreis.css`,
`AkteAbschnitte.tsx`, `Einstellungen/Ich.tsx`, `TaskSuggestions.tsx`. Tests: `sidecar/tests/test_kreis.py`,
`test_akten_arten.py`, `messlatte/tests/test_privat.py`, `app/kingfisher/tests/kreis.test.mjs`. Browserprobe:
`scripts/probe_kreis_ui.py`. Messung: `messlatte/privat.py`, Szenario `messlatte/welt/szenarien/privat.json`.

## Was

**Kreis je Person.** Jede Person mit Adresse bekommt einen Kreis: **innerer Kreis** (Familie, enge Freunde),
**Kollegen** (Menschen aus der Arbeit), **Kontakte** (alle anderen). Solange niemand bestätigt hat, ist er
**noch offen** (`unbestimmt`), und alles bleibt, wie es war. Kingfisher schlägt den Kreis aus festen Merkmalen
vor, ohne Modell:

| Merkmal | Woher |
|---|---|
| Mails in welche Richtung, wie viele, über wie viele Monate | Rolle der Person in der Mail (`von`, `an`/`cc` bei eigenen Mails) |
| privater Anbieter oder Firmenadresse, dieselbe Firma wie du | `identitaet.ist_privater_anbieter`, eigene Domänen |
| gemeinsame Termine | Termin-Episoden mit der Person als Gast |
| Anrede und Gruß | Du, Vorname („Hallo Lea“), Sie („Sehr geehrte“), familiäre Anrede („Mama“) oder Gruß („Hab dich lieb“); nur im eigenen Text der Mail, nicht im Zitat, und familiär nur in Anrede und Schlusszeilen |
| Praxis, Versicherung, Vermieter, Schule | private Art der Organisation hinter der Adresse (unten) |

Die Regel (`kreis.vorschlagen`):

* **Innerer Kreis:** Mails in beide Richtungen, mindestens vier, über mindestens zwei Monate, nicht die eigene
  Firma, kein Dienstleister, und eine familiäre Anrede oder ein familiärer Gruß, oder Du mit Vornamen bei
  privatem Anbieter. Du und Vorname bei einer Firmenadresse reichen nicht: Unter Kollegen ist das üblich.
* **Kollegen:** Mails in beide Richtungen, kein Dienstleister, und dieselbe Firma oder eine Firmenadresse mit
  mindestens drei Mails oder einem gemeinsamen Termin.
* **Kontakte:** alle anderen.

Die Begründung ist ein Satz aus genau diesen Merkmalen: „6 Mails in beide Richtungen seit April 2026, privater
Anbieter, ein gemeinsamer Termin, Anrede „Mama“.“

**Private Akten-Arten.** Neben Person, Organisation, Projekt, Ort und Thema bekommt die Akte einer Organisation
eine private Art: **Haushalt** (Stadtwerke, Hausverwaltung, Vermieter), **Familie** (Schule, Kita), **Gesundheit**
(Praxis, Apotheke, Krankenkasse), **Verträge** (Versicherung, Mobilfunk, Fitnessstudio). Den Vorschlag trägt allein
der **Absender** (Name oder Domäne); ein Betreff wie „Rechnung“, „Vertrag“, „Kündigung“, „Termin“ stützt ihn und
steht in der Begründung, macht aber allein keine private Akte („Rahmenvertrag“ vom Klinikum bleibt beruflich).
„Keine davon“ ist auch eine Antwort.

**Fristen aus privaten Mails.** Aus Mails der Akten mit privater Art (bestätigt oder vorgeschlagen) sucht
`akten_arten.fristen_finden` Kündigungs- und Zahlungsfristen: je Satz mit einem Kündigungs- oder Zahlungswort und
einem **ausgeschriebenen** Kalenderdatum, das noch kommt. Der Betrag kommt aus demselben Satz oder aus einer Zeile
wie „Rechnungsbetrag: 86,40 €“. Daraus wird ein **Aufgabenvorschlag** (die vorhandene Liste „Zur Prüfung“ bei den
Vorhaben): „Zahlung bis 12.10.2026: 86,40 € (Zahnarztpraxis Dr. Lindqvist)“, Beleg ist der Satz, die Fälligkeit
steht vorausgefüllt im Feld „Fällig am“. Erst „Aufgabe festhalten“ legt eine Aufgabe an.

## Warum

Kingfisher führt Akten über andere Menschen, auch über die Familie. Was er ungefragt über jemanden sagt, hängt
davon ab, wer die Person für dich ist, und das kann ein Programm nur vermuten. Ein falscher innerer Kreis wäre
schlimmer als ein zu vorsichtiger: Dann stünde der Alltag eines Fremden im Briefing. Deshalb ist der Kreis ein
Vorschlag mit Begründung, die Schwellen sind streng, und ohne Bestätigung ändert sich nichts.

Private Unterlagen drücken wie berufliche (Zielbild: „Versicherung kündbar bis 30.11.“). Der Absender sagt
zuverlässig, worum es geht; ein Datum in einer Mail ist nur dann eine Frist, wenn es ausgeschrieben dasteht.

## Regeln

1. **Vorschlag ist kein Fakt.** Lesen (`GET /api/v1/kreis`, `/api/v1/kreis/uebersicht`, `/api/v1/akten/art`)
   schreibt nichts. Erst `PUT /api/v1/kreis` oder `PUT /api/v1/akten/art` (der Klick) legt fest; gespeichert wird,
   was gewählt wurde und was Kingfisher in dem Moment vorschlug (Tabellen `personen_kreis`, `akten_arten`,
   Migration 16).
2. **Nie automatisch geändert.** Ein bestätigter Kreis bleibt, bis ein Mensch ihn ändert oder zurücknimmt
   (`DELETE`). Ändert sich die Lage, zeigt die Karte den neuen Vorschlag daneben („Nach dem, was seitdem dazukam,
   würde Kingfisher „Kollegen“ vorschlagen. Es bleibt bei deiner Wahl.“); die Übersicht zählt solche Fälle.
3. **Wirkung nur auf Sortierung und Formulierung, nichts verlässt den Rechner:**
   * **Briefing (messbare Regel):** Fristen aus der Akte eines bestätigten **Kontakts** erscheinen nicht
     ungefragt (`fristlage.ohne_kontakte`). Hängt dieselbe Quelle auch an einer Organisation oder einem Projekt,
     bleibt sie über diese Akte (direkter Bezug). Gefragt bleibt alles erreichbar: Die Akte der Person zeigt die
     Frist weiter.
   * **Wer gibt den Namen:** Die Akte einer Person im inneren Kreis (oder noch offen) vor Projekt und Organisation,
     Kollegen hinter Projekt und Organisation (sachlich, mit Projektbezug), Kontakte zuletzt
     (`fristlage.nach_dringlichkeit`). Ohne Bestätigung bleibt die Reihenfolge wie bisher.
   * **Antwortkontext:** `akten_kontext.Kontext` trägt die bestätigten Kreise der beteiligten Personen
     (`kreise`, je Quelle `personen`, je Akten-Zeile `kreis`); die Zeile einer Quelle im Kontext des Modells trägt
     das Feld `kreis` („Gabriele Hartmann – innerer Kreis: mit Vornamen nennen, Alltägliches (Geburtstag, Termine)
     darf vorkommen“; Kontakte: „nur sagen, wonach gefragt ist, zurückhaltend formulieren“). `kreis_der_quelle`
     nennt der Satzauswahl den zurückhaltendsten Kreis. Ein geänderter Kreis macht eine gespeicherte Antwort
     veraltet (Signatur). Ohne bestätigten Kreis bleibt der gespeicherte Kontext Zeichen für Zeichen wie bisher.
   * **Daten:** `Akte.kreis`, `Akte.akten_art`, `Frist.kreis`, `Person.kreis` der Terminvorbereitung, Kopf der
     Markdown-Akte (`kreis: "innerer_kreis"`, `akten_art: "gesundheit"`). Das Briefing-Layout ist unverändert.
4. **Fristen nie geraten.** Nur ein ausgeschriebenes Datum (Tag und Monat als Ziffern oder Name), nie „in zwei
   Wochen“ oder „bis Freitag“; nichts, was schon verstrichen ist; nichts aus Sätzen, die Erledigtes melden
   („eingegangen“, „gekündigt“); keine Abbuchung („wird am 05.10. abgebucht“: da ist nichts zu tun). Jede Zahl
   im Vorschlag steht wörtlich in der Quelle (`zahlen_belegt`). Was einmal vorgeschlagen war, auch abgelehnt,
   kommt nicht wieder. Die Suche läuft im Hintergrund nach dem Abgleich der Bezüge (höchstens alle zehn Minuten,
   erst nach einer Änderung) und auf Anstoß (`POST /api/v1/akten/arten/fristen`).

## Oberfläche

* **Akte einer Person:** Karte „Kreis“ oben: „Vorschlag: Innerer Kreis. Ein Klick bestätigt ihn, oder du wählst
  einen anderen Kreis.“, darunter „Warum: …“ und drei Knöpfe (der vorgeschlagene hervorgehoben). Nach dem Klick
  steht, was gespeichert ist und was es bewirkt; „Wieder offen lassen“ nimmt es zurück.
* **Akte einer Organisation:** Karte „Art der Akte“, nur wenn es einen Vorschlag oder eine Wahl gibt (eine
  berufliche Akte bleibt ohne Karte).
* **Einstellungen → Kingfisher und du:** statt „kommt später“ der Stand („Für eine Person bestätigt. Offen sind
  23 Vorschläge: 2 für den inneren Kreis, 21 für Kollegen.“), die Vorschläge für den inneren Kreis als Weg in die
  Akte, die für Kollegen eingeklappt. Offen heißt: Vorschlag „innerer Kreis“ oder „Kollegen“ ohne Bestätigung;
  wer „Kontakte“ vorgeschlagen bekommt, muss nicht bestätigt werden.
* **Vorhaben → Zur Prüfung:** Fristvorschläge mit vorausgefülltem Datum.

Kein Fachwort vorne: `Kreis.tsx` steht in der Wortliste der vorderen Einstellungen (`gliederung.VORDERE_DATEIEN`).

## Grenzen

* **Regeln, kein Verständnis.** Die Merkmale sehen Mails und Termine, nicht, was im Leben passiert. Eine Freundin,
  die von der Arbeitsadresse schreibt, wird Kollegin vorgeschlagen; ein Familienmitglied ohne Mailwechsel bleibt
  ohne Vorschlag. Personen ohne Adresse (nur ein Name in Notizen oder im Gespräch) bekommen keinen Vorschlag; die Karte
  steht trotzdem in ihrer Akte, und der Mensch legt den Kreis selbst fest (Fremdprobe 2, Befund 19, unten).
* **Geburtstage** stehen seit dem Rest von M4 im Briefing, nur für den bestätigten inneren Kreis (unten).
* **Private Arten nur für Organisationen.** Ein privater Vermieter mit Freemail-Adresse ist eine Person; seine
  Nebenkostenabrechnung wird kein Fristvorschlag. PDF-Anhänge von Organisationen werden seit dem Rest von M4
  gelesen (unten).
* **Viele Kollegen-Vorschläge** bestätigt seit dem Rest von M4 ein Klick mit einer Rückfrage (unten).
* **Wirkung ist klein.** Gemessen ist eine Regel (Briefing ohne Fristen bestätigter Kontakte). Wie ein Modell den
  Hinweis `kreis` im Antwortkontext umsetzt, misst erst ein Lauf mit Modell.

## Messung

Messlatte, Stufe Privat (`messlatte/privat.py`), im `lauf` immer dabei, wenn die Welt Erwartungen hat:
`python -m messlatte lauf --welt messlatte/welt --modell keins --einordnung regel` (nur diese Stufe: `--nur privat`).
Szenario `privat` (29 Quellen, Bereich privat, keine Fragen): Mutter, Bruder, Freundin, Nachbarin, Hausarzt,
Zahnarztrechnung, Hausratversicherung mit Sonderkündigungsrecht, Nebenkostenabrechnung, Stadtwerke, Schule, Kita
und ein Betrugsversuch („Hallo Mama, das ist meine neue Nummer“ mit Antwort). Dazu zwei Kolleginnen in
beruflichen Szenarien, die per Du und mit gemeinsamen Terminen schreiben. Ein privates Szenario gibt dem Rauschen
keine Wörter: Das Rauschen ist Quelle für Quelle dasselbe wie ohne das Szenario (Test).

| Lauf | Kreise wie erwartet (mit Merkmalen) | falsche innere Kreise | Akten-Arten | Fristen | Zahlen ohne Beleg | nichts bestätigt, keine Aufgabe |
|---|---|---|---|---|---|---|
| vorher (Produkt `fa6c03e`), ohne Rauschen | 0 von 9 | – (keine Vorschläge) | 0 von 7 | 0 von 4 | 0 | ja |
| nachher, ohne Rauschen | **9 von 9** | **0** (66 Personen) | **7 von 7** | **4 von 4** | **0** | ja |
| nachher, 10.000 Rauschquellen | **9 von 9** | **0** (2.717 Personen) | **7 von 7** | **4 von 4** | **0** | ja |

Die Abrufkennzahlen der übrigen Welt sind unverändert (Belege 130 von 142, Fragen vollständig 70 von 77,
Rückfragen 7 von 7, unnötige 0 von 76; mit 10.000 Rauschquellen 115 und 63); die Stufe Lint findet weiter 5 von 5
ohne Fehlalarm. Berichte: `docs/evaluations/messlatte/2026-10-01-privat-*`.

Eine erste Fassung der Regel ließ Du mit Vornamen und einen gemeinsamen Termin auch bei Firmenadressen für den
inneren Kreis genügen. Die Messung fand zwei falsche innere Kreise (zwei Projektpartnerinnen, die per Du
schreiben); die Regel verlangt seitdem einen privaten Anbieter, und beide stehen als Kollegen in der Welt.

## Sabotageproben

Jede Zusicherung wurde absichtlich gebrochen (ein Ausdruck ersetzt), die zuständigen Tests liefen, danach
zurückgestellt (Skript im Arbeitsverzeichnis, nicht im Repository).

| Probe | Gebrochene Zusicherung | Gefangen von |
|---|---|---|
| K1 | Monatsschwelle des inneren Kreises fehlt | `test_ein_fremder_landet_nie_im_inneren_kreis`, Schwellen (2) |
| K2 | Du und Vorname mit Firmenadresse reichen für den inneren Kreis | Schwellen (2), Messlatte `test_alle_erwarteten_kreise…` und Bericht |
| K3 | Begründung nennt keine Termine | `test_familie_wird_innerer_kreis…`, `test_kollege…`, Messlatte (2) |
| K4 | Lesen bestätigt selbst (Vorschlag schreibt) | `test_vorschlag_schreibt_nichts…`, `test_bestaetigter_kreis_bleibt…` |
| K5 | Bestätigter Kreis folgt dem neuen Vorschlag | `test_bestaetigter_kreis_bleibt_auch_wenn_sich_die_lage_aendert` |
| K6 | Fristen bestätigter Kontakte bleiben im Briefing | `test_ohne_andere_akte_faellt_die_frist_eines_kontakts_ganz_weg` |
| K7 | Antwortkontext ohne Kreis | `test_antwortkontext_kennzeichnet_den_bestaetigten_kreis` |
| K8 | Familiäres Wort mitten im Text zählt als Anrede | Messlatte `test_alle_erwarteten_kreise…` und Bericht (der Bruder) |
| A1 | Betreff allein trägt die Art | `test_ohne_privaten_absender_kein_vorschlag` (erst nach dieser Probe mit „Vertrag“ und „Kündigung“ im Betreff; vorher nicht gefangen) |
| A2 | Relative Daten werden Fristen | `test_keine_frist_ohne_beleg_oder_wenn_erledigt` |
| A3 | Erledigtes wird Frist | `test_keine_frist_ohne_beleg_oder_wenn_erledigt` |
| A4 | Vorschlag mit gerechnetem Datum statt Wortlaut | `test_betrag_aus_der_betragszeile_und_kuendigung_mit_monatsname` |
| A5 | Abgelehnte Frist kommt wieder | `test_fristen_werden_aufgabenvorschlaege_mit_beleg_nie_aufgaben` |
| A6 | Fristen auch aus beruflichen Akten | `test_keine_davon_stellt…`, `test_berufliche_rechnung_wird_keine_private_frist` |
| M1 | Rauschen nimmt Wörter privater Szenarien | `test_private_szenarien_aendern_das_rauschen_nicht` |
| M2 | Falsche innere Kreise werden nicht gezählt | `test_falscher_innerer_kreis_ist_jeder_innere_ohne_erwartung` |
| M3 | Merkmale der Begründung werden nicht geprüft | `test_zuordnung_ist_streng…` |
| U1 | Oberfläche: neuer Vorschlag neben bestätigtem Kreis fehlt | `kreis.test.mjs` |
| U2 | Oberfläche: Übersicht verschweigt offene Vorschläge | `kreis.test.mjs` |

19 Proben, alle gefangen; eine (A1) erst, nachdem die Probe einen schwachen Test zeigte.

Browserprobe im echten Chromium (`scripts/probe_kreis_ui.py`, Welt der Messlatte): Stand unter „Kingfisher und
du“ statt „kommt später“, drei Vorschläge für den inneren Kreis vorne, Kollegen eingeklappt, der Betrugsversuch
nicht darunter; Karte „Kreis“ mit Vorschlag und Begründung, vor dem Klick nichts gespeichert, Bestätigen, andere
Wahl, Zurücknehmen, nach dem Neuladen bestätigt; Zählung danach eins weniger offen; „Art der Akte“ bei der
Zahnarztpraxis bestätigt, keine Karte beim Klinikum; Fristvorschlag mit „Fällig am“ 12.10.2026 und ohne neue
Aufgabe; Karte ohne Überlauf bei 900 px; Konsole leer.

## Rest von M4: Geburtstage, Sammelbestätigung, Anhänge, Cloud-Ordner

Stand: 1. Oktober 2026. Code: `wiederkehrendes.py`, `wiederkehrendes_routes.py`, `anhaenge.py`, `kreis.py`
(Sammelbestätigung), `kreis_routes.py`, `ordner_lokal.py` (Cloud-Orte), `pdf_text_worker.py`, `document_text.pdf_seiten`,
`connectors/mail.message_mit_anhaengen`, `mail_ingestion.py`, `mail_intake.py`, `akten_arten.fristen_vorlegen`,
`tagesbriefing.py`, `tag_routes.py`. Oberfläche: `Wiederkehrendes.tsx`, `wiederkehrendes.ts`, `Kreis.tsx`,
`kreis.ts`, `TagesLage.tsx`, `OrdnerImBrowser.tsx`, `ordnerWahl.ts`. Tests: `test_wiederkehrendes.py`,
`test_kreis_sammel.py`, `test_anhaenge.py`, `test_cloud_orte.py`, `messlatte/tests/test_privat.py`,
`wiederkehrendes.test.mjs`, `kreis.test.mjs`, `ordner-wahl.test.mjs`. Browserprobe: `scripts/probe_privat_ui.py`.

### Teil 1: Geburtstage und Wiederkehrendes

**Geburtstage** findet Kingfisher ohne Modell an drei Stellen, und nur für Personen, deren Kreis bestätigt „innerer
Kreis“ ist oder ohne Bestätigung so vorgeschlagen wird; nie für Kollegen und Kontakte:

| Woher | Beispiel | Tag |
|---|---|---|
| eigener Glückwunsch an genau diese Person | „alles Gute zum Geburtstag!“ | Tag der Mail; „nachträglich“, „vorab“, „morgen“ im Satz oder daneben zählt nicht |
| die Person selbst | „mein Geburtstag ist am 18. Dezember“ | wörtlich im Satz; „Papas Geburtstag“, „deinen Geburtstag“ zählen nicht |
| Kalender | „Carlas Geburtstag“, „Geburtstag: Felix“ | aus der Zeile „Wann:“; der Name muss genau eine Person mit Adresse treffen (Vorname oder Anfang der Adresse) |

**Wiederkehrendes** kommt aus Mails und Anhängen der Akten mit privater Art: ein Satz mit **Rhythmus** („monatlich“,
„alle zwei Wochen“, „jeden ersten Dienstag im Monat“, „verlängert sich jeweils um zwölf Monate“) **und Gegenstand**
(Abschlag, Beitrag, Tonne, Elternabend, Mitgliedschaft); fehlt eins, ist es nichts. Dazu Serien im Kalender: derselbe
Titel mindestens dreimal im gleichen Abstand (7 oder 14 Tage, derselbe Tag in Folgemonaten). Die Aussage nennt
Rhythmus, Gegenstand und Betrag so, wie sie im Satz stehen: „Monatlich: Abschlag, 94,00 € (Stadtwerke Taunusstein)“.

Beides sind **Wissenskandidaten** (`knowledge`, Beziehung `geburtstag` bzw. `wiederkehrend`) mit wörtlicher Stelle;
erst „Stimmt, übernehmen“ in der Karte der Akte legt eine Aussage an. Was einmal vorgeschlagen war, auch verworfen,
kommt nicht wieder. Die Suche läuft im Faden der Bezüge (höchstens alle zehn Minuten, nach einer Änderung) und auf
Anstoß (`POST /api/v1/wiederkehrendes/vorschlagen`). **Briefing:** Feld `geburtstage` und die Zeile „Morgen hat
Gabriele Geburtstag.“, nur bei bestätigtem innerem Kreis **und** angenommenem Geburtstag; wird die Person später
Kontakt, verschwindet die Zeile.

### Teil 2: Sammelbestätigung

Unter „Kingfisher und du“ steht bei offenen Vorschlägen für Kollegen „Alle 21 als Kollegen festlegen“. Die Rückfrage
ist ein Satz: „21 Personen als Kollegen festlegen?“ mit „Ja, festlegen“ und „Abbrechen“. Gezählt werden alle offenen
Vorschläge, nicht nur die angezeigten. Hat sich die Zahl seit der Rückfrage geändert, wird nichts gespeichert
(„Inzwischen sind es 22 Vorschläge …“). Danach steht „Zuletzt 21 Personen gesammelt als Kollegen festgelegt.“ mit
**„Liste zurücknehmen“**; das lässt genau diese Personen wieder offen, wer seitdem einzeln geändert wurde, bleibt.
Für den inneren Kreis gibt es **keine** Sammelbestätigung (422): Er wird je Person in der Akte bestätigt. Ohne
Migration: Alle Zeilen einer Sammlung tragen denselben Zeitpunkt `bestaetigt_am`; er ist die Kennung der Liste.

### Teil 3: Anhänge lesen

Die Aufnahme holt eine Mail für den Bestand mit `message_mit_anhaengen` (das Ansehen einer Mail liest keine
Anhänge). PDF-Anhänge werden lokal gelesen, im begrenzten Prozess `pdf_text_worker.py --seiten` (pypdf, CPU 8 s,
256 MiB, Wanduhr 12 s), höchstens 5 Anhänge je Mail, 30 Seiten und 60.000 Zeichen je Anhang, 5 MiB je Datei, und
nur, wenn die Mail unter der Grenze der Aufnahme (2 MiB) blieb. Aus der Datei wird nichts ausgeführt: gelesen werden
Text und eingebettete JPEG-Bilder. Ein Foto ist nur mit einem Dokumentnamen eine Quelle („Rechnung.jpg“, nicht
„Strand.jpg“).

Jeder Anhang wird eine **eigene Quelle** (Art `document`, Markierung `anhang`) mit den Beteiligten der Mail, also in
derselben Akte, Titel „Rechnung-PB-2026-118.pdf (Anhang zu „Ihre Rechnung“)“ und „Seite N“ vor jeder Seite. Sie läuft
durch die Einordnung und die Fristensuche; der Vorschlag nennt die Seite („Aus dem Anhang „…pdf“, Seite 1, einer
Mail der Akte …“), jede Zahl steht wörtlich darin. Dieselbe Frist in Mail und Anhang ist ein Vorschlag, nicht zwei.
**Gescannt** (keine Textebene): Mit einem lokal installierten `glm-ocr` oder `deepseek-ocr` im Ollama liest
Kingfisher die eingebetteten Bilder je Seite („Seite 1 (Texterkennung)“); ein solches Modell nur in Ollamas Cloud
zählt nie. Sonst steht ehrlich da: „Gescannte Rechnung „…pdf“ (1 Seite), noch nicht gelesen.“ Zu groß, verschlüsselt
oder beschädigt: ein Satz, warum.

### Teil 4: Unterlagen aus Cloud-Ordnern

OneDrive, Google Drive und iCloud Drive liegen auf dem Mac als Ordner. Unter Einstellungen → Zugänge → „Dokumente
automatisch aufnehmen“ stehen die, die es gibt, als Orte zum Anklicken, mit lesbarem Namen („OneDrive (Hochschule)“,
„Google Drive (lea@…)“ mit „Meine Ablage“, „iCloud Drive“) und dem Zusatz „aus der Cloud, auf diesem Rechner
abgeglichen“. Freigegeben wird erst, was angeklickt wird; die Dateien bleiben, wo sie sind. Gelesen werden PDF, Text,
Markdown und Word (`folder_sync.SUFFIXES`); eine Datei, die nur in der Cloud liegt (macOS `SF_DATALESS`), wird
übersprungen statt heruntergeladen. **Linux und Docker:** Der Sidecar sieht die Ordner des Rechners nicht; dann steht
„Kingfisher läuft hier in einem Container und sieht OneDrive, Google Drive und iCloud Drive auf deinem Rechner nicht.
Ein Techniker kann einen dieser Ordner einbinden …“. Eingebunden (`KINGFISHER_ORDNER`) trägt er denselben Namen.

### Grenzen

* **Geburtstage nur aus drei Mustern.** Ein Geburtstag, der nur in einer Kontaktkarte (vCard) oder einer Signatur
  steht, wird nicht gefunden; Kontakte liest Kingfisher noch nicht. „Papas Geburtstag“ hat keine Person mit Adresse.
  Ein Glückwunsch einen Tag zu spät ohne „nachträglich“ ergibt den falschen Tag; die Begründung sagt deshalb, dass
  der Tag der Mail gemeint ist, und erst die Annahme macht ihn fest.
* **Wiederkehrendes ist eine Notiz, kein Kalender.** Kingfisher rechnet daraus keine nächsten Termine aus; nur
  Geburtstage erscheinen im Briefing.
* **Anhänge:** nur PDF und Fotos mit Dokumentnamen; Word und Excel im Anhang noch nicht. Die Texterkennung ist mit
  einem nachgebildeten Ollama getestet, nicht mit einem echten OCR-Modell; ihre Güte misst erst ein Lauf auf dem
  Zielgerät. Gescannte Seiten mit anderen Bildformaten als JPEG bleiben ungelesen. Fristen aus Ordner-Dokumenten
  (ohne Absender) werden nicht gesucht.
* **Cloud-Ordner:** Es wird genau ein Ordner für Dokumente freigegeben (wie bisher); wer OneDrive und iCloud will,
  wählt einen gemeinsamen übergeordneten Ordner oder wechselt. Am Mac mit Docker sieht der Sidecar die Ordner nur
  über den Mac-Helfer (sein Auswahlfenster zeigt sie unter „Orte“) oder eingebunden. Office-Text: nur Word.
* **Briefing-Probe** in der Messlatte bestätigt die Kreise und nimmt die Geburtstage an, wie ein Mensch; die Regel
  „nichts bestätigt“ ist davor gemessen.

### Messung

Messlatte, Stufe Privat, Szenario `privat` jetzt mit 43 Quellen (drei Mails mit PDF-Anhang, davon einer gescannt;
Geburtstage per Glückwunsch, eigener Angabe und Kalender, auch je einer einer Nachbarin und einer Kollegin;
Abfallwirtschaft, Fitnessstudio, Elternabend, Chorprobe jede Woche). Vorher: Produkt `a73a291` mit Messlatte und
Welt dieses Zweigs; nachher: dieser Zweig. Regel-Einordnung, ohne Modell.

| Lauf | Fristen (davon aus PDF) | PDF-Anhänge wie erwartet | Geburtstage (nur innerer Kreis) | Geburtstage ohne Erwartung | Wiederkehrendes | Zahlen ohne Beleg | Briefing-Probe | Kreise · falsche innere · Arten | nichts bestätigt |
|---|---|---|---|---|---|---|---|---|---|
| vorher, ohne Rauschen | 4 von 6 (0 von 2) | 0 von 3 | 0 von 3 | 0 | 0 von 8 | 0 | – | 9/9 · 0 · 11/11 | ja |
| nachher, ohne Rauschen | **6 von 6 (2 von 2)** | **3 von 3** | **3 von 3** | **0** | **8 von 8** | **0** | „Morgen hat Gabriele Geburtstag.“, 0 Kontakte | 9/9 · 0 · 11/11 | ja |
| vorher, 10.000 Rauschquellen | 4 von 6 (0 von 2) | 0 von 3 | 0 von 3 | 0 | 0 von 8 | 0 | – | 9/9 · 0 (2.721 Personen) · 11/11 | ja |
| nachher, 10.000 Rauschquellen | **6 von 6 (2 von 2)** | **3 von 3** | **3 von 3** | **0** | **8 von 8** | **0** | „Morgen hat Gabriele Geburtstag.“, 0 Kontakte | 9/9 · 0 (2.721 Personen) · 11/11 | ja |

Die Abrufkennzahlen sind vorher und nachher gleich (Belege 130 von 142, Fragen vollständig 70 von 77, Rückfragen 7
von 7, unnötige 0 von 76, verbotene Belege 21 von 83, ungekennzeichnet 8; mit 10.000 Rauschquellen 115, 63, 7, 19
und 8): Die neuen privaten Quellen geben dem Rauschen keine Wörter, und die Anhänge stehen nur im privaten Szenario.
Die Stufe Privat braucht mit 10.000 Rauschquellen 21 s (vorher 2 s), vor allem für die Kreis-Vorschläge aller 2.721
Personen, aus denen die Geburtstage ihre Kandidaten nehmen.

Die erste Messung mit Rauschen fand **Wiederkehrendes 7 von 8**: Die Suche las wie die Fristensuche nur die jüngsten
400 Organisationen, und mit 10.000 Rauschquellen fiel die Akte der Stadtwerke (Mail vom Juli) heraus. Seitdem
wählen beide ihre Akten über die Absender aus (`akten_arten.private_kandidaten`: Name oder Domäne trifft ein
privates Muster, oder die Art ist bestätigt); danach 8 von 8. Probe A12 bricht das wieder und wird gefangen.

Berichte: `docs/evaluations/messlatte/2026-10-01-m4-rest-*`.

### Sabotageproben

Jede Zusicherung wurde absichtlich gebrochen, die zuständigen Tests liefen, danach zurückgestellt (Skript im
Arbeitsverzeichnis, nicht im Repository).

| Probe | Gebrochene Zusicherung | Gefangen von |
|---|---|---|
| W1 | Briefing ohne bestätigten Kreis | `test_briefing_nur_mit_bestaetigtem_inneren_kreis…` |
| W2 | Geburtstage auch für Kollegen und Kontakte | `test_vorschlag_nur_im_inneren_kreis…` |
| W3 | Nachträglicher Glückwunsch zählt | `test_glueckwunsch_am_tag…` |
| W4 | Verworfener Geburtstag kommt wieder | `test_abgelehnter_geburtstag_kommt_nicht_wieder` |
| W5 | Wiederkehrendes ohne Gegenstand | `test_wiederkehrendes_braucht_rhythmus_und_gegenstand` |
| W6 | Zahl ohne Beleg in der Aussage | `test_wiederkehrendes_braucht_rhythmus_und_gegenstand` |
| W7 | Serie schon ab zwei Terminen | `test_serie_im_kalender` |
| W9 | „Papas Geburtstag“ als eigene Angabe | `test_eigene_angabe_mit_datum…` |
| W10 | Mehrdeutiger Name im Kalender genügt | `test_mehrdeutiger_name_im_kalender_bleibt_ohne_vorschlag` |
| U3 | Oberfläche zeigt Vorschlag als fest | `wiederkehrendes.test.mjs` |
| S1 | Sammeln auch für den inneren Kreis | `test_kein_sammeln_fuer_den_inneren_kreis` |
| S2 | Sammlung nimmt innere Vorschläge mit | `test_ein_klick_bestaetigt_alle_offenen_kollegen…` |
| S3 | Veraltete Zahl wird gespeichert | `test_veraltete_zahl_speichert_nichts` |
| S4 | Zurücknehmen trifft einzeln Geändertes | `test_liste_zuruecknehmen_laesst_genau_diese_wieder_offen` |
| S5, S6 | Oberfläche: Rückfrage ohne Zahl; nur Angezeigte gezählt | `kreis.test.mjs` |
| A1 | Keine Seitenmarke im Anhang | `test_pdf_wird_seite_fuer_seite_gelesen…` |
| A2, A3 | Seitengrenze, Zeitgrenze fehlen | `test_grenzen_seiten_zeit_groesse_und_beschaedigt` |
| A4 | Scan als gelesen ausgegeben | `test_gescannt_ohne_texterkennung_ehrlich…` |
| A5 | OCR-Modell in der Cloud zählt | `test_texterkennung_nur_mit_lokalem_ocr_modell` |
| A6 | Anhang wird keine Quelle | `test_anhang_wird_quelle_in_derselben_akte…` |
| A7 | Aufnahme holt keine Anhänge | Messlatte `test_alle_akten_arten_und_fristen…` |
| A8 | Fristen nur aus Mails | `test_anhang_wird_quelle…` |
| A9 | Seite fehlt in der Begründung | `test_anhang_wird_quelle…` |
| A10 | Dieselbe Frist in Mail und Anhang doppelt | `test_dieselbe_frist_in_mail_und_anhang_ist_ein_vorschlag` (erst gefangen, nachdem der Test das Datum in der Mail anders schreibt als im PDF; vorher fasste der Fingerabdruck gleicher Aussagen beide zusammen) |
| A11 | Urlaubsfoto wird Quelle | `test_pdf_wird_seite_fuer_seite_gelesen_urlaubsfotos_nicht` |
| C1 | Cloud-Ordner wird selbst freigegeben | `test_vorschlag_ist_keine_freigabe_erst_der_klick_liest` |
| C2 | Cloud-Ordner auch im Container | `test_im_container_keine_cloud_ordner…` |
| C3 | Platzhalter aus der Cloud wird gelesen | `test_nur_in_der_cloud_wird_nicht_heruntergeladen` |
| C4 | Name ohne Konto | `test_cloud_ordner_mit_lesbarem_namen…` |
| C5 | Kein Satz ohne Cloud-Ordner | `test_ohne_cloud_ordner_ein_satz` |
| U4 | Oberfläche verschweigt die Cloud | `ordner-wahl.test.mjs` |

| A12 | Nur die jüngsten Organisationen werden gelesen | `test_private_akten_werden_auch_unter_vielen_beruflichen_gefunden` |

33 Proben, alle gefangen; eine (A10) erst nach geschärftem Test.

Browserprobe im echten Chromium (`scripts/probe_privat_ui.py`, Welt der Messlatte): Karte „Geburtstag“ der Mutter
mit Vorschlag und Beleg, vorher keine Aussage; Kreis bestätigt und „Stimmt, übernehmen“, dann im Briefing „Morgen
hat Gabriele Geburtstag.“; keine Karte bei der Nachbarin; „Monatlich: Abschlag, 94,00 €“ bei den Stadtwerken;
Rückfrage „21 Personen als Kollegen festlegen?“, „Abbrechen“ speichert nichts, „Ja, festlegen“ legt 21 fest und die
Mutter bleibt innerer Kreis, „Liste zurücknehmen“ stellt den alten Stand her; PDF-Rechnung als Quelle in der Akte der
Physiotherapie, Frist mit „Fällig am“ 22.10.2026 aus dem PDF und ohne neue Aufgabe; der Scan zeigt „noch nicht
gelesen“; OneDrive, Google Drive und iCloud Drive unter „Dokumente automatisch aufnehmen“, freigegeben erst nach dem
Klick; Karten ohne Überlauf bei 390 px; Konsole leer.

## Fremdprobe 2: Kreis in jeder Akte, Geburtstag aus dem Gespräch

Die Fremdprobe 2 ([`51-fremdprobe-2.md`](51-fremdprobe-2.md), Befunde 19 und 20) fand zwei Lücken: In der Akte von
Anna Berg (nur ein Name, keine Adresse) gab es keine Karte „Kreis“, obwohl „Kingfisher und du“ sagte, man bestätige
den Kreis in der Akte; und ein im Gespräch bestätigter Geburtstag („Merke dir: Anna Berg hat am 12. Oktober
Geburtstag.“) erschien weder im Kalender noch in der Akte noch im Briefing.

* **Kreis in jeder Personenakte.** Die Karte steht in jeder Akte einer Person, auch für `person:n:<name>` (das
  Personenprofil ohne Adresse zeigt sie über `kreis.ts kreisSache`). Gibt es weder Mails noch gemeinsame Termine, liefert
  `GET /api/v1/kreis` `ohne_vorschlag: true`: Die Karte sagt „Noch kein Vorschlag; du kannst den Kreis selbst
  festlegen.“, ohne „Warum“ und ohne hervorgehobenen Knopf; ein bestätigter Kreis zeigt dann nie „würde anders
  vorschlagen“. Erst der Klick speichert, wie bisher. Der Satz unter „Kingfisher und du“ sagt dasselbe.
* **Ein bestätigter Geburtstag, gleich woher.** `wiederkehrendes.bestaetigter_geburtstag` liest die angenommene
  Aussage unter der Sache (`person:a:…`, `person:n:…`) und unter der Personenkennung des Gedächtnisses
  (`graph.person_id_fuer`), unter der Gesprächsvorschläge stehen; der Wert darf `MM-TT`, „12. Oktober“ oder „12.10.“
  sein (`geburtstag_wert`). Ohne Annahme: nichts.
* **Kalender:** `GET /api/v1/calendar` enthält jeden angenommenen Geburtstag als ganztägigen Eintrag
  „Geburtstag: Anna Berg“ (Art `geburtstag`), jedes Jahr wieder, auch ohne verbundenen Kalender. Er steht nur in
  Kingfisher und wird in keinen Kalender eines Anbieters geschrieben (`kalender_eintraege`, `ClaimStore.by_predicate`).
* **Akte:** Karte „Steht an“ mit „Geburtstag am 12. Oktober, in 11 Tagen“ (`GET /api/v1/geburtstag?sache=…`).
* **Briefing:** unverändert nur für den bestätigten inneren Kreis, am Vortag („Morgen hat Anna Geburtstag.“) und am
  Tag; jetzt auch mit einem Geburtstag aus dem Gespräch.

Tests: `test_fremdprobe2_alltag.py` (Kreis ohne Vorschlag, Geburtstag nur nach Annahme in Akte, Kalender, Briefing am
Vortag und Tag, nur innerer Kreis), `kreis.test.mjs`; Sabotageproben S17 bis S21 in `51-fremdprobe-2.md`, alle
gefangen; Browserprobe `scripts/probe_fremdprobe2_alltag_ui.py`.
